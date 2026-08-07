"""Kokoro-82M: pesos Apache-2.0, uso comercial liberado, sem PyTorch.

Escolhido em vez de alternativas melhores em qualidade absoluta porque a licenca
e limpa: Apache-2.0 nos pesos significa que quem usar este projeto pode embarcar
a voz num produto comercial sem pedir permissao a ninguem. XTTS-v2, por exemplo,
tem pesos non-commercial -- ver docs/VOICE_LICENSING.md.

Rodamos via kokoro-onnx (MIT) e nao via o pacote 'kokoro' oficial, porque o
oficial arrasta PyTorch (~2,5 GB) e este projeto ja tem onnxruntime instalado
para o VAD. Modelo ~327 MB, baixado uma vez, sem conta e sem chave.

Nao faz clonagem de voz: sao vozes fixas de preset. Para este projeto isso e
vantagem, nao limitacao.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from pathlib import Path

import numpy as np

log = logging.getLogger("hermes.tts.kokoro")

# pt-BR no Kokoro v1.0: 1 feminina, 2 masculinas. lang_code 'p'.
VOICES = {
    "pm_alex": ("masculina", "Voz masculina pt-BR. A mais proxima do registro contido."),
    "pm_santa": ("masculina", "Masculina, mais grave e lenta."),
    "pf_dora": ("feminina", "Feminina pt-BR."),
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

        for label, path in (("modelo", model_path), ("vozes", voices_path)):
            if not Path(path).exists():
                raise FileNotFoundError(
                    f"Arquivo de {label} do Kokoro ausente: {path}. "
                    "Rode: hermes-voice voices --install kokoro"
                )
        if voice not in VOICES:
            raise ValueError(f"Voz '{voice}' nao e pt-BR. Opcoes: {', '.join(VOICES)}")

        self._k = _Kokoro(model_path, voices_path)
        self._voice = voice
        self._speed = max(0.5, min(2.0, speed))
        log.info("Kokoro pronto: voz '%s', velocidade %.2f.", voice, self._speed)

    def synth(self, text: str) -> Iterator[bytes]:
        # create() devolve float32 no sample rate do modelo.
        samples, rate = self._k.create(text, voice=self._voice, speed=self._speed, lang=LANG_CODE)
        audio = np.asarray(samples, dtype=np.float32)
        rate = int(rate)
        if rate != self.sample_rate:
            audio = _resample(audio, rate, self.sample_rate)
        np.clip(audio, -1.0, 1.0, out=audio)
        # Fatia em pedacos para o Speaker poder interromper no meio da frase.
        step = 4096
        pcm = (audio * 32767.0).astype("<i2")
        for i in range(0, pcm.size, step):
            yield pcm[i : i + step].tobytes()

    def close(self) -> None:
        pass


def _resample(x: np.ndarray, src: int, dst: int) -> np.ndarray:
    """Linear. Suficiente: so corrige divergencia de sample rate do modelo."""
    if src == dst or x.size == 0:
        return x
    n = round(x.size * dst / src)
    return np.interp(
        np.linspace(0.0, x.size - 1, n, dtype=np.float64),
        np.arange(x.size, dtype=np.float64),
        x.astype(np.float64),
    ).astype(np.float32)
