"""Challenge-response auth (Vulnerability #2 cure, Layer 2 & Vulnerability #3).

For high-risk actions JARVIS speaks a random 3-digit code and requires it
back.  This defeats pre-recorded replay attacks.
"""
from __future__ import annotations

import secrets
from typing import Callable


def _normalize_digits(text: str) -> str:
    return "".join(c for c in text if c.isdigit())


def challenge(
    speak: Callable[[str], None],
    listen: Callable[[float], str],
    timeout_s: float = 10.0,
) -> bool:
    """Ask a random 3-digit code; return True iff the user says it back."""
    code = f"{secrets.randbelow(900) + 100:03d}"
    speak(f"Security check. Please say: {code}")
    try:
        reply = listen(timeout_s) or ""
    except Exception:
        return False
    return code in _normalize_digits(reply)


def voice_confirm(
    speak: Callable[[str], None],
    listen: Callable[[float], str],
    prompt: str = "Shall I proceed?",
    timeout_s: float = 6.0,
) -> bool:
    """Medium-tier 'are you sure?' gate. Accepts yes / yeah / confirm / ok."""
    speak(prompt)
    try:
        reply = (listen(timeout_s) or "").lower()
    except Exception:
        return False
    return any(w in reply for w in ("yes", "yeah", "yep", "confirm", "ok", "go ahead", "do it"))
