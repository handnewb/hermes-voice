# Voice persona — "butler" register

Read by `config.py` and injected as the system prompt. Everything before the HTML
comment `PROMPT-BEGIN` is documentation and is discarded.

## Why this file matters more than the TTS choice

The number one failure of a voice assistant is responding with a paragraph that
sounds like a report being read aloud. Timbre is the last 20% of the experience;
the register and the **length** are the first 80%.

The two-sentence limit is the most important rule in the prompt below. If you're
going to change one thing, change that.

## How to adjust

| Symptom | Where to change |
|---|---|
| Long responses, sounds like a report | Tighten the sentence limit |
| Too dry, unpleasant | Loosen the irony rule |
| Reads URL, hash, or path aloud | Reinforce the corresponding rule |
| Explains the obvious | Adjust the "Context" section to your level |

Don't touch the **format** rules. They exist because nobody listens to bullet
points, and the model will insist on producing them if you let it.

## Note on voice licensing

This persona is original. It does not reproduce or imitate the voice, text, or
performance of any specific person or character — it describes a speech register
(formal, restrained, economical), which isn't anyone's property.

If you want a specific timbre, the clean path is ElevenLabs Voice Design: it
generates a novel voice from a textual description. There's an example prompt in
`README.md`. Cloning a real person's voice from a sample is not supported in this
project — see `CONTRIBUTING.md`.

## Where the file lives

The canonical file is `src/hermes_voice/data/persona.md`, packaged in the wheel
so it works in a pip install. To customize without editing the package:

```bash
cp src/hermes_voice/data/persona.md my_persona.md
echo 'PERSONA_FILE=my_persona.md' >> .env
```
