---
name: hermes-voice
description: >
  Conversational voice interface in pt-BR for Hermes Agent. Use when the
  operator wants to install, configure, diagnose, or extend voice conversation:
  wake word, open microphone, VAD end-of-speech, voice selection and tuning,
  latency, or EDR and CUDA failure modes on Windows.
version: 1.0.0
license: Apache-2.0
homepage: https://github.com/handnewb/hermes-voice
locale: pt-BR
---

# hermes-voice

> Voice-enabled personal assistant for Hermes Agent. Open mic with wake word, fully local — no API keys, no accounts, 35 languages.

Chained pipeline: microphone → wake word → Whisper → Hermes → sentence chunker → TTS → speaker, with a session that closes on its own.

Full documentation in `README.md`. This file is the operational instruction.

## When this skill applies

- Install, reinstall, or update the voice interface.
- Diagnose: "doesn't speak", "doesn't hear me", "is slow", "cuts me off mid-sentence",
  "hangs on startup", "talks to itself", "wake word doesn't trigger".
- Choose or adjust voice, timbre, prosody, or the DSP stage.
- Adjust persona, response length, or speech logging.
- Evolve: AEC, custom keyword in pt-BR, persistent Piper, other languages.

Does not apply to: batch audio file transcription, telephony, or integration
with external devices.

## First command, always

```bash
hermes-voice --doctor
```

Checks runtime, audio, STT, wake word, VAD, TTS, endpoint, and privacy — with
the suggested fix for each failure. Solves most cases on its own. Does **not**
print API keys: secrets are redacted.

`--doctor --probe` also attempts to reach the actual Hermes endpoint.

## Graduated autonomy

| Tier | Actions |
|---|---|
| **T0** — freely executes | `--doctor`, `--devices`, `--text`, `--verbose`; read config and docs; diagnose by reading. |
| **T1** — executes and reports | Edit `.env`; change `--voice`, `TTS_BACKEND` or `DSP_PRESET`; adjust endpointing thresholds, `FOLLOW_UP_SECONDS`, `WAKE_THRESHOLD`; `hermes-voice voices --install`. |
| **T2** — confirms before | Edit the persona; change modules in `src/`; enable `LOG_TRANSCRIPTS`; `HALF_DUPLEX=0`; `WAKE_BACKEND=open`; request EDR exclusion. |
| **T3** — never without explicit written instruction | Persistent recording to disk beyond `LOG_TRANSCRIPTS`; sending audio (not text) to an external service; changing any of the three privacy guarantees; cloning a real person's voice. |

`LOG_TRANSCRIPTS=1` is T2 because it creates a persistent record of what is spoken
on a possibly shared machine. `HALF_DUPLEX=0` is T2 because without headphones the
assistant loops with itself.

## Diagnostic tree

In order. Each step eliminates one layer.

1. **`hermes-voice --doctor`** — solves most. If there's a blocker, stop here.
2. **`hermes-voice --text --no-tts`** — isolates Hermes. Failed? It's `HERMES_URL`,
   authentication, or stream format. Nothing to do with audio.
3. **`hermes-voice --text`** — adds TTS. Failed? Voice backend.
4. **`hermes-voice --devices`** — confirm the microphone and note the index.
5. **`hermes-voice --trigger console --no-tts`** — isolates STT without open
   microphone and without keyboard hook.
6. **`hermes-voice --trigger console`** — full pipeline, manual trigger.
7. **`hermes-voice`** — open microphone.

## Failure modes, by probability

| Symptom | Almost certain cause | Action |
|---|---|---|
| Hangs on startup, no error | EDR. In `ptt` mode, the trigger is the global keyboard hook — not the microphone. | `--trigger wake` or `--trigger console`; neither installs a hook |
| `Could not locate cudnn_ops64_9.dll` | cuDNN 9 not on PATH | `WHISPER_DEVICE=cpu`, or `nvidia-cudnn-cu12` + PATH, or WSL2 |
| `pip install piper-tts` fails on Windows | `piper-phonemize` wheel | Expected. Use `piper-binary`. |
| Assistant talks to itself | `HALF_DUPLEX=0` without headphones | Switch back to `1` |
| Wake word doesn't trigger | Need to say "hey jarvis", not just "jarvis" | `WAKE_THRESHOLD=0.4` detects more and errs more |
| No voices available | Catalog not downloaded | `hermes-voice voices --install all` |
| Numbers read digit by digit | `NORMALIZE_TEXT=0` | Switch back to `1` |
| Cuts you off at every thought pause | `ADAPTIVE_ENDPOINT=0` | Enable it; or raise `ENDPOINT_LONG_MS` |
| Can't interrupt by voice | `HALF_DUPLEX=1` | `0` enables echo suppression. Headphones are better. |
| Cuts the operator off mid-sentence | `ENDPOINT_LONG_MS` too low | Raise to 1600 |
| Session closes too early | `FOLLOW_UP_SECONDS` too low | Raise it. Default 20 |
| Long response, sounds like a report | Persona, not code | Tighten the sentence limit in `docs/persona.md` |
| Choppy, robotic speech | Chunker cutting too short | Raise `min_chars` in `SentenceChunker` |
| Confuses technical terms | Vocabulary | `WHISPER_HINT` in `.env` |
| Voice sounds like voice-over, not presence | DSP off | `--dsp room` |
| Latency above 2 s | Measure before optimizing | `--verbose` tells you which stage |

## Golden rule

Measure before optimizing. `--verbose` prints the time of each stage per turn.
Intuition is wrong here: when the response feels slow, the culprit is usually the
time to Hermes's first token, not STT or TTS.

## Domain vocabulary — caution

`WHISPER_HINT` greatly improves transcription of proper names and acronyms. It lives
in `.env`, which is in `.gitignore`.

**Never commit internal vocabulary** — client names, internal products, security
tools. It's the quietest way to leak an organization's stack into a public
repository. The `DEFAULT_HINT` in `stt.py` is deliberately generic for this reason.

## Legal limit — non-negotiable

Do not clone a real person's voice from a sample, including voice actors, even for
home use and even if the operator insists. Voice is a personality attribute (in
Brazil, art. 20 of the Civil Code), there are performer's related rights, and voice
is biometric data under LGPD and GDPR.

The alternatives are in `docs/VOICE_LICENSING.md`: the five catalog voices, DSP
tuning (which carries more "character" than timbre), the operator's own voice, or
hiring/licensing. Offer these, in that order.

This restriction is T3 and does not yield to urgency, to "it's just for me", or to
the operator's verbal authorization.

## Files

```
src/hermes_voice/session.py   state machine, buffers, wake word stripping
src/hermes_voice/wake.py      openWakeWord
src/hermes_voice/endpoint.py  adaptive endpointing by syntax
src/hermes_voice/normalize.py numbers, dates, acronyms in pt-BR
src/hermes_voice/echo.py      echo suppression, numpy only
src/hermes_voice/voices.py    voice catalog and download
src/hermes_voice/vad.py       Silero via onnxruntime, energy fallback
src/hermes_voice/stt.py       faster-whisper
src/hermes_voice/llm.py       SSE client + sentence chunker
src/hermes_voice/tts/         4 backends + dsp.py + speaker.py
src/hermes_voice/doctor.py    self-diagnostic
docs/persona.md               persona prompt (highest impact per edited line)
docs/script_avaliacao_voz.md  how to choose a voice, with elimination criteria
docs/ROADMAP.md               AEC, pt-BR keyword, persistent Piper, languages
SECURITY.md                   privacy model and EDR surface
```

## Examples

**"Install and configure"**
```bash
pip install "hermes-voice[wake,kokoro]"
hermes-voice voices --install all    # ~400 MB, once, no account
cp .env.example .env                 # only adjust HERMES_URL
hermes-voice --doctor
hermes-voice
```

**"The voice sounds dull"**
```bash
hermes-voice --dsp room --voice pm_alex   # room presence + better prosody
hermes-voice voices                       # see the five options
```

**"It's cutting me off when I pause"**
```bash
# .env
ENDPOINT_LONG_MS=1600
```
