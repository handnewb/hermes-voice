"""Adaptive endpointing: deciding when the person has finished speaking.

The fixed silence threshold problem: 400 ms cuts the person off mid-thought
during a natural pause; 1000 ms makes the conversation slow and hesitant.
There's no single number that works for both, because pause duration carries
meaning.

Humans don't count silence -- they use syntax and prosody to predict turn end.
This module makes a cheap approximation of that: transcribes at a short
threshold, looks at whether the phrase *looks finished*, and if it doesn't,
goes back to listening instead of responding.

    "I want"                        -> incomplete, wait more
    "I want to know the status"     -> complete, respond
    "the status of"                 -> dangling preposition, wait
    "what's the status?"            -> closed question, respond fast

The cost is one extra STT pass when the speech seems incomplete. With
large-v3-turbo on GPU that's ~150 ms, paid only when the heuristic thinks
it's warranted.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from enum import Enum

log = logging.getLogger("hermes.endpoint")


class Completeness(Enum):
    COMPLETE = "complete"  # respond now
    UNCERTAIN = "uncertain"  # wait for the normal threshold
    INCOMPLETE = "incomplete"  # wait for the long threshold


# Words that almost never end a turn in pt-BR. Ending here means the person
# paused to think, not that they're done.
_PENDENTES = {
    # prepositions and articles
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
    # conjunctions
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
    # dangling auxiliary and linking verbs
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
    # loose relative and interrogative pronouns
    "qual",
    "quais",
    "quem",
    "onde",
    "cujo",
    "cuja",
    "quantos",
    # dangling subject pronouns: "preciso que voce...", "acho que ele..."
    # Asymmetric cost: waiting 1250 ms instead of 700 is mildly annoying;
    # cutting the person off mid-sentence is very annoying. When in doubt, wait.
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
    # hesitation markers
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

# Endings that strongly close a turn.
_FECHAMENTO = re.compile(r"[.!?]\s*$")

# Short direct questions: responding fast sounds attentive, not rushed.
_INTERROGATIVA = re.compile(
    r"\b(qual|quais|quem|quando|onde|como|quanto|quantos|quantas|por\s?que|"
    r"o\s?que|cadê|será)\b",
    re.IGNORECASE,
)

# Common imperative commands: also close a turn.
_IMPERATIVO = re.compile(
    r"^\s*(isola|isole|para|pare|cancela|cancele|confirma|confirme|abre|abra|"
    r"fecha|feche|mostra|mostre|lista|liste|detalha|detalhe|repete|repita|"
    r"continua|continue|explica|explique|manda|mande|envia|envie|roda|rode|"
    r"executa|execute|verifica|verifique|checa|desliga|liga|silencia)\b",
    re.IGNORECASE,
)


@dataclass(slots=True)
class EndpointConfig:
    short_ms: int = 380  # probe threshold: transcribe and evaluate
    normal_ms: int = 700  # default threshold
    long_ms: int = 1250  # when the phrase looks dangling
    min_words_probe: int = 2  # below this, not worth probing
    max_probes: int = 2  # probe cap per turn, avoids looping


def classify(text: str) -> Completeness:
    """Syntactic heuristic. Doesn't understand the phrase; looks at how it ends."""
    clean = text.strip()
    if not clean:
        return Completeness.INCOMPLETE

    words = re.findall(r"[\w'\u00c0-\u00ff]+", clean.lower())
    if not words:
        return Completeness.INCOMPLETE

    # A single word: the person is almost certainly just starting.
    if len(words) < 2:
        return Completeness.INCOMPLETE

    last = words[-1]

    # A dangling ending dominates any other signal. Even with a period:
    # Whisper adds punctuation where there was no pause.
    if last in _PENDENTES:
        return Completeness.INCOMPLETE

    # Real end punctuation closes.
    if _FECHAMENTO.search(clean):
        return Completeness.COMPLETE

    # Question or command with enough body closes.
    if len(words) >= 3 and (_INTERROGATIVA.search(clean) or _IMPERATIVO.match(clean)):
        return Completeness.COMPLETE

    # Reasonably long phrase ending in a content word: likely done.
    if len(words) >= 6:
        return Completeness.COMPLETE

    return Completeness.UNCERTAIN


def wait_ms(completeness: Completeness, cfg: EndpointConfig) -> int:
    return {
        Completeness.COMPLETE: 0,
        Completeness.UNCERTAIN: cfg.normal_ms - cfg.short_ms,
        Completeness.INCOMPLETE: cfg.long_ms - cfg.short_ms,
    }[completeness]


class Endpointer:
    """End-of-turn decision state within a LISTENING phase.

    Usage by the loop:
        ep.reset()
        ... each frame ...
        if gate says there was short_ms silence:
            if ep.should_probe():
                text = stt.transcribe(audio_so_far)
                if ep.decide(text) is Completeness.COMPLETE: end turn
                else: keep listening with extended threshold
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

        # If the text hasn't grown since the last probe, the person really
        # stopped speaking -- close even if the syntax looks dangling.
        # Without this, "pass me the" with a distracted person would lock
        # the turn.
        if self.probes > 1 and text.strip() == self.last_text.strip():
            log.debug("Text stagnated at %r; closing turn.", text[:40])
            result = Completeness.COMPLETE

        # Last probe available: take what we have.
        if self.probes >= self.cfg.max_probes and result is not Completeness.COMPLETE:
            log.debug("Probe cap reached; closing with %r.", text[:40])
            result = Completeness.COMPLETE

        self.last_text = text
        self.last_result = result
        self.extra_ms = wait_ms(result, self.cfg)
        log.debug("Endpoint: %s (+%d ms) for %r", result.value, self.extra_ms, text[:50])
        return result
