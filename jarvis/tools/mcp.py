"""Minimal Model Context Protocol client.

Speaks JSON-RPC 2.0 over stdio to one or more MCP servers.  Each server
exports tools that land in the MEDIUM permission tier of the sandbox.
The client is deliberately simple — no streaming, no resource fetch — so
it adds zero new dependencies.

Config lives at data/mcp_servers.json:

    {
      "github": {"command": "mcp-server-github", "args": ["--token", "..."]},
      "slack":  {"command": "npx", "args": ["@modelcontextprotocol/server-slack"]}
    }

The file is git-ignored because it can contain tokens.
"""
from __future__ import annotations

import json
import subprocess
import threading
from pathlib import Path
from typing import Any

from jarvis.core.config import DATA_DIR
from jarvis.utils.logging import log_error

CONFIG_PATH = DATA_DIR / "mcp_servers.json"


class MCPServer:
    def __init__(self, name: str, command: str, args: list[str] | None = None) -> None:
        self.name = name
        self.command = command
        self.args = list(args or [])
        self._proc: subprocess.Popen | None = None
        self._lock = threading.Lock()
        self._next_id = 0

    def start(self) -> None:
        self._proc = subprocess.Popen(  # noqa: S603 — command from user-owned config
            [self.command, *self.args],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, bufsize=1,
        )
        self._request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "jarvis", "version": "0.1.0"},
        })

    def _request(self, method: str, params: dict[str, Any] | None = None) -> dict:
        if self._proc is None or self._proc.stdin is None or self._proc.stdout is None:
            raise RuntimeError(f"MCP server {self.name} not running")
        with self._lock:
            self._next_id += 1
            msg = {"jsonrpc": "2.0", "id": self._next_id, "method": method,
                   "params": params or {}}
            self._proc.stdin.write(json.dumps(msg) + "\n")
            self._proc.stdin.flush()
            line = self._proc.stdout.readline()
        return json.loads(line) if line else {}

    def list_tools(self) -> list[dict]:
        resp = self._request("tools/list")
        return (resp.get("result") or {}).get("tools", [])

    def call(self, tool: str, args: dict[str, Any]) -> Any:
        resp = self._request("tools/call", {"name": tool, "arguments": args})
        if "error" in resp:
            raise RuntimeError(resp["error"].get("message", "mcp error"))
        return (resp.get("result") or {}).get("content")

    def stop(self) -> None:
        if self._proc:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=3)
            except Exception:
                self._proc.kill()


def load_servers(path: Path = CONFIG_PATH) -> dict[str, MCPServer]:
    if not path.exists():
        return {}
    try:
        cfg = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        log_error(e, "mcp-config")
        return {}
    servers: dict[str, MCPServer] = {}
    for name, spec in cfg.items():
        cmd = spec.get("command")
        if not cmd:
            continue
        s = MCPServer(name, cmd, spec.get("args"))
        try:
            s.start()
            servers[name] = s
        except Exception as e:
            log_error(e, f"mcp-start:{name}")
    return servers


def register_into_sandbox() -> int:
    """Register MCP tools into the sandbox MEDIUM tier. Returns count registered."""
    from jarvis.tools import sandbox as sb

    servers = load_servers()
    count = 0
    for name, server in servers.items():
        try:
            for tool in server.list_tools():
                tname = f"mcp_{name}_{tool['name']}"

                def _make_call(srv: MCPServer, tool_name: str):
                    def _fn(**kwargs):
                        return srv.call(tool_name, kwargs)
                    return _fn

                sb.TOOL_REGISTRY[tname] = _make_call(server, tool["name"])
                sb.PERMISSION_TIERS["medium"].append(tname)
                count += 1
        except Exception as e:
            log_error(e, f"mcp-list:{name}")
    return count
