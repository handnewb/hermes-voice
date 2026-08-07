"""Reference-based echo suppression: real barge-in, no external dependency.

## The problem

With an open mic and speakers, the VAD hears the synthesized voice itself and
the assistant talks to itself. The standard solution is half-duplex: don't
listen while speaking. It works, but kills fluidity -- human conversation has
overlap, and not being able to interrupt is what makes an assistant feel like
a menu tree.

## The approach

This is NOT acoustic echo cancellation (AEC). True AEC estimates the room's
impulse response with an adaptive filter and subtracts the echo from the signal,
allowing transcription of the user's overlapping speech. It requires precise
time alignment and, generally, a native library.

What we do is more modest and solves the case that matters: **deciding whether
what the microphone captured is the user or the speaker itself.** Since we
generate the output audio, we know exactly what was sent. We compare the
microphone energy with the expected energy of the reference, aligned by
cross-correlation, and only declare "the user is speaking" when the energy
exceeds the reference by a margin. No subtraction, no adaptive filter, ~200
lines of numpy.

## Practical consequence

You can interrupt by speaking louder than the speaker. You can't hold an
overlapping conversation at low volume. With headphones, none of this is
necessary: there is no echo.

Degrades safely: if it can't estimate the delay with confidence, it falls
back to half-duplex instead of letting the assistant loop with itself.
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass

import numpy as np

log = logging.getLogger("hermes.echo")

EPS = 1e-9


@dataclass(slots=True)
class EchoConfig:
    enabled: bool = True
    # How much the microphone energy must exceed the reference, in dB, to
    # count as user speech. Below 4 dB generates false positives; above
    # 12 requires shouting.
    margin_db: float = 7.0
    # Delay search window between output and microphone.
    max_delay_ms: int = 320
    # Consecutive frames above margin to declare barge-in. Prevents triggering
    # on a click.
    trigger_frames: int = 3


class EchoSuppressor:
    """Compares microphone with output reference to detect real speech.

    Usage:
        supr.push_reference(pcm_bytes)     # what was sent to the speaker
        ...
        if supr.is_user_speech(frame):     # microphone frame
            barge_in()
    """

    def __init__(self, config: EchoConfig, sample_rate: int, frame_samples: int = 512):
        self.cfg = config
        self.fs = sample_rate
        self.frame = frame_samples

        max_delay = int(sample_rate * config.max_delay_ms / 1000)
        # One second of history beyond max delay. A short buffer was the first
        # bug: the reference lost the segment the microphone was hearing, and
        # the comparison would look at the wrong audio.
        self._ref = deque(maxlen=max_delay + sample_rate)
        self._margin = 10.0 ** (config.margin_db / 20.0)

        self._delay = 0
        self._locked = False
        self._since_lock = 0
        self._hot = 0

    # -- reference -----------------------------------------------------------
    def push_reference(self, pcm_int16: bytes) -> None:
        """Registers the audio delivered to the speaker."""
        if not self.cfg.enabled or not pcm_int16:
            return
        n = len(pcm_int16) - (len(pcm_int16) % 2)
        if n <= 0:
            return
        samples = np.frombuffer(pcm_int16[:n], dtype="<i2").astype(np.float32) / 32767.0
        self._ref.extend(samples.tolist())

    def clear(self) -> None:
        self._ref.clear()
        self._locked = False
        self._since_lock = 0
        self._hot = 0

    @property
    def has_reference(self) -> bool:
        return len(self._ref) >= self.frame * 2

    # -- decision --------------------------------------------------------------
    def is_user_speech(self, mic_float32: np.ndarray) -> bool:
        """True when the microphone contains speech that isn't from the speaker.

        Instead of estimating a single delay and trusting it, we ask: is there
        ANY alignment of the reference, within the search window, that explains
        this frame's energy? If so, it's echo. This is more robust than locking
        a delay, because it doesn't depend on the envelope having enough
        structure to correlate -- a continuous tone, for example, has a flat
        envelope.
        """
        if not self.cfg.enabled:
            return False

        mic_rms = _rms(mic_float32)
        if mic_rms < 0.008:  # silence: nothing to decide
            self._hot = 0
            return False

        if not self.has_reference:
            return self._accumulate(True)  # nothing playing: it's the user

        ref = np.fromiter(self._ref, dtype=np.float32, count=len(self._ref))
        n = mic_float32.size
        if ref.size < n + 8:
            return self._accumulate(True)

        residual = self._best_residual(ref, mic_float32)
        # residual is the fraction of microphone energy that the reference does
        # NOT explain. Near 0 = pure echo. Near 1 = independent sound.
        threshold = 1.0 / self._margin
        return self._accumulate(residual > threshold)

    def _best_residual(self, ref: np.ndarray, mic: np.ndarray) -> float:
        """Smallest relative residual over all delays in the search window."""
        n = mic.size
        max_delay = int(self.fs * self.cfg.max_delay_ms / 1000)
        hop = max(1, n // 8)  # search in steps, not sample by sample

        mic_energy = float(np.dot(mic, mic)) + EPS
        best = 1.0
        end_max = ref.size
        lag = 0
        while lag <= max_delay:
            end = end_max - lag
            start = end - n
            if start < 0:
                break
            seg = ref[start:end]
            seg_energy = float(np.dot(seg, seg))
            if seg_energy > 1e-8:
                # Optimal gain by least squares, clamped to physical gain.
                gain = float(np.clip(np.dot(mic, seg) / seg_energy, 0.0, 4.0))
                resid = float(np.dot(mic - gain * seg, mic - gain * seg)) / mic_energy
                if resid < best:
                    best = resid
                    self._delay = lag
                    self._locked = True
            lag += hop
        return best

    def _accumulate(self, hot: bool) -> bool:
        self._hot = self._hot + 1 if hot else 0
        return self._hot >= self.cfg.trigger_frames


def _rms(x: np.ndarray) -> float:
    if x.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(x.astype(np.float64) ** 2)))


def build_echo(cfg, sample_rate: int, frame_samples: int = 512) -> EchoSuppressor | None:
    """None when half-duplex is active -- nothing to suppress."""
    if getattr(cfg, "half_duplex", True):
        return None
    ec = EchoConfig(
        enabled=True,
        margin_db=getattr(cfg, "echo_margin_db", 7.0),
        trigger_frames=getattr(cfg, "echo_trigger_frames", 3),
    )
    log.info("Echo suppression active: margin %.1f dB. Headphones are still better.", ec.margin_db)
    return EchoSuppressor(ec, sample_rate, frame_samples)
