"""Wake word detection with openWakeWord.

Apache-2.0, no registration, no API key. Pre-trained models are downloaded
once on first run.

Alternatives that require registration detect better, but the priority here
is to work immediately, without accounts and without third-party dependency.
The cost of that choice is real and documented below.

Cost: openWakeWord's pre-trained catalog is small, and the available activation
model is "hey_jarvis" -- meaning you need to say "hey jarvis" and not just
"jarvis". The false positive rate is also worse. To train a custom word
(including in pt-BR), see docs/ROADMAP.md.

Note on model name: "hey_jarvis" is the file identifier that openWakeWord
distributes. It's a functional dependency, not a project brand.
"""

from __future__ import annotations

import contextlib
import logging
import re
from typing import Protocol

import numpy as np

log = logging.getLogger("hermes.wake")

# Pre-trained models distributed by openWakeWord. Small catalog: for arbitrary
# words, use WAKE_BACKEND=keyword or train your own (see ROADMAP).
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
            "openWakeWord ready: model '%s', threshold %.2f. Say \"hey %s\".",
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
    """ARBITRARY wake word, in any language, without training a model.

    How it works: when the VAD detects speech, it transcribes the window with a
    small Whisper model and searches for the configured word in the text, with
    transcription error tolerance. Accepts any word and any language that Whisper
    covers -- which solves the case of "I want it to be 'Sofia'" or "I want it
    in Spanish" without an hour of training.

    PRIVACY COST, and it's real: in this mode speech is transcribed BEFORE
    activation. It's not quite continuous transcription -- it only runs when the
    VAD detects speech, and nothing is recorded or leaves the machine -- but the
    guarantee "in DORMANT nothing is transcribed" does not hold here. That's why
    it's not the default, and --doctor warns about it.

    The 'tiny' model is enough: we don't need good transcription, just word
    recognition. Costs ~75 MB and ~80 ms per window.
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
            raise ValueError("No word configured in WAKE_WORDS.")
        self._words = tuple(w.strip().lower() for w in words if w.strip())
        self._tolerance = tolerance
        self._language = language or None
        self._need = int(self.sample_rate * window_s)
        self._buf = np.zeros(0, dtype=np.float32)

        compute = "int8" if device == "cpu" else "int8_float16"
        self._stt = WhisperModel(model, device=device, compute_type=compute)
        log.warning(
            "Transcription-based wake word: %s. In this mode speech is "
            "transcribed before activation -- see SECURITY.md.",
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
        text = " ".join(s.text for s in segments).lower()
        if not text.strip():
            return False
        for word in self._words:
            if matches(word, text, self._tolerance):
                log.debug("Activation by '%s' in %r", word, text.strip()[:50])
                self._buf = np.zeros(0, dtype=np.float32)
                return True
        return False

    def close(self) -> None:
        pass


def _levenshtein(a: str, b: str, cap: int) -> int:
    """Edit distance with early cutoff. Returns cap+1 if exceeded."""
    if abs(len(a) - len(b)) > cap:
        return cap + 1
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            current.append(
                min(
                    previous[j] + 1,  # deletion
                    current[j - 1] + 1,  # insertion
                    previous[j - 1] + (ca != cb),  # substitution
                )
            )
        if min(current) > cap:
            return cap + 1
        previous = current
    return previous[-1]


_ACCENTS = str.maketrans("áàãâäéèêëíìîïóòõôöúùûüçñ", "aaaaaeeeeiiiiooooouuuucn")


def _fold(s: str) -> str:
    return s.lower().translate(_ACCENTS)


def default_tolerance(word: str) -> int:
    """How many edits to accept per token.

    Capped at 1 on purpose. With 2, "computer" starts accepting "compiler" --
    and false activation is worse than missed activation: the assistant responds
    out of nowhere in the middle of another conversation.

    To recover the variants that Whisper actually produces with YOUR voice,
    don't increase the tolerance: add aliases.

        WAKE_WORDS=jarvis,jarvez,gervis

    An exact list introduces no new collisions, unlike loosening the threshold.
    """
    return 0 if len(word) <= 4 else 1


def matches(word: str, text: str, tolerance: int | None = None) -> bool:
    """True if any text token matches the word, within tolerance.

    Works token by token and not by substring, so "philosophy" doesn't activate
    "sophy". Accepts plural suffixes.

    Inherent limitation of this approach: a word similar to a common word
    generates false positives. "hermes" collides with "herpes" at one edit;
    "sofia" with "sofa". Choose a distinctive word, three syllables or more,
    and check collisions before adopting. Applies to any wake word system.

    This mode is less accurate than a trained model. When openWakeWord has
    a model for your word, prefer it.
    """
    target = _fold(word)
    cap = default_tolerance(target) if tolerance is None else tolerance
    for token in re.findall(r"[^\W\d_]+", _fold(text), re.UNICODE):
        if token == target:
            return True
        if token.endswith("s") and token[:-1] == target:
            return True
        if token.endswith("es") and token[:-2] == target:
            return True
        if cap and _levenshtein(token, target, cap) <= cap:
            return True
    return False


class AlwaysOpen:
    """No wake word: any speech opens the session.

    Useful with headphones and a quiet room, and is the only mode that works
    without downloading anything. The cost is that background conversation also
    triggers -- and, unlike other modes, any speech audio is transcribed.
    """

    frame_length = 1280
    sample_rate = 16000

    def __init__(self) -> None:
        log.warning(
            "No-wake-word mode: any speech opens the session, and "
            "any speech will be transcribed. Use headphones and a quiet room."
        )

    def process(self, _frame: np.ndarray) -> bool:
        # Never fires: in this mode the loop queries the VAD directly. The
        # parameter exists to satisfy the WakeBackend protocol.
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
        words = tuple(
            w for w in (cfg.wake_words or "").replace(";", ",").split(",") if w.strip()
        )
        return KeywordSpotter(
            words or ("jarvis",),
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
            "openWakeWord unavailable (%s).\n"
            "  Install with: pip install 'hermes-voice[wake]'\n"
            "  Or use: hermes-voice --trigger console",
            exc,
        )
        return None


class FrameAdapter:
    """Regroups 512-sample frames into the size the backend requires (1280)."""

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
                self._buf = np.zeros(0, dtype=np.int16)  # avoid double-fire
                break
        return hit

    def reset(self) -> None:
        self._buf = np.zeros(0, dtype=np.int16)

    def close(self) -> None:
        self._backend.close()
