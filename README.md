# JARVIS — Security-Hardened Voice Assistant for macOS

A local-first voice assistant built around the 12 vulnerabilities and cures
identified in `jarvis_vulnerability_cures.jsx`. Every cure is implemented as
a dedicated module.

| # | Vulnerability | Module |
|---|---|---|
| 1 | No voice authentication | `jarvis.auth.voice` (Resemblyzer) |
| 2 | Replay attacks | `jarvis.auth.liveness`, `jarvis.auth.challenge` |
| 3 | Unsandboxed command exec | `jarvis.tools.sandbox` (3-tier allowlist) |
| 4 | Plaintext API keys | `jarvis.utils.secrets` (macOS Keychain) |
| 5 | No rate limiting | `jarvis.security.rate_limiter` |
| 6 | No input sanitization | `jarvis.security.sanitizer` |
| 7 | Unencrypted memory | `jarvis.memory.store` (Fernet + PII redact) |
| 8 | No TLS | `jarvis.server.app` + `jarvis.server.tls` (auto self-signed) |
| 9 | Wake-word false positives | `jarvis.audio.wake_word` (+ voice-auth gate) |
| 10 | No audit logging | `jarvis.utils.logging` (loguru, rotating) |
| 11 | Dependency CVEs | `requirements.txt` pinned + `pip-audit` |
| 12 | Face-auth spoofing | `jarvis.auth.touch_id` (voice+Touch ID instead) |

## Quick start

```bash
# One-shot setup (venv + deps + Keychain prompts)
./scripts/setup.sh

# Smoke test — no mic, no API keys, pure Python
python -m jarvis text "what time is it"

# Enroll your voice (records ~8 s)
python -m jarvis enroll

# Full voice loop
python -m jarvis run

# Localhost TLS web UI (auto-generates a self-signed cert in data/)
python -m jarvis serve      # https://127.0.0.1:8443/health

# Connect MCP servers (optional — see data/mcp_servers.json)
python -m jarvis mcp
```

## Security model

Every command that reaches the sandbox passes **three gates** before execution:

1. **Liveness** — spectral analysis rejects replayed audio.
2. **Voice auth** — Resemblyzer cosine similarity ≥ 0.85.
3. **Tier gate** — LOW auto-runs, MEDIUM asks for voice confirm, HIGH demands
   a random challenge-response *or* macOS Touch ID.

Raw shell access is never exposed to the LLM. The brain emits
`{"tool": ..., "params": ...}` JSON that is validated against an allowlist.

## Layout

```
jarvis/
  core/         config & orchestrator
  audio/        wake word, recorder, STT, TTS
  auth/         voice, liveness, challenge, Touch ID
  brain/        Claude / Gemini / Ollama routing
  memory/       encrypted SQLite + PII redaction
  security/     rate limiter, sanitizer
  server/       FastAPI + self-signed TLS
  tools/        sandbox + audited macOS helpers + MCP client
  utils/        Keychain secrets, loguru logging
scripts/        setup.sh
tests/          pytest suite (30 tests, bandit-clean)
```

## Running security scans

```bash
pip-audit -r requirements.txt
bandit -r jarvis/
pytest -q
```

## License

MIT. See source headers.
