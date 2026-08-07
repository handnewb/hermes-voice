"""Piper: local TTS, fast, MIT license.

Two paths because the piper-phonemize wheel frequently fails on Windows:
the Python package when available, the binary via subprocess when not.
"""

from __future__ import annotations

import contextlib
import json
import logging
import shutil
import subprocess
from collections.abc import Iterator
from pathlib import Path

import numpy as np

log = logging.getLogger("hermes.tts.piper")


class PiperPython:
    """Backend via the piper-tts package. Lower latency, more fragile wheel."""

    def __init__(self, model_path: str) -> None:
        from piper.voice import PiperVoice  # type: ignore

        path = Path(model_path)
        if not path.exists():
            raise FileNotFoundError(f"Piper model missing: {path}")
        config = path.with_suffix(path.suffix + ".json")
        self._voice = PiperVoice.load(
            str(path), config_path=str(config) if config.exists() else None
        )
        self.sample_rate = int(self._voice.config.sample_rate)
        self.name = "piper-python"

    def synth(self, text: str) -> Iterator[bytes]:
        voice = self._voice
        if hasattr(voice, "synthesize_stream_raw"):  # piper-tts <= 1.2.x
            yield from voice.synthesize_stream_raw(text)
            return
        for chunk in voice.synthesize(text):  # piper-tts >= 1.3.x
            data = getattr(chunk, "audio_int16_bytes", None)
            if data is None:
                data = np.asarray(chunk.audio_int16_array, dtype=np.int16).tobytes()
            yield data

    def close(self) -> None:
        pass


class PiperBinary:
    """Backend via piper.exe. Recommended on Windows.

    One process per segment: ~150 ms of startup. The cost falls on the first
    phrase of each response, not on each word, because the SentenceChunker
    delivers segments and not tokens.
    """

    def __init__(self, binary: str, model_path: str) -> None:
        exe = shutil.which(binary) or binary
        if not Path(exe).exists():
            raise FileNotFoundError(f"Piper binary missing: {exe}")
        model = Path(model_path)
        if not model.exists():
            raise FileNotFoundError(f"Piper model missing: {model}")
        self._exe, self._model = str(exe), str(model)
        self.name = "piper-binary"

        config = model.with_suffix(model.suffix + ".json")
        rate = 22050
        if config.exists():
            try:
                rate = int(json.loads(config.read_text(encoding="utf-8"))["audio"]["sample_rate"])
            except Exception:
                log.warning("Could not read sample_rate from %s; assuming 22050.", config.name)
        self.sample_rate = rate

    def synth(self, text: str) -> Iterator[bytes]:
        proc = subprocess.Popen(
            [self._exe, "-m", self._model, "--output_raw", "-q"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        assert proc.stdin and proc.stdout
        try:
            proc.stdin.write(text.replace("\n", " ").encode("utf-8") + b"\n")
            proc.stdin.close()
            while True:
                data = proc.stdout.read(4096)
                if not data:
                    break
                yield data
        finally:
            with contextlib.suppress(Exception):
                proc.kill()

    def close(self) -> None:
        pass
