"""Pack spec, steering, and repo snapshot for AgentCore requests."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

MAX_FILE_BYTES = 64_000
SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    ".pytest_cache",
    ".ruff_cache",
    "dist",
    "build",
}
TEXT_SUFFIXES = {
    ".py",
    ".md",
    ".toml",
    ".yaml",
    ".yml",
    ".json",
    ".txt",
    ".ini",
    ".cfg",
    ".env.example",
}


def workspace_root() -> Path:
    env = os.environ.get("SWARM_WORKSPACE_ROOT", "").strip()
    if env:
        return Path(env).resolve()
    # mcp-server lives at <workspace>/mcp-server
    return Path(__file__).resolve().parents[3]


def resolve_path(path_str: str, root: Path) -> Path:
    path = Path(path_str)
    if path.is_absolute():
        return path.resolve()
    return (root / path).resolve()


def read_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def list_repo_files(repo_dir: Path) -> list[str]:
    if not repo_dir.exists():
        return []
    files: list[str] = []
    for current, dirnames, filenames in os.walk(repo_dir):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        rel_root = Path(current).relative_to(repo_dir)
        for name in sorted(filenames):
            rel = (rel_root / name).as_posix()
            if rel == ".":
                rel = name
            files.append(rel)
    return files


def repo_snapshot(repo_dir: Path) -> dict[str, Any]:
    snapshot: dict[str, Any] = {"root": str(repo_dir), "files": [], "contents": {}}
    if not repo_dir.exists():
        snapshot["missing"] = True
        return snapshot

    for rel in list_repo_files(repo_dir):
        snapshot["files"].append(rel)
        file_path = repo_dir / rel
        if file_path.suffix.lower() not in TEXT_SUFFIXES and rel != "Dockerfile":
            continue
        try:
            size = file_path.stat().st_size
        except OSError:
            continue
        if size > MAX_FILE_BYTES:
            snapshot["contents"][rel] = f"<skipped: {size} bytes>"
            continue
        try:
            snapshot["contents"][rel] = read_text_file(file_path)
        except OSError:
            continue
    return snapshot


def load_steering(root: Path) -> dict[str, str]:
    steering_dir = root / ".kiro" / "steering"
    if not steering_dir.is_dir():
        return {}
    docs: dict[str, str] = {}
    for path in sorted(steering_dir.glob("*.md")):
        docs[path.name] = read_text_file(path)
    return docs


def build_payload(
    action: str,
    spec_path: str,
    repo_path: str | None = None,
) -> dict[str, Any]:
    root = workspace_root()
    spec_file = resolve_path(spec_path, root)
    if not spec_file.is_file():
        raise FileNotFoundError(f"Spec not found: {spec_file}")

    payload: dict[str, Any] = {
        "action": action,
        "spec_path": spec_path,
        "spec": read_text_file(spec_file),
        "steering": load_steering(root),
        "workspace_root": str(root),
    }

    if repo_path:
        repo_dir = resolve_path(repo_path, root)
        payload["repo_path"] = repo_path
        payload["repo"] = repo_snapshot(repo_dir)

    memory_arn = os.environ.get("SWARM_MEMORY_ARN", "").strip()
    gateway_url = os.environ.get("SWARM_GATEWAY_URL", "").strip()
    if memory_arn:
        payload["memory_arn"] = memory_arn
    if gateway_url:
        payload["gateway_url"] = gateway_url

    return payload
