# Roadmap

Current state: **v1.0.0**. Wake word, VAD, continuous session, four TTS backends,
and the DSP stage are done. What's missing is below, with honest effort estimates.

---

## ~~v1 — Wake word and end-of-speech~~ — done in 1.0.0

Replaces the key with continuous listening. Two pieces:

**Silero VAD** (`snakers4/silero-vad`) — ~2 MB ONNX, ~1 ms inference per 30 ms
window. Replaces key release with real end-of-speech detection. The parameter that
matters is the minimum silence: 300 ms seems aggressive but is what makes the
conversation flow; above 600 ms the assistant sounds hesitant. Make this
configurable and adjust by ear, not by intuition.

**openWakeWord** — train "Hermes" as a custom word. Alternative: Porcupine
(Picovoice), better false positive rate, free for personal use.

Where it fits: `audio_in.Recorder` already keeps the `InputStream` open for the
entire session precisely for this. Swap the trigger for wake word and `stop()` for
VAD; the rest of the pipeline doesn't change.

**Unexpected bonus:** wake word eliminates the global keyboard hook, which is
currently the highest-friction component with behavioral EDR. You trade a keylogger
signature for always-on microphone. From the EDR perspective it's a clear
improvement; from the home privacy perspective, the opposite. Decide with both
sides on the table, not just the first.

**Non-technical consequence.** Wake word means always-on microphone on a work
machine, with family nearby. Before enabling: define that the ring buffer is
circular and bounded (2-3 s are enough not to miss the start of a sentence), that
it never touches disk, and that transcription doesn't go to a persistent log. This
is T3 in the skill for that reason.

## AEC — high effort, the most requested item

Only needed if you want to talk with open speakers. With headphones, skip.

The problem: the microphone hears the output, the VAD triggers with Hermes's own
voice, and you loop. Two things needed:

1. **Reference signal** — WASAPI loopback capture of the output. On Windows,
   `sounddevice` with `WasapiSettings(loopback=True)`, or `soundcard` which exposes
   this more directly.
2. **AEC** — `speexdsp` (`speexdsp-python`) or WebRTC AEC via
   `webrtc-audio-processing`. WebRTC is better but the Python binding is
   irregular.

Honest estimate: this is the part of the project that will consume the most time,
by a wide margin. Temporal alignment between the reference signal and the
microphone is where everything goes wrong — a 20 ms offset degrades cancellation
to the point of uselessness, and the offset varies with the driver.

**Pragmatic shortcut:** a halfway solution that solves 80% of cases without AEC.
While TTS is speaking, raise the VAD threshold and require the detected energy to
exceed the known output energy by a margin. Cheap, works when you speak louder
than the speakers, and it's ~30 lines. Do this before trying real AEC.

## Persistent Piper — low effort, ~150 ms gain

Today `PiperBinary.synth` spawns one process per sentence: ~150 ms startup per
sentence. Sum that over a four-sentence response and you lose half a second.

Solution: long-lived process fed via stdin. The obstacle is that `--output_raw`
doesn't delimit utterances in stdout, so you don't know where one ends. Two
options: `--output-dir` with per-sentence files (loses streaming), or
`--json-input` which returns metadata per utterance. Worth measuring whether the
150 ms gain is justified — if you migrate to Azure, the problem disappears.

## Tools — medium effort

The point where this stops being a toy. Hermes already orchestrates the SOC fleet;
voice becomes an interface for querying state and triggering playbooks.

Two rules that must not yield:

**Voice confirmation for destructive actions, always.** Speech recognition errs,
and a false positive that closes a ticket or isolates an endpoint is expensive. The
`persona_jarvis_ptbr.md` already contains this rule; it needs to be reinforced at
the tool layer, not trusted to the prompt.

**No reading secrets aloud.** The same permanent prohibition that applies to any
secrets vault holds. Audio is the worst possible channel for credentials: it hangs
in the room's air, has no access control, and you don't know who's listening.

## Don't do

**Local speech-to-speech in pt-BR.** Doesn't exist decently yet. Moshi is
English/French, GLM-4-Voice is Chinese/English, Qwen-Omni synthesizes only English
and Mandarin. Reassess in about six months; the field moves fast.

**Real-person voice cloning.** Covered in `SKILL.md` as a T3 restriction.

**Optimize before measuring.** `--verbose` exists for this. When the response feels
slow, the culprit is usually the time to Hermes's first token — not STT or TTS,
which is where intuition says to look.

## Languages beyond pt-BR — low effort, help welcome

The architecture isn't Portuguese-specific. What is: the persona file, the
Whisper `DEFAULT_HINT`, the wake word cleanup regex in `session.py`, and the
sentence chunker abbreviations (`Dr.`, `Sr.`, `etc.`).

To add a language, these four points are the entire job. STT (Whisper) and VAD
(Silero) are already multilingual, and Piper has voices for dozens of languages.
Open an issue saying which language and I'll help map the points.
