"""Captura de microfone: microfone aberto (FrameSource) e push-to-talk (Recorder)."""

from __future__ import annotations

import logging
import queue
import threading

import numpy as np

log = logging.getLogger("hermes.audio")


def _sd():
    """Import preguicoso do sounddevice.

    O modulo carrega a libportaudio no import. Runners de CI e containers nao
    tem placa de som, e o pacote precisa ser importavel (e testavel) sem ela.
    """
    import sounddevice as sd

    return sd


def resolve_device(spec: str, kind: str) -> int | None:
    """Aceita indice numerico ou fragmento do nome do dispositivo."""
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
    log.warning("Dispositivo de %s '%s' nao encontrado; usando o padrao.", kind, spec)
    return None


def list_devices() -> str:
    lines = ["", "Dispositivos de audio disponiveis:", "-" * 60]
    for idx, dev in enumerate(_sd().query_devices()):
        tags = []
        if dev["max_input_channels"] > 0:
            tags.append(f"in:{dev['max_input_channels']}")
        if dev["max_output_channels"] > 0:
            tags.append(f"out:{dev['max_output_channels']}")
        lines.append(f"  [{idx:>2}] {dev['name']}  ({', '.join(tags)})")
    return "\n".join(lines)


class FrameSource:
    """Microfone aberto: entrega frames de tamanho fixo por uma fila.

    Diferente do Recorder, nao tem estado de "gravando". Ele so produz frames; a
    maquina de estados decide o que fazer com cada um. Isso mantem a decisao de
    privacidade num lugar so (session.py) em vez de espalhada pelo audio.

    A fila e limitada: se o consumidor travar, frames antigos sao descartados em
    vez de a memoria crescer sem limite.
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
            log.debug("Status do stream de entrada: %s", status)
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
        """Descarta o acumulado. Usado ao sair de THINKING."""
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
    """Grava enquanto a tecla PTT estiver pressionada.

    O InputStream fica aberto durante toda a sessao (abrir/fechar custa ~200 ms
    no WASAPI). Os frames sao descartados quando nao estamos gravando.
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
            log.debug("Status do stream de entrada: %s", status)
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
        """Retorna (pcm float32 mono, pico de amplitude)."""
        with self._lock:
            self._active = False
            chunks, peak = self._chunks, self._peak
            self._chunks = []
            self._frames = 0
        if not chunks:
            return np.zeros(0, dtype=np.float32), 0.0
        return np.concatenate(chunks).astype(np.float32, copy=False), peak
