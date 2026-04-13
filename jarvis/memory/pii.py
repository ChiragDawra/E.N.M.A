"""PII redaction (Vulnerability #7 cure, part 2)."""
from __future__ import annotations

import re

# Ordered most-specific → least-specific so `phone` (broad) does not
# cannibalize card / aadhaar numbers.
PII_PATTERNS: dict[str, re.Pattern[str]] = {
    "card":    re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b"),
    "aadhaar": re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b"),
    "ssn":     re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "email":   re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"),
    "phone":   re.compile(r"\+?\d[\d\s\-]{8,14}\d"),
}


def redact(text: str) -> str:
    if not text:
        return text
    # Apply most-specific patterns first (card before aadhaar).
    for kind, pat in PII_PATTERNS.items():
        text = pat.sub(f"[REDACTED-{kind.upper()}]", text)
    return text
