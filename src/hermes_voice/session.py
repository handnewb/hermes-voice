"""Continuous conversation state machine.

    DORMANT ──"Jarvis"────────► LISTENING
    LISTENING ──700ms silence──► THINKING ──1st audio──► SPEAKING
    SPEAKING ──audio end──────► FOLLOW_UP
    FOLLOW_UP ──voice detected─► LISTENING      (no need to say "Jarvis")
    FOLLOW_UP ──20 s idle─────► DORMANT

The FOLLOW_UP state is what makes this conversation instead of a remote control:
the wake word opens a session, and within it you speak normally. The session
closes on its own when you stop interacting.

Privacy properties, by construction and not by configuration:
  - In DORMANT nothing is transcribed. Frames go only to the wake word
    detector, which runs locally and produces no text.
  - The pre-roll is a deque bounded to PREROLL_MS. Memory only, never disk.
  - When returning to DORMANT, the speech buffer is explicitly discarded.
"""

from __future__ import annotations

import logging
import re
import time
from collections import deque
from enum import Enum

import numpy as np

log = logging.getLogger("hermes.session")

PREROLL_MS = 480  # covers detector latency without swallowing phrase start


class State(Enum):
    DORMANT = "dormant"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"
    FOLLOW_UP = "follow_up"


# Whisper transcribes the wake word in various forms. We strip it from the
# beginning so it doesn't pollute the Hermes prompt.
_WAKE_PREFIX = re.compile(
    r"^\W*(?:ei|hei|hey|oi|ol[áa]|[óô])?\W*"
    r"(?:j|g|dj|ch)[áaàeéê]?rv[iíeêáa]?[sz]?"
    r"(?![A-Za-zÀ-ÿ])"  # boundary: otherwise "Gervasio" becomes "io"
    r"\W*",
    re.IGNORECASE,
)


def strip_wake_word(text: str) -> str:
    cleaned = _WAKE_PREFIX.sub("", text, count=1).strip()
    return cleaned if cleaned else text.strip()


class Session:
    """Holds state, buffers, and timers. Never touches audio or network."""

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

    # -- transition ------------------------------------------------------------
    def to(self, state: State) -> None:
        # Invariant, not transition effect: being in DORMANT means buffer is
        # empty. Applied before the early-return guard on purpose -- otherwise
        # to(DORMANT) from DORMANT would leave retained audio.
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
        """Like take(), but without consuming. Used by endpoint probing."""
        if not self._utterance:
            return np.zeros(0, dtype=np.float32), 0.0
        pcm = np.concatenate(self._utterance).astype(np.float32, copy=False)
        return pcm, float(np.abs(pcm).max()) if pcm.size else 0.0

    def take(self) -> tuple[np.ndarray, float]:
        """Returns (float32 PCM, peak) and clears the buffer."""
        chunks, self._utterance = self._utterance, []
        if not chunks:
            return np.zeros(0, dtype=np.float32), 0.0
        pcm = np.concatenate(chunks).astype(np.float32, copy=False)
        return pcm, float(np.abs(pcm).max()) if pcm.size else 0.0

    def discard(self) -> None:
        self._utterance = []
        self._preroll.clear()

    # -- display ---------------------------------------------------------
    def banner(self) -> str:
        return {
            State.DORMANT: 'waiting for "Jarvis"',
            State.LISTENING: "listening...",
            State.THINKING: "thinking...",
            State.SPEAKING: "speaking",
            State.FOLLOW_UP: "session open -- you may speak",
        }[self.state]
