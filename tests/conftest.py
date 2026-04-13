"""Test setup — stub Keychain so tests don't touch the real one."""
from __future__ import annotations

import sys
import types
from pathlib import Path

# Make the project importable when pytest is run from anywhere.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# In-memory keyring so tests don't prompt for passwords or touch the real
# macOS Keychain.
_store: dict[tuple[str, str], str] = {}


def _fake_keyring() -> types.ModuleType:
    m = types.ModuleType("keyring")
    m.set_password = lambda service, key, value: _store.__setitem__((service, key), value)  # type: ignore[attr-defined]
    m.get_password = lambda service, key: _store.get((service, key))  # type: ignore[attr-defined]
    m.delete_password = lambda service, key: _store.pop((service, key), None)  # type: ignore[attr-defined]
    return m


sys.modules.setdefault("keyring", _fake_keyring())
