"""Estagio de "presenca": faz a voz soar como som na sala, nao como locucao.

Boa parte do que as pessoas identificam como voz de assistente de ficcao cientifica
nao esta no timbre -- esta no processamento. A fala e tratada como se viesse de
alto-falantes num ambiente, e nenhum TTS entrega isso de fabrica.

Quatro estagios, na ordem em que importam:

  1. high-pass  -- corta abaixo de ~110 Hz. Remove o peso "boca no microfone"
                   que denuncia locucao de proximidade.
  2. compressor -- achata a dinamica. Voz calma e medida tem pouca variacao de
                   volume; e o que da a sensacao de controle.
  3. presence   -- realce suave em 2-4 kHz. Inteligibilidade a distancia.
  4. reverb     -- sala pequena, curto, muito baixo. Da lugar ao som. Exagerar
                   aqui e o erro mais comum e soa como banheiro.

Tudo processa em streaming, bloco por bloco, com estado continuo entre blocos --
sem isso aparece clique nas emendas. Depende apenas de numpy.
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

    # Presets nomeados. 'room' e o default sensato; 'hall' exagera de proposito
    # para voce ouvir o que cada parametro faz antes de calibrar.
    @classmethod
    def preset(cls, name: str) -> PresenceConfig:
        name = (name or "off").lower()
        if name in {"off", "none", ""}:
            return cls(enabled=False)
        if name == "room":
            return cls(enabled=True)
        if name == "close":  # sem sala: so peso e controle
            return cls(enabled=True, reverb_mix=0.0, presence_gain_db=2.0)
        if name == "hall":  # deliberadamente demais
            return cls(
                enabled=True,
                reverb_ms=120.0,
                reverb_mix=0.22,
                reverb_decay=0.5,
                presence_gain_db=4.0,
            )
        if name == "intercom":  # banda estreita, tipo alto-falante de teto
            return cls(
                enabled=True,
                highpass_hz=250.0,
                presence_hz=2200.0,
                presence_gain_db=6.0,
                reverb_mix=0.06,
                comp_threshold_db=-24.0,
                comp_ratio=6.0,
            )
        log.warning("Preset de DSP desconhecido: %r. Usando 'room'.", name)
        return cls(enabled=True)


def _db(x: float) -> float:
    return float(10.0 ** (x / 20.0))


class _Biquad:
    """Biquad direct-form I com estado persistente entre blocos."""

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
        # Loop explicito: precisamos do estado exato nas bordas do bloco, senao
        # aparece descontinuidade audivel a cada emenda.
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
    """Aplica a cadeia em PCM int16 mono, em streaming."""

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

        self._odd = b""  # meio sample entre blocos, se o chunk vier impar
        log.debug("DSP ativo a %d Hz: %s", sample_rate, config)

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
        """Cauda do reverb, para a frase nao terminar em corte seco."""
        if not self.cfg.enabled or self.cfg.reverb_mix <= 0.0:
            self._odd = b""
            return b""
        tail = self._render(np.zeros(self._delay.size * 2, dtype=np.float32))
        self._odd = b""
        return tail

    def reset(self) -> None:
        """Zera TUDO. Os biquads tambem -- esquecer deles deixava resto da frase
        anterior sangrando na proxima."""
        self._hp.reset()
        self._eq.reset()
        self._env = 0.0
        self._delay[:] = 0.0
        self._dpos = 0
        self._odd = b""

    # -- interno -------------------------------------------------------------
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
        # Detector de envelope com attack/release separados; ganho aplicado
        # amostra a amostra para nao criar degrau no meio do bloco.
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
        # Comb filter unico. Nao e reverb de verdade, e nao precisa ser: o que
        # da sensacao de sala e uma reflexao curta e baixa, nao uma cauda densa.
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
    log.info("DSP: preset '%s' a %d Hz.", preset, sample_rate)
    return Presence(pc, sample_rate)
