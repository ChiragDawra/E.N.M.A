"""Entry point: `python -m jarvis [run|enroll|setup|text]`"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def cmd_run(_args: argparse.Namespace) -> int:
    from jarvis.core.orchestrator import Jarvis
    Jarvis().run_forever()
    return 0


def cmd_enroll(args: argparse.Namespace) -> int:
    from jarvis.audio import recorder
    from jarvis.auth import voice

    if args.file:
        path = Path(args.file)
        if not path.exists():
            print(f"no such file: {path}", file=sys.stderr)
            return 2
        voice.enroll(path)
    else:
        print("Recording 8 seconds — speak naturally...")
        samples = recorder.record(seconds=8.0)
        wav = recorder.save_wav(samples)
        voice.enroll(str(wav))
        wav.unlink(missing_ok=True)
    print("Voice profile saved.")
    return 0


def cmd_setup(args: argparse.Namespace) -> int:
    from jarvis.utils.secrets import delete_secret, get_secret
    if args.reset:
        delete_secret("anthropic_api_key")
        delete_secret("gemini_api_key")
        print("Existing keys cleared from Keychain.")
    for name in ("anthropic_api_key", "gemini_api_key"):
        val = get_secret(name)
        if val:
            print(f"  {name}: {'*' * 8}{val[-4:]}  ✓")
        else:
            print(f"  {name}: (skipped)")
    return 0


def cmd_text(args: argparse.Namespace) -> int:
    from jarvis.core.orchestrator import Jarvis
    j = Jarvis()
    print(j.run_once_text(args.prompt))
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    from jarvis.server.app import run
    run(host=args.host, port=args.port)
    return 0


def cmd_mcp(_args: argparse.Namespace) -> int:
    from jarvis.tools import mcp as _mcp
    n = _mcp.register_into_sandbox()
    print(f"Registered {n} MCP tool(s).")
    return 0


def cmd_doctor(_args: argparse.Namespace) -> int:
    """Ping every brain and report which one is working."""
    from jarvis.brain import llm as _llm
    from jarvis.utils.secrets import get_secret

    results: list[tuple[str, str]] = []

    # Claude
    try:
        key = get_secret("anthropic_api_key", prompt=False)
        if not key:
            results.append(("claude", "no key in Keychain"))
        else:
            reply = _llm._call_claude("say 'ok' only", [])
            results.append(("claude", f"OK — {reply[:60]!r}"))
    except Exception as e:
        results.append(("claude", f"FAIL — {type(e).__name__}: {str(e)[:120]}"))

    # Gemini
    try:
        key = get_secret("gemini_api_key", prompt=False)
        if not key:
            results.append(("gemini", "no key in Keychain"))
        else:
            reply = _llm._call_gemini("say 'ok' only", [])
            results.append(("gemini", f"OK — {reply[:60]!r}"))
    except Exception as e:
        results.append(("gemini", f"FAIL — {type(e).__name__}: {str(e)[:120]}"))

    ok = 0
    for name, status in results:
        mark = "✓" if status.startswith("OK") else "✗"
        print(f"  [{mark}] {name:8s} {status}")
        if status.startswith("OK"):
            ok += 1
    print(f"\n{ok}/{len(results)} brains reachable.")
    if ok == 0:
        print("\nRun:  python -m jarvis setup --reset   to re-enter your keys.")
    return 0 if ok > 0 else 1


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="jarvis")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("run", help="start the full voice loop").set_defaults(func=cmd_run)

    e = sub.add_parser("enroll", help="create your voice profile")
    e.add_argument("--file", help="enroll from an existing WAV instead of recording")
    e.set_defaults(func=cmd_enroll)

    sp = sub.add_parser("setup", help="store API keys in Keychain")
    sp.add_argument("--reset", action="store_true",
                    help="delete existing keys first and re-prompt")
    sp.set_defaults(func=cmd_setup)

    t = sub.add_parser("text", help="send a single text prompt (no audio)")
    t.add_argument("prompt")
    t.set_defaults(func=cmd_text)

    s = sub.add_parser("serve", help="start the localhost TLS web UI")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", default=8443, type=int)
    s.set_defaults(func=cmd_serve)

    sub.add_parser("mcp", help="connect MCP servers from data/mcp_servers.json").set_defaults(func=cmd_mcp)

    sub.add_parser("doctor", help="ping each brain and report what's broken").set_defaults(func=cmd_doctor)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
