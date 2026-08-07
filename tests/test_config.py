"""Configuracao, redacao de segredos e extracao da persona."""

from __future__ import annotations

import pytest

from hermes_voice.config import Config, _env_bool, _env_opt_float, load_dotenv


@pytest.fixture(autouse=True)
def ambiente_limpo(monkeypatch):
    for key in list(__import__("os").environ):
        if key.split("_")[0] in {
            "HERMES",
            "WHISPER",
            "TTS",
            "PIPER",
            "AZURE",
            "KOKORO",
            "DSP",
            "WAKE",
            "VAD",
            "VOICE",
            "ENDPOINT",
            "ECHO",
        }:
            monkeypatch.delenv(key, raising=False)


class TestRedacaoDeSegredos:
    @pytest.mark.parametrize("var,campo", [("HERMES_API_KEY", "hermes_api_key")])
    def test_chave_nunca_aparece(self, monkeypatch, var, campo):
        segredo = "sk_naodeveriaaparecernolog_123456"
        monkeypatch.setenv(var, segredo)
        red = Config.from_env().redacted()
        assert segredo not in str(red)
        assert "definida" in red[campo]

    def test_chave_ausente_marcada(self):
        assert Config.from_env().redacted()["hermes_api_key"] == "<vazia>"

    def test_projeto_tem_um_unico_segredo(self):
        """Nenhuma engine exige chave: TTS e wake word rodam locais."""
        assert Config().SECRET_FIELDS == ("hermes_api_key",)

    def test_todos_os_campos_secretos_existem(self):
        cfg = Config()
        for campo in cfg.SECRET_FIELDS:
            assert hasattr(cfg, campo), campo


class TestParsers:
    @pytest.mark.parametrize(
        "valor,esperado",
        [
            ("1", True),
            ("true", True),
            ("sim", True),
            ("on", True),
            ("0", False),
            ("false", False),
            ("nao", False),
        ],
    )
    def test_bool(self, monkeypatch, valor, esperado):
        monkeypatch.setenv("TESTE_BOOL", valor)
        assert _env_bool("TESTE_BOOL", not esperado) is esperado

    def test_opt_float_distingue_ausente_de_zero(self, monkeypatch):
        assert _env_opt_float("NAO_DEFINIDO_AQUI") is None
        monkeypatch.setenv("TESTE_ZERO", "0")
        assert _env_opt_float("TESTE_ZERO") == 0.0

    def test_opt_float_invalido_vira_none(self, monkeypatch):
        monkeypatch.setenv("TESTE_RUIM", "nao-e-numero")
        assert _env_opt_float("TESTE_RUIM") is None

    def test_valor_invalido_cai_no_default(self, monkeypatch):
        monkeypatch.setenv("SILENCE_MS", "abacaxi")
        assert Config.from_env().silence_ms == 700


class TestDotenv:
    def test_le_e_ignora_comentarios(self, tmp_path, monkeypatch):
        env = tmp_path / ".env"
        env.write_text('# comentario\nHERMES_MODEL="test-model"\n\nVAZIO\n', encoding="utf-8")
        monkeypatch.delenv("HERMES_MODEL", raising=False)
        load_dotenv(env)
        assert __import__("os").environ["HERMES_MODEL"] == "test-model"

    def test_nao_sobrescreve_ambiente(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HERMES_MODEL", "do-ambiente")
        env = tmp_path / ".env"
        env.write_text("HERMES_MODEL=do-arquivo\n", encoding="utf-8")
        load_dotenv(env)
        assert __import__("os").environ["HERMES_MODEL"] == "do-ambiente"

    def test_arquivo_ausente_nao_explode(self, tmp_path):
        load_dotenv(tmp_path / "nao-existe.env")


class TestPersona:
    def test_marcador_corta_documentacao(self, tmp_path, monkeypatch):
        doc = tmp_path / "persona.md"
        doc.write_text(
            "# Cabecalho\nExplica o marcador PROMPT-BEGIN aqui.\n"
            "<!-- PROMPT-BEGIN -->\nVoce e o assistente.\n",
            encoding="utf-8",
        )
        monkeypatch.setenv("PERSONA_FILE", str(doc))
        persona = Config.from_env().persona()
        assert persona == "Voce e o assistente."
        assert "Cabecalho" not in persona

    def test_usa_rsplit(self, tmp_path, monkeypatch):
        """O cabecalho pode citar o marcador ao se explicar -- e citava."""
        doc = tmp_path / "persona.md"
        doc.write_text(
            "Doc menciona <!-- PROMPT-BEGIN --> no texto.\n<!-- PROMPT-BEGIN -->\nPrompt real.\n",
            encoding="utf-8",
        )
        monkeypatch.setenv("PERSONA_FILE", str(doc))
        assert Config.from_env().persona() == "Prompt real."

    def test_fallback_quando_arquivo_falta(self, monkeypatch, tmp_path):
        monkeypatch.setenv("PERSONA_FILE", str(tmp_path / "ausente.md"))
        assert "senhor" in Config.from_env().persona()
