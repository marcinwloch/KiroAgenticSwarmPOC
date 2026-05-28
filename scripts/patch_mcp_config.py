#!/usr/bin/env python3
"""Patch .kiro/settings/mcp.json with absolute paths for Kiro IDE.

Kiro does not expand ${workspaceFolder} in mcp.json (see kirodotdev/Kiro#5060).
After bootstrap, this writes a venv python command and env from aws-endpoints.env.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

AUTO_APPROVE = [
    "swarm.start",
    "swarm.architect",
    "swarm.develop",
    "swarm.test",
    "swarm.review",
    "swarm.status",
    "swarm.plan",
]


def load_env_file(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if not path.is_file():
        return env
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, sep, value = line.partition("=")
        if sep:
            env[key.strip()] = value.strip()
    return env


def venv_python_path(repo_root: Path) -> Path:
    if os.name == "nt":
        return repo_root / "mcp-server" / ".venv" / "Scripts" / "python.exe"
    return repo_root / "mcp-server" / ".venv" / "bin" / "python"


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    python = venv_python_path(repo_root)
    if not python.is_file():
        print(
            f"ERROR: {python} not found. Run scripts/bootstrap.ps1 or bootstrap.sh first.",
            file=sys.stderr,
        )
        return 1

    endpoints = load_env_file(repo_root / "aws-endpoints.env")
    mcp_json_path = repo_root / ".kiro" / "settings" / "mcp.json"
    mcp_json_path.parent.mkdir(parents=True, exist_ok=True)

    env = {
        "AWS_REGION": endpoints.get("AWS_REGION", "eu-central-1"),
        "AWS_PROFILE": "nortal-swarm",
        "SWARM_WORKSPACE_ROOT": repo_root.as_posix(),
        "PYTHONUNBUFFERED": "1",
    }
    for key, value in endpoints.items():
        if key.startswith("SWARM_") or key == "AWS_REGION":
            env[key] = value

    config = {
        "mcpServers": {
            "nortal-swarm": {
                "command": python.as_posix(),
                "args": ["-m", "swarm_mcp.server"],
                "env": env,
                "disabled": False,
                "autoApprove": AUTO_APPROVE,
            }
        }
    }

    mcp_json_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    print(f"Patched {mcp_json_path}")
    print(f"  command: {python.as_posix()}")
    print(f"  workspace: {repo_root.as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
