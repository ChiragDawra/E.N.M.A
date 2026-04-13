"""Voice authentication via Resemblyzer (Vulnerability #1 cure).

Enrollment records the user's voiceprint once.  Every command is then
compared via cosine similarity; commands below threshold are rejected.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional, Union

import numpy as np

from jarvis.core.config import CONFIG
from jarvis.utils.logging import log_auth

try:
    from resemblyzer import VoiceEncoder, preprocess_wav
    _HAS_RESEMBLYZER = True
except ImportError:  # pragma: no cover
    VoiceEncoder = None  # type: ignore[assignment]
    preprocess_wav = None  # type: ignore[assignment]
    _HAS_RESEMBLYZER = False


_encoder: Optional["VoiceEncoder"] = None


def _get_encoder() -> "VoiceEncoder":
    global _encoder
    if not _HAS_RESEMBLYZER:
        raise RuntimeError("resemblyzer not installed; run: pip install resemblyzer")
    if _encoder is None:
        _encoder = VoiceEncoder()
    return _encoder


AudioLike = Union[str, Path, np.ndarray]


def _embed(audio: AudioLike) -> np.ndarray:
    enc = _get_encoder()
    if isinstance(audio, (str, Path)):
        wav = preprocess_wav(str(audio))
    else:
        wav = np.asarray(audio, dtype=np.float32)
    return enc.embed_utterance(wav)


def enroll(audio: AudioLike, profile_path: Path | None = None) -> Path:
    """Create a voiceprint and persist it.  Overwrites any existing profile."""
    profile_path = profile_path or CONFIG.voice_profile_path
    emb = _embed(audio)
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    np.save(profile_path, emb)
    return profile_path


def _load_profile(profile_path: Path | None = None) -> np.ndarray:
    profile_path = profile_path or CONFIG.voice_profile_path
    if not profile_path.exists():
        raise FileNotFoundError(
            f"No voice profile at {profile_path}. Run enrollment first."
        )
    return np.load(profile_path)


def verify(audio: AudioLike, threshold: float | None = None,
           profile_path: Path | None = None) -> tuple[bool, float]:
    """Return (accepted, similarity)."""
    threshold = CONFIG.voice_auth_threshold if threshold is None else threshold
    profile = _load_profile(profile_path)
    emb = _embed(audio)
    # both vectors come from the same encoder, so L2 norms are ~1 but we
    # normalize defensively
    sim = float(np.dot(profile, emb) / (np.linalg.norm(profile) * np.linalg.norm(emb) + 1e-9))
    ok = sim >= threshold
    log_auth(ok, similarity=sim, note="voiceprint")
    return ok, sim
