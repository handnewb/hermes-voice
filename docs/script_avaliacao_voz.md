# Voice evaluation script — Hermes/butler register (pt-BR)

Original text, written for this project. Not a transcribed movie dialog, which
means you can use it commercially, publish comparisons, and send it to a vendor
without liability.

**How to use.** Paste `script_avaliacao_voz.txt` (unannotated version) into
ElevenLabs, Azure Speech Studio, or Piper and generate with each candidate voice.
Listen in order. Then listen to just block 6 of each candidate in sequence — that's
where bad voices reveal themselves.

**What each block tests** is annotated below. Don't paste the titles: the TTS
reads.

---

## Block 1 — Opening and dry irony

Tests: base register, naturalness in short sentences, restrained humor rhythm. If
the voice sounds enthusiastic here, discard it.

> Good morning, sir. It's six forty-two. You slept four hours and nineteen
> minutes. I noted the number, but I won't comment on it.

## Block 2 — Report with spoken numbers

Tests: long numbers spelled out, which is what the persona actually produces.
Enumeration cadence without sounding like a list.

> Overnight the operations center processed one hundred forty-seven thousand
> events. Three were escalated and none required your attention. The rest closed
> on their own, as they should.

## Block 3 — Raw numbers, acronyms, and foreignisms

Tests: the TTS normalizer, not the persona. If the model fails here, you know you
need to pre-normalize in code before synthesizing.

> Compliance report: ISO 27001 requires annual review, LGPD sets no deadline, and
> the certificate expires on 12/03/2026. The dashboard shows 99.7% availability.
> The firewall playbook ran 1,482 times.

## Block 4 — Phonetic coverage

Tests: nasals (ã, õ, ãe), digraphs lh and nh, r in initial, medial, and coda
positions, sibilant sandhi. It's the most annoying block to listen to and the most
diagnostic.

> Tomorrow morning the work includes three meetings, a conference, and the board
> report. The information is already organized. There will be no exceptions, and
> you didn't ask, but I would answer that there will also be no delays.

## Block 5 — Alert and restrained urgency

Tests: whether the voice can sound urgent without raising pitch. Jarvis never
shouts.

> Sir, we have an anomaly. Station nine-four-two opened a connection to a domain
> registered eighteen hours ago. I preemptively isolated it. You can revert, but I
> wouldn't recommend it.

## Block 6 — Long subordinate sentence

Tests: prosody consistency under load, breath control, whether the voice degrades
at the end. This is where mediocre TTS falls apart.

> You asked me yesterday whether the identity flow automation could operate
> without human approval in standard cases, and the answer remains that it can, as
> long as the policy stays with whoever has the authority to answer for it, and
> not with me, because the distinction between operating and governing is the only
> thing that prevents this arrangement from becoming your problem.

## Block 7 — Confirmation of destructive action

Tests: weight and pause. Must sound like a brake, not a formality.

> Before proceeding. This will revoke the credentials of four hundred twelve
> users, and it is irreversible. I need your confirmation aloud.

## Block 8 — Refusal

Tests: firmness without hostility. The voice needs to be able to say no.

> No, sir. I don't read secrets aloud, even when you ask. The air in this room has
> no access control.

## Block 9 — Uncertainty

Tests: naturalness in a short, straight sentence, without artificial hesitation.

> I don't know, sir. I can look into it, but I won't invent to fill the silence.

## Block 10 — Questions and intonation

Tests: interrogative contour, which is where synthetic voices sound most fake.
Listen to all three in sequence.

> Detail? Do you want me to continue? Should I isolate the machine now?

## Block 11 — Closing

Tests: descending cadence, closure. Should sound like an end, not a cutoff.

> Good night, sir. I'll dim the lights and continue monitoring. If anything
> changes, you'll be the first to know. And if nothing changes, I won't wake you
> to say so.

---

## Judgment criteria

Listen in order and score from one to five. Discard any candidate that fails any
of the first three — the others are refinable, these aren't.

1. **Doesn't sound cheerful.** Eliminatory. Most commercial pt-BR voices are
   trained for customer service and come with a built-in smile.
2. **Handles block 6 without degrading.** Eliminatory.
3. **Can say no (block 8) without sounding aggressive or submissive.**
   Eliminatory.
4. Block 4 nasals clean, without metallic quality.
5. Block 3 normalized correctly, or at least predictably.
6. Block 10 questions with credible contour.
7. Timbre consistency between block 1 and block 11.

## After choosing

Timbre is half. The other half is processing — bass cut, compression, and a touch
of room reverb is what makes the voice sound like presence in the space rather than
voice-over. No TTS ships this out of the box. See `docs/ROADMAP.md`.
