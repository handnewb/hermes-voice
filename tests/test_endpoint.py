"""Endpointing adaptativo: nao cortar a pessoa no meio do raciocinio."""

from __future__ import annotations

import pytest

from hermes_voice.endpoint import (
    Completeness,
    EndpointConfig,
    Endpointer,
    classify,
    wait_ms,
)


class TestClassificacao:
    @pytest.mark.parametrize(
        "texto",
        [
            "eu quero",
            "o status do",
            "me passa o",
            "preciso que você",
            "isso é porque",
            "tipo",
            "status",
            "acho que ele",
            "vou até a",
        ],
    )
    def test_incompleto(self, texto):
        assert classify(texto) is Completeness.INCOMPLETE

    @pytest.mark.parametrize(
        "texto",
        [
            "qual o status?",
            "qual o status do servidor",
            "isola a máquina agora",
            "detalha o terceiro incidente",
            "o servidor caiu.",
            "me diz quantos eventos foram processados essa noite",
        ],
    )
    def test_completo(self, texto):
        assert classify(texto) is Completeness.COMPLETE

    def test_vazio_e_incompleto(self):
        assert classify("") is Completeness.INCOMPLETE
        assert classify("   ") is Completeness.INCOMPLETE

    def test_pontuacao_nao_salva_terminacao_pendurada(self):
        """O Whisper inventa pontuacao onde nao houve pausa."""
        assert classify("eu quero.") is Completeness.INCOMPLETE


class TestLimiares:
    def test_completo_nao_espera(self):
        cfg = EndpointConfig()
        assert wait_ms(Completeness.COMPLETE, cfg) == 0

    def test_incompleto_espera_mais_que_incerto(self):
        cfg = EndpointConfig()
        assert wait_ms(Completeness.INCOMPLETE, cfg) > wait_ms(Completeness.UNCERTAIN, cfg)

    def test_total_incompleto_e_o_long_ms(self):
        cfg = EndpointConfig()
        assert cfg.short_ms + wait_ms(Completeness.INCOMPLETE, cfg) == cfg.long_ms


class TestEndpointer:
    def test_texto_estagnado_destrava(self):
        """Pessoa distraida no meio da frase nao pode travar o turno."""
        ep = Endpointer()
        assert ep.decide("me passa o") is Completeness.INCOMPLETE
        assert ep.decide("me passa o") is Completeness.COMPLETE

    def test_teto_de_sondagens(self):
        ep = Endpointer(EndpointConfig(max_probes=2))
        ep.decide("eu quero")
        assert ep.decide("eu quero muito o") is Completeness.COMPLETE
        assert not ep.should_probe()

    def test_fala_crescendo_encerra_quando_completa(self):
        ep = Endpointer(EndpointConfig(max_probes=3))
        assert ep.decide("eu quero") is Completeness.INCOMPLETE
        assert ep.decide("eu quero saber o status do servidor") is Completeness.COMPLETE

    def test_reset_zera(self):
        ep = Endpointer()
        ep.decide("eu quero")
        ep.reset()
        assert ep.probes == 0 and ep.last_text == "" and ep.extra_ms == 0

    def test_should_probe_inicial(self):
        assert Endpointer().should_probe()
