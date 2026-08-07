"""hermes-voice -- conversational voice interface in Brazilian Portuguese for Hermes Agent.

Open mic, wake word, VAD end-of-speech, session that closes on its own.
Chained pipeline (STT -> LLM -> TTS) with sentence-level streaming.
"""

from __future__ import annotations

__version__ = "1.0.1"
__all__ = ["__version__"]
