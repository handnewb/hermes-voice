"""pt-BR text normalization before synthesis.

No local TTS reads "R$ 1,500.00" or "08/06/2026" correctly. Piper reads digit
by digit; Kokoro stumbles. The perceived quality gain here is greater than
switching engines, and costs a single regex pass.

The persona already instructs the model to write numbers in full. This is the
safety net for when it slips -- and it does slip.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Number words (Brazilian Portuguese — keep as data, not translatable strings)
# ---------------------------------------------------------------------------
_UNIDADES = (
    "zero",
    "um",
    "dois",
    "três",
    "quatro",
    "cinco",
    "seis",
    "sete",
    "oito",
    "nove",
    "dez",
    "onze",
    "doze",
    "treze",
    "quatorze",
    "quinze",
    "dezesseis",
    "dezessete",
    "dezoito",
    "dezenove",
)
_DEZENAS = (
    "",
    "",
    "vinte",
    "trinta",
    "quarenta",
    "cinquenta",
    "sessenta",
    "setenta",
    "oitenta",
    "noventa",
)
_CENTENAS = (
    "",
    "cento",
    "duzentos",
    "trezentos",
    "quatrocentos",
    "quinhentos",
    "seiscentos",
    "setecentos",
    "oitocentos",
    "novecentos",
)

_MESES = (
    "janeiro",
    "fevereiro",
    "março",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
)


def _abaixo_de_mil(n: int) -> str:
    if n < 20:
        return _UNIDADES[n]
    if n < 100:
        d, u = divmod(n, 10)
        return _DEZENAS[d] + (f" e {_UNIDADES[u]}" if u else "")
    if n == 100:
        return "cem"
    c, resto = divmod(n, 100)
    saida = _CENTENAS[c]
    return saida + (f" e {_abaixo_de_mil(resto)}" if resto else "")


def numero_extenso(n: int) -> str:
    """Cardinal number in pt-BR. Supports up to billions, which covers any real use."""
    if n < 0:
        return f"menos {numero_extenso(-n)}"
    if n < 1000:
        return _abaixo_de_mil(n)

    for divisor, singular, plural in (
        (1_000_000_000, "bilhão", "bilhões"),
        (1_000_000, "milhão", "milhões"),
        (1000, "mil", "mil"),
    ):
        if n >= divisor:
            quant, resto = divmod(n, divisor)
            if divisor == 1000:
                cabeca = "mil" if quant == 1 else f"{_abaixo_de_mil(quant)} mil"
            else:
                nome = singular if quant == 1 else plural
                cabeca = f"{numero_extenso(quant)} {nome}"
            if not resto:
                return cabeca
            # "e" before small or round remainders; comma otherwise.
            ligacao = " e " if resto < 100 or resto % 100 == 0 else ", "
            return cabeca + ligacao + numero_extenso(resto)
    return str(n)


def _ordinal(n: int, feminino: bool = False) -> str:
    tabela = {
        1: "primeir",
        2: "segund",
        3: "terceir",
        4: "quart",
        5: "quint",
        6: "sext",
        7: "sétim",
        8: "oitav",
        9: "non",
        10: "décim",
    }
    if n in tabela:
        return tabela[n] + ("a" if feminino else "o")
    return f"{numero_extenso(n)}º"


# ---------------------------------------------------------------------------
# Abbreviations (Brazilian Portuguese — keep as data)
# ---------------------------------------------------------------------------
_ABREV = {
    r"\bDr\.": "doutor",
    r"\bDra\.": "doutora",
    r"\bSr\.": "senhor",
    r"\bSra\.": "senhora",
    r"\bSrta\.": "senhorita",
    r"\bProf\.": "professor",
    r"\bProfa\.": "professora",
    r"\bEng\.": "engenheiro",
    r"\bAv\.": "avenida",
    r"\bR\.": "rua",
    r"\betc\.": "etcétera",
    r"\bex\.": "exemplo",
    r"\bpág\.": "página",
    r"\bnº\b": "número",
    r"\bn°\b": "número",
    r"\bart\.": "artigo",
    r"\bobs\.": "observação",
    r"\bapx\.": "aproximadamente",
    r"\bmin\b": "minutos",
    r"\bseg\b": "segundos",
    r"\bkm/h\b": "quilômetros por hora",
    r"\bkm\b": "quilômetros",
    r"\bkg\b": "quilos",
    r"\bGB\b": "gigabytes",
    r"\bTB\b": "terabytes",
    r"\bMB\b": "megabytes",
    r"\bKB\b": "kilobytes",
    r"\bms\b": "milissegundos",
}

# Acronyms read as words, not letter by letter. Without this the TTS spells them.
_SIGLAS_PALAVRA = {
    "ISO",
    "IBGE",
    "USP",
    "OTAN",
    "UNESCO",
    "COVID",
    "PIX",
    "CEP",
    "CNPJ",
    "CPF",
    "SUS",
    "IPVA",
    "FGTS",
}


# ---------------------------------------------------------------------------
# Rules, in order. Order matters: currency before decimal, decimal before
# thousands separator, otherwise "R$ 1,500.00" is destroyed in pieces.
# ---------------------------------------------------------------------------
def _moeda(m: re.Match) -> str:
    inteiro = int(m.group(1).replace(".", "").replace(" ", ""))
    centavos = int((m.group(2) or "0").ljust(2, "0")[:2])
    reais = "real" if inteiro == 1 else "reais"
    saida = f"{numero_extenso(inteiro)} {reais}"
    if centavos:
        moeda_c = "centavo" if centavos == 1 else "centavos"
        saida += f" e {numero_extenso(centavos)} {moeda_c}"
    return saida


def _hora(m: re.Match) -> str:
    h, mi = int(m.group(1)), int(m.group(2))
    if mi == 0:
        return f"{numero_extenso(h)} horas" if h != 1 else "uma hora"
    if mi == 30:
        return f"{numero_extenso(h)} e meia"
    return f"{numero_extenso(h)} e {numero_extenso(mi)}"


def _data(m: re.Match) -> str:
    d, mes = int(m.group(1)), int(m.group(2))
    if not 1 <= mes <= 12:
        return m.group(0)
    dia = "primeiro" if d == 1 else numero_extenso(d)
    saida = f"{dia} de {_MESES[mes - 1]}"
    if m.group(3):
        ano = int(m.group(3))
        ano = ano + 2000 if ano < 100 else ano
        saida += f" de {numero_extenso(ano)}"
    return saida


def _decimal(m: re.Match) -> str:
    inteiro, frac = m.group(1), m.group(2)
    n = numero_extenso(int(inteiro.replace(".", "")))
    if frac == "5" and inteiro != "0":
        return f"{n} e meio"
    digitos = " ".join(_UNIDADES[int(c)] for c in frac)
    return f"{n} vírgula {digitos}"


def _milhar(m: re.Match) -> str:
    return numero_extenso(int(m.group(0).replace(".", "")))


def _percentual(m: re.Match) -> str:
    corpo = m.group(1)
    if "," in corpo:
        inteiro, frac = corpo.split(",", 1)
        texto = _decimal(re.match(r"([\d.]+),(\d+)", f"{inteiro},{frac}"))
    else:
        texto = numero_extenso(int(corpo.replace(".", "")))
    return f"{texto} por cento"


def _ordinal_sub(m: re.Match) -> str:
    return _ordinal(int(m.group(1)), feminino=m.group(2) == "ª")


def _inteiro(m: re.Match) -> str:
    return numero_extenso(int(m.group(0)))


def _sigla(m: re.Match) -> str:
    s = m.group(0)
    if s in _SIGLAS_PALAVRA:
        return s.capitalize()
    return "-".join(s)  # TTS spells hyphen-separated content


_REGRAS: list[tuple[re.Pattern, object]] = [
    # currency
    (re.compile(r"R\$\s?([\d.]+)(?:,(\d{1,2}))?"), _moeda),
    (
        re.compile(r"US\$\s?([\d.]+)(?:,(\d{1,2}))?"),
        lambda m: _moeda(m).replace("reais", "dólares").replace("real", "dólar"),
    ),
    # percentage
    (re.compile(r"([\d.]+(?:,\d+)?)\s?%"), _percentual),
    # date
    (re.compile(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b"), _data),
    # time
    (re.compile(r"\b(\d{1,2}):(\d{2})(?::\d{2})?\b"), _hora),
    (re.compile(r"\b(\d{1,2})h(\d{2})\b"), _hora),
    (re.compile(r"\b(\d{1,2})h\b"), lambda m: f"{numero_extenso(int(m.group(1)))} horas"),
    # ordinal
    (re.compile(r"\b(\d+)(º|ª)"), _ordinal_sub),
    # decimal and thousands. Comma first; period with 1-2 digits is also decimal
    # ("2.5"), while groups of 3 are thousands separator ("1,500").
    (re.compile(r"\b([\d.]+),(\d+)\b"), _decimal),
    (re.compile(r"\b(\d+)\.(\d{1,2})\b"), _decimal),
    (re.compile(r"\b\d{1,3}(?:\.\d{3})+\b"), _milhar),
    # standalone integer, last
    (re.compile(r"\b\d+\b"), _inteiro),
]


def normalize(text: str, expand_numbers: bool = True) -> str:
    """Prepare text for synthesis. Idempotent: normalizing twice doesn't change."""
    if not text:
        return text

    for padrao, troca in _ABREV.items():
        text = re.sub(padrao, troca, text)

    # ORDER MATTERS. Numeric rules run first because the acronym regex would
    # swallow the "US" in "US$" before the currency rule sees the value.
    if expand_numbers:
        for padrao, funcao in _REGRAS:
            text = padrao.sub(funcao, text)  # type: ignore[arg-type]

    # 2-6 uppercase acronyms: spelled out, or read as word when known.
    text = re.sub(r"\b[A-Z]{2,6}\b(?![$\d])", _sigla, text)

    # loose symbols
    text = text.replace("&", " e ").replace("@", " arroba ")
    text = re.sub(r"\s*/\s*", " ou ", text)
    text = re.sub(r"(?<=\w)-(?=\w{2,})", " ", text)  # hyphen between words

    return " ".join(text.split())
