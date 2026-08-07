# Governance

How decisions are made, who can do what, and when each layer of process kicks in.

## The principle

**Process is added when pain appears, not before.**

A project with one maintainer and zero contributors that requires two approvals and
three reviewers is theater: the maintainer approves themselves, the ritual catches
nothing, and the first contributor gives up on the third round of bureaucracy. This
is stiffening without gaining robustness.

On the other hand, a project that records audio and downloads models needs real
guardrails where it matters. The solution isn't choosing between robust and lean —
it's being strict on a small set of paths and loose on the rest.

This document is organized by **stage**. Each stage lists what holds now and the
trigger that opens the next one. Don't skip stages out of anticipation.

---

## Current stage: 0 — one maintainer

What holds today.

**Everything goes through a pull request, including from the maintainer.** Not out
of ceremony: it's what ensures CI always runs and the history stays reviewable.
Direct push to `main` is blocked.

**No approval requirement.** With one person, approval is self-approval. What
protects is green CI, not a signature.

**Squash merge, always.** One commit per change on `main`, descriptive message,
usable `git bisect`. Merge commit and rebase are disabled.

**Mandatory gate:** green `lint` and `build`. Failure in either blocks.

### Trigger for stage 1

Two people besides the maintainer with an accepted pull request, or the first
contribution touching a protected path.

---

## Stage 1 — recurring contributors

Adds:

- **One mandatory approval**, from someone who isn't the author.
- **Active `CODEOWNERS`** on protected paths (list below).
- **Triage role** for frequent contributors — not Write.
- **Manual CI approval for first contribution** from a new account. This is the
  defense against malicious workflow from a fork.

### Trigger for stage 2

A second maintainer with merge rights, or an issue volume one person can't triage
in 48 h.

---

## Stage 2 — more than one maintainer

Adds:

- `MAINTAINERS.md` with names, areas, and timezone.
- **Two approvals** for protected paths; one for the rest.
- Release rotation, so there's no single-person dependency.
- Decision by simple consensus; persistent deadlock goes to whoever has maintained
  the longest. Recorded in the issue, not in private conversation.

---

## GitHub roles, and what each can do

Permission grants are irreversible in practice: removing someone's access is
socially expensive, so grant slowly.

| Role | Can | When to grant |
|---|---|---|
| **Read** (public) | Fork, pull request, issue, discussion | Automatic. Enough to contribute. |
| **Triage** | Label, close, and assign issues; no code write | After 1–2 accepted PRs. Low risk, real relief. GitHub's most underused role. |
| **Write** | Push to branch, merge PR | After 3+ accepted PRs, including one on a protected path. Only with history. |
| **Maintain** | Non-sensitive settings | De facto second maintainer. |
| **Admin** | Everything, including deleting the repository | Only the owner. |

**Contributing requires no permission.** Fork plus pull request covers 100% of
cases, and that's how it should be: newcomers don't need to ask for access — they
need to open a PR.

---

## Protected paths

These require closer review, and in stage 1 enter `CODEOWNERS`. It's not about
trust in the person — it's about what the change can cause.

| Path | Why |
|---|---|
| `src/hermes_voice/session.py` | Contains the three privacy guarantees. A change here can make the project transcribe what it shouldn't, without anything appearing wrong. |
| `src/hermes_voice/audio.py` | Microphone capture and buffer limits. |
| `src/hermes_voice/echo.py` | Output audio reference buffer. |
| `.github/workflows/**` | **Classic attack vector.** An altered workflow can exfiltrate secrets, publish a fake release, or inject code into the artifact. Treat as the most sensitive file in the repository. |
| `pyproject.toml` | A new dependency is a supply chain decision. |
| `docs/persona.md`, `src/hermes_voice/data/persona.md` | Defines the assistant's behavior, including confirming destructive actions. |

### Rules that don't yield to stage

Independent of how many people maintain the project:

1. **Never `pull_request_target` in a workflow.** That trigger gives secrets to
   code coming from a fork. If someone needs something only it solves, the answer is no.
2. **No new dependency without written justification in the PR.** This project
   records audio; the trust budget is tight.
3. **Changes to audio capture, retention, or transmission require an issue before
   code.** See `CONTRIBUTING.md`.
4. **Real-person voice cloning does not enter.** See `docs/VOICE_LICENSING.md`.
5. **Never a secret in a PR workflow variable.** Publishing uses Trusted Publishing
   via OIDC, no token in the repository.

---

## What prevents the project from stiffening

Robustness without friction requires the boring things to run on their own.

**Dependabot with auto-merge** for patch and minor dev tool updates when CI passes.
Major and runtime dependencies stay manual. Without this, the maintainer spends
their energy on version bumps instead of code.

**A single mandatory gate: green CI.** No manual checklist, no committee approval,
no "awaiting architecture review".

**Auto-merge available for any PR.** Author marks it, and the merge happens when CI
closes. Nobody waits for someone to wake up.

**Response in 48 h, even if only to say it was seen.** What kills contribution
isn't rejection — it's silence.

**Declared scope.** `docs/ROADMAP.md` says what's in the plan and what isn't, with
honest effort estimates. A contributor who knows where to help doesn't need to ask.

**Rejection comes with a reason and an alternative.** "This won't go in because X;
what would solve your case is Y."

---

## Versioning and release

SemVer. In this phase, `main` is always publishable and a release goes out when
there's a reason, not on a calendar.

Breaking changes require: an entry in `CHANGELOG.md` under `### Changed`, a
migration path in the text, and a major bump. A removed environment variable
continues to be read for one minor version, with a warning.

---

## How to become a maintainer

There's no form. The path is the normal one: consistent contributions, useful
review on other people's PRs, and willingness to maintain what you wrote. The
invitation comes from whoever already maintains, and is recorded in a public issue.

Leaving is also normal and isn't abandonment. Open an issue, and the line in
`MAINTAINERS.md` comes out. Preferable to keeping the name of someone who no longer
responds — that misleads those who trust the project.

---

## Conduct

[`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md), Contributor Covenant 2.1, unmodified.
Reporting via private advisory.
