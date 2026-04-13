"""Input sanitization (Vulnerability #6 cure).

Rejects text that matches SQL-injection, shell-injection, path-traversal,
or Python-eval patterns. All DB code must still use parameterized queries.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Optional

from jarvis.utils.logging import log_security_event

MAX_LEN = 500

_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f-\x9f]")

INJECTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)\b(drop|delete|update|insert|alter|truncate)\s+(table|database|from)"),
    re.compile(r"(?i)('\s*(or|and)\s*'?\d*\s*=\s*\d*)"),
    re.compile(r"(?i)(;\s*(rm|del|format|shutdown|kill|mkfs|dd)\b)"),
    re.compile(r"\.\.[\\/]"),
    re.compile(r"(?i)(\beval\s*\(|\bexec\s*\(|__import__|import\s+os\s*;|subprocess\.)"),
    re.compile(r"[;|&`$]"),
    re.compile(r"<\s*script", re.IGNORECASE),
)


def sanitize(text: str | None) -> tuple[Optional[str], Optional[str]]:
    """Return (clean_text, error).  If error is not None, reject the input."""
    if not text:
        return None, "empty input"
    text = unicodedata.normalize("NFKC", text)
    if len(text) > MAX_LEN:
        return None, "input too long"

    text = _CONTROL_CHARS.sub("", text).strip()
    if not text:
        return None, "empty after cleaning"

    for pat in INJECTION_PATTERNS:
        if pat.search(text):
            log_security_event("injection_attempt", text)
            return None, "suspicious input detected"
    return text, None
