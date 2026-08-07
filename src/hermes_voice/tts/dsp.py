""""Presence" stage: makes the voice sound like room sound, not narration.

Much of what people identify as a sci-fi assistant voice isn't in the timbre --
it's in the processing. Speech is treated as coming from speakers in a room,
and no TTS delivers that out of the box.

Four stages, in order of importance:

  1. high-pass  -- cuts below ~110 Hz. Removes the "mouth on mic" weight
                   that betrays close-mic narration.
  2. compressor -- flattens dynamics. Calm, measured voice has little volume
                   variation; this is what gives the sense of control.
  3. presence   -- gentle boost at 2-4 kHz. Distance intelligibility.
  4. reverb     -- small room, short, very low. Gives the sound a place.
                   Overdoing this is the most common mistake and sounds like
                   a bathroom.

Everything processes in streaming, block by block, with continuous state
across blocks -- without this, clicks appear at the seams. Depends only
on numpy.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

log = logging.getLogger("hermes.tts.dsp")

INT16_MAX = 32767.0


@dataclass(slots=True)
class PresenceConfig:
    enabled: bool = False
    highpass_hz: float = 110.0
    comp_threshold_db: float = -20.0
    comp_ratio: float = 4.0
    comp_attack_ms: float = 5.0
    comp_release_ms: float = 120.0
    comp_makeup_db: float = 3.0
    presence_hz: float = 3000.0
    presence_gain_db: float = 3.0
    presence_q: float = 0.8
    reverb_ms: float = 55.0
    reverb_mix: float = 0.10
    reverb_decay: float = 0.35
    output_gain_db: float = 0.0

    # Named presets. 'room' is the sensible default; 'hall' exaggerates on
    # purpose so you can hear what each parameter does before calibrating.
    @classmethod
    def preset(cls, name: str) -> PresenceConfig:
        name = (name or "off").lower()
        if name in {"off", "none", ""}:
            return cls(enabled=False)
        if name == "room":
            return cls(enabled=True)
        if name == "close":  # no room: just weight and control
            return cls(enabled=True, reverb_mix=0.0, presence_gain_db=2.0)
        if name == "hall":  # deliberately overdone
            return cls(
                enabled=True,
                reverb_ms=120.0,
                reverb_mix=0.22,
                reverb_decay=0.5,
                presence_gain_db=4.0,
            )
        if name == "intercom":  # narrow band, like ceiling speakers
            return cls(
                enabled=True,
                highpass_hz=250.0,
                presence_hz=2200.0,
                presence_gain_db=6.0,
                reverb_mix=0.06,
                comp_threshold_db=-24.0,
                comp_ratio=6.0,
            )
        log.warning("Unknown DSP preset: %r. Using 'room'.", name)
        return cls(enabled=True)


def _db(x: float) -> float:
    return float(10.0 ** (x / 20.0))


class _Biquad:
    """Direct-form I biquad with persistent state across blocks."""

    __slots__ = ("_x1", "_x2", "_y1", "_y2", "a1", "a2", "b0", "b1", "b2")

    def __init__(self, b0, b1, b2, a0, a1, a2) -> None:
        self.b0, self.b1, self.b2 = b0 / a0, b1 / a0, b2 / a0
        self.a1, self.a2 = a1 / a0, a2 / a0
        self._x1 = self._x2 = self._y1 = self._y2 = 0.0

    @classmethod
    def highpass(cls, fs: float, f0: float, q: float = 0.707) -> _Biquad:
        w = 2.0 * np.pi * f0 / fs
        cw, sw = np.cos(w), np.sin(w)
        alpha = sw / (2.0 * q)
        return cls((1 + cw) / 2, -(1 + cw), (1 + cw) / 2, 1 + alpha, -2 * cw, 1 - alpha)

    @classmethod
    def peaking(cls, fs: float, f0: float, gain_db: float, q: float) -> _Biquad:
        a = 10.0 ** (gain_db / 40.0)
        w = 2.0 * np.pi * f0 / fs
        cw, sw = np.cos(w), np.sin(w)
        alpha = sw / (2.0 * q)
        return cls(1 + alpha * a, -2 * cw, 1 - alpha * a, 1 + alpha / a, -2 * cw, 1 - alpha / a)

    def reset(self) -> None:
        self._x1 = self._x2 = self._y1 = self._y2 = 0.0

    def process(self, x: np.ndarray) -> np.ndarray:
        # Explicit loop: we need exact state at block boundaries, otherwise
        # an audible discontinuity appears at every splice.
        y = np.empty_like(x)
        x1, x2, y1, y2 = self._x1, self._x2, self._y1, self._y2
        b0, b1, b2, a1, a2 = self.b0, self.b1, self.b2, self.a1, self.a2
        for i in range(x.size):
            xi = x[i]
            yi = b0 * xi + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
            x2, x1 = x1, xi
            y2, y1 = y1, yi
            y[i] = yi
        self._x1, self._x2, self._y1, self._y2 = x1, x2, y1, y2
        return y


class Presence:
    """Applies the chain to mono int16 PCM, in streaming."""

    def __init__(self, config: PresenceConfig, sample_rate: int) -> None:
        self.cfg = config
        self.fs = float(sample_rate)

        self._hp = _Biquad.highpass(self.fs, config.highpass_hz)
        self._eq = _Biquad.peaking(
            self.fs, config.presence_hz, config.presence_gain_db, config.presence_q
        )

        self._thresh = _db(config.comp_threshold_db)
        self._ratio = max(1.0, config.comp_ratio)
        self._makeup = _db(config.comp_makeup_db)
        self._out_gain = _db(config.output_gain_db)
        self._atk = float(np.exp(-1.0 / max(1e-6, self.fs * config.comp_attack_ms / 1000.0)))
        self._rel = float(np.exp(-1.0 / max(1e-6, self.fs * config.comp_release_ms / 1000.0)))
        self._env = 0.0

        delay = max(1, int(self.fs * config.reverb_ms / 1000.0))
        self._delay = np.zeros(delay, dtype=np.float32)
        self._dpos = 0

        self._odd = b""  # half-sample between blocks, if chunk is odd-sized
        log.debug("DSP active at %d Hz: %s", sample_rate, config)

    # -- API -----------------------------------------------------------------
    def process(self, pcm: bytes) -> bytes:
        if not self.cfg.enabled:
            return pcm
        data = self._odd + pcm
        usable = len(data) - (len(data) % 2)
        self._odd = data[usable:]
        if usable == 0:
            return b""
        x = np.frombuffer(data[:usable], dtype="<i2").astype(np.float32) / INT16_MAX
        return self._render(x)

    def flush(self) -> bytes:
        """Reverb tail, so the phrase doesn't end with an abrupt cut."""
        if not self.cfg.enabled or self.cfg.reverb_mix <= 0.0:
            self._odd = b""
            return b""
        tail = self._render(np.zeros(self._delay.size * 2, dtype=np.float32))
        self._odd = b""
        return tail

    def reset(self) -> None:
        """Resets EVERYTHING. Biquads too -- forgetting them would let the
        previous phrase's residue bleed into the next one."""
        self._hp.reset()
        self._eq.reset()
        self._env = 0.0
        self._delay[:] = 0.0
        self._dpos = 0
        self._odd = b""

    # -- internal -------------------------------------------------------------
    def _render(self, x: np.ndarray) -> bytes:
        x = self._hp.process(x)
        x = self._compress(x)
        x = self._eq.process(x)
        if self.cfg.reverb_mix > 0.0:
            x = self._reverb(x)
        x = x * self._out_gain
        np.clip(x, -1.0, 1.0, out=x)
        return (x * INT16_MAX).astype("<i2").tobytes()

    def _compress(self, x: np.ndarray) -> np.ndarray:
        # Envelope detector with separate attack/release; gain applied sample
        # by sample to avoid creating a step inside the block.
        out = np.empty_like(x)
        env, atk, rel = self._env, self._atk, self._rel
        thresh, ratio, makeup = self._thresh, self._ratio, self._makeup
        for i in range(x.size):
            a = abs(float(x[i]))
            coef = atk if a > env else rel
            env = a + coef * (env - a)
            over = env > thresh
            gain = (thresh + (env - thresh) / ratio) / max(env, 1e-9) if over else 1.0
            out[i] = x[i] * gain * makeup
        self._env = env
        return out

    def _reverb(self, x: np.ndarray) -> np.ndarray:
        # Single comb filter. It's not real reverb, and doesn't need to be:
        # what gives the room feeling is a short, low reflection, not a dense
        # tail.
        buf, n = self._delay, self._delay.size
        mix, decay = self.cfg.reverb_mix, self.cfg.reverb_decay
        out = np.empty_like(x)
        pos = self._dpos
        for i in range(x.size):
            echoed = buf[pos]
            dry = float(x[i])
            buf[pos] = dry + echoed * decay
            out[i] = dry * (1.0 - mix) + echoed * mix
            pos = (pos + 1) % n
        self._dpos = pos
        return out


def build_dsp(cfg, sample_rate: int) -> Presence | None:
    preset = getattr(cfg, "dsp_preset", "off")
    pc = PresenceConfig.preset(preset)
    if not pc.enabled:
        return None
    for field in ("reverb_mix", "presence_gain_db", "comp_ratio", "output_gain_db"):
        override = getattr(cfg, f"dsp_{field}", None)
        if override is not None:
            setattr(pc, field, override)
    log.info("DSP: preset '%s' at %d Hz.", preset, sample_rate)
    return Presence(pc, sample_rate)
