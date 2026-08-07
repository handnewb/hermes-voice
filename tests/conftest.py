"""Fixtures compartilhadas.

Nenhum teste desta suite exige placa de som, GPU, rede ou chave de API. Isso e
requisito, nao coincidencia: o CI roda em runner sem audio, e um projeto de voz
que so pode ser testado com hardware acaba sem testes nenhum.
"""

from __future__ import annotations

import numpy as np
import pytest


@pytest.fixture
def tone():
    """Gerador de tom puro em PCM int16 mono."""

    def _make(freq: float, seconds: float = 1.0, fs: int = 24000, amp: float = 0.3):
        t = np.arange(int(fs * seconds)) / fs
        return (amp * np.sin(2 * np.pi * freq * t) * 32767).astype("<i2").tobytes()

    return _make


@pytest.fixture
def spectral_peak():
    """Energia em torno de uma frequencia, para checar filtros."""

    def _peak(pcm: bytes, freq: float, fs: int = 24000) -> float:
        x = np.frombuffer(pcm, dtype="<i2").astype(np.float64) / 32767
        if x.size == 0:
            return 0.0
        k = int(freq * x.size / fs)
        sp = np.abs(np.fft.rfft(x))
        return float(sp[max(0, k - 2) : k + 3].max())

    return _peak
