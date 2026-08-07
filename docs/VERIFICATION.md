# Verification status

This document exists because the difference between "written" and "verified" is
usually implicit, and in a project that records audio and downloads models, that
difference matters. Below is what has been executed, what hasn't, and where I
would bet there are issues.

Written before the first publication. Update alongside fixes.

---

## Verified by automated testing

229 tests, run repeatedly. None require a sound card, GPU, network, or API key.

| Component | What was verified |
|---|---|
| `llm.SentenceChunker` | Identical result for deltas of 1 to 23 characters; no character lost; `12:30`, `4.812`, `Dr.` preserved; emits before end of stream |
| `session.Session` | Full state cycle; pre-roll limited to 480 ms after 64 s of audio; buffer discarded on sleep, including when already sleeping |
| `session.strip_wake_word` | 7 variants removed; 9 legitimate words preserved, including "Gervásio" and "Java" |
| `tts.dsp.Presence` | −12.5 dB at 80 Hz measured by FFT; state continuity with error ≤ 1 LSB in blocks of 2 to 4096 bytes; odd chunk never generates stray byte; compressor reduces dynamics from 18× to 6.1×; output never saturates |
| `echo.EchoSuppressor` | Zero false positives with pure echo at 4 delays (20–300 ms) × 4 room gains (0.25–1.3); triggers with loud overlapping speech |
| `normalize` | Cardinals up to millions; currency, date, time, percentage, ordinal, decimal with comma and dot; idempotency; no remaining digits |
| `endpoint` | Classification of 15 cases; hysteresis; unlocks with stagnant text; probe ceiling |
| `wake.matches` | Nicknames accepted, collisions rejected, tolerance limited to 1 |
| `config` | Secret redaction with test injecting known value; `.env` doesn't override environment; persona extraction via `rsplit` |
| Packaging | Wheel builds, installs in clean venv, entry point executes, persona travels inside the package |

---

## Verified on real hardware (2026-08-07)

### Jarvis — Windows 11, NVIDIA RTX 4060, Python 3.13.13

| Component | Result |
|---|---|
| **Install** | `pip install -e ".[dev,wake,kokoro]"` — success |
| **Tests** | 229/229 passed in 1.55s |
| **Ruff lint** | All checks passed |
| **Ruff format** | 48 files already formatted |
| **Doctor** | All 8 groups green (Runtime, Audio, STT, Wake, VAD, TTS, Hermes, Privacy) |
| **GPU/CUDA** | 1 device detected |
| **Audio** | 11 microphones, 14 outputs |
| **Voice catalog** | Piper index parsed successfully (8 pt-BR voices) |
| **Voice download** | Piper (60 MB) + Kokoro (327 MB) downloaded, MD5 verified |
| **Piper binary** | Synthesized without error at 22050 Hz |
| **DSP** | Preset 'room' applied, no error |
| **Hermes endpoint** | `--doctor --probe` → HTTP 200 |
| **LLM pipeline** | DeepSeek responded in Portuguese following the persona |
| **Latency** | 1670ms to first audio (LLM + TTS) |
| **Full pipeline** | `--text` with LLM + Piper binary TTS + DSP → functional |

### Mestre — Linux 6.8, Python 3.11.15, no GPU

| Component | Result |
|---|---|
| **Tests** | 229/229 passed in 4.13s |
| **Ruff lint** | All checks passed |
| **Ruff format** | 48 files already formatted |
| **Doctor** | 4 expected blocks (PortAudio, CUDA, wake, voices — headless VPS) |
| **Build** | sdist + wheel generated without error |

### Gaps found

| Gap | Detail | Workaround |
|---|---|---|
| **Kokoro + espeak-ng on Windows** | `language "p" is not supported by the espeak backend` — espeak-ng has no pt-BR data on Windows | `TTS_BACKEND=piper-binary` |
| **`auto` backend on Windows** | Tries Kokoro first (fails on espeak-ng), falls to piper-python (not installed on Windows), never reaches piper-binary | Explicit `TTS_BACKEND=piper-binary` |
| **Open microphone** | Not tested (remote SSH, no interaction) | Awaiting local test |
| **Real wake word** | openWakeWord installed but not tested with real audio | Awaiting local test |

### What was NOT tested (yet)

- Open microphone with wake word (`hermes-voice` without `--text`)
- Barge-in / echo suppression with real hardware
- Adaptive endpointing with real audio
- `ptt` mode (keyboard hook + EDR)
- macOS (not available)
- Piper Python backend (not installable on Windows)

---

## Where I would bet the problem is

In order of probability.

**1. Endpoint probe latency blocks the audio loop.**
The probe calls `stt.transcribe()` synchronously on the thread consuming
frames. On GPU it's ~150 ms, acceptable. On CPU it can be 1–3 s, and the
`FrameSource` queue has 64 frames (~2 s) and discards old ones when full. That is:
**on CPU, the probe probably swallows audio.** The fix is to run the probe in a
thread, or disable `ADAPTIVE_ENDPOINT` when `WHISPER_DEVICE=cpu`. Not implemented
because I can't measure.

**2. Schema divergence in `voices.json`.** See above.

**3. Kokoro API signature.** If `create()` has a different parameter order or
returns a different format, the backend breaks on first use.

**4. Piper sample rate.** The code reads `audio.sample_rate` from `.onnx.json`, with
fallback to 22050. If a `.json` lacks that field, the voice comes out with the wrong
pitch instead of failing — worse than an error, because it seems to work.

**5. Echo suppression alignment on real hardware.** The test uses synthetic echo
with constant delay. Real drivers have jitter, and the `RawOutputStream` buffer
introduces delay I haven't modeled. May need a search window larger than 320 ms.

**6. README latency numbers are estimates.** They come from published benchmarks
of the components, not from measurement in this codebase. `--verbose` exists for
you to measure; replace the numbers with yours.

---

## Manual verification script

The first time you run on real hardware, in this order:

```bash
hermes-voice --doctor                       # 1. environment
hermes-voice voices --languages             # 2. did the Piper index load?
hermes-voice voices --install pt_BR-faber-medium   # 3. download and MD5
hermes-voice --text --no-tts                # 4. just Hermes
hermes-voice --text                         # 5. + synthesis
hermes-voice --devices                      # 6. devices
hermes-voice --trigger console --no-tts     # 7. just STT
hermes-voice --trigger console              # 8. pipeline, manual trigger
hermes-voice --verbose                      # 9. open microphone, with timings
```

Note what fails. Steps 2, 3, and 9 exercise code that has never been executed.

For DSP, compare by ear:

```bash
hermes-voice --text --dsp off
hermes-voice --text --dsp room
hermes-voice --text --dsp intercom
```

---

## What this document is not

It's not a list of known bugs — a known bug is fixed, not documented. It's the
boundary between what has been verified and what has only been carefully written.

If you find something on this list working, remove the line. If you find it
failing, open an issue and move it to `CHANGELOG.md` when fixed.
