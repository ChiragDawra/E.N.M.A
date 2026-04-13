"""Encrypted memory store (Vulnerability #7 cure).

SQLite + Fernet (AES-128-CBC + HMAC).  The encryption key is stored in
Keychain; a fresh 32-byte key is generated on first launch.  All writes
go through PII redaction first so even the encrypted column never holds
raw phone numbers / emails / card numbers.
"""
from __future__ import annotations

import base64
import os
import sqlite3
import threading
import time
from typing import Iterable, Optional

from jarvis.core.config import CONFIG
from jarvis.memory.pii import redact
from jarvis.utils.secrets import get_secret, set_secret

try:
    from cryptography.fernet import Fernet, InvalidToken
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    _HAS_CRYPTO = True
except ImportError:  # pragma: no cover
    Fernet = None  # type: ignore[assignment]
    InvalidToken = Exception  # type: ignore[assignment]
    _HAS_CRYPTO = False


_KEY_NAME = "memory_master_key"
_SALT_NAME = "memory_master_salt"


def _get_or_create_salt() -> bytes:
    existing = get_secret(_SALT_NAME, prompt=False)
    if existing:
        return base64.urlsafe_b64decode(existing.encode())
    salt = os.urandom(16)
    set_secret(_SALT_NAME, base64.urlsafe_b64encode(salt).decode())
    return salt


def _get_or_create_master() -> str:
    existing = get_secret(_KEY_NAME, prompt=False)
    if existing:
        return existing
    # Use Fernet's generator for a cryptographically strong 32-byte base64 key.
    token = Fernet.generate_key().decode()
    set_secret(_KEY_NAME, token)
    return token


def _build_cipher() -> "Fernet":
    if not _HAS_CRYPTO:
        raise RuntimeError("cryptography not installed; run: pip install cryptography")
    password = _get_or_create_master().encode()
    salt = _get_or_create_salt()
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt,
                     iterations=480_000)
    key = base64.urlsafe_b64encode(kdf.derive(password))
    return Fernet(key)


class MemoryStore:
    """Thread-safe encrypted key/value + conversation log."""

    def __init__(self, db_path=None) -> None:
        self.db_path = db_path or CONFIG.memory_db_path
        self._lock = threading.Lock()
        self._cipher = _build_cipher()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as c:
            c.execute(
                "CREATE TABLE IF NOT EXISTS conversations ("
                " id INTEGER PRIMARY KEY AUTOINCREMENT,"
                " ts REAL NOT NULL,"
                " role TEXT NOT NULL,"
                " payload BLOB NOT NULL"
                ")"
            )
            c.execute(
                "CREATE TABLE IF NOT EXISTS kv ("
                " key TEXT PRIMARY KEY,"
                " payload BLOB NOT NULL"
                ")"
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), isolation_level=None)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _enc(self, text: str) -> bytes:
        return self._cipher.encrypt(redact(text).encode("utf-8"))

    def _dec(self, token: bytes) -> str:
        try:
            return self._cipher.decrypt(token).decode("utf-8")
        except InvalidToken:
            return "[DECRYPT-FAILED]"

    def add_message(self, role: str, text: str) -> None:
        payload = self._enc(text)
        with self._lock, self._connect() as c:
            c.execute(
                "INSERT INTO conversations (ts, role, payload) VALUES (?, ?, ?)",
                (time.time(), role, payload),
            )

    def recent(self, limit: int = 20) -> list[tuple[float, str, str]]:
        with self._lock, self._connect() as c:
            rows = c.execute(
                "SELECT ts, role, payload FROM conversations "
                "ORDER BY id DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
        return [(ts, role, self._dec(blob)) for ts, role, blob in reversed(rows)]

    def set(self, key: str, value: str) -> None:
        payload = self._enc(value)
        with self._lock, self._connect() as c:
            c.execute(
                "INSERT INTO kv (key, payload) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET payload=excluded.payload",
                (key, payload),
            )

    def get(self, key: str) -> Optional[str]:
        with self._lock, self._connect() as c:
            row = c.execute(
                "SELECT payload FROM kv WHERE key = ?", (key,)
            ).fetchone()
        return self._dec(row[0]) if row else None

    def keys(self) -> Iterable[str]:
        with self._lock, self._connect() as c:
            return [r[0] for r in c.execute("SELECT key FROM kv").fetchall()]
