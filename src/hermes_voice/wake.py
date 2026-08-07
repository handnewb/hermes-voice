"""Deteccao de palavra de ativacao com openWakeWord.

Apache-2.0, sem cadastro, sem chave de API. Os modelos pre-treinados sao baixados
uma vez na primeira execucao.

Alternativas que exigem cadastro detectam melhor, mas a
prioridade aqui e funcionar imediatamente, sem conta e sem depender de terceiro.
O custo dessa escolha e real e esta documentado abaixo.

Custo: o catalogo pre-treinado do openWakeWord e pequeno, e o modelo de
ativacao disponivel e "hey_jarvis" -- ou seja, e preciso dizer "ei jarvis" e nao
apenas "jarvis". A taxa de falso positivo tambem e pior. Para treinar uma palavra
propria (inclusive em pt-BR), ver docs/ROADMAP.md.

Nota sobre o nome do modelo: "hey_jarvis" e o identificador do arquivo que o
openWakeWord distribui. E dependencia funcional, nao marca do projeto.
"""

from __future__ import annotations

import contextlib
import logging
import re
from typing import Protocol

import numpy as np

log = logging.getLogger("hermes.wake")

# Modelos pre-treinados que o openWakeWord distribui. Catalogo pequeno: para
# palavra arbitraria, use WAKE_BACKEND=keyword ou treine a sua (ver ROADMAP).
PRETRAINED = ("hey_jarvis", "alexa", "hey_mycroft", "hey_rhasspy")
DEFAULT_MODEL = "hey_jarvis"


class WakeBackend(Protocol):
    frame_length: int
    sample_rate: int

    def process(self, frame_int16: np.ndarray) -> bool: ...
    def close(self) -> None: ...


class OpenWakeWord:
    frame_length = 1280  # 80 ms @ 16 kHz
    sample_rate = 16000

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        threshold: float = 0.5,
        model_path: str = "",
        auto_download: bool = True,
    ) -> None:
        from openwakeword.model import Model  # type: ignore

        if auto_download and not model_path:
            with contextlib.suppress(Exception):
                import openwakeword.utils  # type: ignore

                openwakeword.utils.download_models(model_names=[model])

        target = model_path or model
        self._model = Model(wakeword_models=[target], inference_framework="onnx")
        self._key = model
        self._threshold = threshold
        log.info(
            "openWakeWord pronto: modelo '%s', limiar %.2f. Diga \"ei %s\".",
            model,
            threshold,
            model.replace("hey_", ""),
        )

    def process(self, frame_int16: np.ndarray) -> bool:
        scores = self._model.predict(frame_int16)
        for name, score in scores.items():
            if self._key in name and score >= self._threshold:
                self._model.reset()
                return True
        return False

    def close(self) -> None:
        pass


class KeywordSpotter:
    """Palavra de ativacao ARBITRARIA, em qualquer idioma, sem treinar modelo.

    Como funciona: quando o VAD detecta fala, transcreve a janela com um modelo
    Whisper pequeno e procura a palavra configurada no texto, com tolerancia a
    erro de transcricao. Aceita qualquer palavra e qualquer idioma que o Whisper
    cubra -- o que resolve o caso "quero que seja 'Sofia'" ou "quero em espanhol"
    sem uma hora de treinamento.

    CUSTO DE PRIVACIDADE, e e real: neste modo a fala e transcrita ANTES de haver
    ativacao. Nao chega a ser transcricao continua -- so roda quando o VAD ve
    fala, e nada e gravado nem sai da maquina -- mas a garantia "em DORMANT nada
    e transcrito" nao vale aqui. Por isso nao e o padrao, e o --doctor avisa.

    O modelo 'tiny' basta: nao precisamos de transcricao boa, so de reconhecer
    uma palavra. Custa ~75 MB e ~80 ms por janela.
    """

    frame_length = 1280
    sample_rate = 16000

    def __init__(
        self,
        words: tuple[str, ...],
        model: str = "tiny",
        device: str = "cpu",
        language: str = "",
        window_s: float = 1.6,
        tolerance: int | None = None,
    ) -> None:
        from faster_whisper import WhisperModel  # type: ignore

        if not words:
            raise ValueError("Nenhuma palavra configurada em WAKE_WORDS.")
        self._words = tuple(w.strip().lower() for w in words if w.strip())
        self._tolerance = tolerance
        self._language = language or None
        self._need = int(self.sample_rate * window_s)
        self._buf = np.zeros(0, dtype=np.float32)

        compute = "int8" if device == "cpu" else "int8_float16"
        self._stt = WhisperModel(model, device=device, compute_type=compute)
        log.warning(
            "Palavra de ativacao por transcricao: %s. Neste modo a fala e "
            "transcrita antes da ativacao -- ver SECURITY.md.",
            ", ".join(self._words),
        )

    def process(self, frame_int16: np.ndarray) -> bool:
        audio = frame_int16.astype(np.float32) / 32768.0
        self._buf = np.concatenate((self._buf, audio))[-self._need * 2 :]
        if self._buf.size < self._need:
            return False

        window, self._buf = self._buf[-self._need :], self._buf[-self._need // 2 :]
        if float(np.abs(window).max()) < 0.01:
            return False

        segments, _ = self._stt.transcribe(
            window,
            language=self._language,
            beam_size=1,
            temperature=0.0,
            vad_filter=False,
            condition_on_previous_text=False,
        )
        texto = " ".join(s.text for s in segments).lower()
        if not texto.strip():
            return False
        for palavra in self._words:
            if matches(palavra, texto, self._tolerance):
                log.debug("Ativacao por '%s' em %r", palavra, texto.strip()[:50])
                self._buf = np.zeros(0, dtype=np.float32)
                return True
        return False

    def close(self) -> None:
        pass


def _levenshtein(a: str, b: str, cap: int) -> int:
    """Distancia de edicao com corte precoce. Retorna cap+1 se exceder."""
    if abs(len(a) - len(b)) > cap:
        return cap + 1
    anterior = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        atual = [i]
        for j, cb in enumerate(b, 1):
            atual.append(
                min(
                    anterior[j] + 1,  # remocao
                    atual[j - 1] + 1,  # insercao
                    anterior[j - 1] + (ca != cb),  # substituicao
                )
            )
        if min(atual) > cap:
            return cap + 1
        anterior = atual
    return anterior[-1]


_ACENTOS = str.maketrans("áàãâäéèêëíìîïóòõôöúùûüçñ", "aaaaaeeeeiiiiooooouuuucn")


def _fold(s: str) -> str:
    return s.lower().translate(_ACENTOS)


def default_tolerance(word: str) -> int:
    """Quantas edicoes aceitar por token.

    Teto de 1 de proposito. Com 2, "computador" passa a aceitar "compilador" --
    e ativacao falsa e pior que ativacao perdida: o assistente responde do nada
    no meio de outra conversa.

    Para recuperar as variantes que o Whisper realmente produz na SUA voz, nao
    suba a tolerancia: adicione apelidos.

        WAKE_WORDS=jarvis,jarvez,gervis

    Lista exata nao introduz colisao nova, ao contrario de afrouxar o limiar.
    """
    return 0 if len(word) <= 4 else 1


def matches(word: str, text: str, tolerance: int | None = None) -> bool:
    """True se algum token do texto for a palavra, dentro da tolerancia.

    Trabalha token a token e nao por substring, para "filosofia" nao ativar
    "sofia". Aceita sufixo de plural.

    Limite inerente a esta abordagem: palavra parecida com palavra comum gera
    falso positivo. "hermes" colide com "herpes" a uma edicao; "sofia" com
    "sofa". Escolha palavra distintiva, de tres silabas ou mais, e verifique
    colisao antes de adotar. Vale para qualquer sistema de wake word.

    Este modo e menos preciso que um modelo treinado. Quando o openWakeWord
    tiver um modelo para a sua palavra, prefira-o.
    """
    alvo = _fold(word)
    cap = default_tolerance(alvo) if tolerance is None else tolerance
    for token in re.findall(r"[^\W\d_]+", _fold(text), re.UNICODE):
        if token == alvo:
            return True
        if token.endswith("s") and token[:-1] == alvo:
            return True
        if token.endswith("es") and token[:-2] == alvo:
            return True
        if cap and _levenshtein(token, alvo, cap) <= cap:
            return True
    return False


class AlwaysOpen:
    """Sem palavra de ativacao: qualquer fala abre a sessao.

    Util em fone de ouvido e sala silenciosa, e o unico modo que funciona sem
    baixar nada. O custo e que conversa de fundo tambem dispara -- e, ao
    contrario dos outros modos, o audio de qualquer fala e transcrito.
    """

    frame_length = 1280
    sample_rate = 16000

    def __init__(self) -> None:
        log.warning(
            "Modo sem palavra de ativacao: qualquer fala abre a sessao, e "
            "qualquer fala sera transcrita. Use fone e sala silenciosa."
        )

    def process(self, _frame: np.ndarray) -> bool:
        # Nunca dispara: neste modo o loop consulta o VAD diretamente. O
        # parametro existe para satisfazer o protocolo WakeBackend.
        return False

    def close(self) -> None:
        pass


def build_wake(cfg) -> WakeBackend | None:
    want = (getattr(cfg, "wake_backend", "auto") or "auto").lower()
    if want in {"none", "off"}:
        return None
    if want == "open":
        return AlwaysOpen()
    if want == "keyword":
        palavras = tuple(
            w for w in (cfg.wake_words or "").replace(";", ",").split(",") if w.strip()
        )
        return KeywordSpotter(
            palavras or ("jarvis",),
            cfg.wake_keyword_model,
            cfg.wake_keyword_device,
            cfg.whisper_language,
            tolerance=cfg.wake_tolerance if cfg.wake_tolerance >= 0 else None,
        )
    try:
        return OpenWakeWord(
            cfg.wake_model,
            cfg.wake_threshold,
            cfg.wake_model_path,
            cfg.wake_auto_download,
        )
    except Exception as exc:
        log.error(
            "openWakeWord indisponivel (%s).\n"
            "  Instale com: pip install 'hermes-voice[wake]'\n"
            "  Ou use: hermes-voice --trigger console",
            exc,
        )
        return None


class FrameAdapter:
    """Reagrupa frames de 512 amostras no tamanho que o backend exige (1280)."""

    def __init__(self, backend: WakeBackend) -> None:
        self._backend = backend
        self._need = backend.frame_length
        self._buf = np.zeros(0, dtype=np.int16)

    def feed(self, frame_int16: np.ndarray) -> bool:
        self._buf = np.concatenate((self._buf, frame_int16))
        hit = False
        while self._buf.size >= self._need:
            chunk, self._buf = self._buf[: self._need], self._buf[self._need :]
            if self._backend.process(chunk):
                hit = True
                self._buf = np.zeros(0, dtype=np.int16)  # evita disparo duplo
                break
        return hit

    def reset(self) -> None:
        self._buf = np.zeros(0, dtype=np.int16)

    def close(self) -> None:
        self._backend.close()
