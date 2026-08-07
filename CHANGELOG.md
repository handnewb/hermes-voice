# Changelog

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
[SemVer](https://semver.org/spec/v2.0.0.html) versioning.

## [1.0.1] — 2026-08-07

### Fixed

- **`auto` backend on Windows:** prefers `piper-binary` before `kokoro`
  because espeak-ng often lacks language data, and `piper-python`
  doesn't compile on Windows. Before, `auto` tried Kokoro → piper-python →
  piper-binary, and the first two failed silently.
- **Lint:** misplaced `os` and `pathlib.Path` imports in `tts/__init__.py`.

### Verified

- **Jarvis** (Windows 11, RTX 4060, Python 3.13): 229 tests ✅, lint ✅,
  doctor 8/8 ✅, GPU CUDA ✅, 11 microphones ✅, Piper binary TTS ✅, DSP
  room ✅, endpoint HTTP 200 ✅, full LLM+TTS+DSP pipeline at 1573ms.
- **Mestre** (Linux 6.8, Python 3.11): 229 tests ✅, lint ✅, format ✅.

### Known

- Kokoro + espeak-ng on Windows: `TTS_BACKEND=piper-binary`.
- Wake word and open microphone not tested via remote SSH.

---

## [1.0.0] — 2026-08-06

First public release.

### Added

- **Continuous conversation** with open microphone. The wake word opens a
  session; inside it you speak without repeating it. The session closes on its own
  after `FOLLOW_UP_SECONDS` without speech. State machine in `session.py`.
- **Three trigger modes**: `wake` (open microphone), `console` (ENTER, no
  keyboard hook), and `ptt` (hold a key).
- **Wake word** via Porcupine, where `jarvis` is a native keyword — zero
  training. Fallback to openWakeWord.
- **End-of-speech** via Silero VAD on onnxruntime, no torch. Deliberate
  hysteresis: enters speech fast, exits slowly, to avoid cutting natural pauses.
  Energy fallback when the model is unavailable.
- **STT** with faster-whisper, configurable domain vocabulary, and automatic
  fallback to CPU when CUDA fails.
- **Four TTS backends**: ElevenLabs, Azure Speech, Piper (Python), and Piper
  (binary), with automatic selection by quality order.
- **Presence DSP stage**: high-pass, compressor, presence lift, and short room
  reverb. Five presets. Makes the voice sound like sound in a room rather than
  voice-over, which is half the experience no TTS delivers.
- **Sentence chunker** that sends the first sentence to TTS while the model is
  still generating the second. Cuts 60–70% of perceived latency.
- **`--doctor`**: diagnoses runtime, audio, STT, wake word, VAD, TTS, endpoint,
  and privacy, with suggested fix for each failure.
- **Annotated voice evaluation script**, with elimination criteria, and a
  1,031-word monologue for long-form stability testing.
- Test suite of 128 tests requiring no sound card, GPU, network, or API key.
- CI on Linux, Windows, and macOS × Python 3.10–3.13. CodeQL and Gitleaks.

### Security

- Pre-roll bounded by construction (`deque` with `maxlen`), not by configuration.
  Tested with 64 s of continuous audio.
- Nothing is transcribed in `DORMANT` state.
- `Config.redacted()` for logging and diagnostics, with a test that fails if a
  known secret appears in the output.
- `LOG_TRANSCRIPTS=0` by default.

### Notes

- Does **not** include voice cloning, by project decision. See `CONTRIBUTING.md`.
- AEC not implemented: in `wake` mode, `HALF_DUPLEX=1` (default) prevents the
  assistant from hearing its own voice. To converse with open speakers, see
  `docs/ROADMAP.md`.
