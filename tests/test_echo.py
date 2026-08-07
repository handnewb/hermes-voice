"""Supressao de eco: barge-in real sem dependencia externa."""

from __future__ import annotations

import numpy as np
import pytest

from hermes_voice.echo import EchoConfig, EchoSuppressor, build_echo

FS, FRAME = 16000, 512
DELAY, ROOM_GAIN = 1600, 0.55  # 100 ms, sala atenua


def speechlike(n: int, seed: int = 0, amp: float = 0.5) -> np.ndarray:
    """Envelope silabico ~3 Hz. Tom continuo nao representa fala."""
    rng = np.random.default_rng(seed)
    t = np.arange(n) / FS
    env = 0.35 + 0.65 * np.abs(np.sin(2 * np.pi * 3.1 * t))
    car = sum(np.sin(2 * np.pi * f * t + rng.uniform(0, 6)) for f in (140, 280, 420, 900, 1800))
    x = (env * car / 5).astype(np.float32)
    return (x / max(np.abs(x).max(), 1e-9) * amp).astype(np.float32)


def to_pcm(x: np.ndarray) -> bytes:
    return (np.clip(x, -1, 1) * 32767).astype("<i2").tobytes()


def run(suppressor, output, mic, frames=None):
    """Empurra referencia e le microfone frame a frame, como no loop real."""
    hits, total = 0, 0
    limit = min(output.size, mic.size) - FRAME
    for i in range(0, limit, FRAME):
        suppressor.push_reference(to_pcm(output[i : i + FRAME]))
        total += 1
        if suppressor.is_user_speech(mic[i : i + FRAME]):
            hits += 1
        if frames and total >= frames:
            break
    return hits, total


@pytest.fixture
def output():
    return speechlike(FS * 2, seed=1)


@pytest.fixture
def echo_only(output):
    delayed = np.concatenate([np.zeros(DELAY, dtype=np.float32), output])
    return (delayed[: output.size] * ROOM_GAIN).astype(np.float32)


class TestRejeitaEco:
    def test_eco_puro_nao_dispara(self, output, echo_only):
        """O caso que importa: sem isto o assistente conversa consigo mesmo."""
        hits, total = run(EchoSuppressor(EchoConfig(), FS, FRAME), output, echo_only)
        assert total > 20
        assert hits == 0, f"{hits} falsos positivos em {total} frames"

    @pytest.mark.parametrize("gain", [0.25, 0.55, 0.9, 1.3])
    def test_robusto_ao_ganho_da_sala(self, output, gain):
        delayed = np.concatenate([np.zeros(DELAY, dtype=np.float32), output])
        mic = (delayed[: output.size] * gain).astype(np.float32)
        hits, _ = run(EchoSuppressor(EchoConfig(), FS, FRAME), output, mic)
        assert hits == 0

    @pytest.mark.parametrize("delay_ms", [20, 100, 200, 300])
    def test_robusto_ao_atraso(self, output, delay_ms):
        d = int(FS * delay_ms / 1000)
        delayed = np.concatenate([np.zeros(d, dtype=np.float32), output])
        mic = (delayed[: output.size] * ROOM_GAIN).astype(np.float32)
        hits, _ = run(EchoSuppressor(EchoConfig(), FS, FRAME), output, mic)
        assert hits == 0


class TestAceitaUsuario:
    def test_usuario_alto_sobre_eco_dispara(self, output, echo_only):
        voz = speechlike(echo_only.size, seed=99, amp=0.9)
        hits, _ = run(EchoSuppressor(EchoConfig(), FS, FRAME), output, echo_only + voz)
        assert hits > 0

    def test_sem_referencia_qualquer_fala_conta(self):
        s = EchoSuppressor(EchoConfig(), FS, FRAME)
        fala = speechlike(FS, seed=3)
        assert any(s.is_user_speech(fala[i : i + FRAME]) for i in range(0, FS - FRAME, FRAME))


class TestComportamentoBasico:
    def test_silencio_nunca_dispara(self, output):
        s = EchoSuppressor(EchoConfig(), FS, FRAME)
        s.push_reference(to_pcm(output[:FS]))
        mudo = np.zeros(FRAME, dtype=np.float32)
        assert not any(s.is_user_speech(mudo) for _ in range(20))

    def test_desligado_e_noop(self):
        s = EchoSuppressor(EchoConfig(enabled=False), FS, FRAME)
        alto = speechlike(FS, seed=4, amp=0.99)
        assert not any(s.is_user_speech(alto[i : i + FRAME]) for i in range(0, FS - FRAME, FRAME))

    def test_trigger_frames_exige_persistencia(self):
        s = EchoSuppressor(EchoConfig(trigger_frames=3), FS, FRAME)
        fala = speechlike(FS, seed=5)
        r = [s.is_user_speech(fala[i : i + FRAME]) for i in range(0, FRAME * 4, FRAME)]
        assert r[:2] == [False, False]

    def test_clear_reseta(self, output):
        s = EchoSuppressor(EchoConfig(), FS, FRAME)
        s.push_reference(to_pcm(output[:FS]))
        assert s.has_reference
        s.clear()
        assert not s.has_reference

    def test_pcm_impar_nao_quebra(self):
        s = EchoSuppressor(EchoConfig(), FS, FRAME)
        s.push_reference(b"\x01\x02\x03")
        s.push_reference(b"")


class TestBuild:
    def test_meia_duplex_dispensa_supressor(self):
        class C:
            half_duplex = True

        assert build_echo(C(), FS) is None

    def test_duplex_cria_supressor(self):
        class C:
            half_duplex = False
            echo_margin_db = 7.0
            echo_trigger_frames = 3

        assert build_echo(C(), FS) is not None
