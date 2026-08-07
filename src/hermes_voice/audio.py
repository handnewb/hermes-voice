"""Microphone capture: open mic (FrameSource) and push-to-talk (Recorder)."""

from __future__ import annotations

import logging
import queue
import threading

import numpy as np

log = logging.getLogger("hermes.audio")


def _sd():
    """Lazy import of sounddevice.

    The module loads libportaudio on import. CI runners and containers don't
    have sound cards, and the package needs to be importable (and testable)
    without one.
    """
    import sounddevice as sd

    return sd


def resolve_device(spec: str, kind: str) -> int | None:
    """Accepts numeric index or device name fragment."""
    spec = (spec or "").strip()
    if not spec:
        return None
    if spec.isdigit():
        return int(spec)
    want = spec.lower()
    key = "max_input_channels" if kind == "input" else "max_output_channels"
    for idx, dev in enumerate(_sd().query_devices()):
        if dev[key] > 0 and want in dev["name"].lower():
            return idx
    log.warning("%s device '%s' not found; using default.", kind, spec)
    return None


def list_devices() -> str:
    lines = ["", "Available audio devices:", "-" * 60]
    for idx, dev in enumerate(_sd().query_devices()):
        tags = []
        if dev["max_input_channels"] > 0:
            tags.append(f"in:{dev['max_input_channels']}")
        if dev["max_output_channels"] > 0:
            tags.append(f"out:{dev['max_output_channels']}")
        lines.append(f"  [{idx:>2}] {dev['name']}  ({', '.join(tags)})")
    return "\n".join(lines)


class FrameSource:
    """Open mic: delivers fixed-size frames through a queue.

    Unlike Recorder, it has no "recording" state. It just produces frames; the
    state machine decides what to do with each one. This keeps the privacy
    decision in one place (session.py) instead of spread across audio.

    The queue is bounded: if the consumer stalls, old frames are dropped instead
    of memory growing unbounded.
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        device: str = "",
        frame_samples: int = 512,
        max_queue: int = 64,
    ) -> None:
        self.sample_rate = sample_rate
        self.frame_samples = frame_samples
        self.frame_ms = int(frame_samples * 1000 / sample_rate)
        self._q: queue.Queue = queue.Queue(maxsize=max_queue)
        self.dropped = 0

        self._stream = _sd().InputStream(
            samplerate=sample_rate,
            channels=1,
            dtype="float32",
            blocksize=frame_samples,
            device=resolve_device(device, "input"),
            callback=self._callback,
        )

    def _callback(self, indata, _frames, _time, status) -> None:
        if status:
            log.debug("Input stream status: %s", status)
        try:
            self._q.put_nowait(indata[:, 0].copy())
        except queue.Full:
            self.dropped += 1
            try:
                self._q.get_nowait()
                self._q.put_nowait(indata[:, 0].copy())
            except queue.Empty:
                pass

    def __enter__(self) -> FrameSource:
        self._stream.start()
        return self

    def __exit__(self, *_exc) -> None:
        self.close()

    def read(self, timeout: float = 0.5) -> np.ndarray | None:
        try:
            return self._q.get(timeout=timeout)
        except queue.Empty:
            return None

    def drain(self) -> int:
        """Discards accumulated frames. Used when leaving THINKING."""
        n = 0
        while True:
            try:
                self._q.get_nowait()
                n += 1
            except queue.Empty:
                return n

    def close(self) -> None:
        try:
            self._stream.stop()
            self._stream.close()
        except Exception:
            pass


class Recorder:
    """Records while the PTT key is held down.

    The InputStream stays open for the entire session (open/close costs ~200 ms
    on WASAPI). Frames are discarded when we're not recording.
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        device: str = "",
        max_seconds: float = 45.0,
        blocksize: int = 512,
    ) -> None:
        self.sample_rate = sample_rate
        self.max_frames = int(max_seconds * sample_rate)
        self._lock = threading.Lock()
        self._active = False
        self._chunks: list[np.ndarray] = []
        self._frames = 0
        self._peak = 0.0

        self._stream = _sd().InputStream(
            samplerate=sample_rate,
            channels=1,
            dtype="float32",
            blocksize=blocksize,
            device=resolve_device(device, "input"),
            callback=self._callback,
        )

    def _callback(self, indata, _frames, _time, status) -> None:
        if status:
            log.debug("Input stream status: %s", status)
        with self._lock:
            if not self._active or self._frames >= self.max_frames:
                return
            block = indata[:, 0].copy()
            self._chunks.append(block)
            self._frames += block.shape[0]
            peak = float(np.abs(block).max())
            if peak > self._peak:
                self._peak = peak

    def __enter__(self) -> Recorder:
        self._stream.start()
        return self

    def __exit__(self, *_exc) -> None:
        self.close()

    def close(self) -> None:
        try:
            self._stream.stop()
            self._stream.close()
        except Exception:
            pass

    def start(self) -> None:
        with self._lock:
            self._chunks.clear()
            self._frames = 0
            self._peak = 0.0
            self._active = True

    @property
    def recording(self) -> bool:
        with self._lock:
            return self._active

    @property
    def peak(self) -> float:
        with self._lock:
            return self._peak

    def stop(self) -> tuple[np.ndarray, float]:
        """Returns (float32 mono PCM, amplitude peak)."""
        with self._lock:
            self._active = False
            chunks, peak = self._chunks, self._peak
            self._chunks = []
            self._frames = 0
        if not chunks:
            return np.zeros(0, dtype=np.float32), 0.0
        return np.concatenate(chunks).astype(np.float32, copy=False), peak
