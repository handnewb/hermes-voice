"""hermes-voice -- interface de voz conversacional em pt-BR para o Hermes Agent.

Microfone aberto, palavra de ativacao, fim de fala por VAD, sessao que fecha
sozinha. Pipeline encadeado (STT -> LLM -> TTS) com streaming por sentenca.
"""

from __future__ import annotations

__version__ = "1.0.1"
__all__ = ["__version__"]
