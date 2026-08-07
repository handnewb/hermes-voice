"""Endpointing adaptativo: decidir quando a pessoa terminou de falar.

O problema do limiar fixo de silencio: 400 ms corta a pessoa no meio de uma
pausa natural de pensamento; 1000 ms deixa a conversa lenta e hesitante. Nao
existe um numero que sirva para os dois casos, porque a duracao da pausa carrega
significado.

Humanos nao contam silencio -- usam sintaxe e prosodia para prever o fim do
turno. Este modulo faz uma aproximacao barata disso: transcreve num limiar curto,
olha se a frase *parece terminada*, e se nao parecer, volta a escutar em vez de
responder.

    "eu quero"                      -> incompleto, espera mais
    "eu quero saber o status"       -> completo, responde
    "o status do"                   -> preposicao pendurada, espera
    "qual o status?"                -> pergunta fechada, responde rapido

O custo e uma passada extra de STT quando a fala parece incompleta. Com
large-v3-turbo em GPU sao ~150 ms, pagos so quando a heuristica acha que vale.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from enum import Enum

log = logging.getLogger("hermes.endpoint")


class Completeness(Enum):
    COMPLETE = "complete"  # responde agora
    UNCERTAIN = "uncertain"  # espera o limiar normal
    INCOMPLETE = "incomplete"  # espera o limiar longo


# Palavras que quase nunca encerram um turno em pt-BR. Terminar aqui significa
# que a pessoa parou para pensar, nao que acabou.
_PENDENTES = {
    # preposicoes e artigos
    "de",
    "da",
    "do",
    "das",
    "dos",
    "em",
    "no",
    "na",
    "nos",
    "nas",
    "a",
    "o",
    "as",
    "os",
    "um",
    "uma",
    "uns",
    "umas",
    "ao",
    "aos",
    "à",
    "às",
    "pelo",
    "pela",
    "para",
    "pra",
    "por",
    "com",
    "sem",
    "sob",
    "sobre",
    "entre",
    "até",
    "desde",
    "após",
    "ante",
    "perante",
    "contra",
    "num",
    "numa",
    "dum",
    "duma",
    # conjuncoes
    "e",
    "ou",
    "mas",
    "porém",
    "contudo",
    "todavia",
    "porque",
    "pois",
    "que",
    "se",
    "quando",
    "enquanto",
    "embora",
    "caso",
    "conforme",
    "como",
    "então",
    "logo",
    "portanto",
    "assim",
    "também",
    "nem",
    "tanto",
    "quanto",
    # verbos auxiliares e de ligacao pendurados
    "é",
    "são",
    "foi",
    "era",
    "está",
    "estão",
    "tem",
    "têm",
    "há",
    "vai",
    "vou",
    "vamos",
    "quero",
    "queria",
    "preciso",
    "posso",
    "pode",
    "deve",
    "devo",
    "seria",
    "estava",
    "ficou",
    "fica",
    "tinha",
    "havia",
    "sendo",
    "tendo",
    # pronomes relativos e interrogativos soltos
    "qual",
    "quais",
    "quem",
    "onde",
    "cujo",
    "cuja",
    "quantos",
    # pronomes-sujeito pendurados: "preciso que voce...", "acho que ele..."
    # Custo assimetrico: esperar 1250 ms em vez de 700 incomoda pouco; cortar
    # a pessoa no meio da frase irrita muito. Na duvida, espera.
    "você",
    "vocês",
    "voce",
    "voces",
    "eu",
    "ele",
    "ela",
    "eles",
    "elas",
    "nós",
    "me",
    "te",
    "lhe",
    "gente",
    # marcadores de hesitacao
    "tipo",
    "né",
    "aí",
    "bom",
    "olha",
    "veja",
    "sabe",
    "hum",
    "uhm",
    "eh",
    "ah",
    "é...",
}

# Terminacoes que fecham turno com forca.
_FECHAMENTO = re.compile(r"[.!?]\s*$")

# Perguntas curtas e diretas: responder rapido soa atento, nao apressado.
_INTERROGATIVA = re.compile(
    r"\b(qual|quais|quem|quando|onde|como|quanto|quantos|quantas|por\s?que|"
    r"o\s?que|cadê|será)\b",
    re.IGNORECASE,
)

# Comandos imperativos comuns: tambem fecham turno.
_IMPERATIVO = re.compile(
    r"^\s*(isola|isole|para|pare|cancela|cancele|confirma|confirme|abre|abra|"
    r"fecha|feche|mostra|mostre|lista|liste|detalha|detalhe|repete|repita|"
    r"continua|continue|explica|explique|manda|mande|envia|envie|roda|rode|"
    r"executa|execute|verifica|verifique|checa|desliga|liga|silencia)\b",
    re.IGNORECASE,
)


@dataclass(slots=True)
class EndpointConfig:
    short_ms: int = 380  # limiar de sondagem: transcreve e avalia
    normal_ms: int = 700  # limiar padrao
    long_ms: int = 1250  # quando a frase parece pendurada
    min_words_probe: int = 2  # abaixo disso nem vale sondar
    max_probes: int = 2  # teto de sondagens por turno, evita loop


def classify(text: str) -> Completeness:
    """Heuristica sintatica. Nao entende a frase; olha como ela termina."""
    limpo = text.strip()
    if not limpo:
        return Completeness.INCOMPLETE

    palavras = re.findall(r"[\w'\u00c0-\u00ff]+", limpo.lower())
    if not palavras:
        return Completeness.INCOMPLETE

    # Uma palavra so: quase sempre a pessoa esta comecando.
    if len(palavras) < 2:
        return Completeness.INCOMPLETE

    ultima = palavras[-1]

    # Terminacao pendurada domina qualquer outro sinal. Mesmo com ponto final:
    # o Whisper adiciona pontuacao onde nao houve pausa.
    if ultima in _PENDENTES:
        return Completeness.INCOMPLETE

    # Pontuacao final de verdade fecha.
    if _FECHAMENTO.search(limpo):
        return Completeness.COMPLETE

    # Pergunta ou comando com corpo suficiente fecha.
    if len(palavras) >= 3 and (_INTERROGATIVA.search(limpo) or _IMPERATIVO.match(limpo)):
        return Completeness.COMPLETE

    # Frase razoavelmente longa terminando em palavra de conteudo: provavel fim.
    if len(palavras) >= 6:
        return Completeness.COMPLETE

    return Completeness.UNCERTAIN


def wait_ms(completeness: Completeness, cfg: EndpointConfig) -> int:
    return {
        Completeness.COMPLETE: 0,
        Completeness.UNCERTAIN: cfg.normal_ms - cfg.short_ms,
        Completeness.INCOMPLETE: cfg.long_ms - cfg.short_ms,
    }[completeness]


class Endpointer:
    """Estado da decisao de fim de turno dentro de um LISTENING.

    Uso pelo loop:
        ep.reset()
        ... a cada frame ...
        if gate diz que houve silencio de short_ms:
            if ep.should_probe():
                texto = stt.transcribe(audio_ate_agora)
                if ep.decide(texto) is Completeness.COMPLETE: encerra
                else: continua escutando com limiar estendido
    """

    def __init__(self, cfg: EndpointConfig | None = None) -> None:
        self.cfg = cfg or EndpointConfig()
        self.reset()

    def reset(self) -> None:
        self.probes = 0
        self.last_text = ""
        self.last_result = Completeness.UNCERTAIN
        self.extra_ms = 0

    def should_probe(self) -> bool:
        return self.probes < self.cfg.max_probes

    def decide(self, text: str) -> Completeness:
        self.probes += 1
        result = classify(text)

        # Se o texto nao cresceu desde a ultima sondagem, a pessoa parou de
        # falar de verdade -- encerra mesmo que a sintaxe pareca pendurada.
        # Sem isto, "me passa o" com a pessoa distraida travaria o turno.
        if self.probes > 1 and text.strip() == self.last_text.strip():
            log.debug("Texto estagnado em %r; encerrando turno.", text[:40])
            result = Completeness.COMPLETE

        # Ultima sondagem disponivel: aceita o que tem.
        if self.probes >= self.cfg.max_probes and result is not Completeness.COMPLETE:
            log.debug("Teto de sondagens; encerrando com %r.", text[:40])
            result = Completeness.COMPLETE

        self.last_text = text
        self.last_result = result
        self.extra_ms = wait_ms(result, self.cfg)
        log.debug("Endpoint: %s (+%d ms) para %r", result.value, self.extra_ms, text[:50])
        return result
