"""Estagio de presenca. Validado numericamente, sem placa de som."""

from __future__ import annotations

import numpy as np
import pytest

from hermes_voice.tts.dsp import Presence, PresenceConfig, build_dsp

FS = 24000


def chain(preset: str = "room", fs: int = FS) -> Presence:
    return Presence(PresenceConfig.preset(preset), fs)


class TestPresets:
    @pytest.mark.parametrize("name", ["room", "close", "hall", "intercom"])
    def test_presets_ligados(self, name):
        assert PresenceConfig.preset(name).enabled

    @pytest.mark.parametrize("name", ["off", "none", ""])
    def test_presets_desligados(self, name):
        assert not PresenceConfig.preset(name).enabled

    def test_desconhecido_cai_em_room(self):
        assert PresenceConfig.preset("banheiro").enabled

    def test_close_sem_reverb(self):
        assert PresenceConfig.preset("close").reverb_mix == 0.0

    def test_intercom_corta_mais_grave(self):
        assert (
            PresenceConfig.preset("intercom").highpass_hz
            > PresenceConfig.preset("room").highpass_hz
        )


class TestRespostaEmFrequencia:
    def test_highpass_corta_graves(self, tone, spectral_peak):
        pcm = tone(80, fs=FS)
        out = chain().process(pcm)
        assert spectral_peak(out, 80) < spectral_peak(pcm, 80) * 0.5

    def test_preserva_faixa_de_presenca(self, tone, spectral_peak):
        pcm = tone(3000, fs=FS)
        out = chain().process(pcm)
        assert spectral_peak(out, 3000) > spectral_peak(pcm, 3000) * 0.85

    def test_desligado_e_passthrough_exato(self, tone):
        pcm = tone(440, fs=FS)
        assert chain("off").process(pcm) == pcm


class TestStreaming:
    @pytest.mark.parametrize("size", [2, 256, 512, 2048, 4096])
    def test_estado_persiste_entre_blocos(self, tone, size):
        """Sem estado continuo aparece clique audivel em cada emenda."""
        pcm = tone(440, seconds=0.5, fs=FS)
        a = chain()
        ref = a.process(pcm) + a.flush()
        b = chain()
        got = b"".join(b.process(pcm[i : i + size]) for i in range(0, len(pcm), size))
        got += b.flush()
        x = np.frombuffer(ref, dtype="<i2").astype(float)
        y = np.frombuffer(got, dtype="<i2").astype(float)
        n = min(x.size, y.size)
        assert np.abs(x[:n] - y[:n]).max() <= 1

    @pytest.mark.parametrize("size", [1, 3, 333, 1001])
    def test_chunk_impar_nunca_gera_byte_solto(self, tone, size):
        pcm = tone(440, seconds=0.2, fs=FS)
        d = chain()
        out = b"".join(d.process(pcm[i : i + size]) for i in range(0, len(pcm), size))
        out += d.flush()
        assert len(out) % 2 == 0

    def test_flush_adiciona_cauda_de_reverb(self, tone):
        d = chain("room")
        d.process(tone(440, seconds=0.2, fs=FS))
        assert len(d.flush()) > 0

    def test_flush_sem_reverb_e_vazio(self, tone):
        d = chain("close")
        d.process(tone(440, seconds=0.2, fs=FS))
        assert d.flush() == b""

    def test_reset_zera_estado(self, tone):
        pcm = tone(440, seconds=0.2, fs=FS)
        d = chain()
        primeiro = d.process(pcm)
        d.reset()
        assert d.process(pcm) == primeiro

    def test_entrada_vazia(self):
        assert chain().process(b"") == b""


class TestCompressor:
    def test_reduz_dinamica(self, tone):
        baixo = np.frombuffer(tone(400, 0.5, FS, amp=0.05), dtype="<i2")
        alto = np.frombuffer(tone(400, 0.5, FS, amp=0.9), dtype="<i2")
        pcm = np.concatenate([baixo, alto]).astype("<i2").tobytes()
        out = chain().process(pcm)

        def razao(b):
            x = np.frombuffer(b, dtype="<i2").astype(float) / 32767
            meio = x.size // 2
            r1 = np.sqrt(np.mean(x[2000 : meio - 2000] ** 2))
            r2 = np.sqrt(np.mean(x[meio + 2000 : -2000] ** 2))
            return r2 / max(r1, 1e-9)

        assert razao(out) < razao(pcm)


class TestNaoSatura:
    def test_saida_dentro_da_faixa(self, tone):
        pcm = tone(300, seconds=0.3, fs=FS, amp=0.99)
        out = chain("hall").process(pcm)
        x = np.frombuffer(out, dtype="<i2")
        assert x.max() <= 32767 and x.min() >= -32768


class TestBuild:
    def test_preset_off_devolve_none(self):
        class C:
            dsp_preset = "off"

        assert build_dsp(C(), FS) is None

    def test_override_aplicado(self):
        class C:
            dsp_preset = "room"
            dsp_reverb_mix = 0.02
            dsp_presence_gain_db = None
            dsp_comp_ratio = None
            dsp_output_gain_db = None

        d = build_dsp(C(), FS)
        assert d is not None and d.cfg.reverb_mix == 0.02
