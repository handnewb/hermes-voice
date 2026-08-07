# Architecture

## The pipeline

```
microphone (always open, 32 ms frames)
   │
   ├── DORMANT ──► wake.py ────────────────► nothing transcribed here
   │                  │ triggers
   ├── LISTENING ──► vad.py ──► end of speech ──► session.take()
   │                                              │
   │                              stt.py (faster-whisper)
   │                                              │
   │                              llm.py ──► SentenceChunker
   │                                              │ sentence by sentence
   │                              tts/ ──► dsp.py ──► speaker.py ──► output
   │                                                      │
   └── SPEAKING ◄────────────────────────────────────────┘
```

## The three decisions that define the rest

**1. Chained pipeline, not speech-to-speech.** There's no decent local S2S model
in pt-BR today. It's the right choice, not a compromise — and it lets you swap any
stage independently. Reassess when a multilingual local S2S exists.

**2. Per-sentence chunking instead of waiting for the full response.** It's the
only latency optimization that changes the order of magnitude. The others are
marginal.

**3. State machine as the single source of truth about audio.** Every decision of
"what to do with this frame" is in `loops.run_wake_mode`, consulting
`session.state`. Without this, privacy rules are spread across three modules and
nobody can audit.

## Why audio imports are lazy

`sounddevice` loads `libportaudio` on import. CI runners and containers don't have
a sound card. If the import were at the top, the package would be unimportable in
CI and the test suite wouldn't exist — which is the fate of most audio projects.

`audio._sd()` solves this: the package imports anywhere, and PortAudio is only
required when someone actually captures or plays audio.

## Contracts between modules

| Boundary | Contract |
|---|---|
| `audio.FrameSource` → loop | `np.float32`, mono, 512 samples, bounded queue that discards old |
| loop → `wake.FrameAdapter` | `int16`; adapter regroups to what the backend demands (512 for Porcupine, 1280 for openWakeWord) |
| loop → `vad` | `float32`, exactly 512 samples (Silero v5 requirement) |
| `session.take()` → `stt` | `float32` mono 16 kHz concatenated, plus amplitude peak |
| `llm.stream()` → `SentenceChunker` | text deltas of arbitrary size |
| `SentenceChunker` → `tts` | speakable chunks, no markdown |
| backend `tts` → `speaker` | PCM `int16` little-endian in chunks of arbitrary size |

The `SentenceChunker` contract has an explicitly tested property: **the result must
not depend on how the stream slices the deltas.** Deltas of 1 to 23 characters must
produce identical output. Without this the audio changes with network speed.

## State, and where it lives

Four places hold mutable state. All other modules are stateless.

- `session.Session` — conversation state, pre-roll, speech buffer
- `vad.SpeechGate` — speech/silence hysteresis
- `tts.dsp.Presence` — biquad filters, compressor envelope, delay line
- `llm.HermesClient` — conversation history

The first three have `reset()`, and there's a test verifying that `reset()` zeros
everything — including the biquads, whose forgetfulness used to make residue from
the previous sentence bleed into the next.

## Where to touch to extend

| Goal | File | Note |
|---|---|---|
| New TTS backend | `tts/`, plus an entry in `_make()` | Implement `synth()` and `close()` |
| New wake word detector | `wake.py` | `FrameAdapter` handles frame size |
| Swap the STT | `stt.py` | Contract: `float32` 16 kHz → `str` |
| New language | `docs/persona.md`, `DEFAULT_HINT`, regex in `session.py`, `ABBREVIATIONS` in `llm.py` | These are the only four points |
| AEC | `audio.py` (loopback) and the `SPEAKING` branch in `loops.py` | See ROADMAP; it's the hard item |
