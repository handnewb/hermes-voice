# Voice, rights, and what this project supports

This document exists because the question always comes up: *"can I use the voice of
[character / actor / voice actor]?"* The short answer is that it depends on who
owns the voice, and it's almost never you. The long answer is below, with the paths
that work.

This is not a legal opinion. It's a summary of the landscape for you to discuss
with someone who can give one, if needed.

---

## What comes ready

Five pt-BR voices, all free, all with licenses permitting commercial use:

```bash
hermes-voice voices                          # lists and shows what's installed
hermes-voice voices --install pm_alex        # download
hermes-voice --voice pm_alex                 # use
```

| Voice | Engine | Weights license | Commercial |
|---|---|---|---|
| `pt_BR-faber-medium` | Piper | MIT | yes |
| `pt_BR-edresson-low` | Piper | MIT | yes |
| `pm_alex` | Kokoro-82M | Apache-2.0 | yes |
| `pm_santa` | Kokoro-82M | Apache-2.0 | yes |
| `pf_dora` | Kokoro-82M | Apache-2.0 | yes |

None require an account, API key, or accepting terms of use. None of them mimic a
real identifiable person.

**Kokoro does not do cloning** — they are fixed preset voices. Piper doesn't
either. This is a choice of this project, not an accidental limitation.

---

## If you want a different timbre

In order of effort, and all three are clean:

### 1. Adjust the processing, not the voice

Probably the most underestimated path. Much of what people identify as "the sci-fi
assistant voice" isn't in the timbre — it's in the processing. A free male voice
plus `--dsp intercom` gets surprisingly close, and costs zero.

```bash
hermes-voice --voice pm_alex --dsp intercom
```

Try the five presets before concluding you need another voice.

### 2. Record your own voice

You are the rights holder of your own voice. A reference-based synthesis backend
(see below) synthesizes from a short sample of yours. This is legitimate, common,
and the result is yours.

### 3. Hire or license

Voice acting and narration are professions. Voice actors do commercial sessions,
and there's a growing market for voice licensing for AI use — in part, precisely
because unauthorized cloning has become a problem for the profession.

If you want a few system phrases, it's a short studio session, not a perpetual
synthetic voice license. Voice agencies have voice banks with ready licensing.
The result is exclusive, documented, and you can show it to anyone.

---

## The legal landscape

Four independent layers. Authorization in one doesn't cover the others.

### Personality rights

In Brazil, art. 20 of the Civil Code deals with unauthorized use of a person's
image and attributes. Voice is recognized as a personality attribute, and
protection does not depend on registration or on the person being famous. Art. 21
protects private life.

In the United States there's the *right of publicity*, which varies by state;
there are specific precedents on vocal imitation in advertising. In the European
Union protection comes from national personality rights plus GDPR.

### Performer's related rights

A voice actor or narrator has rights over the **performance**, separate from the
rights over the script or the work. In Brazil this is in Law 9,610/98. Licensing
the work does not license the performance, and vice versa.

Practical consequence: even if a recording is publicly available, the performer
retains rights over it.

### Voice as biometric data

Under LGPD, biometric data is sensitive personal data. Voice identifies a person,
and a reference sample for cloning constitutes processing of sensitive data —
which requires a legal basis, typically specific and highlighted consent. GDPR
treats it equivalently when voice is used to uniquely identify someone.

This applies even to home use in some interpretations, and certainly to anything
that leaves your machine.

### Trademark

Character names and product names can be registered trademarks, which is
independent of everything above. Trademark protects source identification: the
problem is suggesting affiliation or endorsement that doesn't exist. Famous
trademark holders tend to actively defend theirs in the category they operate in,
and there are known cases of AI products that had to be renamed because of this.

If you rename a fork of this project, it's worth researching the trademark before
building an audience. Renaming later costs stars, links, and SEO. Choosing well
beforehand costs nothing.

---

## What this project supports, and what it doesn't

**Supports:** the five catalog voices; prosody and DSP tuning; reference-based
synthesis for your own voice or a voice you have the right to use.

**Does not support, and will not be accepted in contributions:** instructions,
tools, or features aimed at reproducing the voice of an identifiable real person
without their authorization. This applies to voice actors, narrators, public
figures, and people you know, and applies equally to home use.

The reason is simple: a liability disclaimer transfers risk between the publisher
and the user, and does nothing for the person whose voice is at stake — who is the
affected party and participates in no agreement.

If you decide to follow another path in your own fork, the decision and the
responsibility are yours. This document exists so that decision is informed.

---

## Note on XTTS-v2

XTTS-v2 is the most well-known open-source option for reference-based synthesis,
and it makes sense to consider it. Two points first:

**Weights license.** The model is distributed under the Coqui Public Model License,
which **restricts commercial use**. This is not covered by the Apache-2.0 license
of this project. If you embed XTTS in a commercial product assuming the
repository's license covers everything, the assumption is wrong. That's why it's
not in the default path.

**Weight.** Requires PyTorch, on the order of 2.5 GB, against 63 MB for Piper and
327 MB for Kokoro. Goes against the goal of working out of the box.

Coqui, the original company, ceased operations; development continues in a
community fork. If you want to use it anyway:

```bash
pip install "hermes-voice[xtts]"
hermes-voice --tts xtts --reference my_voice.wav
```

The backend prints the license restriction on load, in the terminal — not just
here in the documentation. Use with your own voice.

---

## Summary

| You want | Do |
|---|---|
| Just work | Nothing. `pt_BR-faber-medium` comes ready. |
| Better free quality | `hermes-voice voices --install pm_alex` |
| Character, room presence | `--dsp room` or `--dsp intercom` |
| Your own voice | `xtts` extra, with the license caveat |
| A specific person's timbre | Hire or license. That's the only clean path. |
