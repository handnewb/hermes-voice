"""Playback em streaming com interrupcao, comum a todos os backends.

A escrita e feita em frames de ~23 ms para que interrupt() corte o audio em
tempo humano em vez de esperar o fim do trecho sintetizado.
"""

from __future__ import annotations

import contextlib
import logging
import queue
import threading

from ..audio import _sd, resolve_device
from .dsp import Presence

log = logging.getLogger("hermes.tts.speaker")

_END = object()
FRAME_SAMPLES = 512


class Speaker:
    def __init__(self, backend, output_device: str = "", dsp: Presence | None = None) -> None:
        self._backend = backend
        self._dsp = dsp
        self._echo = None
        self._q: queue.Queue = queue.Queue()
        self._stop = threading.Event()
        self._idle = threading.Event()
        self._idle.set()

        self._stream = _sd().RawOutputStream(
            samplerate=backend.sample_rate,
            channels=1,
            dtype="int16",
            blocksize=FRAME_SAMPLES,
            device=resolve_device(output_device, "output"),
        )
        self._stream.start()
        self._thread = threading.Thread(target=self._run, name="tts", daemon=True)
        self._thread.start()

    def set_echo(self, suppressor) -> None:
        """Registra o supressor de eco que recebe a referencia do que tocamos."""
        self._echo = suppressor

    # -- API do orquestrador -------------------------------------------------
    def begin_turn(self) -> None:
        self._drain()
        self._stop.clear()
        self._idle.clear()
        if self._dsp is not None:
            self._dsp.reset()

    def say(self, text: str) -> None:
        text = text.strip()
        if text:
            self._q.put(text)

    def end_turn(self) -> None:
        self._q.put(_END)

    def interrupt(self) -> None:
        self._stop.set()
        self._drain()
        self._idle.set()
        if self._echo is not None:
            self._echo.clear()

    def wait_until_idle(self, timeout: float | None = None) -> bool:
        return self._idle.wait(timeout)

    @property
    def speaking(self) -> bool:
        return not self._idle.is_set()

    def close(self) -> None:
        self.interrupt()
        for target in (self._stream, self._backend):
            with contextlib.suppress(Exception):
                target.close()

    # -- interno -------------------------------------------------------------
    def _drain(self) -> None:
        while True:
            try:
                self._q.get_nowait()
            except queue.Empty:
                return

    def _run(self) -> None:
        while True:
            item = self._q.get()
            if item is _END:
                self._idle.set()
                continue
            if self._stop.is_set():
                continue
            try:
                self._play(str(item))
            except Exception as exc:
                log.error("Falha na sintese: %s", exc)

    def _play(self, text: str) -> None:
        frame_bytes = FRAME_SAMPLES * 2
        pending = b""
        for chunk in self._backend.synth(text):
            if self._stop.is_set():
                return
            if self._dsp is not None:
                chunk = self._dsp.process(chunk)
            pending += chunk
            while len(pending) >= frame_bytes:
                if self._stop.is_set():
                    return
                block = pending[:frame_bytes]
                if self._echo is not None:
                    self._echo.push_reference(block)
                self._stream.write(block)
                pending = pending[frame_bytes:]
        if self._dsp is not None:
            pending += self._dsp.flush()
        if pending and not self._stop.is_set():
            tail = pending + b"\x00" * ((-len(pending)) % 2)
            if self._echo is not None:
                self._echo.push_reference(tail)
            self._stream.write(tail)
