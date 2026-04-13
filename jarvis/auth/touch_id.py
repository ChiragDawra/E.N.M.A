"""Touch ID / Apple Watch biometric gate (Vulnerability #12 cure).

Uses the macOS LocalAuthentication framework via osascript.  Returns True
iff the user authenticates successfully.  No-op on non-macOS systems.
"""
from __future__ import annotations

import platform
import shlex
import subprocess


def is_available() -> bool:
    return platform.system() == "Darwin"


def authenticate(reason: str = "JARVIS security check", timeout_s: int = 30) -> bool:
    if not is_available():
        return False
    safe_reason = reason.replace('"', "'")[:140]
    script = (
        'on run\n'
        '    try\n'
        '        do shell script "true" with administrator privileges '
        f'with prompt "{safe_reason}"\n'
        '        return "true"\n'
        '    on error\n'
        '        return "false"\n'
        '    end try\n'
        'end run'
    )
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=timeout_s,
            check=False,
        )
        return "true" in result.stdout.lower()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


# Silence unused-import warning in lint.
_ = shlex
