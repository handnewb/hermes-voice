"""Normalizacao pt-BR. Nenhum TTS local le "R$ 1.500,00" sem isto."""

from __future__ import annotations

import pytest

from hermes_voice.normalize import normalize, numero_extenso


class TestCardinais:
    @pytest.mark.parametrize(
        "n,esperado",
        [
            (0, "zero"),
            (1, "um"),
            (15, "quinze"),
            (21, "vinte e um"),
            (100, "cem"),
            (101, "cento e um"),
            (150, "cento e cinquenta"),
            (999, "novecentos e noventa e nove"),
            (1000, "mil"),
            (1001, "mil e um"),
            (1500, "mil e quinhentos"),
            (2026, "dois mil e vinte e seis"),
            (147200, "cento e quarenta e sete mil e duzentos"),
            (1_000_000, "um milhão"),
            (2_000_000, "dois milhões"),
        ],
    )
    def test_por_extenso(self, n, esperado):
        assert numero_extenso(n) == esperado

    def test_negativo(self):
        assert numero_extenso(-5) == "menos cinco"

    @pytest.mark.parametrize("n", [7, 42, 813, 1234, 99999, 1234567])
    def test_nunca_deixa_digito(self, n):
        assert not any(c.isdigit() for c in numero_extenso(n))


class TestMoeda:
    def test_reais_com_centavos(self):
        assert normalize("R$ 1.500,50") == ("mil e quinhentos reais e cinquenta centavos")

    def test_reais_sem_centavos(self):
        assert normalize("R$ 1.500,00") == "mil e quinhentos reais"

    def test_um_real_singular(self):
        assert normalize("R$ 1,00") == "um real"

    def test_dolar(self):
        assert "dólares" in normalize("US$ 250,00")

    def test_us_nao_e_soletrado(self):
        """O regex de sigla engolia o "US" de "US$" antes da regra de moeda."""
        assert "U-S" not in normalize("US$ 250,00")


class TestDataHora:
    def test_data_completa(self):
        assert normalize("08/06/2026") == "oito de junho de dois mil e vinte e seis"

    def test_dia_primeiro(self):
        assert normalize("01/12") == "primeiro de dezembro"

    def test_mes_invalido_nao_e_lido_como_data(self):
        """Nao deve inventar mes. Os digitos ainda sao expandidos por outra regra."""
        saida = normalize("13/45")
        assert not any(mes in saida for mes in ("janeiro", "junho", "dezembro"))
        assert not any(c.isdigit() for c in saida)

    @pytest.mark.parametrize(
        "entrada,esperado",
        [
            ("14:30", "quatorze e meia"),
            ("08:00", "oito horas"),
            ("14:15", "quatorze e quinze"),
            ("8h", "oito horas"),
            ("14h30", "quatorze e meia"),
        ],
    )
    def test_hora(self, entrada, esperado):
        assert normalize(entrada) == esperado


class TestNumeros:
    def test_percentual_decimal(self):
        assert normalize("99,7%") == "noventa e nove vírgula sete por cento"

    def test_decimal_com_virgula(self):
        assert normalize("2,5 metros") == "dois e meio metros"

    def test_decimal_com_ponto(self):
        """Estilo ingles: "2.5" e decimal, "1.500" e milhar."""
        assert normalize("2.5 GB") == "dois e meio gigabytes"

    def test_milhar_com_ponto(self):
        assert normalize("1.482 vezes") == "mil, quatrocentos e oitenta e dois vezes"

    def test_ordinal_masculino(self):
        assert normalize("3º lugar") == "terceiro lugar"

    def test_ordinal_feminino(self):
        assert normalize("1ª tentativa") == "primeira tentativa"


class TestAbreviacoes:
    @pytest.mark.parametrize(
        "entrada,contem",
        [
            ("Dr. Silva", "doutor"),
            ("Sra. Costa", "senhora"),
            ("Av. Paulista", "avenida"),
            ("45 ms", "milissegundos"),
            ("2 TB", "terabytes"),
        ],
    )
    def test_expande(self, entrada, contem):
        assert contem in normalize(entrada)


class TestSiglas:
    def test_soletra_desconhecida(self):
        assert "L-G-P-D" in normalize("A LGPD não fixa prazo")

    def test_le_conhecida_como_palavra(self):
        assert "L-G-P-D" not in normalize("A norma ISO exige")


class TestPropriedades:
    CASOS: tuple[str, ...] = (
        "O ticket custou R$ 1.500,00 e fecha em 08/06/2026.",
        "Reunião às 14:30, disponibilidade de 99,7%.",
        "O Dr. Silva ligou às 8h. Processamos 147200 eventos.",
        "A norma ISO 27001 exige revisão anual.",
        "3º lugar, 1ª tentativa, 2.5 GB de log.",
    )

    @pytest.mark.parametrize("texto", CASOS)
    def test_idempotente(self, texto):
        """Normalizar duas vezes tem que dar o mesmo resultado."""
        uma = normalize(texto)
        assert normalize(uma) == uma

    @pytest.mark.parametrize("texto", CASOS)
    def test_nao_sobra_digito(self, texto):
        assert not any(c.isdigit() for c in normalize(texto))

    def test_vazio(self):
        assert normalize("") == ""

    def test_desligar_numeros(self):
        assert "147200" in normalize("147200 eventos", expand_numbers=False)
