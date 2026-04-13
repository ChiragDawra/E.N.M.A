"""Runtime configuration — paths, thresholds, feature flags.

Secrets are NEVER stored here; they come from Keychain via utils.secrets.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
LOGS_DIR = ROOT / "logs"
MODELS_DIR = ROOT / "models"

for _d in (DATA_DIR, LOGS_DIR, MODELS_DIR):
    _d.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class Config:
    sample_rate: int = 16000
    voice_auth_threshold: float = 0.85
    liveness_threshold: float = 0.6
    wake_word_threshold: float = 0.7
    voice_profile_path: Path = DATA_DIR / "voice_profile.npy"
    memory_db_path: Path = DATA_DIR / "memory.db"
    wake_word_model: Path = MODELS_DIR / "hey_jarvis.onnx"
    keychain_service: str = "jarvis-assistant"
    offline_mode: bool = False
    tool_timeout_s: int = 30
    rate_limits: dict = field(default_factory=lambda: {
        "claude_api": (20, 60),
        "gemini_api": (30, 60),
        "tool_low": (10, 60),
        "tool_medium": (5, 60),
        "tool_high": (3, 60),
        "total": (60, 60),
    })


CONFIG = Config()
