"""Permission-tiered command sandbox (Vulnerability #3 cure).

The AI never executes arbitrary shell.  Instead it emits structured
`(tool_name, params)` pairs that are validated against an allowlist; each
tier gates on a different authentication mechanism.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable, Optional

from jarvis.auth import challenge as _challenge
from jarvis.auth import touch_id as _touch_id
from jarvis.security.rate_limiter import LIMITER
from jarvis.security.sanitizer import sanitize
from jarvis.tools import macos as _mac
from jarvis.utils.logging import log_command, log_security_event

PERMISSION_TIERS: dict[str, list[str]] = {
    "low": [
        "get_time", "get_battery", "control_volume", "control_brightness",
        "open_app", "control_spotify", "get_current_track",
        "toggle_dark_mode", "take_screenshot",
    ],
    "medium": [
        "send_imessage", "create_reminder", "search_web",
    ],
    "high": [
        # High-tier tools are wired up case-by-case so an LLM can't wander
        # into destructive surface area by accident.
        "touch_id_gate",
    ],
}

# Patterns that must NEVER appear in a tool's stringified params, regardless
# of which tool is being called.
BLOCKED_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE) for p in (
        r"\brm\s+-rf\b",
        r"\bsudo\b",
        r"\beval\s*\(",
        r"\bexec\s*\(",
        r"\bos\.system\s*\(",
        r"\bsubprocess\.(call|run|Popen)\s*\(",
        r"curl\s+[^|]+\|",
        r"\bwget\b",
        r">\s*/dev/",
        r"\bchmod\s+777\b",
        r"\bmkfs\b",
        r"\bdd\s+if=",
        r"\bkill\s+-9\b",
    )
)


def _tier_of(tool_name: str) -> Optional[str]:
    for tier, tools in PERMISSION_TIERS.items():
        if tool_name in tools:
            return tier
    return None


def _params_are_safe(params: dict[str, Any]) -> bool:
    blob = repr(params)
    return not any(p.search(blob) for p in BLOCKED_PATTERNS)


TOOL_REGISTRY: dict[str, Callable[..., Any]] = {
    "get_time": _mac.get_time,
    "get_battery": _mac.get_battery,
    "control_volume": _mac.control_volume,
    "control_brightness": _mac.control_brightness,
    "open_app": _mac.open_app,
    "control_spotify": _mac.control_spotify,
    "get_current_track": _mac.get_current_track,
    "toggle_dark_mode": _mac.toggle_dark_mode,
    "take_screenshot": _mac.take_screenshot,
    "send_imessage": _mac.send_imessage,
    "create_reminder": _mac.create_reminder,
    "search_web": _mac.search_web,
    "touch_id_gate": lambda reason="JARVIS": _touch_id.authenticate(reason),
}


@dataclass
class ExecutionContext:
    """Callbacks the sandbox needs when a tier requires user interaction."""
    speak: Callable[[str], None]
    listen: Callable[[float], str]


def _sanitize_params(params: dict[str, Any]) -> tuple[Optional[dict[str, Any]], Optional[str]]:
    clean: dict[str, Any] = {}
    for k, v in params.items():
        if isinstance(v, str):
            cleaned, err = sanitize(v)
            if err:
                return None, f"param '{k}' rejected: {err}"
            clean[k] = cleaned
        else:
            clean[k] = v
    return clean, None


def execute_tool(
    tool_name: str,
    params: dict[str, Any] | None = None,
    ctx: Optional[ExecutionContext] = None,
    speaker_verified: bool = False,
) -> tuple[bool, Any]:
    """Attempt to run a named tool.  Returns (ok, result_or_error_string)."""
    params = dict(params or {})
    tier = _tier_of(tool_name)
    if tier is None:
        log_security_event("unknown_tool", tool_name)
        return False, f"tool '{tool_name}' is not allowed"

    if not _params_are_safe(params):
        log_security_event("blocked_pattern", f"{tool_name} {params!r}")
        return False, "dangerous pattern in parameters"

    clean, err = _sanitize_params(params)
    if err:
        return False, err
    params = clean or {}

    if not LIMITER.check_all(f"tool_{tier}"):
        return False, "rate limit exceeded"

    # Tier gating
    if tier == "medium":
        if ctx is None:
            return False, "medium-tier tools require interactive confirmation"
        if not _challenge.voice_confirm(ctx.speak, ctx.listen):
            log_command(tool_name, params, "cancelled", speaker_verified)
            return False, "cancelled by user"
    elif tier == "high":
        if ctx is None:
            # fall back to Touch ID if available
            if not _touch_id.authenticate():
                log_command(tool_name, params, "auth-failed", speaker_verified)
                return False, "authentication failed"
        else:
            if not _challenge.challenge(ctx.speak, ctx.listen):
                log_command(tool_name, params, "auth-failed", speaker_verified)
                return False, "authentication failed"

    fn = TOOL_REGISTRY[tool_name]
    try:
        result = fn(**params)
    except TypeError as e:
        return False, f"bad arguments: {e}"
    except Exception as e:  # pragma: no cover - best-effort runtime guard
        log_command(tool_name, params, f"exception:{e}", speaker_verified)
        return False, f"tool failed: {e}"
    log_command(tool_name, params, result, speaker_verified)
    return True, result


def all_tools() -> list[str]:
    return sorted(TOOL_REGISTRY.keys())
