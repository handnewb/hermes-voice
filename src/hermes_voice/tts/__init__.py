"""Speech synthesis: backend selection, DSP, and playback.

Local engines only, with permissively licensed weights. No network calls at
runtime, no API keys, no registration.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Iterator
from typing import TYPE_CHECKING, Protocol

from .dsp import Presence, PresenceConfig, build_dsp

if TYPE_CHECKING:
    from .speaker import Speaker

log = logging.getLogger("hermes.tts")

# Order for 'auto': piper-binary before kokoro on Windows because espeak-ng
# often lacks language data, and piper-python doesn't compile.
if os.name == "nt":
    BACKENDS = ("piper-binary", "kokoro", "piper-python")
else:
    BACKENDS = ("kokoro", "piper-python", "piper-binary")

__all__ = [
    "BACKENDS",
    "Backend",
    "Presence",
    "PresenceConfig",
    "Speaker",
    "build_backend",
    "build_dsp",
    "build_speaker",
]


class Backend(Protocol):
    sample_rate: int
    name: str

    def synth(self, text: str) -> Iterator[bytes]: ...
    def close(self) -> None: ...


def build_backend(cfg) -> Backend | None:
    want = (cfg.tts_backend or "auto").lower()
    if want == "none":
        return None
    order = list(BACKENDS) if want == "auto" else [want]

    errors: list[str] = []
    for name in order:
        try:
            return _make(name, cfg)
        except Exception as exc:
            errors.append(f"{name}: {exc}")
    log.error(
        "No TTS backend available.\n  %s\n  Install a voice with: hermes-voice voices --install %s",
        "\n  ".join(errors),
        cfg.voice or "pt_BR-faber-medium",
    )
    return None


def _make(name: str, cfg) -> Backend:
    if name == "kokoro":
        from .kokoro import Kokoro

        return Kokoro(cfg.kokoro_model, cfg.kokoro_voices, cfg.kokoro_voice, cfg.kokoro_speed)
    if name == "piper-python":
        from .piper import PiperPython

        return PiperPython(cfg.piper_model)
    if name == "piper-binary":
        from .piper import PiperBinary

        return PiperBinary(cfg.piper_binary, cfg.piper_model)
    raise ValueError(f"unknown backend: {name!r} (options: {', '.join(BACKENDS)})")


def build_speaker(cfg) -> Speaker | None:
    from .speaker import Speaker  # loads portaudio only when about to play audio

    backend = build_backend(cfg)
    if backend is None:
        return None
    log.info("TTS: '%s' at %d Hz.", backend.name, backend.sample_rate)
    return Speaker(backend, cfg.output_device, build_dsp(cfg, backend.sample_rate))
