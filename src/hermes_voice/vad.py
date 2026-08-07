"""Voice activity detection and end-of-speech detection.

Two backends:
  1. silero  -- ~2 MB ONNX via onnxruntime, ~1 ms per 32 ms window. Robust to
                background noise. Requires exactly 512-sample frames.
  2. energy  -- RMS threshold. Zero dependencies, works in a quiet room,
                triggers with air conditioning. Exists so the system never
                becomes inoperable if the Silero download fails.

End-of-speech logic lives in SpeechGate, common to both backends.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Protocol

import numpy as np

log = logging.getLogger("hermes.vad")

FRAME = 512  # 32 ms @ 16 kHz -- required by Silero v5


class VadBackend(Protocol):
    def prob(self, frame_float32: np.ndarray) -> float: ...
    def reset(self) -> None: ...


class SileroVad:
    def __init__(self, model_path: str = "") -> None:
        import onnxruntime as ort  # type: ignore

        path = Path(model_path) if model_path else _locate_silero()
        if path is None or not path.exists():
            raise FileNotFoundError(
                "silero_vad.onnx not found. Install with "
                "'pip install silero-vad' or point VAD_MODEL to the file."
            )

        opts = ort.SessionOptions()
        opts.inter_op_num_threads = 1
        opts.intra_op_num_threads = 1
        opts.log_severity_level = 3
        self._sess = ort.InferenceSession(
            str(path), sess_options=opts, providers=["CPUExecutionProvider"]
        )
        self._inputs = {i.name for i in self._sess.get_inputs()}
        # v5 uses a single 'state' tensor; v4 used separate 'h' and 'c'.
        self._v5 = "state" in self._inputs
        self.reset()
        log.info("Silero VAD loaded from %s (%s).", path.name, "v5" if self._v5 else "v4")

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
    """RMS fallback. Calibrates the noise floor on the first frames."""

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
            log.warning("Silero unavailable (%s). Using energy VAD.", exc)
    return EnergyVad(cfg.vad_energy_threshold)


class SpeechGate:
    """Converts per-frame probability into speech start and end events.

    Deliberate hysteresis: enters speech fast (2 frames) and exits slowly
    (silence_ms), because cutting the user off mid-natural-pause is the most
    annoying voice-assistant defect.
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
        """Returns '', 'start', or 'end'."""
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
