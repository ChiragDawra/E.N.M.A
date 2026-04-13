#!/usr/bin/env bash
set -euo pipefail

# JARVIS first-run setup.  Creates a venv, installs pinned dependencies,
# and walks through Keychain-backed secret storage.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [ ! -d .venv ]; then
  echo "[1/4] Creating virtualenv at .venv"
  python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

echo "[2/4] Upgrading pip and installing requirements"
python -m pip install --upgrade pip --quiet
python -m pip install -r requirements.txt

echo "[3/4] Storing API keys in macOS Keychain (press Enter to skip any)"
python -m jarvis setup

echo "[4/4] Done."
cat <<'NOTE'

Next steps:
  • Enroll your voice:    python -m jarvis enroll
  • Smoke test (no mic):  python -m jarvis text "what time is it"
  • Full voice loop:      python -m jarvis run
  • Web UI (TLS):         python -m jarvis serve  →  https://127.0.0.1:8443/health

For a custom "hey jarvis" wake-word model (optional), train one on the
free Colab notebook:
  https://colab.research.google.com/drive/1q1oe2zOyZp7UsB3jJiQ1IFn8z5YfjwEb
…and drop the .onnx file into models/hey_jarvis.onnx.
NOTE
