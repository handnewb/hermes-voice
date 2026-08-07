"""Self-diagnostics. Checks everything before the user discovers issues in practice.

Exists because, in a voice project, 90% of reported problems are environment and
not code: audio driver, missing cuDNN, wheel that didn't compile, missing key,
endpoint down, EDR blocking. Without this, every opened issue becomes a ten-message
conversation to discover which of ten things broke.

Nothing here writes files, sends audio, or prints secrets.
"""

from __future__ import annotations

import importlib.util
import os
import platform
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

from .config import Config
from .ui import BOLD, CYAN, DIM, GREEN, RED, RESET, YELLOW


@dataclass(slots=True)
class Check:
    name: str
    status: str  # "ok" | "warn" | "fail" | "skip"
    detail: str = ""
    fix: str = ""


_MARK = {
    "ok": (GREEN, "ok  "),
    "warn": (YELLOW, "!!  "),
    "fail": (RED, "XX  "),
    "skip": (DIM, "--  "),
}


def _has(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ValueError):
        return False


# ---------------------------------------------------------------------------
# Check groups
# ---------------------------------------------------------------------------
def check_runtime() -> list[Check]:
    out = []
    v = sys.version_info
    ver = f"{v.major}.{v.minor}.{v.micro}"
    if v < (3, 10):
        out.append(Check("Python", "fail", ver, "Use 3.10 or higher."))
    elif v >= (3, 14):
        out.append(
            Check(
                "Python",
                "warn",
                ver,
                "ctranslate2/pynput wheels may not exist. 3.12 is safer.",
            )
        )
    else:
        out.append(Check("Python", "ok", ver))
    out.append(
        Check("System", "ok", f"{platform.system()} {platform.release()} ({platform.machine()})")
    )
    return out


def check_audio(cfg: Config) -> list[Check]:
    if not _has("sounddevice"):
        return [Check("sounddevice", "fail", "missing", "pip install sounddevice")]
    try:
        import sounddevice as sd

        devices = sd.query_devices()
    except Exception as exc:
        return [
            Check(
                "PortAudio",
                "fail",
                str(exc)[:90],
                "Linux: apt install libportaudio2. Windows: reinstall sounddevice.",
            )
        ]

    ins = [d for d in devices if d["max_input_channels"] > 0]
    outs = [d for d in devices if d["max_output_channels"] > 0]
    out = [
        Check(
            "Microphones",
            "ok" if ins else "fail",
            f"{len(ins)} found",
            "" if ins else "No input. Check system microphone permission.",
        ),
        Check("Audio outputs", "ok" if outs else "fail", f"{len(outs)} found"),
    ]
    for label, spec, kind in (
        ("INPUT_DEVICE", cfg.input_device, "input"),
        ("OUTPUT_DEVICE", cfg.output_device, "output"),
    ):
        if not spec:
            out.append(Check(label, "skip", "system default"))
            continue
        from .audio import resolve_device

        idx = resolve_device(spec, kind)
        if idx is None:
            out.append(
                Check(
                    label,
                    "warn",
                    f"'{spec}' not found",
                    "Run --devices and use the numeric index.",
                )
            )
        else:
            out.append(Check(label, "ok", f"[{idx}] {devices[idx]['name'][:44]}"))
    return out


def check_stt(cfg: Config) -> list[Check]:
    if not _has("faster_whisper"):
        return [Check("faster-whisper", "fail", "missing", "pip install faster-whisper")]
    out = [Check("faster-whisper", "ok", f"model '{cfg.whisper_model}'")]
    if cfg.whisper_device != "cuda":
        out.append(
            Check("STT acceleration", "warn", "cpu", "1-3 s per turn. With GPU drops to ~300 ms.")
        )

        return out
    try:
        import ctranslate2  # type: ignore

        n = ctranslate2.get_cuda_device_count()
    except Exception as exc:
        return [*out, Check("CUDA", "warn", str(exc)[:80], "Falls back to CPU automatically.")]
    if n == 0:
        out.append(
            Check(
                "CUDA",
                "warn",
                "no visible device",
                "WHISPER_DEVICE=cpu, or install nvidia-cudnn-cu12 and adjust PATH.",
            )
        )
    else:
        out.append(Check("CUDA", "ok", f"{n} device(s)"))
    return out


def check_wake(cfg: Config) -> list[Check]:
    if cfg.wake_backend in ("none", "off"):
        return [Check("Wake word", "skip", "disabled")]
    if cfg.wake_backend == "open":
        return [
            Check(
                "Wake word",
                "warn",
                "open mode",
                "Any speech opens a session AND will be transcribed. Use headphones.",
            )
        ]
    if not _has("openwakeword"):
        return [
            Check(
                "openWakeWord",
                "fail",
                "missing",
                "pip install 'hermes-voice[wake]', or --trigger console",
            )
        ]
    palavra = cfg.wake_model.replace("hey_", "")
    return [
        Check("openWakeWord", "ok", f"model '{cfg.wake_model}', threshold {cfg.wake_threshold}"),
        Check("Word to say", "ok", f'"hey {palavra}"'),
    ]


def check_vad(cfg: Config) -> list[Check]:
    if not _has("onnxruntime"):
        return [
            Check(
                "VAD",
                "warn",
                "onnxruntime missing",
                "Falls back to energy VAD, which triggers with background noise.",
            )
        ]
    try:
        from .vad import _locate_silero

        path = _locate_silero()
    except Exception:
        path = None
    out = []
    if path and path.exists():
        out.append(Check("Silero VAD", "ok", path.name))
    else:
        out.append(
            Check(
                "Silero VAD",
                "warn",
                "model not found",
                "hermes-voice voices --install all downloads it together.",
            )
        )
    if cfg.adaptive_endpoint:
        out.append(
            Check(
                "Endpointing", "ok", f"adaptive {cfg.endpoint_short_ms}-{cfg.endpoint_long_ms} ms"
            )
        )
    else:
        out.append(
            Check(
                "Endpointing",
                "warn",
                f"fixed {cfg.silence_ms} ms",
                "ADAPTIVE_ENDPOINT=1 avoids cutting phrases in half.",
            )
        )
    out.append(Check("Session", "ok", f"closes after {cfg.follow_up_seconds:.0f} s"))
    return out


def check_tts(cfg: Config) -> list[Check]:
    from .voices import kokoro_catalog

    root = Path(cfg.data_dir)
    out: list[Check] = []

    piper_dir = root / "voices"
    piper_onnx = sorted(piper_dir.glob("*.onnx")) if piper_dir.exists() else []
    kokoro_ok = (root / "models" / "kokoro-v1.0.onnx").exists()

    total = len(piper_onnx) + (len(kokoro_catalog()) if kokoro_ok else 0)
    if total:
        detail = f"{len(piper_onnx)} Piper" + (", Kokoro present" if kokoro_ok else "")
        out.append(Check("Installed voices", "ok", detail))
    else:
        out.append(
            Check(
                "Installed voices",
                "fail",
                "none",
                "hermes-voice voices --install pt_BR-faber-medium",
            )
        )

    chosen = cfg.voice or "pt_BR-faber-medium"
    ready = kokoro_ok if cfg.tts_backend == "kokoro" else Path(cfg.piper_model).exists()
    out.append(
        Check(
            "Chosen voice",
            "ok" if ready else "fail",
            f"{chosen} ({cfg.tts_backend})",
            "" if ready else f"hermes-voice voices --install {chosen}",
        )
    )

    out.append(
        Check(
            "Kokoro Engine",
            "ok" if _has("kokoro_onnx") else "skip",
            "kokoro-onnx present" if _has("kokoro_onnx") else "not installed (optional)",
        )
    )
    exe = shutil.which(cfg.piper_binary) or cfg.piper_binary
    has_exe = Path(exe).exists()
    out.append(
        Check(
            "Piper Engine",
            "ok" if has_exe else "warn",
            "binary present" if has_exe else "binary missing",
            "" if has_exe else "hermes-voice voices --install <ID>",
        )
    )

    if cfg.dsp_preset not in ("off", "none", ""):
        out.append(Check("Presence DSP", "ok", f"preset '{cfg.dsp_preset}'"))
    else:
        out.append(Check("Presence DSP", "skip", "off -- --dsp room gives room presence"))
    return out


def check_llm(cfg: Config, probe: bool = False) -> list[Check]:
    out = [Check("Hermes endpoint", "ok", cfg.hermes_url)]
    persona = Path(cfg.persona_file)
    out.append(
        Check(
            "Persona file",
            "ok" if persona.exists() else "warn",
            persona.name if persona.exists() else "missing",
            "" if persona.exists() else "Using built-in fallback.",
        )
    )
    if not probe:
        out.append(Check("Endpoint reachability", "skip", "use --doctor --probe to test"))
        return out
    try:
        import httpx

        r = httpx.post(
            cfg.hermes_url,
            timeout=8.0,
            json={
                "model": cfg.hermes_model,
                "stream": False,
                "max_tokens": 1,
                "messages": [{"role": "user", "content": "ping"}],
            },
            headers={"Authorization": f"Bearer {cfg.hermes_api_key}"} if cfg.hermes_api_key else {},
        )
        if r.status_code < 400:
            out.append(Check("Endpoint reachability", "ok", f"HTTP {r.status_code}"))
        elif r.status_code in (401, 403):
            out.append(
                Check(
                    "Endpoint reachability",
                    "fail",
                    f"HTTP {r.status_code}",
                    "Check HERMES_API_KEY.",
                )
            )
        else:
            out.append(
                Check(
                    "Endpoint reachability",
                    "warn",
                    f"HTTP {r.status_code}",
                    "Responded, but rejected the request. Check HERMES_MODEL.",
                )
            )
    except Exception as exc:
        out.append(
            Check(
                "Endpoint reachability",
                "fail",
                type(exc).__name__,
                "Is Hermes running and listening at that address?",
            )
        )
    return out


def check_privacy(cfg: Config) -> list[Check]:
    out = []
    if cfg.log_transcripts:
        out.append(
            Check(
                "Transcript logging",
                "warn",
                "ON",
                "Writes what you say to disk. LOG_TRANSCRIPTS=0 turns it off.",
            )
        )
    else:
        out.append(Check("Transcript logging", "ok", "off, nothing touches disk"))
    out.append(
        Check(
            "Half-duplex",
            "ok" if cfg.half_duplex else "warn",
            "on" if cfg.half_duplex else "OFF",
            "" if cfg.half_duplex else "Without headphones, Hermes will talk to itself.",
        )
    )
    hint = (cfg.whisper_hint or "").strip()
    if hint:
        out.append(
            Check("Custom vocabulary", "ok", f"{len(hint.split(','))} term(s) via WHISPER_HINT")
        )
    out.append(
        Check(
            "Data egress",
            "ok",
            "only the Hermes endpoint; voice and wake word run locally",
        )
    )
    if not cfg.half_duplex:
        out.append(
            Check(
                "Echo suppression",
                "ok",
                f"margin {cfg.echo_margin_db:.0f} dB -- headphones are still better",
            )
        )
    return out


# ---------------------------------------------------------------------------
def run(cfg: Config | None = None, probe: bool = False) -> int:
    cfg = cfg or Config.from_env()
    groups = [
        ("Runtime", check_runtime()),
        ("Audio", check_audio(cfg)),
        ("Transcription", check_stt(cfg)),
        ("Wake word", check_wake(cfg)),
        ("End of speech", check_vad(cfg)),
        ("Speech synthesis", check_tts(cfg)),
        ("Hermes", check_llm(cfg, probe)),
        ("Privacy", check_privacy(cfg)),
    ]

    from . import __version__

    print(f"\n{BOLD}hermes-voice {__version__} -- diagnostics{RESET}")
    fails = warns = 0
    for title, checks in groups:
        print(f"\n{CYAN}{title}{RESET}")
        for c in checks:
            color, mark = _MARK[c.status]
            print(f"  {color}{mark}{RESET}{c.name:<22}{DIM}{c.detail}{RESET}")
            if c.fix and c.status in ("warn", "fail"):
                print(f"      {DIM}-> {c.fix}{RESET}")
            fails += c.status == "fail"
            warns += c.status == "warn"

    print()
    if fails:
        print(
            f"{RED}{fails} blocking{RESET}"
            + (f", {YELLOW}{warns} warning(s){RESET}" if warns else "")
        )
        print(f"{DIM}Blocking issues prevent execution. Warnings degrade the experience.{RESET}")
    elif warns:
        print(f"{YELLOW}{warns} warning(s){RESET} -- should work, with caveats.")
    else:
        print(f"{GREEN}All good.{RESET}")

    if os.environ.get("CI"):
        print(f"{DIM}CI detected: absence of audio and GPU is expected here.{RESET}")
    print()
    return 1 if fails else 0
