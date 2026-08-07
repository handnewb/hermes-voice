# Security Policy

## Reporting a vulnerability

Do not open a public issue. Use
[Security Advisories](https://github.com/handnewb/hermes-voice/security/advisories/new).

Response within 5 business days. If you don't hear back within that timeframe, open
an issue saying only that there's a pending advisory — no technical details.

Coordinated disclosure: 90 days or until a fix is published, whichever comes first.
Credit in CHANGELOG if you want it.

## Scope

This project continuously captures microphone audio, transcribes speech, talks to
an LLM endpoint, and plays audio. The surface that matters:

**In scope**
- Leakage of audio or transcription to disk, log, or network beyond what's configured
- Circumvention of the retention guarantees described in "Privacy model"
- Injection via transcribed text or via LLM response resulting in execution
- Credential exposure in logs, error messages, `--doctor` output, or crashes
- Dependency confusion, typosquatting in extras, or tampered release artifacts

**Out of scope**
- Vulnerabilities in third-party services (Picovoice, Azure, ElevenLabs) — report
  to them
- Wake word false positives or negatives (model quality)
- EDR blocking the process (EDR doing its job)

## Privacy model

Three guarantees implemented in `session.py`, by construction and not by
configuration — they can't be turned off by accident:

1. **In `DORMANT` state nothing is transcribed.** Frames only feed the wake word
   detector, which runs locally and produces no text.
2. **The pre-roll is a `deque` with a fixed `maxlen`** of 480 ms. There's a test
   that feeds 64 seconds of continuous audio and verifies that only 480 ms are
   retained.
3. **When returning to `DORMANT` the buffer is explicitly discarded.** Also
   tested, including the case where it was already in `DORMANT`.

Nothing touches disk unless you set `LOG_TRANSCRIPTS=1`, which is `0` by default
and appears as a warning in `--doctor`.

If `TTS_BACKEND` is `azure` or `elevenlabs`, the **text** of the response goes to
the provider. Your microphone audio never goes out in any configuration. Use Piper
to keep everything local — it's the default.

## Credentials

- `.env` is in `.gitignore`. Check before the first commit.
- `Config.redacted()` exists for logging and `--doctor`. There's a test that injects
  a known secret and fails if it appears in the output.
- Restrict the key at the provider: minimum scope, credit quota, IP allowlist.
- A third-party key with associated cost belongs in a vault, not in a text file.
  `.env` is for development.

## EDR detection surface

This project exhibits three behaviors that behavioral EDR engines legitimately
monitor for. There's nothing malicious here, but the observable behavior is
indistinguishable from spyware, and the alert is **expected**:

| Behavior | Risk | Mitigation |
|---|---|---|
| Global keyboard hook (`pynput`, `ptt` mode) | High — keylogger signature | `--trigger wake` or `--trigger console`. Neither installs a hook. |
| Continuous microphone capture (`wake` mode) | Medium | `--trigger console` only records on command |
| Native DLLs (ctranslate2, onnxruntime, CUDA) | Low | Usually just startup slowness |

Prefer switching trigger modes over requesting exclusions. Weakening the endpoint
posture to run a voice assistant is a bad trade.

## Supply chain

- Dependencies with explicit version ranges in `pyproject.toml`
- Weekly Dependabot for pip and GitHub Actions
- CodeQL with `security-extended`, weekly and on every PR
- Gitleaks in CI, across the entire history
- Releases via Trusted Publishing (OIDC), no API token in the repository

**Known gap:** actions are pinned to tags (`@v4`), not SHAs. Pinning to SHA is
more correct. To do:

```bash
pipx run pin-github-action .github/workflows/*.yml
```
