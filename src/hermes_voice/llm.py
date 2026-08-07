"""Cliente de streaming para o Hermes + fatiador de sentencas.

O fatiador e a peca que corta 60-70% da latencia percebida: em vez de esperar a
resposta inteira, a primeira frase vai para o TTS enquanto o modelo ainda gera a
segunda.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterator

import httpx

log = logging.getLogger("hermes.llm")

HARD_STOPS = ".!?:;"
SOFT_STOPS = ",)"

# Abreviacoes pt-BR que terminam em ponto e NAO encerram frase.
ABBREVIATIONS = {
    "sr",
    "sra",
    "srta",
    "dr",
    "dra",
    "prof",
    "profa",
    "eng",
    "av",
    "ex",
    "etc",
    "ref",
    "obs",
    "fig",
    "pag",
    "art",
    "cf",
    "vs",
    "aprox",
    "num",
}

_TRAILING_WORD = re.compile(r"([A-Za-zÀ-ÿ]+)\.$")
_MARKDOWN = re.compile(r"[*_`#>]+|\[(.*?)\]\(.*?\)")
_BULLET = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+", re.MULTILINE)


def clean_for_speech(text: str) -> str:
    """Remove residuo de markdown que o modelo insiste em emitir."""
    text = _BULLET.sub("", text)
    text = _MARKDOWN.sub(r"\1", text)
    return " ".join(text.split())


class SentenceChunker:
    """Acumula deltas de token e devolve trechos falaveis."""

    def __init__(self, min_chars: int = 24, max_chars: int = 200) -> None:
        self.min_chars = min_chars
        self.max_chars = max_chars
        self._buf = ""

    def feed(self, delta: str) -> list[str]:
        self._buf += delta
        out: list[str] = []
        while True:
            cut = self._find_cut()
            if cut is None:
                return out
            piece, self._buf = self._buf[:cut].strip(), self._buf[cut:].lstrip()
            if piece:
                out.append(piece)

    def flush(self) -> list[str]:
        piece, self._buf = self._buf.strip(), ""
        return [piece] if piece else []

    def _find_cut(self) -> int | None:
        buf = self._buf
        if len(buf) < self.min_chars:
            return None

        for i, ch in enumerate(buf):
            if i + 1 < self.min_chars:
                continue
            if ch == "\n":
                return i + 1
            # Lookahead obrigatorio: sem o proximo caractere nao ha como saber se
            # o ponto encerra a frase ou faz parte de "3.5" / "12:30" / "Dr.".
            # Se a pontuacao e o ultimo char do buffer, espera o proximo delta.
            if i + 1 >= len(buf):
                break
            if ch in HARD_STOPS and self._is_boundary(buf, i):
                return i + 1

        # Sem pontuacao e o buffer esta longo: corta num limite razoavel para
        # nao deixar o usuario esperando em silencio.
        if len(buf) >= self.max_chars:
            window = buf[: self.max_chars]
            for sep in (SOFT_STOPS, " "):
                idx = max((window.rfind(c) for c in sep), default=-1)
                if idx >= self.min_chars:
                    return idx + 1
            return self.max_chars
        return None

    @staticmethod
    def _is_boundary(buf: str, i: int) -> bool:
        ch = buf[i]
        prev = buf[i - 1] if i else ""
        nxt = buf[i + 1] if i + 1 < len(buf) else ""

        # Decimais e milhares: 3.5 / 100.000 / 12:30
        if prev.isdigit() and nxt.isdigit():
            return False
        # Precisa de espaco ou fim de buffer depois da pontuacao
        if nxt and not nxt.isspace():
            return False
        if ch == ".":
            match = _TRAILING_WORD.search(buf[: i + 1])
            if match and match.group(1).lower() in ABBREVIATIONS:
                return False
            # Inicial isolada: "J. A. R. V. I. S."
            if len(prev) == 1 and prev.isupper() and (i < 2 or not buf[i - 2].isalpha()):
                return False
        return True


class HermesClient:
    """Fala com um endpoint compativel com /v1/chat/completions em streaming."""

    def __init__(
        self,
        url: str,
        model: str,
        api_key: str = "",
        timeout: float = 60.0,
        system_prompt: str = "",
        history_turns: int = 8,
    ) -> None:
        self.url = url
        self.model = model
        self.timeout = timeout
        self.system_prompt = system_prompt
        self.history_turns = max(1, history_turns)
        self._history: list[dict[str, str]] = []

        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self._client = httpx.Client(headers=headers, timeout=httpx.Timeout(timeout))

    def reset(self) -> None:
        self._history.clear()

    def close(self) -> None:
        self._client.close()

    def _messages(self, user_text: str) -> list[dict[str, str]]:
        msgs: list[dict[str, str]] = []
        if self.system_prompt:
            msgs.append({"role": "system", "content": self.system_prompt})
        msgs.extend(self._history[-self.history_turns * 2 :])
        msgs.append({"role": "user", "content": user_text})
        return msgs

    def stream(self, user_text: str) -> Iterator[str]:
        """Emite deltas de texto. Ao final, grava o turno no historico."""
        payload = {
            "model": self.model,
            "messages": self._messages(user_text),
            "stream": True,
            "temperature": 0.4,
            "max_tokens": 400,  # voz: respostas curtas por construcao
        }
        parts: list[str] = []
        try:
            with self._client.stream("POST", self.url, json=payload) as response:
                if response.status_code >= 400:
                    body = response.read().decode("utf-8", "replace")[:400]
                    raise RuntimeError(f"HTTP {response.status_code}: {body}")
                for line in response.iter_lines():
                    delta = _parse_sse(line)
                    if delta is None:
                        continue
                    if delta == "":
                        continue
                    parts.append(delta)
                    yield delta
        except httpx.HTTPError as exc:
            raise RuntimeError(f"Hermes inacessivel em {self.url}: {exc}") from exc
        finally:
            answer = "".join(parts).strip()
            if answer:
                self._history.append({"role": "user", "content": user_text})
                self._history.append({"role": "assistant", "content": answer})


def _parse_sse(line: str) -> str | None:
    """Extrai o delta de conteudo de uma linha SSE. None = ignorar."""
    if not line:
        return None
    if line.startswith("data:"):
        line = line[5:].strip()
    if not line or line == "[DONE]":
        return None
    try:
        obj = json.loads(line)
    except json.JSONDecodeError:
        return None
    try:
        choice = obj["choices"][0]
    except (KeyError, IndexError, TypeError):
        return None
    delta = choice.get("delta") or {}
    content = delta.get("content")
    if content is None:
        # Alguns servidores emitem 'text' (completions legado)
        content = choice.get("text")
    return content if isinstance(content, str) else None
