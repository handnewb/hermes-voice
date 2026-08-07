"""Transcription with faster-whisper, tuned for spoken pt-BR."""

from __future__ import annotations

import logging
import time

import numpy as np

log = logging.getLogger("hermes.stt")

# Domain vocabulary: drastically reduces errors on proper names and acronyms.
# Whisper uses this as a conditioning prefix, not as a rigid constraint.
#
# IMPORTANT: put YOUR vocabulary in WHISPER_HINT in .env -- product names,
# client names, internal tools. Don't commit internal terms to a public
# repository; it's the quietest way to leak your stack.
DEFAULT_HINT = (
    "Hermes, agent, skill, playbook, endpoint, ticket, webhook, container, "
    "deploy, pipeline, dashboard, LGPD, GDPR, ISO 27001."
)


class Transcriber:
    def __init__(
        self,
        model: str = "large-v3-turbo",
        device: str = "cuda",
        compute_type: str = "int8_float16",
        language: str = "pt",
        hint: str = "",
    ) -> None:
        from faster_whisper import WhisperModel  # lazy import: loads CUDA

        self.language = language
        self.hint = hint.strip() or DEFAULT_HINT

        try:
            self._model = WhisperModel(model, device=device, compute_type=compute_type)
            self.device = device
        except Exception as exc:  # missing CUDA/cuDNN is the most common error on Windows
            if device == "cpu":
                raise
            log.warning(
                "Failed to start Whisper on %s (%s). Falling back to CPU int8.",
                device, exc,
            )
            self._model = WhisperModel(model, device="cpu", compute_type="int8")
            self.device = "cpu"

        log.info("Whisper '%s' ready on %s.", model, self.device)

    def warmup(self) -> None:
        """Pays the first-inference cost before the user speaks."""
        silence = np.zeros(self.sample_rate // 2, dtype=np.float32)
        t0 = time.perf_counter()
        self.transcribe(silence)
        log.info("STT warmup in %.0f ms.", (time.perf_counter() - t0) * 1000)

    sample_rate = 16000

    def transcribe(self, pcm_float32: np.ndarray) -> str:
        """pcm_float32: mono, 16 kHz, range [-1, 1]."""
        if pcm_float32.size < self.sample_rate // 10:  # < 100 ms
            return ""
        segments, _info = self._model.transcribe(
            pcm_float32,
            language=self.language,
            beam_size=1,  # greedy: half the latency
            temperature=0.0,
            vad_filter=True,  # trims silence at edges
            vad_parameters={"min_silence_duration_ms": 300},
            condition_on_previous_text=False,  # avoids hallucination in loop
            initial_prompt=self.hint,
            no_speech_threshold=0.5,
        )
        text = " ".join(seg.text.strip() for seg in segments)
        return " ".join(text.split()).strip()
