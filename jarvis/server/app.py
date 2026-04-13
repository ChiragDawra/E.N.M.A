"""FastAPI front-door for JARVIS.  Localhost-only, TLS-enabled.

Mostly for debugging and headless clients — voice loop remains the primary
interface. Every request flows through the exact same sanitizer + sandbox
chain as the voice path, so the security posture is identical.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from jarvis.security.sanitizer import sanitize

try:
    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel
    _HAS_FASTAPI = True
except ImportError:  # pragma: no cover
    _HAS_FASTAPI = False

if TYPE_CHECKING:
    from jarvis.core.orchestrator import Jarvis


def create_app() -> "FastAPI":
    if not _HAS_FASTAPI:
        raise RuntimeError("fastapi not installed; run: pip install fastapi uvicorn")
    from jarvis.core.orchestrator import Jarvis

    app = FastAPI(title="JARVIS", version="0.1.0", docs_url=None, redoc_url=None)
    jarvis: "Jarvis" = Jarvis()

    class Prompt(BaseModel):
        text: str

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/text")
    def text(prompt: Prompt) -> dict[str, str]:
        cleaned, err = sanitize(prompt.text)
        if err or cleaned is None:
            raise HTTPException(status_code=400, detail=err or "bad input")
        reply = jarvis.run_once_text(cleaned) or ""
        return {"reply": reply}

    return app


def run(host: str = "127.0.0.1", port: int = 8443) -> None:
    import uvicorn
    from jarvis.server.tls import ensure_cert

    cert, key = ensure_cert()
    uvicorn.run(
        "jarvis.server.app:create_app",
        factory=True,
        host=host,
        port=port,
        ssl_certfile=str(cert),
        ssl_keyfile=str(key),
        log_level="info",
    )
