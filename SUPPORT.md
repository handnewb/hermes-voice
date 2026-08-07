# Where to ask

Choosing the right channel saves everyone's time.

| Your situation | Go to |
|---|---|
| It doesn't work and you think it's a bug | [Bug issue](../../issues/new?template=bug_report.yml) — **paste the output of `hermes-voice --doctor`** |
| Configuration or usage question | [Discussions](../../discussions) |
| Idea or feature request | [Feature request issue](../../issues/new?template=feature_request.yml), after reading the [roadmap](docs/ROADMAP.md) |
| Security vulnerability | [Private advisory](../../security/advisories/new). **Do not open a public issue.** |
| You want to contribute | [`CONTRIBUTING.md`](CONTRIBUTING.md) |
| You want to understand how decisions are made | [`GOVERNANCE.md`](GOVERNANCE.md) |

## Before opening anything

```bash
hermes-voice --doctor
```

Checks environment, audio, transcription, wake word, VAD, voice, endpoint, and
privacy — with the suggested fix for each failure. Solves most cases on its own, and
the output does **not** contain API keys: secrets are redacted.

It's also worth checking [`docs/VERIFICATION.md`](docs/VERIFICATION.md): parts of
the project haven't yet been executed on real hardware, and what you found may
already be listed there.

## What helps in an issue

Operating system, `--doctor` output, trigger mode, voice in use, and the log with
`--verbose`. Without this the conversation turns into ten messages to figure out
which of the ten things broke.

## Timeline

Response in 48 h, even if only to say it was seen. One maintainer, new project — if
it goes past that, comment on the issue itself.

## What isn't support from this project

Issues with Hermes Agent itself, your endpoint, or third-party engines (Piper,
Kokoro, openWakeWord, faster-whisper). Report to them. If you're unsure about the
boundary, ask in Discussions and I'll help you locate it.
