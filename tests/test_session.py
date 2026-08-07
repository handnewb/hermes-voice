"""Maquina de estados, limites de buffer e limpeza da palavra de ativacao."""

from __future__ import annotations

import time

import numpy as np
import pytest

from hermes_voice.session import PREROLL_MS, Session, State, strip_wake_word

FRAME = np.zeros(512, dtype=np.float32)


class TestStripWakeWord:
    @pytest.mark.parametrize(
        "entrada,esperado",
        [
            ("Jarvis, qual o status?", "qual o status?"),
            ("Járvis qual o status", "qual o status"),
            ("Ei Jarvis, isola a maquina.", "isola a maquina."),
            ("jarvis. Detalha o incidente", "Detalha o incidente"),
            ("Gervis, bom dia", "bom dia"),
            ("Jarvez qual a hora", "qual a hora"),
            ("Hey Jarvis abre o painel", "abre o painel"),
        ],
    )
    def test_remove_variantes_do_whisper(self, entrada, esperado):
        assert strip_wake_word(entrada) == esperado

    @pytest.mark.parametrize(
        "frase",
        [
            "Gera o relatorio agora",
            "Java esta desatualizado",
            "Chaves de API expiradas",
            "Cheque o firewall",
            "Junta os dois tickets",
            "Gervasio ligou",
            "Gervásio ligou",
            "Jarvisson chegou",
            "Qual o status do deploy?",
        ],
    )
    def test_nao_corta_palavra_legitima(self, frase):
        """ "Gervásio" virava "io" antes da fronteira de palavra."""
        assert strip_wake_word(frase) == frase

    def test_nunca_devolve_vazio(self):
        assert strip_wake_word("Jarvis") == "Jarvis"
        assert strip_wake_word("jarvis!!!") == "jarvis!!!"


class TestCicloDeEstados:
    def test_comeca_dormindo(self):
        assert Session().state is State.DORMANT

    def test_ciclo_completo(self):
        s = Session(follow_up_seconds=0.05)
        for st in (State.LISTENING, State.THINKING, State.SPEAKING, State.FOLLOW_UP):
            s.to(st)
            assert s.state is st
        time.sleep(0.06)
        assert s.follow_up_expired
        s.to(State.DORMANT)
        assert s.state is State.DORMANT

    def test_follow_up_nao_expira_em_outros_estados(self):
        s = Session(follow_up_seconds=0.0)
        s.to(State.LISTENING)
        assert not s.follow_up_expired

    def test_transicao_para_o_mesmo_estado_nao_reseta_timer(self):
        s = Session()
        s.to(State.FOLLOW_UP)
        time.sleep(0.02)
        antes = s.elapsed
        s.to(State.FOLLOW_UP)
        assert s.elapsed >= antes


class TestBuffers:
    def test_preroll_limitado_por_construcao(self):
        """Garantia de privacidade: deque com maxlen, nao configuracao."""
        s = Session()
        for _ in range(2000):  # ~64 s de audio
            s.keep_preroll(FRAME)
        s.begin_utterance(include_preroll=True)
        ms = s.take()[0].size / 16000 * 1000
        assert ms <= PREROLL_MS + 32

    def test_dormir_descarta_tudo(self):
        s = Session()
        for _ in range(10):
            s.keep_preroll(FRAME)
        s.begin_utterance(True)
        for _ in range(10):
            s.append(FRAME)
        s.to(State.DORMANT)
        assert s.take()[0].size == 0

    def test_sem_preroll_quando_pedido(self):
        s = Session()
        for _ in range(10):
            s.keep_preroll(FRAME)
        s.begin_utterance(include_preroll=False)
        assert s.take()[0].size == 0

    def test_corta_fala_interminavel(self):
        s = Session(max_utterance_seconds=0.5)
        for _ in range(200):
            s.append(FRAME)
        assert s.overlong
        assert s.take()[0].size / 16000 <= 0.55

    def test_take_calcula_pico(self):
        s = Session()
        s.append(np.full(512, 0.42, dtype=np.float32))
        pcm, peak = s.take()
        assert pcm.size == 512
        assert peak == pytest.approx(0.42, abs=1e-6)

    def test_take_esvazia(self):
        s = Session()
        s.append(FRAME)
        s.take()
        assert s.take()[0].size == 0

    def test_banner_cobre_todos_os_estados(self):
        s = Session()
        for st in State:
            s.state = st
            assert s.banner()
