from __future__ import annotations

from pathlib import Path

MASKED_PATH_TEXT = "[configured, hidden]"


def canonicalize_project_path(project_id: str, project_path: str, base_dir: Path) -> str:
    pid = str(project_id or "").strip().lower()
    if pid == "default":
        return "."

    raw = str(project_path or "").strip()
    if not raw:
        return ""

    return str(Path(raw).expanduser().resolve())


def resolve_project_root(project_id: str, project_path: str, base_dir: Path) -> Path:
    pid = str(project_id or "").strip().lower()
    raw = str(project_path or "").strip()
    if pid == "default" or raw in {"", ".", "./"}:
        return base_dir.resolve()
    return Path(raw).expanduser().resolve()


def mask_project_path(project_id: str, project_path: str) -> str:
    pid = str(project_id or "").strip().lower()
    raw = str(project_path or "").strip()
    if pid == "default" or raw in {"", ".", "./"}:
        return "."
    return MASKED_PATH_TEXT
