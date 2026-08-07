# Contributing

Contributions are welcome. This document exists so you don't waste time.

## Set up the environment

```bash
git clone https://github.com/handnewb/hermes-voice
cd hermes-voice
python -m venv .venv
source .venv/bin/activate          # Windows: .\.venv\Scripts\Activate.ps1
pip install -e ".[dev,all]"
cp .env.example .env
hermes-voice --doctor
```

## Before opening a PR

```bash
ruff check . && ruff format . && pytest
```

## The rule that matters most here

**No test may require a sound card, GPU, network, or API key.**

This isn't a preference — it's what keeps the suite alive. Audio projects that can
only be tested with hardware end up with no tests. The `sounddevice` imports are
lazy on purpose (`audio._sd()`) so the package is importable and testable in a
runner without audio.

What can be tested without hardware, and is tested: sentence chunker, state
machine, buffer limits, wake word cleanup, DSP chain (numerically, with synthetic
tone), config parsing, secret redaction.

What needs manual testing: wake word detection quality, latency feel, timbre.
Describe in the PR what you tested manually, on which OS, and with which backend.

## Code standards

- `ruff` handles style and imports. Don't argue about formatting — run the tool.
- Docstrings and comments in pt-BR. Identifier names in English.
- Comments explain **why**, not what. If the code needs a comment to say what it
  does, rewrite the code.
- No new dependency without justification in the PR. Each one is a supply chain
  decision, and this project already records audio — the trust budget is tight.

## Changes that require discussion before code

Open an issue first if the PR:

- changes **audio capture, retention, or transmission**, including buffer size,
  what is transcribed in each state, or what goes to disk;
- adds a backend that sends audio (not text) to an external service;
- touches the three guarantees described in `SECURITY.md`.

This isn't bureaucracy. These guarantees are the reason you can run this on a
machine with other people nearby, and changing them without discussion breaks the
project's premise.

## What won't be accepted

**Cloning a real person's voice from a sample.** Voice is a personality attribute
(in Brazil, art. 20 of the Civil Code), there are performer's related rights, and
voice is biometric data under LGPD and GDPR. This applies to voice actors and to
"personal use only" as well.

The alternative exists and is better: ElevenLabs Voice Design generates a novel
timbre from a textual description. No real person involved, and the result is
yours. There's an example prompt in `README.md`.

## Where to help

`docs/ROADMAP.md` has the backlog with honest effort estimates. The highest-impact
items today:

- **AEC** (echo cancellation) to converse with open speakers. It's the hardest
  and most requested item.
- **Wake word in pt-BR** trained natively, instead of the English model.
- **Piper with persistent process**, to eliminate ~150 ms of startup.
- **More languages.** The architecture isn't Portuguese-specific; the persona and
  vocabulary are.

## Governance and permissions

[`GOVERNANCE.md`](GOVERNANCE.md) describes how decisions are made, the protected
paths, and what each GitHub role can do.

Two points that save time: **contributing requires no permission** — fork plus
pull request covers all cases, and you don't need to ask for access. And the Triage
role, granted after one or two accepted PRs, is the normal first step: it lets you
label and close issues without touching code.

## Code of conduct

See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
