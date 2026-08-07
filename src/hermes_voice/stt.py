"""Transcricao com faster-whisper, ajustada para pt-BR falado."""

from __future__ import annotations

import logging
import time

import numpy as np

log = logging.getLogger("hermes.stt")

# Vocabulario de dominio: reduz drasticamente erro em nomes proprios e siglas.
# O Whisper usa isso como prefixo condicionante, nao como restricao rigida.
#
# IMPORTANTE: coloque o SEU vocabulario em WHISPER_HINT no .env -- nomes de
# produto, cliente, ferramenta interna. Nao faca commit de termos internos num
# repositorio publico; e a forma mais silenciosa de vazar a sua stack.
DEFAULT_HINT = (
    "Hermes, agente, skill, playbook, endpoint, ticket, webhook, container, "
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
        from faster_whisper import WhisperModel  # import tardio: carrega CUDA

        self.language = language
        self.hint = hint.strip() or DEFAULT_HINT

        try:
            self._model = WhisperModel(model, device=device, compute_type=compute_type)
            self.device = device
        except Exception as exc:  # CUDA/cuDNN ausente e o erro mais comum no Windows
            if device == "cpu":
                raise
            log.warning("Falha ao iniciar Whisper em %s (%s). Caindo para CPU int8.", device, exc)
            self._model = WhisperModel(model, device="cpu", compute_type="int8")
            self.device = "cpu"

        log.info("Whisper '%s' pronto em %s.", model, self.device)

    def warmup(self) -> None:
        """Paga o custo da primeira inferencia antes do usuario falar."""
        silence = np.zeros(self.sample_rate // 2, dtype=np.float32)
        t0 = time.perf_counter()
        self.transcribe(silence)
        log.info("Warmup do STT em %.0f ms.", (time.perf_counter() - t0) * 1000)

    sample_rate = 16000

    def transcribe(self, pcm_float32: np.ndarray) -> str:
        """pcm_float32: mono, 16 kHz, faixa [-1, 1]."""
        if pcm_float32.size < self.sample_rate // 10:  # < 100 ms
            return ""
        segments, _info = self._model.transcribe(
            pcm_float32,
            language=self.language,
            beam_size=1,  # greedy: metade da latencia
            temperature=0.0,
            vad_filter=True,  # corta silencio nas pontas
            vad_parameters={"min_silence_duration_ms": 300},
            condition_on_previous_text=False,  # evita alucinacao em loop
            initial_prompt=self.hint,
            no_speech_threshold=0.5,
        )
        text = " ".join(seg.text.strip() for seg in segments)
        return " ".join(text.split()).strip()
