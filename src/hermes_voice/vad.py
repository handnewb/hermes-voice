"""Deteccao de atividade de voz e de fim de fala.

Dois backends:
  1. silero  -- ONNX de ~2 MB via onnxruntime, ~1 ms por janela de 32 ms. Robusto
                a ruido de fundo. Precisa de frames de exatamente 512 amostras.
  2. energy  -- limiar de RMS. Zero dependencia, funciona em sala silenciosa,
                dispara com ar-condicionado. Existe para o sistema nunca ficar
                inoperante se o download do Silero falhar.

A logica de fim de fala fica em SpeechGate, comum aos dois backends.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Protocol

import numpy as np

log = logging.getLogger("hermes.vad")

FRAME = 512  # 32 ms @ 16 kHz -- exigido pelo Silero v5


class VadBackend(Protocol):
    def prob(self, frame_float32: np.ndarray) -> float: ...
    def reset(self) -> None: ...


class SileroVad:
    def __init__(self, model_path: str = "") -> None:
        import onnxruntime as ort  # type: ignore

        path = Path(model_path) if model_path else _locate_silero()
        if path is None or not path.exists():
            raise FileNotFoundError(
                "silero_vad.onnx nao encontrado. Instale com "
                "'pip install silero-vad' ou aponte VAD_MODEL para o arquivo."
            )

        opts = ort.SessionOptions()
        opts.inter_op_num_threads = 1
        opts.intra_op_num_threads = 1
        opts.log_severity_level = 3
        self._sess = ort.InferenceSession(
            str(path), sess_options=opts, providers=["CPUExecutionProvider"]
        )
        self._inputs = {i.name for i in self._sess.get_inputs()}
        # v5 usa um tensor 'state' unico; v4 usava 'h' e 'c' separados.
        self._v5 = "state" in self._inputs
        self.reset()
        log.info("Silero VAD carregado de %s (%s).", path.name, "v5" if self._v5 else "v4")

    def reset(self) -> None:
        if self._v5:
            self._state = np.zeros((2, 1, 128), dtype=np.float32)
        else:
            self._h = np.zeros((2, 1, 64), dtype=np.float32)
            self._c = np.zeros((2, 1, 64), dtype=np.float32)

    def prob(self, frame_float32: np.ndarray) -> float:
        x = frame_float32.reshape(1, -1).astype(np.float32)
        feed: dict = {"input": x, "sr": np.array(16000, dtype=np.int64)}
        if self._v5:
            feed["state"] = self._state
            out, self._state = self._sess.run(None, feed)
        else:
            feed["h"], feed["c"] = self._h, self._c
            out, self._h, self._c = self._sess.run(None, feed)
        return float(np.asarray(out).reshape(-1)[0])


def _locate_silero() -> Path | None:
    try:
        import silero_vad  # type: ignore

        base = Path(silero_vad.__file__).parent
        for candidate in base.rglob("silero_vad*.onnx"):
            return candidate
    except Exception:
        pass
    local = Path(__file__).resolve().parent.parent / "models" / "silero_vad.onnx"
    return local if local.exists() else None


class EnergyVad:
    """Fallback por RMS. Calibra o piso de ruido nos primeiros frames."""

    def __init__(self, threshold: float = 0.02, calibration_frames: int = 30) -> None:
        self._threshold = threshold
        self._floor = 0.0
        self._seen = 0
        self._calib = calibration_frames

    def prob(self, frame_float32: np.ndarray) -> float:
        rms = float(np.sqrt(np.mean(frame_float32.astype(np.float64) ** 2)))
        if self._seen < self._calib:
            self._seen += 1
            self._floor = max(self._floor, rms)
            return 0.0
        margin = max(self._threshold, self._floor * 2.5)
        return 1.0 if rms > margin else 0.0

    def reset(self) -> None:
        pass


def build_vad(cfg) -> VadBackend:
    want = (getattr(cfg, "vad_backend", "auto") or "auto").lower()
    if want != "energy":
        try:
            return SileroVad(getattr(cfg, "vad_model", ""))
        except Exception as exc:
            if want == "silero":
                raise
            log.warning("Silero indisponivel (%s). Usando VAD por energia.", exc)
    return EnergyVad(cfg.vad_energy_threshold)


class SpeechGate:
    """Converte probabilidade por frame em eventos de inicio e fim de fala.

    Histerese deliberada: entra em fala rapido (2 frames) e sai devagar
    (silence_ms), porque cortar o usuario no meio de uma pausa natural e o
    defeito mais irritante de assistente de voz.
    """

    def __init__(
        self,
        threshold: float = 0.5,
        silence_ms: int = 700,
        min_speech_ms: int = 200,
        frame_ms: int = 32,
    ) -> None:
        self.threshold = threshold
        self._silence_frames = max(1, silence_ms // frame_ms)
        self._min_speech_frames = max(1, min_speech_ms // frame_ms)
        self.reset()

    def reset(self) -> None:
        self._speaking = False
        self._speech_run = 0
        self._silence_run = 0
        self._total_speech = 0

    @property
    def speaking(self) -> bool:
        return self._speaking

    @property
    def had_speech(self) -> bool:
        return self._total_speech >= self._min_speech_frames

    def update(self, prob: float) -> str:
        """Retorna '', 'start' ou 'end'."""
        voiced = prob >= self.threshold
        if voiced:
            self._speech_run += 1
            self._silence_run = 0
            self._total_speech += 1
            if not self._speaking and self._speech_run >= 2:
                self._speaking = True
                return "start"
            return ""

        self._speech_run = 0
        if self._speaking:
            self._silence_run += 1
            if self._silence_run >= self._silence_frames:
                self._speaking = False
                return "end" if self.had_speech else ""
        return ""
