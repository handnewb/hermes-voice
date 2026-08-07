# hermes-voice

**Voice-enabled personal assistant for [Hermes Agent](https://github.com/NousResearch/hermes-agent).** Open mic with wake word, fully local — no API keys, no accounts, 35 languages.

[![CI](https://github.com/handnewb/hermes-voice/actions/workflows/ci.yml/badge.svg)](https://github.com/handnewb/hermes-voice/actions/workflows/ci.yml)
[![CodeQL](https://github.com/handnewb/hermes-voice/actions/workflows/codeql.yml/badge.svg)](https://github.com/handnewb/hermes-voice/actions/workflows/codeql.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![License: Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-green)](LICENSE)

```
you:     "Jarvis, what ran overnight?"
hermes:  "One hundred forty-seven thousand events, sir. Three escalated."
you:     "detail the third"          ← no wake word needed
hermes:  "Connection to a domain registered eighteen hours ago. Isolated."
         ...20 seconds of silence...
                                     ← goes back to sleep on its own
```

<details>
<summary><b>English</b> — short version</summary>

Talk to your Hermes agent the way you would talk to a person. Say the wake word
and speak; the wake word opens a **session**, so follow-up turns need no
repetition. The session closes on its own when you stop talking.

```bash
pip install "hermes-voice[wake,kokoro]"
hermes-voice voices --install pt_BR-faber-medium   # or --lang en, es, fr, zh...
hermes-voice --doctor
hermes-voice
```

**Runs entirely offline.** Speech recognition (faster-whisper), voice activity
detection (Silero), wake word (openWakeWord) and synthesis (Piper, Kokoro-82M) all
run locally. The only address contacted at runtime is your own Hermes endpoint.

- **Adaptive turn-taking** — instead of a fixed silence threshold, it transcribes
  early and checks whether the sentence *looks finished*. "I want" waits;
  "what's the status?" answers immediately.
- **Barge-in without external dependencies** — echo suppression in ~200 lines of
  numpy. Zero false positives across four delays and four room gains.
- **Presence DSP** — high-pass, compression, presence lift, short room reverb.
  Much of what people recognise as "assistant voice" is processing, not timbre.
- **Voices in 35 languages** via the public Piper index, MD5-verified, plus 9 via
  Kokoro. All default voices permit commercial use.
- **Voice cloning of real people is deliberately unsupported.** Reasoning and
  clean alternatives in [`docs/VOICE_LICENSING.md`](docs/VOICE_LICENSING.md).

Read [`docs/VERIFICATION.md`](docs/VERIFICATION.md) before trusting it: it states
plainly which parts have run on real hardware and which have not.

Documentation and the default persona are Brazilian Portuguese; the architecture
and voice catalog are language-agnostic. Contributions welcome, including
translations — see [`CONTRIBUTING.md`](CONTRIBUTING.md).

</details>

> **Verification status.** The components have 229 automated tests, but parts of
> the project — all audio I/O, the voice engines, and downloads — have never
> been executed on real hardware. Before trusting, read
> [`docs/VERIFICATION.md`](docs/VERIFICATION.md): it lists what has been verified,
> what hasn't, and where I would bet there are issues.

---

## The design point

If you have to say the wake word every turn, that's a **remote control**, not a conversation. Here the word opens a **session**, and inside it you speak normally.

```
DORMANT ──"Jarvis"──────────► LISTENING
LISTENING ──700 ms silence──► THINKING ──1st audio──► SPEAKING
SPEAKING ──end of audio─────► FOLLOW_UP
FOLLOW_UP ──you speak───────► LISTENING     (no wake word needed)
FOLLOW_UP ──20s idle────────► DORMANT
```

The two parameters that define the feel:

| Variable | Default | Effect |
|---|---|---|
| `SILENCE_MS` | `700` | Silence that ends your speech. Below 400 cuts you off at natural pauses; above 900 sounds hesitant. |
| `FOLLOW_UP_SECONDS` | `20` | How long the session stays open after the response. |

Adjust by ear, not by intuition.

## Getting started

```bash
pip install "hermes-voice[wake,kokoro]"
hermes-voice voices --install all   # downloads voices and models, ~400 MB, once
hermes-voice --doctor               # tells you exactly what's missing
hermes-voice                        # speak
```

**No accounts, no API keys, no cloud services.** All engines run locally. The
only address the program contacts at runtime is your own Hermes.

Or from the repository, with the setup that downloads the voice and the Piper binary:

```powershell
git clone https://github.com/handnewb/hermes-voice && cd hermes-voice
.\scripts\setup.ps1            # Windows
./scripts/setup.sh             # Linux and macOS
```

**Always start with `--doctor`.** In a voice project, 90% of problems are environmental: audio driver, missing cuDNN, wheel that didn't compile, absent key, EDR blocking. The doctor checks the eight groups and tells you the fix for each failure, instead of you discovering through trial and error.

## Three trigger modes

| Mode | How | When to use |
|---|---|---|
| `--trigger wake` *(default)* | Say the word and speak | Normal use |
| `--trigger console` | ENTER starts, ENTER sends | When you can't have an open mic or keyboard hook |
| `--trigger ptt` | Hold a key | Noisy environment |

The `console` mode exists for a specific reason. A global keyboard hook (`SetWindowsHookEx`, used by `pynput` in `ptt` mode) is the classic keylogger signature; combined with microphone capture and network egress, it forms the behavioral triad of a spyware implant. A behavioral EDR engine will flag it, and it will be right. The `console` mode installs no hook. See [SECURITY.md](SECURITY.md).

## The wake word

Three modes, with explicit tradeoff. None requires an account.

| `WAKE_BACKEND` | Word | Accuracy | Cost |
|---|---|---|---|
| `auto` *(default)* | openWakeWord catalog | Best | Requires "**hey** jarvis"; only 4 words |
| `keyword` | **Any word, any language** | Lower | Transcribes speech before activating |
| `open` | None — any speech | — | Transcribes everything. Headphones only. |

The `auto` mode uses pre-trained models (`hey_jarvis`, `alexa`, `hey_mycroft`,
`hey_rhasspy`). Better detection, but a small catalog and you need to say "hey"
first.

The `keyword` mode accepts whatever word you want, in any language, without training
anything: when the VAD detects speech, a Whisper `tiny` transcribes the window and
searches for the word with transcription error tolerance.

```bash
# .env
WAKE_BACKEND=keyword
WAKE_WORDS=jarvis,jarvez,gervis
```

The comma-separated list is the mechanism that matters. Edit tolerance is
deliberately limited to 1 — with 2, "computer" starts accepting "compiler", and
false activation is worse than missed activation. To recover what Whisper gets
wrong for *your* voice, **add nicknames** instead of loosening the threshold: an
exact list introduces no new collisions.

Choose a distinctive word of three syllables or more, and check for collisions
before adopting: "hermes" collides with "herpes" at one edit, "sofia" with "sofa".
This applies to any wake word system.

**Privacy cost of `keyword` mode**, and it's real: speech is transcribed before
activation occurs. It's not continuous transcription — it only runs when the VAD
sees speech, nothing is recorded, and nothing leaves the machine — but the
guarantee "in `DORMANT` nothing is transcribed" doesn't hold in this mode. That's
why it's not the default, and `--doctor` warns about it.

For a custom word with trained model accuracy, openWakeWord has a training
pipeline with synthetic data. See [roadmap](docs/ROADMAP.md).

## Voice

Hundreds of voices in dozens of languages, all free, all with licenses permitting
commercial use. Two engines, both local.

```bash
hermes-voice voices --languages           # which languages exist
hermes-voice voices --lang es             # filter
hermes-voice voices --install em_alex
hermes-voice --voice em_alex
```

**Piper**: the catalog is not hardcoded. The program queries the
`voices.json` published on Hugging Face at runtime — 35 languages, hundreds of
voices, MIT license — and verifies the MD5 that comes in the index itself. A new
voice upstream appears without a release from us. If the index is unreachable,
Kokoro keeps working and a warning is logged.

**Kokoro-82M**: 54 voices in 9 languages in a single Apache-2.0 weights file —
American and British English, Spanish, French, Hindi, Italian, Japanese, Brazilian
Portuguese, and Mandarin.

| Voice | Engine | License | Note |
|---|---|---|---|
| `pt_BR-faber-medium` | Piper | MIT | **Default.** 63 MB, runs on CPU, ~50 ms. |
| `pm_alex` | Kokoro | Apache-2.0 | pt-BR, much better prosody than Piper. |
| `am_michael` | Kokoro | Apache-2.0 | en-US male. |
| `em_alex` | Kokoro | Apache-2.0 | Spanish male. |
| `zm_yunxi` | Kokoro | Apache-2.0 | Mandarin male. |
| ...and hundreds of Piper voices | Piper | MIT | `voices --lang <code>` |

Kokoro runs via `kokoro-onnx` and not the official package, because the official
one drags in PyTorch (~2.5 GB) and this project already has onnxruntime installed
for the VAD.

Neither engine does voice cloning — they are fixed voices. This is a project
choice, and [`docs/VOICE_LICENSING.md`](docs/VOICE_LICENSING.md) explains the
legal landscape (personality rights, performer's related rights, voice as
biometric data) and the clean paths for those who want a specific timbre.

### Choosing a voice seriously

[`docs/script_avaliacao_voz.md`](docs/script_avaliacao_voz.md) has an 11-block
script, each isolating a failure mode, with three elimination criteria.

The two blocks nobody thinks to test: the voice needs to be able to **say no** and
**admit ignorance** without sounding aggressive or submissive. Pt-BR voices are
almost all trained for customer service, come with a built-in smile, and fail
badly precisely on these two — which are the utterances that matter most for an
assistant that confirms destructive actions.

For long-form stability there's
[`docs/monologo_1000_palavras.txt`](docs/monologo_1000_palavras.txt): 1,031
continuous words, ~7 minutes. Compare the last minute with the first.

## The stage that makes more difference than timbre

```bash
hermes-voice --dsp room
```

Much of what people identify as "sci-fi assistant voice" isn't in the timbre — it's in the **processing**. Speech is treated as if coming from speakers in a space, and no TTS ships this out of the box.

Four stages, streaming, numpy-only:

1. **High-pass** at 110 Hz — removes the "mouth on mic" weight that gives away close-miked speech
2. **Compressor** — flattens dynamics; a calm voice has little volume variation, and that's what gives a sense of control
3. **Presence lift** at 3 kHz — intelligibility at a distance
4. **Short room reverb**, very low — gives the sound a place

Five presets: `off`, `room`, `close`, `hall`, `intercom`. Start with `room`. Use `hall` once just to hear what each parameter does — it exaggerates on purpose.

Overdoing reverb is the most common mistake and sounds like a bathroom.

## Fluidity

Three things separate "conversation" from "voice remote control", and none of them
is timbre.

**Adaptive endpointing.** A fixed silence threshold doesn't work: 400 ms cuts you
off mid-thought, 1000 ms makes the assistant sound hesitant. Pause length carries
meaning. So instead of counting silence, the system transcribes at a short
threshold and checks whether the sentence *looks finished*:

```
"I want"                      → dangling, waits up to 1250 ms
"the status of"               → stranded preposition, waits
"what's the status?"          → closed question, answers in 380 ms
"isolate the machine now"     → complete imperative, answers
```

If the text hasn't grown between two probes, it ends anyway — someone distracted
mid-sentence can't lock the turn.

**Text normalization.** No local TTS reads `$1,500.00` or `06/08/2026` correctly.
Piper spells digit by digit. Normalization converts before synthesizing, and the
perceived quality gain is larger than switching engines:

```
"$1,500.50 on 06/08/2026 at 2:30 PM, 99.7% availability"
→ "one thousand five hundred dollars and fifty cents on June eighth two
   thousand twenty-six at two thirty PM, ninety-nine point seven percent..."
```

**Real interruption.** See the duplex section below.

Language caveat: endpointing and normalization are **pt-BR specific**. The
architecture is multilingual and STT, VAD, and voices are too, but the word lists
in `endpoint.py`, the rules in `normalize.py`, and the persona are in Portuguese.
Other languages work with a fixed threshold and without normalization — worse, not
broken. Adding a language is four points, listed in
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Latency

The gain doesn't come from optimizing each stage — it comes from **pipelining**: the first sentence of the response goes to TTS while the model is still generating the second.

| Stage | Target |
|---|---|
| End of speech (Silero VAD) | ~700 ms (that's `SILENCE_MS`, adjustable) |
| STT (`large-v3-turbo`, GPU) | 200–400 ms |
| Hermes to 1st token | 100–500 ms |
| TTS to 1st audio | 150–300 ms |
| **Perceived** | **~700–1000 ms** |

`--verbose` prints the real time of each stage per turn. Measure before optimizing: when it feels slow, the culprit is usually the time to Hermes's first token, not STT or TTS — which is where intuition says to look.

## Privacy

An open microphone on a personal machine deserves guarantees, not configuration.
Three properties implemented in [`session.py`](src/hermes_voice/session.py) **by
construction** — they can't be turned off by accident:

- **In `DORMANT` nothing is transcribed.** Frames only feed the wake word
  detector, which runs locally and produces no text.
- **The pre-roll is a `deque` with a fixed `maxlen`** of 480 ms. There's a test
  that feeds 64 seconds of continuous audio and verifies that only 480 ms are
  retained.
- **On sleeping, the buffer is discarded**, explicitly and even when it was
  already dormant.

Nothing touches disk unless you set `LOG_TRANSCRIPTS=1`, which is `0` by default
and appears as a warning in `--doctor`.

The 480 ms of pre-roll exist because the detector fires ~300 ms after the word
ends; without it you lose the first syllable of what came next.

No audio or text goes to a voice provider, because there is no voice provider:
Piper, Kokoro, Silero, and openWakeWord all run locally. The only address
contacted at runtime is your own Hermes endpoint.

## Duplex and interruption

`HALF_DUPLEX=1` (default): while the assistant speaks, the microphone is not
evaluated. Robust, and the cost is not being able to interrupt by voice.

`HALF_DUPLEX=0` enables **echo suppression** and you can interrupt by speaking.

This is not AEC. Real AEC estimates the room impulse response with an adaptive
filter and subtracts echo from the signal. What we do is more modest and solves the
case that matters: since we generate the output audio, we know exactly what was
sent. For each microphone frame, we check whether **any** alignment of the
reference, within a 320 ms window, explains the captured energy. If it does, it's
echo. If not, it's you. Two hundred lines of numpy, zero dependencies.

Tested with 20–300 ms delay and 0.25–1.3 room gain: zero false positives with
pure echo, and triggers with overlapping speech.

Practical consequence: you interrupt by speaking louder than the speaker. No
low-volume overlapping conversation. With headphones none of this is necessary —
there's no echo.

## Architecture

| Module | Responsibility |
|---|---|
| `session.py` | State machine, buffer limits, wake word cleanup |
| `wake.py` | openWakeWord, with frame size adapter |
| `vad.py` | Silero via onnxruntime (no torch), energy fallback, hysteresis |
| `stt.py` | faster-whisper with domain vocabulary and CPU fallback |
| `llm.py` | SSE client and sentence chunker |
| `tts/` | Four backends, DSP, and interruptible playback |
| `endpoint.py` | Adaptive endpointing by syntax |
| `normalize.py` | Numbers, dates, acronyms and abbreviations in pt-BR |
| `echo.py` | Reference-based echo suppression, numpy only |
| `voices.py` | Voice and model catalog and download |
| `doctor.py` | Self-diagnostic |
| `loops.py` | The three trigger modes |

There's no decent local speech-to-speech in pt-BR today — Moshi is English and
French, GLM-4-Voice is Chinese and English, Qwen-Omni synthesizes only English and
Mandarin. A chained pipeline is the right choice, not a compromise. Reassess in a
few months.

## Tests

```bash
pip install -e ".[dev]" && pytest
```

229 tests, none requiring a sound card, GPU, network, or API key. This is a
requirement, not a coincidence: an audio project that can only be tested with
hardware ends up with no tests. The `sounddevice` imports are lazy on purpose.

The test that matters most: the sentence chunker is verified with deltas of 1 to
23 characters, requiring identical results. Without this property, the audio
changes with network speed — which was exactly the bug that cut "12:30" in half.

## Name and trademarks

The project is called **hermes-voice** and is not affiliated with, sponsored by, or
endorsed by any trademark holder.

`hey_jarvis` appears as the default value of `WAKE_MODEL` because it's the
identifier of one of the few pre-trained models that openWakeWord distributes — it's
a functional dependency and a third-party filename, not branding of this project.
Change it in `WAKE_MODEL` to any other in the catalog (`alexa`, `hey_mycroft`,
`hey_rhasspy`), or train your own.

The **persona name** is configurable in `docs/persona.md`: what you call your
assistant on your machine is your decision.

If you rename a fork, research the trademark before building an audience. There
are [known cases](docs/VOICE_LICENSING.md) of AI products that had to be renamed,
and renaming later costs stars, links, and SEO.

## Contributing

[`CONTRIBUTING.md`](CONTRIBUTING.md) for the environment and code rules.
[`GOVERNANCE.md`](GOVERNANCE.md) for how decisions are made, who can do what, and
which process applies at each project stage. [`SUPPORT.md`](SUPPORT.md) for where
to ask what.

Contributing requires no permission: fork plus pull request covers all cases. The
only mandatory gate is green CI.

## License

[Apache 2.0](LICENSE) for the code. Downloaded models and voices have their own
licenses, all permissive: Piper and rhasspy voices are MIT, Kokoro-82M is
Apache-2.0, Silero VAD is MIT, openWakeWord is Apache-2.0.

No component in the default path restricts commercial use. See
[`docs/VOICE_LICENSING.md`](docs/VOICE_LICENSING.md) for what stays out and why.

## Acknowledgments

[Hermes Agent](https://github.com/NousResearch/hermes-agent) (Nous Research) • [faster-whisper](https://github.com/SYSTRAN/faster-whisper) • [Silero VAD](https://github.com/snakers4/silero-vad) • [Piper](https://github.com/rhasspy/piper) • [openWakeWord](https://github.com/dscripka/openWakeWord) • [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M) • [kokoro-onnx](https://github.com/thewh1teagle/kokoro-onnx)
