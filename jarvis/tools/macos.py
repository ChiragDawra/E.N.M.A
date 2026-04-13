"""Audited macOS control helpers used by the sandboxed tool registry.

Every helper here must be safe to expose to the AI — no unescaped user
input reaches a shell.  Strings that come from the user are passed as
arguments to osascript, never interpolated into a script literal.
"""
from __future__ import annotations

import platform
import shlex
import subprocess
from typing import Optional

_IS_MAC = platform.system() == "Darwin"


def _run(cmd: list[str], timeout: int = 15) -> str:
    try:
        out = subprocess.run(cmd, capture_output=True, text=True,
                             timeout=timeout, check=False)
        return (out.stdout or out.stderr).strip()
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        return f"error: {e.__class__.__name__}"


def _osascript(script: str, *args: str) -> str:
    if not _IS_MAC:
        return "not-a-mac"
    return _run(["osascript", "-e", script, *args])


def get_time() -> str:
    import datetime as _dt
    return _dt.datetime.now().strftime("%A %d %B %Y, %H:%M")


def get_battery() -> str:
    return _run(["pmset", "-g", "batt"]) if _IS_MAC else "unavailable"


def control_volume(level: int) -> str:
    level = max(0, min(100, int(level)))
    # AppleScript `set volume output volume` takes arg via `--`
    return _osascript(f"set volume output volume {level}")


def control_brightness(level: int) -> str:
    # brightness control requires a helper binary on modern macOS; best-effort
    level = max(0, min(100, int(level)))
    return _run(["brightness", f"{level/100:.2f}"])


def open_app(name: str) -> str:
    # Pass app name as an explicit argument list; no shell.
    name = shlex.quote(name)[1:-1]  # strip outer quotes, still safe: using list exec
    if not _IS_MAC:
        return "not-a-mac"
    return _run(["open", "-a", name])


def take_screenshot(path: Optional[str] = None) -> str:
    import tempfile
    if path is None:
        path = tempfile.mkstemp(suffix=".png", prefix="jarvis_shot_")[1]
    return _run(["screencapture", "-x", path]) or path


def toggle_dark_mode() -> str:
    return _osascript(
        'tell application "System Events" to tell appearance preferences '
        "to set dark mode to not dark mode"
    )


def control_spotify(action: str) -> str:
    action = action.lower().strip()
    allowed = {"play", "pause", "next track", "previous track"}
    if action not in allowed:
        return "unsupported action"
    return _osascript(f'tell application "Spotify" to {action}')


def get_current_track() -> str:
    return _osascript(
        'tell application "Spotify" to (artist of current track) '
        '& " - " & (name of current track)'
    )


def send_imessage(recipient: str, body: str) -> str:
    # Recipient and body reach AppleScript via argv, not interpolation.
    if not _IS_MAC:
        return "not-a-mac"
    script = (
        'on run argv\n'
        '  tell application "Messages"\n'
        '    set targetService to 1st service whose service type = iMessage\n'
        '    set targetBuddy to buddy (item 1 of argv) of targetService\n'
        '    send (item 2 of argv) as text to targetBuddy\n'
        '  end tell\n'
        'end run'
    )
    return _run(["osascript", "-e", script, recipient, body])


def create_reminder(title: str) -> str:
    script = (
        'on run argv\n'
        '  tell application "Reminders" to make new reminder with properties {name: (item 1 of argv)}\n'
        'end run'
    )
    return _run(["osascript", "-e", script, title]) if _IS_MAC else "not-a-mac"


def search_web(query: str) -> str:
    import urllib.parse
    url = "https://duckduckgo.com/?q=" + urllib.parse.quote(query)
    return _run(["open", url]) if _IS_MAC else url
