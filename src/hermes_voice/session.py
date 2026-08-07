"""Maquina de estados da conversa contínua.

    DORMANT ──"Jarvis"────────► LISTENING
    LISTENING ──silencio 700ms──► THINKING ──1o audio──► SPEAKING
    SPEAKING ──fim do audio────► FOLLOW_UP
    FOLLOW_UP ──voz detectada──► LISTENING      (sem precisar dizer "Jarvis")
    FOLLOW_UP ──20 s parado────► DORMANT

O estado FOLLOW_UP e o que faz isto ser conversa e nao controle remoto: a
palavra de ativacao abre uma sessao, e dentro dela voce fala normalmente. A
sessao fecha sozinha quando voce para de interagir.

Propriedades de privacidade, por construcao e nao por configuracao:
  - Em DORMANT nada e transcrito. Os frames vao apenas para o detector de wake
    word, que roda local e nao produz texto.
  - O pre-roll e um deque limitado a PREROLL_MS. Memoria apenas, nunca disco.
  - Ao voltar para DORMANT, o buffer de fala e descartado explicitamente.
"""

from __future__ import annotations

import logging
import re
import time
from collections import deque
from enum import Enum

import numpy as np

log = logging.getLogger("hermes.session")

PREROLL_MS = 480  # cobre a latencia do detector sem engolir o inicio da frase


class State(Enum):
    DORMANT = "dormant"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"
    FOLLOW_UP = "follow_up"


# O Whisper transcreve a palavra de ativacao de varias formas. Removemos do
# inicio para nao poluir o prompt do Hermes.
_WAKE_PREFIX = re.compile(
    r"^\W*(?:ei|hei|hey|oi|ol[áa]|[óô])?\W*"
    r"(?:j|g|dj|ch)[áaàeéê]?rv[iíeêáa]?[sz]?"
    r"(?![A-Za-zÀ-ÿ])"  # fronteira: senao "Gervasio" viraria "io"
    r"\W*",
    re.IGNORECASE,
)


def strip_wake_word(text: str) -> str:
    cleaned = _WAKE_PREFIX.sub("", text, count=1).strip()
    return cleaned if cleaned else text.strip()


class Session:
    """Mantem estado, buffers e temporizadores. Nao toca em audio nem em rede."""

    def __init__(
        self,
        sample_rate: int = 16000,
        frame_ms: int = 32,
        follow_up_seconds: float = 20.0,
        max_utterance_seconds: float = 30.0,
    ) -> None:
        self.sample_rate = sample_rate
        self.frame_ms = frame_ms
        self.follow_up_seconds = follow_up_seconds
        self.max_utterance_frames = int(max_utterance_seconds * 1000 / frame_ms)

        preroll_frames = max(1, int(PREROLL_MS / frame_ms))
        self._preroll: deque[np.ndarray] = deque(maxlen=preroll_frames)
        self._utterance: list[np.ndarray] = []

        self.state = State.DORMANT
        self._entered = time.monotonic()

    # -- transicao ------------------------------------------------------------
    def to(self, state: State) -> None:
        # Invariante, nao efeito de transicao: estar em DORMANT significa buffer
        # vazio. Aplicado antes do guard de early-return de proposito -- senao
        # to(DORMANT) a partir de DORMANT deixaria audio retido.
        if state == State.DORMANT:
            self.discard()
        if state == self.state:
            return
        log.debug("%s -> %s", self.state.value, state.value)
        self.state = state
        self._entered = time.monotonic()

    @property
    def elapsed(self) -> float:
        return time.monotonic() - self._entered

    @property
    def follow_up_expired(self) -> bool:
        return self.state == State.FOLLOW_UP and self.elapsed >= self.follow_up_seconds

    # -- buffers --------------------------------------------------------------
    def keep_preroll(self, frame: np.ndarray) -> None:
        self._preroll.append(frame)

    def begin_utterance(self, include_preroll: bool = True) -> None:
        self._utterance = list(self._preroll) if include_preroll else []
        self._preroll.clear()

    def append(self, frame: np.ndarray) -> None:
        if len(self._utterance) < self.max_utterance_frames:
            self._utterance.append(frame)

    @property
    def overlong(self) -> bool:
        return len(self._utterance) >= self.max_utterance_frames

    def peek(self) -> tuple[np.ndarray, float]:
        """Como take(), mas sem consumir. Usado pela sondagem de endpoint."""
        if not self._utterance:
            return np.zeros(0, dtype=np.float32), 0.0
        pcm = np.concatenate(self._utterance).astype(np.float32, copy=False)
        return pcm, float(np.abs(pcm).max()) if pcm.size else 0.0

    def take(self) -> tuple[np.ndarray, float]:
        """Devolve (pcm float32, pico) e limpa o buffer."""
        chunks, self._utterance = self._utterance, []
        if not chunks:
            return np.zeros(0, dtype=np.float32), 0.0
        pcm = np.concatenate(chunks).astype(np.float32, copy=False)
        return pcm, float(np.abs(pcm).max()) if pcm.size else 0.0

    def discard(self) -> None:
        self._utterance = []
        self._preroll.clear()

    # -- apresentacao ---------------------------------------------------------
    def banner(self) -> str:
        return {
            State.DORMANT: 'aguardando "Jarvis"',
            State.LISTENING: "escutando...",
            State.THINKING: "pensando...",
            State.SPEAKING: "falando",
            State.FOLLOW_UP: "sessao aberta -- pode falar",
        }[self.state]
