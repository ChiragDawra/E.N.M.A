"""Structured audit logging (Vulnerability #10 cure).

Three rotating log streams — commands, auth, errors — with weekly rotation,
gzip compression, and 30-day retention.
"""
from __future__ import annotations

import json
import sys
from typing import Any

try:
    from loguru import logger
    _HAS_LOGURU = True
except ImportError:  # pragma: no cover
    import logging as _stdlog
    _stdlog.basicConfig(level=_stdlog.INFO)
    logger = _stdlog.getLogger("jarvis")  # type: ignore[assignment]
    _HAS_LOGURU = False

from jarvis.core.config import LOGS_DIR

_configured = False


def configure() -> None:
    global _configured
    if _configured or not _HAS_LOGURU:
        _configured = True
        return

    logger.remove()
    logger.add(sys.stderr, level="INFO",
               format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}")
    logger.add(LOGS_DIR / "commands.log",
               rotation="1 week", compression="gz", retention="30 days",
               filter=lambda r: r["extra"].get("channel") == "command",
               format="{time:YYYY-MM-DD HH:mm:ss} | {message}")
    logger.add(LOGS_DIR / "auth.log",
               rotation="1 week", compression="gz", retention="30 days",
               filter=lambda r: r["extra"].get("channel") == "auth",
               format="{time:YYYY-MM-DD HH:mm:ss} | {message}")
    logger.add(LOGS_DIR / "errors.log",
               rotation="1 week", compression="gz", retention="30 days",
               level="ERROR")
    _configured = True


def _emit(channel: str, payload: dict[str, Any]) -> None:
    configure()
    msg = json.dumps(payload, default=str)
    if _HAS_LOGURU:
        logger.bind(channel=channel).info(msg)
    else:
        logger.info("%s %s", channel, msg)


def log_command(tool: str, params: dict, result: Any, speaker_verified: bool) -> None:
    _emit("command", {
        "type": "command",
        "tool": tool,
        "params": params,
        "result": str(result)[:200],
        "speaker_verified": speaker_verified,
    })


def log_auth(success: bool, similarity: float | None = None, note: str = "") -> None:
    _emit("auth", {
        "type": "auth",
        "success": success,
        "similarity": round(similarity, 4) if similarity is not None else None,
        "note": note,
    })


def log_security_event(kind: str, detail: str) -> None:
    _emit("auth", {"type": "security", "kind": kind, "detail": detail[:200]})


def log_error(err: BaseException, where: str = "") -> None:
    configure()
    if _HAS_LOGURU:
        logger.opt(exception=err).error("{} | {}", where, err)
    else:
        logger.error("%s | %s", where, err, exc_info=err)
