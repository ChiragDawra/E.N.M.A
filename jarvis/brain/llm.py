"""LLM routing with automatic failover.

Order of preference:
  1. Claude (Anthropic Pro) — primary brain with tool-calling.
  2. Gemini — fallback if Claude fails or circuit breaker is open.
  3. Ollama + Llama 3 — offline fallback.

Every call runs through the RateLimiter; consecutive failures trip the
circuit breaker and force offline mode for 60 s.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Optional

from jarvis.core.config import CONFIG
from jarvis.security.rate_limiter import LIMITER
from jarvis.tools import sandbox as _sb
from jarvis.utils.logging import log_error
from jarvis.utils.secrets import get_secret

try:
    import anthropic  # type: ignore
    _HAS_ANTHROPIC = True
except ImportError:  # pragma: no cover
    anthropic = None  # type: ignore[assignment]
    _HAS_ANTHROPIC = False

try:
    import warnings as _w
    with _w.catch_warnings():
        _w.filterwarnings("ignore", category=FutureWarning)
        import google.generativeai as genai  # type: ignore
    _HAS_GEMINI = True
except ImportError:  # pragma: no cover
    genai = None  # type: ignore[assignment]
    _HAS_GEMINI = False

try:
    import requests  # used for Ollama
    _HAS_REQUESTS = True
except ImportError:  # pragma: no cover
    requests = None  # type: ignore[assignment]
    _HAS_REQUESTS = False


SYSTEM_PROMPT = (
    "You are JARVIS, a helpful, concise macOS voice assistant. "
    "When the user asks you to perform an action, respond ONLY with a single "
    "JSON object on its own line of the form "
    '{"tool": "<tool_name>", "params": {...}, "say": "<short spoken reply>"} '
    "choosing a tool from: " + ", ".join(_sb.all_tools()) + ". "
    "If no tool is appropriate, respond with "
    '{"tool": null, "say": "<your spoken reply>"}.'
)


@dataclass
class Decision:
    tool: Optional[str]
    params: dict
    say: str

    @classmethod
    def from_text(cls, text: str) -> "Decision":
        text = text.strip()
        # tolerate code-fenced JSON
        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json"):
                text = text[4:]
        try:
            obj = json.loads(text)
        except json.JSONDecodeError:
            return cls(tool=None, params={}, say=text[:200])
        return cls(
            tool=obj.get("tool"),
            params=obj.get("params") or {},
            say=(obj.get("say") or "").strip(),
        )


def _call_claude(prompt: str, history: list[dict]) -> str:
    if not _HAS_ANTHROPIC:
        raise RuntimeError("anthropic package missing")
    api_key = get_secret("anthropic_api_key")
    if not api_key:
        raise RuntimeError("no anthropic api key")
    client = anthropic.Anthropic(api_key=api_key)
    msgs = history + [{"role": "user", "content": prompt}]
    resp = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=400,
        system=SYSTEM_PROMPT,
        messages=msgs,
    )
    return resp.content[0].text  # type: ignore[no-any-return, index]


def _call_gemini(prompt: str, history: list[dict]) -> str:
    if not _HAS_GEMINI:
        raise RuntimeError("google-generativeai package missing")
    api_key = get_secret("gemini_api_key")
    if not api_key:
        raise RuntimeError("no gemini api key")
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.5-flash", system_instruction=SYSTEM_PROMPT)
    # Gemini roles are "user" / "model"; our memory uses "user" / "assistant".
    remap = {"user": "user", "assistant": "model", "model": "model"}
    chat = model.start_chat(history=[
        {"role": remap.get(m["role"], "user"), "parts": [m["content"]]}
        for m in history
    ])
    r = chat.send_message(prompt)
    return r.text  # type: ignore[no-any-return]


def _call_ollama(prompt: str, history: list[dict]) -> str:
    if not _HAS_REQUESTS:
        raise RuntimeError("requests package missing")
    msgs = ([{"role": "system", "content": SYSTEM_PROMPT}]
            + history + [{"role": "user", "content": prompt}])
    r = requests.post(
        f"{CONFIG.ollama_url}/api/chat",
        json={"model": CONFIG.ollama_model, "messages": msgs,
              "stream": False, "format": "json"},
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["message"]["content"]  # type: ignore[no-any-return]


def _internet_ok(timeout_s: float = 1.0) -> bool:
    """Fast TCP probe to a public DNS resolver.  True ⇒ cloud brains worth trying."""
    import socket
    try:
        with socket.create_connection(("1.1.1.1", 53), timeout=timeout_s):
            return True
    except OSError:
        return False


# Brains that returned a permanent error (401/403/400 billing) are
# disabled for the rest of the session so we don't pay their timeout cost
# on every subsequent call.
_DISABLED_BRAINS: set[str] = set()

# Gemini-first by default; Claude moves to primary only if explicitly preferred.
import os as _os
_CLAUDE_PRIMARY = _os.environ.get("JARVIS_CLAUDE_PRIMARY") == "1"


def _preferred_order() -> list[tuple[str, callable]]:
    from jarvis.utils.secrets import get_secret
    has_claude = (bool(get_secret("anthropic_api_key", prompt=False))
                  and "claude_api" not in _DISABLED_BRAINS)
    has_gemini = (bool(get_secret("gemini_api_key", prompt=False))
                  and "gemini_api" not in _DISABLED_BRAINS)
    order: list[tuple[str, callable]] = []
    if _CLAUDE_PRIMARY and has_claude:
        order.append(("claude_api", _call_claude))
        if has_gemini:
            order.append(("gemini_api", _call_gemini))
    else:
        if has_gemini:
            order.append(("gemini_api", _call_gemini))
        if has_claude:
            order.append(("claude_api", _call_claude))
    return order


def _is_permanent_error(exc: BaseException) -> bool:
    """Auth / billing / quota errors won't fix themselves this session."""
    name = type(exc).__name__
    msg = str(exc).lower()
    if name in {"AuthenticationError", "PermissionDeniedError"}:
        return True
    if "invalid_request_error" in msg and ("credit" in msg or "billing" in msg):
        return True
    if "401" in msg or "403" in msg:
        return True
    return False


def decide(prompt: str, history: Optional[list[dict]] = None) -> Decision:
    history = history or []

    # Short-circuit to Ollama when we know the network is down or the
    # cloud-brain circuit breaker has tripped recently.  Avoids waiting out
    # the Anthropic/Gemini HTTP timeout on e.g. airplane mode.
    go_offline = (
        CONFIG.offline_mode
        or LIMITER.circuit_open()
        or not _internet_ok()
    )
    if go_offline:
        try:
            return Decision.from_text(_call_ollama(prompt, history))
        except Exception as e:
            log_error(e, "ollama")
            return Decision(None, {},
                "I can't reach the cloud and the local model isn't responding.")

    last_err: str | None = None
    for bucket, fn in _preferred_order():
        if not LIMITER.allow(bucket):
            continue
        try:
            out = fn(prompt, history)
            LIMITER.record_success()
            return Decision.from_text(out)
        except Exception as e:
            LIMITER.record_failure()
            log_error(e, bucket.split("_")[0])
            last_err = f"{type(e).__name__}: {str(e)[:80]}"
            if _is_permanent_error(e):
                _DISABLED_BRAINS.add(bucket)

    # Cloud brains all failed (auth, rate, 5xx). Fall back to local.
    try:
        return Decision.from_text(_call_ollama(prompt, history))
    except Exception as e:
        log_error(e, "ollama")
        msg = last_err or "no brains reachable"
        return Decision(None, {}, f"All brains unavailable ({msg}).")


_ = Any  # keep mypy happy when optional deps absent
