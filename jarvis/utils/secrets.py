"""Keychain-backed secret store (Vulnerability #4 cure).

API keys live in the macOS Keychain, never on disk. First use prompts the
user; subsequent launches read transparently.
"""
from __future__ import annotations

import getpass
import os
from typing import Optional

try:
    import keyring
except ImportError:  # pragma: no cover - keyring is a hard dep at runtime
    keyring = None  # type: ignore[assignment]

from jarvis.core.config import CONFIG


def _require_keyring() -> None:
    if keyring is None:
        raise RuntimeError(
            "The 'keyring' package is required. Install with: pip install keyring"
        )


def get_secret(name: str, prompt: bool = True) -> Optional[str]:
    """Return a secret from Keychain, prompting once if missing.

    Env-var override (useful for CI): JARVIS_<NAME_UPPER>.
    """
    env_key = f"JARVIS_{name.upper()}"
    if env_key in os.environ:
        return os.environ[env_key]

    _require_keyring()
    value = keyring.get_password(CONFIG.keychain_service, name)
    if value is None and prompt:
        value = getpass.getpass(f"Enter value for '{name}' (stored in Keychain): ").strip()
        if value:
            keyring.set_password(CONFIG.keychain_service, name, value)
    return value or None


def set_secret(name: str, value: str) -> None:
    _require_keyring()
    keyring.set_password(CONFIG.keychain_service, name, value)


def delete_secret(name: str) -> None:
    _require_keyring()
    try:
        keyring.delete_password(CONFIG.keychain_service, name)
    except Exception:
        pass
