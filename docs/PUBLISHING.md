# Publishing runbook

Executable instructions for publishing this project. Written to be handed to an
agent, but human-readable.

**Order matters.** Steps 0 and 1 are blocking: once the public history exists,
fixing a leak requires rewriting history, and by then someone may have already
cloned.

---

## 0. Decisions that need answers before any command

Don't proceed without all four.

| Decision | Default in this repo | Where to change |
|---|---|---|
| Repository name | `hermes-voice` | `pyproject.toml`, `README.md`, all URLs |
| GitHub handle | `handnewb` | Same — 14 occurrences |
| License | Apache-2.0 | `LICENSE`, `pyproject.toml` |
| Publish to PyPI? | No (job disabled) | `.github/workflows/release.yml`, `if: false` |

To change handle or repo name in one go:

```bash
grep -rl 'handnewb/hermes-voice' --include='*.md' --include='*.toml' --include='*.yml' . \
  | xargs sed -i 's|handnewb/hermes-voice|YOUR_HANDLE/YOUR_REPO|g'
```

Check the result before committing:

```bash
grep -rn 'handnewb' . --include='*.md' --include='*.toml' --include='*.yml' | grep -v '\.git/'
```

### About the name

This repository is deliberately called `hermes-voice`, not something derived from a
franchise character. `jarvis` appears only as the **default configuration value**
for the wake word, because it's a native keyword of Porcupine.

The distinction is defensible: a user preference in a config file is not branding.
Naming the project and its promotional material after a franchise character is
another matter, and the exposure grows when the repository is public, associated
with your name and your company.

If you want to name it differently regardless, use the `sed` above and avoid
franchise references in the name, description, topics, and screenshots.

---

## 1. Leak check — BLOCKING

Run everything. Each command must come up empty.

```bash
# a) secrets and keys
grep -rniE '(api[_-]?key|secret|token|password|bearer)\s*[:=]\s*["'"'"']?[A-Za-z0-9_\-]{16,}' \
  . --include='*.py' --include='*.md' --include='*.yml' --include='*.toml' --include='*.ps1' --include='*.sh'

# b) real .env not tracked
test -f .env && echo "WARNING: .env exists locally -- confirm it's in .gitignore"
git check-ignore -v .env 2>/dev/null || echo "FAIL: .env is NOT ignored"

# c) internal names, clients, products, security vendors
grep -rniE 'oplium|tessera|motiva|senhasegura|cyberark|sentinelone|fortiedr|crowdstrike' . \
  --exclude-dir=.git

# d) private IP, internal host, connection string
grep -rnE '(10\.[0-9]+\.[0-9]+\.[0-9]+|192\.168\.|172\.(1[6-9]|2[0-9]|3[01])\.)' . --exclude-dir=.git
grep -rniE '\.(corp|internal|local|intra)\b' . --exclude-dir=.git

# e) audio and transcription
find . -name '*.wav' -o -name '*.mp3' -o -name 'transcripts.log' | grep -v '\.git/'
```

If **(c)** returns anything, stop and clean before any commit. A client name in a
public repository is the quietest way to leak a consultancy's client list, and an
EDR vendor name discloses the publisher's defensive posture.

Then, automated scan:

```bash
pipx run detect-secrets scan > /tmp/secrets.json && python -c "
import json; d=json.load(open('/tmp/secrets.json'))
print('FINDINGS:', d['results'] or 'none')"
```

---

## 2. Quality check

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"

ruff check .                    # must pass
ruff format --check .           # must pass
pytest -q                       # 128 tests, all green
python -m build                 # generates sdist and wheel
pipx run twine check dist/*     # valid metadata
hermes-voice --doctor           # audio blockers expected in a container
```

If `ruff format --check` complains, run `ruff format .` and commit together.

---

## 3. Clean history from the first commit

Configure identity and signing **before** the first commit. Fixing later requires
rewriting history.

```bash
git init -b main

# Email: use GitHub's no-reply to avoid exposing personal email in public history.
# The number comes from github.com/settings/emails
git config user.name  "Your Name"
git config user.email "ID+handle@users.noreply.github.com"

# SSH signing — simpler than GPG and equally valid
git config gpg.format ssh
git config user.signingkey ~/.ssh/id_ed25519.pub
git config commit.gpgsign true
git config tag.gpgsign true
```

Register the public key as a **Signing Key** at github.com/settings/keys, in
addition to the Authentication Key. They are separate entries; the authentication
key alone won't make the "Verified" badge appear.

```bash
git add .
git status --short          # review the ENTIRE list before committing
git commit -m "feat: conversational voice interface in pt-BR for Hermes Agent

Open microphone with wake word, VAD end-of-speech, and session that
closes on its own. Chained pipeline with per-sentence streaming.

- 3 trigger modes: wake, console, and push-to-talk
- 4 TTS backends: ElevenLabs, Azure, Piper Python, and Piper binary
- Presence DSP stage with 5 presets
- Self-diagnostic via --doctor
- 128 tests, none requiring audio, GPU, network, or API key"

git log --show-signature -1 | head -5   # confirm the signature
```

---

## 4. Create the repository

```bash
gh auth status || gh auth login

gh repo create hermes-voice --public --source=. --remote=origin \
  --description "Voice-enabled personal assistant for Hermes Agent. Open mic with wake word, fully local - no API keys, no accounts, 35 languages." \
  --push
```

Topics — the main discovery vector:

```bash
gh repo edit --add-topic hermes-agent,nous-research,voice-assistant,speech-to-text \
  --add-topic text-to-speech,wake-word,whisper,piper-tts,kokoro,vad \
  --add-topic offline-first,local-first,python,portuguese
```

Repository configuration:

```bash
gh repo edit --enable-issues --enable-discussions \
  --delete-branch-on-merge --enable-squash-merge \
  --enable-merge-commit=false --enable-rebase-merge=false
```

Enable security features in Settings → Code security, or:

```bash
gh api -X PATCH repos/:owner/:repo --field security_and_analysis[secret_scanning][status]=enabled
gh api -X PATCH repos/:owner/:repo --field security_and_analysis[secret_scanning_push_protection][status]=enabled
```

**Push protection is the most important item** — it blocks the commit containing a
secret before it leaves your machine, instead of warning you afterward.

### Collaboration rules

Apply after the first green CI. The important detail: **these are the stage 0
rules**, for one maintainer. `GOVERNANCE.md` says what to add at each stage and
which trigger opens the next one — don't apply stage 1 before you have
contributors, because mandatory approval with one person is self-approval.

```bash
# Squash merge only: one commit per change, usable git bisect
gh repo edit --enable-squash-merge \
  --enable-merge-commit=false --enable-rebase-merge=false \
  --delete-branch-on-merge

# Repository-level auto-merge: author marks it, merge goes out when CI closes.
# This is what avoids a queue waiting for someone to wake up.
gh api -X PATCH repos/:owner/:repo -f allow_auto_merge=true

# Main branch protection — stage 0
gh api -X PUT repos/:owner/:repo/branches/main/protection --input - <<'JSON'
{
  "required_status_checks": {"strict": true, "contexts": ["lint", "build"]},
  "enforce_admins": false,
  "required_pull_request_reviews": null,
  "restrictions": null,
  "required_linear_history": true,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "required_conversation_resolution": true
}
JSON
```

`enforce_admins: false` is deliberate in stage 0: with one maintainer, a locked
admin only creates a situation where nobody can fix broken `main`. It becomes
`true` in stage 2.

**Stage 1** (two recurring contributors, or the first PR on a protected path) —
swap the `required_pull_request_reviews` block for:

```json
{"required_approving_review_count": 1,
 "require_code_owner_reviews": true,
 "dismiss_stale_reviews": true}
```

And, at the same time, require manual CI approval for new accounts — this is the
defense against malicious workflow from a fork:

```
Settings > Actions > General > Fork pull request workflows
  -> "Require approval for first-time contributors"
```

### Labels

Few and used beats many and ignored.

```bash
GH_TOKEN=$(gh auth token) pipx run github-label-sync \
  --access-token "$GH_TOKEN" --labels .github/labels.yml OWNER/REPO
```

Two deserve attention: **`audio-privacy`** marks anything touching capture,
retention, or transmission of audio, and these require an issue before code.
**`unverified`** marks areas listed in `docs/VERIFICATION.md` as never executed —
this is the label that will get the most issues in the first weeks.

### Dependabot auto-merge

`.github/workflows/auto-merge.yml` merges dev tool bumps when CI is green, and
labels the rest as `manual-review`. No runtime or major dependency goes in
automatically.

It runs on `schedule` and not `pull_request_target`, even though the latter is the
widespread default. The reason is in the file's comment: the project has an
absolute rule against that trigger, and a rule the author themselves bypasses
ceases to be a rule — the next person copies the pattern and checks out the PR
code, which is where the vulnerability lives.

Confirm it exists and runs:

```bash
gh workflow list
gh workflow run "Dependabot auto-merge"    # manual test
```

## 5. Release

```bash
gh workflow list                       # confirm CI passed
gh run watch

git tag -s v1.0.0 -m "v1.0.0 -- first public release"
git push origin v1.0.0                 # triggers release.yml
gh release view v1.0.0
```

---

## 6. Submit to Hermes Atlas

Curated catalog, with security review before inclusion and weekly curation.
So: the repository needs to be good **beforehand**, and the submission is a
request.

### There are two criteria

1. Be specifically built for or integrated with Hermes Agent.
2. Have been created after July 22, 2025.

You meet both. **There is no minimum star count on the Atlas**, and that's the
detail that matters: the other two ecosystem directories (`get-hermes.ai/community`
and `discoverhermes.com`) require 50 stars. Start with the Atlas; the others come
later, with traction.

### Before opening the issue: record the demo

The Atlas evaluates by documentation, installation evidence, maintenance, and
adoption signals. Of the four, the only one you control immediately is
**installation evidence** — and it's precisely the weak point, because
`docs/VERIFICATION.md` says candidly that the audio path has never been executed.

Run the manual verification script from `VERIFICATION.md`, fix what breaks, and
then record:

```bash
pipx run asciinema rec demo.cast --overwrite
#   hermes-voice --doctor
#   hermes-voice voices --lang en
#   hermes-voice --verbose      (speak a few sentences)
# Ctrl+D to end
pipx run asciinema upload demo.cast
```

For a voice tool the ideal is **audio**: thirty seconds where you hear the
conversation are worth more than any paragraph, and that's what decides the star.
Put it at the top of the README.

### The submission

It's an issue with the repository URL. The body is already written in
`docs/atlas-submission.md` — delete the instruction header before posting, it's
marked.

```bash
gh repo view ksimback/hermes-ecosystem     # confirm the current path first

gh issue create --repo ksimback/hermes-ecosystem \
  --title "Add: handnewb/hermes-voice — voice-enabled personal assistant" \
  --body-file docs/atlas-submission.md
```

Community project processes change. If there's a `CONTRIBUTING.md` there describing
another format, follow theirs instead.

**Likely category:** integrations, or developer tools. It's not a pure skill or a
plugin — it's a tool that ships a `SKILL.md`.

### Publish SKILL.md as a skill

Independent of the Atlas, the `SKILL.md` follows the agentskills.io standard:

```bash
hermes skills publish        # confirm syntax with: hermes skills --help
```

## 7. After publishing

In the first week:

- [ ] Read `GOVERNANCE.md` and confirm stage 0 rules are applied

- [ ] Respond to every issue within 48 h, even if only to say you saw it
- [ ] Add a GIF or short video at the top of the README — for a voice tool,
      hearing is worth more than any paragraph, and that's what decides the star
- [ ] Check CI on Windows: that's where `piper-phonemize` and cuDNN break, and
      where you won't reproduce locally if you develop on Linux
- [ ] Pin actions to SHA: `pipx run pin-github-action .github/workflows/*.yml`
- [ ] Enable Dependabot alerts if not already on

What **not** to do: promise AEC with a date. It's the most requested and hardest
item, and the roadmap is already honest about it.

---

## Final checklist

```
[ ] Step 1 entirely clean — especially (c), internal names
[ ] .env ignored, confirmed with git check-ignore
[ ] ruff, pytest, and build clean
[ ] First commit signed, with no-reply email
[ ] Handle and repo name replaced in all URLs
[ ] Secret scanning and push protection enabled
[ ] Squash-only, repository auto-merge, stage 0 main protection
[ ] Labels synced from .github/labels.yml
[ ] CI green on all three OSes before the tag
[ ] Tag signed, release published
[ ] VERIFICATION.md manual verification script executed
[ ] Demo recorded and at the top of the README
[ ] Atlas submission only after everything above
```
