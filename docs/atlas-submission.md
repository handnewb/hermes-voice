# Submissão ao Hermes Atlas — corpo da issue

Arquivo pronto para postar. Confira os dois critérios antes, revise as
pendências no fim, e então:

```bash
gh issue create --repo ksimback/hermes-ecosystem \
  --title "Add: handnewb/hermes-voice — voice-enabled personal assistant" \
  --body-file docs/atlas-submission.md
```

**Critérios do Atlas** (só dois, e você atende os dois):

1. Ser especificamente construído para ou integrado ao Hermes Agent — sim, é uma
   interface de voz para o Hermes Agent, com `SKILL.md` no padrão agentskills.io.
2. Criado depois de 22 de julho de 2025 — sim.

Não há mínimo de estrelas no Atlas. Já `get-hermes.ai/community` e
`discoverhermes.com` exigem 50+ estrelas — deixe os dois para depois.

**Antes de postar, confirme:** o repositório está público, o CI está verde, há um
release com tag, e existe um GIF ou vídeo curto no README. Esse último importa
mais do que parece: o Atlas avalia por documentação, evidência de instalação,
manutenção e adoção, e uma demonstração é a evidência de instalação mais direta
que existe para uma ferramenta de voz.

Apague tudo acima desta linha antes de postar.

---

## handnewb/hermes-voice

**Voice-enabled personal assistant for Hermes Agent. Open mic with wake word,
fully local — no API keys, no accounts, 35 languages.**

https://github.com/handnewb/hermes-voice

### What it does

Talk to your Hermes agent the way you'd talk to a person. Say the wake word and
speak; the wake word opens a *session*, so follow-up turns need no repetition.
The session closes on its own when you stop talking.

```
you:     "Jarvis, what ran overnight?"
hermes:  "One hundred forty-seven thousand events. Three escalated."
you:     "detail the third"          ← no wake word needed
hermes:  "Connection to a domain registered eighteen hours ago. Isolated."
         ...20 seconds of silence...
                                      ← goes back to sleep
```

### Why it might be worth listing

**Runs entirely offline.** No API key, no account, no cloud provider. Speech
recognition (faster-whisper), voice activity detection (Silero), wake word
(openWakeWord) and speech synthesis (Piper, Kokoro-82M) all run locally. The only
address contacted at runtime is your own Hermes endpoint. Every other voice
assistant project I could find requires at least an OpenAI key and usually an
ElevenLabs one too.

**Adaptive turn-taking.** A fixed silence threshold doesn't work — 400 ms cuts you
off mid-thought, 1000 ms feels hesitant, because pause length carries meaning.
Instead of counting silence, it transcribes at a short threshold and checks
whether the sentence *looks finished*: "I want" waits, "what's the status?"
answers immediately.

**Barge-in without external dependencies.** Echo suppression in ~200 lines of
numpy: since we generate the output audio, we check whether any alignment of the
reference within a 320 ms window explains the microphone energy. If it does, it's
echo. Tested against synthetic echo across four delays and four room gains with
zero false positives.

**Presence DSP.** Much of what people recognise as "assistant voice" is
processing, not timbre: high-pass, compression, presence lift, short room reverb.
Five presets. No TTS ships this.

**Licensing done deliberately.** Apache-2.0 code. All default voices permit
commercial use (Piper MIT, Kokoro Apache-2.0). Voice cloning of real people is
explicitly unsupported, with the reasoning and the clean alternatives documented
in `docs/VOICE_LICENSING.md`.

### Category

Integrations, or developer tools. It's a tool that ships a `SKILL.md`, not a pure
skill and not a plugin.

### Repo state

- Apache-2.0
- 229 automated tests; none require audio hardware, GPU, network or API keys
- CI on Linux, Windows and macOS × Python 3.10–3.13; CodeQL; Gitleaks
- `SECURITY.md` with a documented privacy model and three guarantees enforced by
  construction (nothing transcribed while dormant, bounded pre-roll, buffer
  discarded on sleep)
- `docs/VERIFICATION.md` states plainly which parts have been executed on real
  hardware and which have not

That last file is unusual for a submission, and it's deliberate. I'd rather you
review an honest account than discover the gaps yourself.

### Language note

Documentation and the default persona are Brazilian Portuguese; the code,
architecture and voice catalog are language-agnostic. Voices are available in 35
languages via the Piper index and 9 via Kokoro. English README section at the top.
