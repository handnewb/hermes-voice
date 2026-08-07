"""O fatiador de sentencas e o que corta 60-70% da latencia percebida."""

from __future__ import annotations

import pytest

from hermes_voice.llm import SentenceChunker, _parse_sse, clean_for_speech


def feed_all(text: str, delta: int = 7) -> list[str]:
    ch = SentenceChunker()
    out: list[str] = []
    for i in range(0, len(text), delta):
        out += ch.feed(text[i : i + delta])
    return out + ch.flush()


TEXT = (
    "Bom dia, senhor. O sistema processou cento e quarenta e sete mil eventos, "
    "com 3 incidentes. O Dr. Almeida pediu o relatorio as 12:30. O ticket 4.812 "
    "fechou. Detalho?"
)


@pytest.mark.parametrize("delta", range(1, 24))
def test_invariante_ao_tamanho_do_delta(delta):
    """Propriedade central: o resultado nao pode depender de como o stream fatia.

    Sem isto, o audio muda conforme a velocidade da rede -- que foi exatamente o
    bug que cortava "12:30" ao meio.
    """
    assert " ".join(feed_all(TEXT, delta)) == " ".join(feed_all(TEXT, 1))


@pytest.mark.parametrize("delta", [1, 3, 7, 11, 50])
def test_nenhum_caractere_perdido(delta):
    joined = " ".join(feed_all(TEXT, delta))
    assert "".join(joined.split()) == "".join(TEXT.split())


@pytest.mark.parametrize("trecho", ["12:30", "4.812", "Dr. Almeida"])
def test_nao_parte_numeros_nem_abreviacoes(trecho):
    assert any(trecho in piece for piece in feed_all(TEXT))


def test_emite_antes_do_fim_do_stream():
    """A propriedade que da o ganho de latencia: sai audio antes do ultimo token."""
    ch = SentenceChunker()
    emitido_durante = []
    for i in range(0, len(TEXT), 7):
        emitido_durante += ch.feed(TEXT[i : i + 7])
    restante = ch.flush()
    assert emitido_durante, "nada emitido antes do flush -- pipeline nao funciona"
    assert len(emitido_durante) >= 2
    assert len("".join(emitido_durante)) > len("".join(restante))


def test_corta_quando_nao_ha_pontuacao():
    ch = SentenceChunker(max_chars=60)
    longo = "o sistema esta respondendo normalmente e nao ha incidente aberto senhor"
    pieces = ch.feed(longo) + ch.flush()
    assert len(pieces) > 1
    assert all(len(p) <= 70 for p in pieces)


def test_buffer_vazio():
    ch = SentenceChunker()
    assert ch.feed("") == []
    assert ch.flush() == []


class TestLimpezaParaFala:
    @pytest.mark.parametrize(
        "entrada,esperado",
        [
            ("- **Alerta** critico", "Alerta critico"),
            ("1. primeiro item", "primeiro item"),
            ("veja [aqui](http://x.com)", "veja aqui"),
            ("`codigo` inline", "codigo inline"),
            ("## Titulo", "Titulo"),
            ("texto    com   espacos", "texto com espacos"),
        ],
    )
    def test_remove_markdown(self, entrada, esperado):
        assert clean_for_speech(entrada) == esperado


class TestSSE:
    def test_delta_de_conteudo(self):
        assert _parse_sse('data: {"choices":[{"delta":{"content":"ola"}}]}') == "ola"

    @pytest.mark.parametrize(
        "linha",
        [
            "",
            "data: [DONE]",
            "data: nao-e-json",
            ": comentario",
            'data: {"choices":[]}',
            'data: {"sem":"choices"}',
        ],
    )
    def test_linhas_ignoradas(self, linha):
        assert _parse_sse(linha) is None

    def test_formato_completions_legado(self):
        assert _parse_sse('data: {"choices":[{"text":"oi"}]}') == "oi"
