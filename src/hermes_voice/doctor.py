"""Autodiagnostico. Verifica tudo antes de o usuario descobrir na pratica.

Existe porque, num projeto de voz, 90% dos problemas relatados sao de ambiente e
nao de codigo: driver de audio, cuDNN faltando, wheel que nao compilou, chave
ausente, endpoint fora do ar, EDR bloqueando. Sem isto, cada issue aberta vira
uma conversa de dez mensagens para descobrir qual das dez coisas quebrou.

Nada aqui escreve arquivo, envia audio ou imprime segredo.
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
# Grupos de verificacao
# ---------------------------------------------------------------------------
def check_runtime() -> list[Check]:
    out = []
    v = sys.version_info
    ver = f"{v.major}.{v.minor}.{v.micro}"
    if v < (3, 10):
        out.append(Check("Python", "fail", ver, "Use 3.10 ou superior."))
    elif v >= (3, 14):
        out.append(
            Check(
                "Python",
                "warn",
                ver,
                "Wheels de ctranslate2/pynput podem nao existir. 3.12 e mais seguro.",
            )
        )
    else:
        out.append(Check("Python", "ok", ver))
    out.append(
        Check("Sistema", "ok", f"{platform.system()} {platform.release()} ({platform.machine()})")
    )
    return out


def check_audio(cfg: Config) -> list[Check]:
    if not _has("sounddevice"):
        return [Check("sounddevice", "fail", "ausente", "pip install sounddevice")]
    try:
        import sounddevice as sd

        devices = sd.query_devices()
    except Exception as exc:
        return [
            Check(
                "PortAudio",
                "fail",
                str(exc)[:90],
                "Linux: apt install libportaudio2. Windows: reinstale sounddevice.",
            )
        ]

    ins = [d for d in devices if d["max_input_channels"] > 0]
    outs = [d for d in devices if d["max_output_channels"] > 0]
    out = [
        Check(
            "Microfones",
            "ok" if ins else "fail",
            f"{len(ins)} encontrado(s)",
            "" if ins else "Nenhuma entrada. Verifique a permissao de microfone do sistema.",
        ),
        Check("Saidas de audio", "ok" if outs else "fail", f"{len(outs)} encontrada(s)"),
    ]
    for label, spec, kind in (
        ("INPUT_DEVICE", cfg.input_device, "input"),
        ("OUTPUT_DEVICE", cfg.output_device, "output"),
    ):
        if not spec:
            out.append(Check(label, "skip", "padrao do sistema"))
            continue
        from .audio import resolve_device

        idx = resolve_device(spec, kind)
        if idx is None:
            out.append(
                Check(
                    label,
                    "warn",
                    f"'{spec}' nao encontrado",
                    "Rode --devices e use o indice numerico.",
                )
            )
        else:
            out.append(Check(label, "ok", f"[{idx}] {devices[idx]['name'][:44]}"))
    return out


def check_stt(cfg: Config) -> list[Check]:
    if not _has("faster_whisper"):
        return [Check("faster-whisper", "fail", "ausente", "pip install faster-whisper")]
    out = [Check("faster-whisper", "ok", f"modelo '{cfg.whisper_model}'")]
    if cfg.whisper_device != "cuda":
        out.append(
            Check("Aceleracao STT", "warn", "cpu", "1-3 s por turno. Com GPU cai para ~300 ms.")
        )

        return out
    try:
        import ctranslate2  # type: ignore

        n = ctranslate2.get_cuda_device_count()
    except Exception as exc:
        return [*out, Check("CUDA", "warn", str(exc)[:80], "Cai para CPU automaticamente.")]
    if n == 0:
        out.append(
            Check(
                "CUDA",
                "warn",
                "nenhum device visivel",
                "WHISPER_DEVICE=cpu, ou instale nvidia-cudnn-cu12 e ajuste o PATH.",
            )
        )
    else:
        out.append(Check("CUDA", "ok", f"{n} device(s)"))
    return out


def check_wake(cfg: Config) -> list[Check]:
    if cfg.wake_backend in ("none", "off"):
        return [Check("Wake word", "skip", "desabilitada")]
    if cfg.wake_backend == "open":
        return [
            Check(
                "Wake word",
                "warn",
                "modo aberto",
                "Qualquer fala abre sessao E sera transcrita. Use fone.",
            )
        ]
    if not _has("openwakeword"):
        return [
            Check(
                "openWakeWord",
                "fail",
                "ausente",
                "pip install 'hermes-voice[wake]', ou --trigger console",
            )
        ]
    palavra = cfg.wake_model.replace("hey_", "")
    return [
        Check("openWakeWord", "ok", f"modelo '{cfg.wake_model}', limiar {cfg.wake_threshold}"),
        Check("Palavra a dizer", "ok", f'"ei {palavra}"'),
    ]


def check_vad(cfg: Config) -> list[Check]:
    if not _has("onnxruntime"):
        return [
            Check(
                "VAD",
                "warn",
                "onnxruntime ausente",
                "Cai para VAD por energia, que dispara com ruido de fundo.",
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
                "modelo nao encontrado",
                "hermes-voice voices --install all baixa junto.",
            )
        )
    if cfg.adaptive_endpoint:
        out.append(
            Check(
                "Endpointing", "ok", f"adaptativo {cfg.endpoint_short_ms}-{cfg.endpoint_long_ms} ms"
            )
        )
    else:
        out.append(
            Check(
                "Endpointing",
                "warn",
                f"fixo {cfg.silence_ms} ms",
                "ADAPTIVE_ENDPOINT=1 evita cortar frase pela metade.",
            )
        )
    out.append(Check("Sessao", "ok", f"fecha apos {cfg.follow_up_seconds:.0f} s"))
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
        detalhe = f"{len(piper_onnx)} Piper" + (", Kokoro presente" if kokoro_ok else "")
        out.append(Check("Vozes instaladas", "ok", detalhe))
    else:
        out.append(
            Check(
                "Vozes instaladas",
                "fail",
                "nenhuma",
                "hermes-voice voices --install pt_BR-faber-medium",
            )
        )

    escolhida = cfg.voice or "pt_BR-faber-medium"
    pronta = kokoro_ok if cfg.tts_backend == "kokoro" else Path(cfg.piper_model).exists()
    out.append(
        Check(
            "Voz escolhida",
            "ok" if pronta else "fail",
            f"{escolhida} ({cfg.tts_backend})",
            "" if pronta else f"hermes-voice voices --install {escolhida}",
        )
    )

    out.append(
        Check(
            "Engine Kokoro",
            "ok" if _has("kokoro_onnx") else "skip",
            "kokoro-onnx presente" if _has("kokoro_onnx") else "nao instalada (opcional)",
        )
    )
    exe = shutil.which(cfg.piper_binary) or cfg.piper_binary
    tem_exe = Path(exe).exists()
    out.append(
        Check(
            "Engine Piper",
            "ok" if tem_exe else "warn",
            "binario presente" if tem_exe else "binario ausente",
            "" if tem_exe else "hermes-voice voices --install <ID>",
        )
    )

    if cfg.dsp_preset not in ("off", "none", ""):
        out.append(Check("DSP de presenca", "ok", f"preset '{cfg.dsp_preset}'"))
    else:
        out.append(Check("DSP de presenca", "skip", "off -- --dsp room da presenca de sala"))
    return out


def check_llm(cfg: Config, probe: bool = False) -> list[Check]:
    out = [Check("Endpoint do Hermes", "ok", cfg.hermes_url)]
    persona = Path(cfg.persona_file)
    out.append(
        Check(
            "Arquivo de persona",
            "ok" if persona.exists() else "warn",
            persona.name if persona.exists() else "ausente",
            "" if persona.exists() else "Usando fallback embutido.",
        )
    )
    if not probe:
        out.append(Check("Alcance do endpoint", "skip", "use --doctor --probe para testar"))
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
            out.append(Check("Alcance do endpoint", "ok", f"HTTP {r.status_code}"))
        elif r.status_code in (401, 403):
            out.append(
                Check(
                    "Alcance do endpoint",
                    "fail",
                    f"HTTP {r.status_code}",
                    "Verifique HERMES_API_KEY.",
                )
            )
        else:
            out.append(
                Check(
                    "Alcance do endpoint",
                    "warn",
                    f"HTTP {r.status_code}",
                    "Responde, mas rejeitou a requisicao. Confira HERMES_MODEL.",
                )
            )
    except Exception as exc:
        out.append(
            Check(
                "Alcance do endpoint",
                "fail",
                type(exc).__name__,
                "O Hermes esta rodando e escutando nesse endereco?",
            )
        )
    return out


def check_privacy(cfg: Config) -> list[Check]:
    out = []
    if cfg.log_transcripts:
        out.append(
            Check(
                "Log de transcricao",
                "warn",
                "LIGADO",
                "Grava em disco o que voce falar. LOG_TRANSCRIPTS=0 desliga.",
            )
        )
    else:
        out.append(Check("Log de transcricao", "ok", "desligado, nada toca o disco"))
    out.append(
        Check(
            "Meia-duplex",
            "ok" if cfg.half_duplex else "warn",
            "ligado" if cfg.half_duplex else "DESLIGADO",
            "" if cfg.half_duplex else "Sem fone, o Hermes vai conversar consigo mesmo.",
        )
    )
    hint = (cfg.whisper_hint or "").strip()
    if hint:
        out.append(
            Check("Vocabulario custom", "ok", f"{len(hint.split(','))} termo(s) via WHISPER_HINT")
        )
    out.append(
        Check(
            "Egress de dados",
            "ok",
            "so o endpoint do Hermes; voz e wake word rodam locais",
        )
    )
    if not cfg.half_duplex:
        out.append(
            Check(
                "Supressao de eco",
                "ok",
                f"margem {cfg.echo_margin_db:.0f} dB -- fone ainda e melhor",
            )
        )
    return out


# ---------------------------------------------------------------------------
def run(cfg: Config | None = None, probe: bool = False) -> int:
    cfg = cfg or Config.from_env()
    groups = [
        ("Runtime", check_runtime()),
        ("Audio", check_audio(cfg)),
        ("Transcricao", check_stt(cfg)),
        ("Palavra de ativacao", check_wake(cfg)),
        ("Fim de fala", check_vad(cfg)),
        ("Sintese de voz", check_tts(cfg)),
        ("Hermes", check_llm(cfg, probe)),
        ("Privacidade", check_privacy(cfg)),
    ]

    from . import __version__

    print(f"\n{BOLD}hermes-voice {__version__} -- diagnostico{RESET}")
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
            f"{RED}{fails} bloqueante(s){RESET}"
            + (f", {YELLOW}{warns} aviso(s){RESET}" if warns else "")
        )
        print(f"{DIM}Bloqueantes impedem a execucao. Avisos degradam a experiencia.{RESET}")
    elif warns:
        print(f"{YELLOW}{warns} aviso(s){RESET} -- deve funcionar, com ressalvas.")
    else:
        print(f"{GREEN}Tudo pronto.{RESET}")

    if os.environ.get("CI"):
        print(f"{DIM}CI detectado: ausencia de audio e GPU e esperada aqui.{RESET}")
    print()
    return 1 if fails else 0
