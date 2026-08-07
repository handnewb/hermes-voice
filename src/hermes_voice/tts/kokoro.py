"""Kokoro-82M: Apache-2.0 weights, commercial use allowed, no PyTorch.

Chosen over alternatives with better absolute quality because the license is
clean: Apache-2.0 on the weights means whoever uses this project can embed the
voice in a commercial product without asking anyone's permission. XTTS-v2, for
example, has non-commercial weights -- see docs/VOICE_LICENSING.md.

We run via kokoro-onnx (MIT) and not the official 'kokoro' package, because the
official one pulls in PyTorch (~2.5 GB) and this project already has onnxruntime
installed for the VAD. Model ~327 MB, downloaded once, no account and no key.

No voice cloning: these are fixed preset voices. For this project that's an
advantage, not a limitation.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from pathlib import Path

import numpy as np

log = logging.getLogger("hermes.tts.kokoro")

# pt-BR in Kokoro v1.0: 1 female, 2 male. lang_code 'p'.
VOICES = {
    "pm_alex": ("male", "Male pt-BR voice. Closest to a contained register."),
    "pm_santa": ("male", "Male, deeper and slower."),
    "pf_dora": ("female", "Female pt-BR."),
}
DEFAULT_VOICE = "pm_alex"
LANG_CODE = "p"


class Kokoro:
    name = "kokoro"
    sample_rate = 24000

    def __init__(
        self,
        model_path: str,
        voices_path: str,
        voice: str = DEFAULT_VOICE,
        speed: float = 0.95,
    ) -> None:
        from kokoro_onnx import Kokoro as _Kokoro  # type: ignore

        for label, path in (("model", model_path), ("voices", voices_path)):
            if not Path(path).exists():
                raise FileNotFoundError(
                    f"Kokoro {label} file missing: {path}. "
                    "Run: hermes-voice voices --install kokoro"
                )
        if voice not in VOICES:
            raise ValueError(f"Voice '{voice}' is not pt-BR. Options: {', '.join(VOICES)}")

        self._k = _Kokoro(model_path, voices_path)
        self._voice = voice
        self._speed = max(0.5, min(2.0, speed))
        log.info("Kokoro ready: voice '%s', speed %.2f.", voice, self._speed)

    def synth(self, text: str) -> Iterator[bytes]:
        # create() returns float32 at the model's sample rate.
        samples, rate = self._k.create(text, voice=self._voice, speed=self._speed, lang=LANG_CODE)
        audio = np.asarray(samples, dtype=np.float32)
        rate = int(rate)
        if rate != self.sample_rate:
            audio = _resample(audio, rate, self.sample_rate)
        np.clip(audio, -1.0, 1.0, out=audio)
        # Slices into chunks so the Speaker can interrupt mid-phrase.
        step = 4096
        pcm = (audio * 32767.0).astype("<i2")
        for i in range(0, pcm.size, step):
            yield pcm[i : i + step].tobytes()

    def close(self) -> None:
        pass


def _resample(x: np.ndarray, src: int, dst: int) -> np.ndarray:
    """Linear. Sufficient: only corrects model sample rate divergence."""
    if src == dst or x.size == 0:
        return x
    n = round(x.size * dst / src)
    return np.interp(
        np.linspace(0.0, x.size - 1, n, dtype=np.float64),
        np.arange(x.size, dtype=np.float64),
        x.astype(np.float64),
    ).astype(np.float32)
