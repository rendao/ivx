#!/usr/bin/env python3
"""Live progress dashboard server for AI-led R&D framework.

Provides:
- Static web UI at /
- Current progress JSON at /api/progress
- SSE stream at /api/stream
- Progress update endpoint at /api/progress (POST)
"""

from __future__ import annotations

import argparse
import datetime as dt
import errno
import hashlib
import json
import os
import re
import subprocess
import sys
import threading
import time
import xml.etree.ElementTree as ET
from copy import deepcopy
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import shutil
import tempfile
from typing import Any, Dict
from urllib.parse import urlparse

from .governance import append_governance_event
from .governance import derive_governance_metrics
from .governance import governance_recent_events
from .path_policy import canonicalize_project_path as policy_canonicalize_project_path
from .path_policy import mask_project_path as policy_mask_project_path
from .path_policy import resolve_project_root as policy_resolve_project_root
from .telemetry import apply_repository_signals

PACKAGE_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = PACKAGE_DIR.parents[1]
BASE_DIR = REPO_DIR if (REPO_DIR / "web" / "index.html").exists() and (REPO_DIR / "data").exists() else PACKAGE_DIR
WEB_DIR = BASE_DIR / "web"
IVX_DIRNAME = ".ivx"
STATE_ROOT_DIR = Path(os.getenv("DASHBOARD_STATE_ROOT", str(Path.cwd() / IVX_DIRNAME))).expanduser().resolve()
DATA_DIR = STATE_ROOT_DIR / "data"
PROJECTS_DIR = DATA_DIR / "projects"
PROJECT_STATE_FILE = DATA_DIR / "dashboard_state.json"
BASE_PROGRESS_FILE = Path(os.getenv("DASHBOARD_DATA_FILE", str(DATA_DIR / "live_progress.json"))).expanduser().resolve()
PROGRESS_FILE = BASE_PROGRESS_FILE
DEFAULT_PROJECT_NAME = os.getenv("DASHBOARD_DEFAULT_PROJECT", BASE_DIR.name)
DEFAULT_PROJECT_PATH = os.getenv("DASHBOARD_DEFAULT_PROJECT_PATH", ".")
DEBUG_LOG_ENABLED = str(os.getenv("DASHBOARD_DEBUG", "")).strip().lower() in {"1", "true", "yes", "on", "debug"}
DEBUG_LOG_FILE = DATA_DIR / "dashboard_debug.log"

FILE_LOCK = threading.RLock()
AUTO_COLLECT_ENABLED = str(os.getenv("DASHBOARD_AUTO_COLLECT", "1")).strip().lower() not in {"0", "false", "no", "off"}
AUTO_COLLECT_INTERVAL_SECONDS = max(5, int(os.getenv("DASHBOARD_COLLECT_INTERVAL_SECONDS", "20") or "20"))
LAST_AUTO_COLLECT_AT = 0.0

ALLOWED_PROGRESS_KEYS = {
    "project_id",
    "project_name",
    "project_path",
    "project",
    "name",
    "phase",
    "task",
    "progress_percent",
    "status",
    "risk_level",
    "failed_checks",
    "blockers",
    "next_milestone",
    "pipeline_metrics",
    "collaborators",
    "recent_events",
    "recent_events_append",
    "collaborators_upsert",
    "last_update",
    "human_intervention",
    "bootstrap",
    "force_bootstrap",
}

ALLOWED_PROGRESS_STATUSES = {"green", "yellow", "red"}
ALLOWED_RISK_LEVELS = {"low", "medium", "high", "critical"}
ALLOWED_COLLABORATOR_ROLES = {"development", "testing", "review", "release", "ops"}
ALLOWED_COLLABORATOR_STATUS = {"active", "blocked", "idle"}
ALLOWED_CI_STATUS = {"success", "failed", "running"}


def backup_path_for(path: Path) -> Path:
    return path.parent / ".backups"


def rotate_backups(path: Path, keep: int = 3) -> None:
    if not path.exists() or not path.is_file():
        return

    backup_dir = backup_path_for(path)
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S")
    backup_file = backup_dir / f"{path.stem}-{stamp}{path.suffix}"
    shutil.copy2(path, backup_file)

    backups = sorted(
        [candidate for candidate in backup_dir.glob(f"{path.stem}-*{path.suffix}") if candidate.is_file()],
        key=lambda candidate: candidate.stat().st_mtime,
        reverse=True,
    )
    for stale in backups[keep:]:
        try:
            stale.unlink()
        except Exception:
            pass


def atomic_write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        rotate_backups(path)

    temp_handle = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=str(path.parent),
        prefix=f".{path.stem}.",
        suffix=".tmp",
        delete=False,
    )
    temp_name = Path(temp_handle.name)
    try:
        with temp_handle:
            json.dump(payload, temp_handle, ensure_ascii=False, indent=2)
            temp_handle.write("\n")
        os.replace(temp_name, path)
    except Exception:
        try:
            temp_name.unlink(missing_ok=True)
        except Exception:
            pass
        raise


def load_json_with_recovery(path: Path, fallback: Dict[str, Any]) -> Dict[str, Any]:
    if not path.exists():
        return deepcopy(fallback)

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            return raw
    except Exception:
        pass

    backup_dir = backup_path_for(path)
    if backup_dir.exists():
        backups = sorted(
            [candidate for candidate in backup_dir.glob(f"{path.stem}-*{path.suffix}") if candidate.is_file()],
            key=lambda candidate: candidate.stat().st_mtime,
            reverse=True,
        )
        for candidate in backups:
            try:
                raw = json.loads(candidate.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    atomic_write_json(path, raw)
                    return raw
            except Exception:
                continue

    atomic_write_json(path, fallback)
    return deepcopy(fallback)


def validation_error(message: str, details: list[str] | None = None) -> ValueError:
    if details:
        message = f"{message}: {'; '.join(details)}"
    return ValueError(message)


def _validate_string_field(payload: Dict[str, Any], key: str, errors: list[str]) -> None:
    if key in payload and payload[key] is not None and not isinstance(payload[key], str):
        errors.append(f"{key} must be a string")


def _validate_int_range(payload: Dict[str, Any], key: str, minimum: int, maximum: int, errors: list[str]) -> None:
    if key not in payload or payload[key] is None:
        return
    try:
        value = int(payload[key])
    except Exception:
        errors.append(f"{key} must be an integer")
        return
    if value < minimum or value > maximum:
        errors.append(f"{key} must be between {minimum} and {maximum}")


def _validate_non_negative_int(payload: Dict[str, Any], key: str, errors: list[str]) -> None:
    if key not in payload or payload[key] is None:
        return
    try:
        value = int(payload[key])
    except Exception:
        errors.append(f"{key} must be a non-negative integer")
        return
    if value < 0:
        errors.append(f"{key} must be a non-negative integer")


def _validate_string_list(payload: Dict[str, Any], key: str, errors: list[str]) -> None:
    if key not in payload or payload[key] is None:
        return
    value = payload[key]
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        errors.append(f"{key} must be a list of strings")


def _validate_enum(payload: Dict[str, Any], key: str, allowed: set[str], errors: list[str]) -> None:
    if key not in payload or payload[key] is None:
        return
    value = str(payload[key]).strip().lower()
    if value not in allowed:
        errors.append(f"{key} must be one of {', '.join(sorted(allowed))}")


def _validate_pipeline_section(section_name: str, section: Any, errors: list[str]) -> None:
    if not isinstance(section, dict):
        errors.append(f"pipeline_metrics.{section_name} must be an object")
        return

    if section_name == "development":
        _validate_non_negative_int(section, "tasks_planned", errors)
        _validate_non_negative_int(section, "tasks_done", errors)
        _validate_non_negative_int(section, "velocity_points", errors)
    elif section_name == "testing":
        _validate_non_negative_int(section, "tests_passed", errors)
        _validate_non_negative_int(section, "tests_failed", errors)
        _validate_int_range(section, "coverage_percent", 0, 100, errors)
        _validate_non_negative_int(section, "regressions", errors)
    elif section_name == "commit":
        _validate_non_negative_int(section, "commits_today", errors)
        _validate_non_negative_int(section, "prs_open", errors)
        _validate_non_negative_int(section, "review_pending", errors)
        _validate_non_negative_int(section, "avg_pr_cycle_minutes", errors)
    elif section_name == "ci":
        if "last_build_status" in section and str(section.get("last_build_status") or "") not in ALLOWED_CI_STATUS:
            errors.append("pipeline_metrics.ci.last_build_status must be one of success, failed, running")
        _validate_int_range(section, "build_success_rate", 0, 100, errors)
        _validate_int_range(section, "deploy_success_rate", 0, 100, errors)
    elif section_name == "quality":
        _validate_non_negative_int(section, "defect_escape", errors)
        _validate_non_negative_int(section, "rollback_count", errors)
    elif section_name == "governance":
        _validate_int_range(section, "decision_logs_24h", 0, 10_000, errors)
        _validate_int_range(section, "gate_pass_rate_percent", 0, 100, errors)
        _validate_int_range(section, "human_response_sla_percent", 0, 100, errors)
        _validate_int_range(section, "traceability_coverage_percent", 0, 100, errors)
        _validate_int_range(section, "transparency_score", 0, 100, errors)
        _validate_int_range(section, "controllability_score", 0, 100, errors)
        _validate_int_range(section, "events_24h", 0, 10_000, errors)


def validate_progress_payload(payload: Dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        raise validation_error("payload must be a JSON object")

    unknown_keys = sorted(key for key in payload.keys() if key not in ALLOWED_PROGRESS_KEYS)
    if unknown_keys:
        raise validation_error("payload contains unsupported fields", [", ".join(unknown_keys)])

    errors: list[str] = []
    for key in ("project_id", "project_name", "project_path", "project", "name", "phase", "task", "status", "risk_level", "next_milestone", "last_update"):
        _validate_string_field(payload, key, errors)

    _validate_int_range(payload, "progress_percent", 0, 100, errors)
    _validate_non_negative_int(payload, "failed_checks", errors)
    _validate_string_list(payload, "blockers", errors)
    _validate_enum(payload, "status", ALLOWED_PROGRESS_STATUSES, errors)
    _validate_enum(payload, "risk_level", ALLOWED_RISK_LEVELS, errors)

    if "pipeline_metrics" in payload and payload["pipeline_metrics"] is not None:
        pipeline_metrics = payload["pipeline_metrics"]
        if not isinstance(pipeline_metrics, dict):
            errors.append("pipeline_metrics must be an object")
        else:
            allowed_sections = {"development", "testing", "commit", "ci", "quality", "governance"}
            extra_sections = sorted(set(pipeline_metrics.keys()) - allowed_sections)
            if extra_sections:
                errors.append(f"pipeline_metrics contains unsupported sections: {', '.join(extra_sections)}")
            for section_name in allowed_sections:
                if section_name in pipeline_metrics:
                    _validate_pipeline_section(section_name, pipeline_metrics[section_name], errors)

    if "collaborators" in payload and payload["collaborators"] is not None:
        collaborators = payload["collaborators"]
        if not isinstance(collaborators, list):
            errors.append("collaborators must be a list")
        else:
            for index, collaborator in enumerate(collaborators):
                if not isinstance(collaborator, dict):
                    errors.append(f"collaborators[{index}] must be an object")
                    continue
                if "role" in collaborator and str(collaborator.get("role") or "") not in ALLOWED_COLLABORATOR_ROLES:
                    errors.append(f"collaborators[{index}].role must be one of development, testing, review, release, ops")
                if "status" in collaborator and str(collaborator.get("status") or "") not in ALLOWED_COLLABORATOR_STATUS:
                    errors.append(f"collaborators[{index}].status must be one of active, blocked, idle")
                _validate_string_field(collaborator, "id", errors)
                _validate_string_field(collaborator, "name", errors)
                _validate_string_field(collaborator, "current_task", errors)
                _validate_string_field(collaborator, "note", errors)
                _validate_int_range(collaborator, "progress_percent", 0, 100, errors)
                _validate_non_negative_int(collaborator, "commits_today", errors)
                _validate_non_negative_int(collaborator, "tests_passed", errors)
                _validate_non_negative_int(collaborator, "tests_failed", errors)
                _validate_non_negative_int(collaborator, "prs_open", errors)
                _validate_non_negative_int(collaborator, "reviews_pending", errors)

    if "recent_events" in payload and payload["recent_events"] is not None:
        recent_events = payload["recent_events"]
        if not isinstance(recent_events, list):
            errors.append("recent_events must be a list")

    if "recent_events_append" in payload and payload["recent_events_append"] is not None:
        recent_events_append = payload["recent_events_append"]
        if not isinstance(recent_events_append, list):
            errors.append("recent_events_append must be a list")

    if "collaborators_upsert" in payload and payload["collaborators_upsert"] is not None:
        collaborators_upsert = payload["collaborators_upsert"]
        if not isinstance(collaborators_upsert, list):
            errors.append("collaborators_upsert must be a list")

    if errors:
        raise validation_error("invalid progress payload", errors)


def health_snapshot() -> Dict[str, Any]:
    registry_state = inspect_json_state(PROJECT_STATE_FILE)
    registry_meta = load_registry() if registry_state == "ok" else default_registry()
    current_meta = registry_meta.get("projects", {}).get(registry_meta.get("current_project_id", "default")) if isinstance(registry_meta.get("projects"), dict) else default_project_meta()
    if not isinstance(current_meta, dict):
        current_meta = default_project_meta()

    project_root = policy_resolve_project_root(str(current_meta.get("id") or "default"), str(current_meta.get("path") or ""), BASE_DIR)
    progress_state = inspect_json_state(PROGRESS_FILE)
    current_progress = load_json_with_recovery(PROGRESS_FILE, default_progress(current_meta))

    project_path_state = "ok"
    if str(current_meta.get("path") or "").strip() and not project_root.exists():
        project_path_state = "missing"

    if progress_state == "invalid" or registry_state == "invalid":
        status = "unhealthy"
    elif progress_state != "ok" or project_path_state != "ok" or registry_state != "ok":
        status = "degraded"
    else:
        status = "ok"

    return {
        "status": status,
        "service": "up",
        "time": now_iso(),
        "current_project": public_project_meta(current_meta),
        "checks": {
            "progress_file": progress_state,
            "registry_file": registry_state,
            "project_path": project_path_state,
        },
        "paths": {
            "progress_file": str(PROGRESS_FILE),
            "registry_file": str(PROJECT_STATE_FILE),
            "project_root": str(project_root),
        },
        "progress": {
            "project_id": current_progress.get("project_id"),
            "project": current_progress.get("project"),
            "progress_percent": current_progress.get("progress_percent"),
            "status": current_progress.get("status"),
            "risk_level": current_progress.get("risk_level"),
            "last_update": current_progress.get("last_update"),
        },
    }


def inspect_json_state(path: Path) -> str:
    if not path.exists():
        return "missing"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return "ok" if isinstance(raw, dict) else "invalid"
    except Exception:
        return "invalid"


def debug_log(message: str) -> None:
    if DEBUG_LOG_ENABLED:
        timestamped = f"[dashboard-debug] {now_iso()} {message}"
        print(timestamped, flush=True)
        try:
            DEBUG_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
            with DEBUG_LOG_FILE.open("a", encoding="utf-8") as handle:
                handle.write(timestamped + "\n")
        except Exception:
            pass


def sanitize_key(value: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9._-]+", "-", str(value or "").strip().lower())
    text = text.strip("-_.")
    return text or "project"


def short_hash(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:8]


def project_id_for(name: str, project_path: str) -> str:
    base = sanitize_key(name or Path(project_path or "project").name or "project")
    if project_path:
        return f"{base}-{short_hash(str(policy_resolve_project_root('', project_path, BASE_DIR)))}"
    return base


def normalize_project_path(project_path: str, fallback: str = ".") -> str:
    return policy_canonicalize_project_path("default", project_path, BASE_DIR) if str(project_path or "").strip() else fallback


def resolve_project_root(project_path: str) -> Path:
    return policy_resolve_project_root("default", project_path, BASE_DIR)


def mask_project_path(project_path: str) -> str:
    return policy_mask_project_path("default", project_path)


def public_project_meta(meta: Dict[str, Any] | None) -> Dict[str, Any]:
    source = meta if isinstance(meta, dict) else {}
    project_id = str(source.get("id") or "default")
    raw_path = str(source.get("path") or "")
    return {
        "id": project_id,
        "name": str(source.get("name") or DEFAULT_PROJECT_NAME),
        "path": policy_mask_project_path(project_id, raw_path),
        "path_configured": bool(raw_path.strip()),
    }


def default_project_meta() -> Dict[str, Any]:
    return {
        "id": "default",
        "name": DEFAULT_PROJECT_NAME,
        "path": ".",
        "data_file": str(BASE_PROGRESS_FILE),
    }


def project_data_file(project_id: str) -> Path:
    if project_id == "default":
        return BASE_PROGRESS_FILE
    return (PROJECTS_DIR / f"{sanitize_key(project_id)}.json").resolve()


def resolve_project_data_file(project_id: str, project_path: str, existing_data_file: str = "") -> Path:
    if project_id == "default":
        return BASE_PROGRESS_FILE

    raw_path = str(project_path or "").strip()
    if raw_path:
        root = policy_resolve_project_root(project_id, raw_path, BASE_DIR)
        # Canonical project-local path for ivx contract storage.
        return (root / IVX_DIRNAME / "data" / "live_progress.json").resolve()

    existing = str(existing_data_file or "").strip()
    if existing:
        return Path(existing).expanduser().resolve()

    return project_data_file(project_id)


def default_registry() -> Dict[str, Any]:
    return {
        "current_project_id": "default",
        "projects": {
            "default": default_project_meta(),
        },
    }


def load_registry() -> Dict[str, Any]:
    if not PROJECT_STATE_FILE.exists():
        if PROGRESS_FILE.exists():
            registry = default_registry()
            current = registry["projects"]["default"]
            current["data_file"] = str(PROGRESS_FILE)
            return registry
        return default_registry()

    try:
        raw = json.loads(PROJECT_STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return default_registry()

    projects = raw.get("projects") if isinstance(raw, dict) else {}
    if not isinstance(projects, dict):
        projects = {}

    normalized: Dict[str, Dict[str, Any]] = {}
    for project_id, meta in projects.items():
        if not isinstance(meta, dict):
            continue
        pid = sanitize_key(meta.get("id") or project_id)
        if pid == "project" and not str(meta.get("path") or "").strip() and str(meta.get("name") or pid).strip().lower() == "project":
            continue
        normalized[pid] = {
            "id": pid,
            "name": str(meta.get("name") or pid),
            "path": policy_canonicalize_project_path(pid, str(meta.get("path") or ""), BASE_DIR),
            "data_file": str(meta.get("data_file") or project_data_file(pid)),
        }

    if "default" not in normalized:
        normalized["default"] = default_project_meta()

    current_project_id = sanitize_key(raw.get("current_project_id") or "default") if isinstance(raw, dict) else "default"
    if current_project_id not in normalized:
        current_project_id = "default"

    result = {"current_project_id": current_project_id, "projects": normalized}
    if raw != result:
        save_registry(result)
    return result


def save_registry(registry: Dict[str, Any]) -> None:
    PROJECT_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(PROJECT_STATE_FILE, registry)


def current_project_meta() -> Dict[str, Any]:
    registry = load_registry()
    current_id = sanitize_key(registry.get("current_project_id") or "default")
    project = registry.get("projects", {}).get(current_id)
    if not isinstance(project, dict):
        project = default_project_meta()
    return project


def set_current_project(project_meta: Dict[str, Any], force_bootstrap: bool = False) -> Dict[str, Any]:
    registry = load_registry()
    project_id = sanitize_key(project_meta.get("id") or "default")
    project_path = policy_canonicalize_project_path(project_id, str(project_meta.get("path") or ""), BASE_DIR)
    resolved_data_file = resolve_project_data_file(
        project_id,
        project_path,
        str(project_meta.get("data_file") or ""),
    )
    selected = {
        "id": project_id,
        "name": str(project_meta.get("name") or project_id),
        "path": project_path,
        "data_file": str(resolved_data_file),
    }
    registry.setdefault("projects", {})[project_id] = selected
    registry["current_project_id"] = project_id
    save_registry(registry)

    global PROGRESS_FILE
    PROGRESS_FILE = Path(selected["data_file"]).expanduser().resolve()
    PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)

    ensure_project_progress_contract(selected, force_bootstrap=force_bootstrap)

    debug_log(
        f"set_current_project id={selected['id']} name={selected['name']} data_file={selected['data_file']}"
    )

    return selected


def collect_project_snapshot(project_path: str) -> Dict[str, Any]:
    root = policy_resolve_project_root("", project_path, BASE_DIR)
    if not root.exists() or not root.is_dir():
        return {
            "exists": False,
            "files": 0,
            "python_files": 0,
            "markdown_files": 0,
            "tracked_files": 0,
            "is_git_repo": False,
            "branch": "",
            "dirty_files": 0,
        }

    files = 0
    py_files = 0
    md_files = 0
    max_scan = 4000

    for path in root.rglob("*"):
        if files >= max_scan:
            break
        try:
            if path.is_file():
                files += 1
                suffix = path.suffix.lower()
                if suffix == ".py":
                    py_files += 1
                elif suffix in {".md", ".markdown"}:
                    md_files += 1
        except Exception:
            continue

    is_git_repo = (root / ".git").exists()
    branch = ""
    dirty_files = 0
    tracked_files = 0
    if is_git_repo:
        try:
            branch_cmd = subprocess.run(
                ["git", "-C", str(root), "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                check=False,
                timeout=4,
            )
            if branch_cmd.returncode == 0:
                branch = branch_cmd.stdout.strip()
        except Exception:
            branch = ""

        try:
            status_cmd = subprocess.run(
                ["git", "-C", str(root), "status", "--porcelain"],
                capture_output=True,
                text=True,
                check=False,
                timeout=4,
            )
            if status_cmd.returncode == 0:
                dirty_files = len([line for line in status_cmd.stdout.splitlines() if line.strip()])
        except Exception:
            dirty_files = 0

        try:
            tracked_cmd = subprocess.run(
                ["git", "-C", str(root), "ls-files"],
                capture_output=True,
                text=True,
                check=False,
                timeout=6,
            )
            if tracked_cmd.returncode == 0:
                tracked_files = len([line for line in tracked_cmd.stdout.splitlines() if line.strip()])
        except Exception:
            tracked_files = 0

    return {
        "exists": True,
        "files": files,
        "python_files": py_files,
        "markdown_files": md_files,
        "tracked_files": tracked_files,
        "is_git_repo": is_git_repo,
        "branch": branch,
        "dirty_files": dirty_files,
    }


def build_bootstrap_progress(project_meta: Dict[str, Any]) -> Dict[str, Any]:
    project_path = str(project_meta.get("path") or "")
    snapshot = collect_project_snapshot(project_path)

    base = default_progress(project_meta)
    base["phase"] = "Phase 0 - Auto Discovery"
    base["task"] = "Auto-constructed dashboard contract"
    base["next_milestone"] = "Project emits live progress updates"
    base["progress_percent"] = 5 if snapshot.get("exists") else 0
    base["status"] = "green"
    base["risk_level"] = "medium" if snapshot.get("exists") else "high"

    files = int(snapshot.get("files", 0))
    tracked_files = int(snapshot.get("tracked_files", 0))
    py_files = int(snapshot.get("python_files", 0))
    md_files = int(snapshot.get("markdown_files", 0))
    dirty_files = int(snapshot.get("dirty_files", 0))

    workload_files = tracked_files if tracked_files > 0 else files
    planned = max(8, min(500, max(1, workload_files) // 8 if workload_files else 10))
    done = min(planned, max(0, py_files // 20 + md_files // 30))

    base["pipeline_metrics"] = {
        "development": {
            "tasks_planned": planned,
            "tasks_done": done,
            "velocity_points": max(0, done * 3),
        },
        "testing": {
            "tests_passed": 0,
            "tests_failed": 0,
            "coverage_percent": 0,
            "regressions": 0,
        },
        "commit": {
            "commits_today": 0,
            "prs_open": 0,
            "review_pending": 0,
            "avg_pr_cycle_minutes": 0,
        },
        "ci": {
            "build_success_rate": 100,
            "deploy_success_rate": 100,
            "last_build_status": "running" if snapshot.get("is_git_repo") else "success",
        },
        "quality": {
            "defect_escape": 0,
            "rollback_count": 0,
        },
    }

    discovery_msg = (
        f"auto-bootstrap files={files}, py={py_files}, md={md_files}, "
        f"git={'yes' if snapshot.get('is_git_repo') else 'no'}, "
        f"branch={snapshot.get('branch') or '-'}, dirty={dirty_files}"
    )
    base["recent_events"] = [
        {
            "time": now_iso(),
            "type": "bootstrap",
            "actor": "dashboard",
            "message": discovery_msg,
            "severity": "info",
        }
    ]
    base["collaborators"] = [
        {
            "id": "bootstrap-agent",
            "name": "Bootstrap Agent",
            "role": "ops",
            "status": "active",
            "current_task": "Constructing baseline dashboard contract",
            "progress_percent": base["progress_percent"],
            "commits_today": 0,
            "tests_passed": 0,
            "tests_failed": 0,
            "prs_open": 0,
            "reviews_pending": 0,
            "needs_human": False,
            "note": "Project has no pre-agreed dashboard contract; baseline auto-generated.",
            "last_update": now_iso(),
        }
    ]

    normalized = normalize_progress(base, existing=default_progress(project_meta))
    return attach_project_meta(normalized, project_meta)


def collect_git_activity(project_path: str, event_limit: int = 10) -> Dict[str, Any]:
    root = policy_resolve_project_root("", project_path, BASE_DIR)
    if not root.exists() or not root.is_dir():
        return {"events": [], "commits_today": 0}

    if not (root / ".git").exists():
        return {"events": [], "commits_today": 0}

    events: list[Dict[str, Any]] = []
    commits_today = 0
    total_commits = 0

    try:
        log_cmd = subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "log",
                "--max-count",
                str(max(1, event_limit)),
                "--date=iso-strict",
                "--pretty=format:%cI%x1f%an%x1f%s",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=6,
        )
        if log_cmd.returncode == 0:
            for line in log_cmd.stdout.splitlines():
                parts = line.split("\x1f")
                if len(parts) < 3:
                    continue
                timestamp = parts[0].strip() or now_iso()
                author = parts[1].strip() or "git"
                subject = parts[2].strip() or "commit"
                events.append(
                    {
                        "time": timestamp,
                        "type": "commit",
                        "actor": author,
                        "message": subject,
                        "severity": "info",
                    }
                )
    except Exception:
        events = []

    try:
        count_cmd = subprocess.run(
            ["git", "-C", str(root), "rev-list", "--count", "--since=midnight", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
            timeout=4,
        )
        if count_cmd.returncode == 0:
            commits_today = max(0, int((count_cmd.stdout or "0").strip() or "0"))
    except Exception:
        commits_today = 0

    try:
        total_cmd = subprocess.run(
            ["git", "-C", str(root), "rev-list", "--count", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
            timeout=4,
        )
        if total_cmd.returncode == 0:
            total_commits = max(0, int((total_cmd.stdout or "0").strip() or "0"))
    except Exception:
        total_commits = 0

    return {"events": events, "commits_today": commits_today, "total_commits": total_commits}


def _iter_limited_candidates(root: Path, patterns: list[str], limit: int) -> list[Path]:
    found: list[Path] = []
    seen: set[Path] = set()
    for pattern in patterns:
        for candidate in root.glob(pattern):
            resolved = candidate.resolve()
            if resolved in seen or not resolved.is_file():
                continue
            seen.add(resolved)
            found.append(resolved)
            if len(found) >= limit:
                return found
    return found


def collect_test_activity(project_path: str) -> Dict[str, Any]:
    root = policy_resolve_project_root("", project_path, BASE_DIR)
    if not root.exists() or not root.is_dir():
        return {
            "tests_passed": 0,
            "tests_failed": 0,
            "coverage_percent": 0,
            "regressions": 0,
            "report_found": False,
            "source": "none",
        }

    junit_patterns = [
        "**/junit*.xml",
        "**/pytest*.xml",
        "**/test-results*.xml",
        "**/nosetests*.xml",
        "**/TEST-*.xml",
    ]
    coverage_patterns = ["**/coverage.xml", "**/cobertura.xml"]

    tests_total = 0
    failures_total = 0
    errors_total = 0
    skipped_total = 0
    report_found = False

    for xml_path in _iter_limited_candidates(root, junit_patterns, limit=20):
        try:
            tree = ET.parse(xml_path)
            xml_root = tree.getroot()
            report_found = True

            suites: list[ET.Element] = []
            if xml_root.tag.endswith("testsuite"):
                suites = [xml_root]
            elif xml_root.tag.endswith("testsuites"):
                suites = [elem for elem in xml_root if elem.tag.endswith("testsuite")]

            if not suites:
                continue

            for suite in suites:
                tests_total += int(float(suite.attrib.get("tests", "0") or "0"))
                failures_total += int(float(suite.attrib.get("failures", "0") or "0"))
                errors_total += int(float(suite.attrib.get("errors", "0") or "0"))
                skipped_total += int(float(suite.attrib.get("skipped", "0") or "0"))
        except Exception:
            continue

    tests_failed = max(0, failures_total + errors_total)
    tests_passed = max(0, tests_total - tests_failed - skipped_total)

    coverage_percent = 0
    for coverage_path in _iter_limited_candidates(root, coverage_patterns, limit=3):
        try:
            tree = ET.parse(coverage_path)
            xml_root = tree.getroot()
            report_found = True

            line_rate = xml_root.attrib.get("line-rate")
            if line_rate is not None:
                coverage_percent = max(0, min(100, int(round(float(line_rate) * 100))))
                break

            lines_valid = xml_root.attrib.get("lines-valid")
            lines_covered = xml_root.attrib.get("lines-covered")
            if lines_valid is not None and lines_covered is not None:
                valid = float(lines_valid)
                covered = float(lines_covered)
                if valid > 0:
                    coverage_percent = max(0, min(100, int(round((covered / valid) * 100))))
                    break
        except Exception:
            continue

    regressions = tests_failed

    # Fallback: pytest cache can provide weak signals when xml reports are absent.
    if not report_found:
        cache_dir = root / ".pytest_cache" / "v" / "cache"
        lastfailed_path = cache_dir / "lastfailed"
        nodeids_path = cache_dir / "nodeids"
        failed_from_cache = 0
        total_from_cache = 0

        try:
            if lastfailed_path.exists():
                raw = json.loads(lastfailed_path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    failed_from_cache = len([k for k, v in raw.items() if v])
        except Exception:
            failed_from_cache = 0

        try:
            if nodeids_path.exists():
                raw = json.loads(nodeids_path.read_text(encoding="utf-8"))
                if isinstance(raw, list):
                    total_from_cache = len(raw)
        except Exception:
            total_from_cache = 0

        if failed_from_cache > 0 or total_from_cache > 0:
            tests_failed = max(tests_failed, failed_from_cache)
            if total_from_cache > 0:
                tests_passed = max(tests_passed, total_from_cache - tests_failed)
            regressions = max(regressions, tests_failed)
            return {
                "tests_passed": tests_passed,
                "tests_failed": tests_failed,
                "coverage_percent": coverage_percent,
                "regressions": regressions,
                "report_found": False,
                "source": "pytest_cache",
            }

    return {
        "tests_passed": tests_passed,
        "tests_failed": tests_failed,
        "coverage_percent": coverage_percent,
        "regressions": regressions,
        "report_found": report_found,
        "source": "report_xml",
    }


def apply_git_activity(payload: Dict[str, Any], project_meta: Dict[str, Any]) -> Dict[str, Any]:
    project_id = str(project_meta.get("id") or "default")
    project_path = str(project_meta.get("path") or "")
    project_root = policy_resolve_project_root(project_id, project_path, BASE_DIR)
    enriched = apply_repository_signals(payload, project_root=project_root)

    governance = derive_governance_metrics(enriched, project_root=project_root)
    pipeline = enriched.get("pipeline_metrics") if isinstance(enriched.get("pipeline_metrics"), dict) else {}
    pipeline_governance = pipeline.get("governance") if isinstance(pipeline.get("governance"), dict) else {}
    pipeline_governance.update(
        {
            "decision_logs_24h": governance.get("decision_logs_24h", 0),
            "gate_pass_rate_percent": governance.get("gate_pass_rate_percent", 100),
            "human_response_sla_percent": governance.get("human_response_sla_percent", 100),
            "review_requests_24h": governance.get("review_requests_24h", 0),
            "unresolved_human_reviews": governance.get("unresolved_human_reviews", 0),
            "traceability_coverage_percent": governance.get("traceability_coverage_percent", 100),
            "transparency_score": governance.get("transparency_score", 100),
            "controllability_score": governance.get("controllability_score", 100),
            "objective_defined": governance.get("objective_defined", True),
            "events_24h": governance.get("events_24h", 0),
            "ai_task_started_24h": governance.get("ai_task_started_24h", 0),
            "ai_task_completed_24h": governance.get("ai_task_completed_24h", 0),
            "ai_task_stopped_24h": governance.get("ai_task_stopped_24h", 0),
            "ai_task_stop_rate_percent": governance.get("ai_task_stop_rate_percent", 0),
            "human_authorization_requests_24h": governance.get("human_authorization_requests_24h", 0),
            "human_authorization_approved_24h": governance.get("human_authorization_approved_24h", 0),
            "human_authorization_denied_24h": governance.get("human_authorization_denied_24h", 0),
            "pending_authorization_requests_24h": governance.get("pending_authorization_requests_24h", 0),
            "authorization_approval_rate_percent": governance.get("authorization_approval_rate_percent", 100),
            "human_confirmations_24h": governance.get("human_confirmations_24h", 0),
            "human_skips_24h": governance.get("human_skips_24h", 0),
            "human_stops_24h": governance.get("human_stops_24h", 0),
            "human_confirmation_rate_percent": governance.get("human_confirmation_rate_percent", 100),
            "human_interactions_24h": governance.get("human_interactions_24h", 0),
            "human_interaction_rate_percent": governance.get("human_interaction_rate_percent", 0),
            "ai_behavior_events_24h": governance.get("ai_behavior_events_24h", 0),
            "human_behavior_events_24h": governance.get("human_behavior_events_24h", 0),
            "system_behavior_events_24h": governance.get("system_behavior_events_24h", 0),
            "behavior_events_total_24h": governance.get("behavior_events_total_24h", 0),
            "ai_behavior_ratio_percent": governance.get("ai_behavior_ratio_percent", 0),
            "human_behavior_ratio_percent": governance.get("human_behavior_ratio_percent", 0),
            "ai_behavior_type_counts_24h": governance.get("ai_behavior_type_counts_24h", {}),
            "human_behavior_type_counts_24h": governance.get("human_behavior_type_counts_24h", {}),
            "system_behavior_type_counts_24h": governance.get("system_behavior_type_counts_24h", {}),
            "interaction_traceability_percent": governance.get("interaction_traceability_percent", 100),
            "process_observability_score": governance.get("process_observability_score", 100),
            "objective_progress_score": governance.get("objective_progress_score", 100),
            "human_collaboration_quality_score": governance.get("human_collaboration_quality_score", 100),
            "risk_control_score": governance.get("risk_control_score", 100),
            "overall_governance_score": governance.get("overall_governance_score", 100),
            "data_quality_tier": governance.get("data_quality_tier", "C"),
            "governance_recommendations": governance.get("governance_recommendations", []),
        }
    )
    pipeline["governance"] = pipeline_governance
    enriched["pipeline_metrics"] = pipeline

    current_events = enriched.get("recent_events") if isinstance(enriched.get("recent_events"), list) else []
    governance_events = governance_recent_events(project_root=project_root, limit=6)
    existing_keys = {
        f"{str(item.get('time') or '')}|{str(item.get('type') or '')}|{str(item.get('message') or '')}"
        for item in current_events
        if isinstance(item, dict)
    }
    merged_events = list(current_events)
    for item in governance_events:
        if not isinstance(item, dict):
            continue
        key = f"{str(item.get('time') or '')}|{str(item.get('type') or '')}|{str(item.get('message') or '')}"
        if key in existing_keys:
            continue
        merged_events.append(item)
        existing_keys.add(key)

    merged_events.sort(key=lambda entry: str(entry.get("time") or ""), reverse=True)
    enriched["recent_events"] = merged_events[:20]

    if int(governance.get("unresolved_human_reviews", 0)) > 0:
        if str(enriched.get("status", "green")).lower() == "green":
            enriched["status"] = "yellow"
        if str(enriched.get("risk_level", "low")).lower() in {"low", "medium"}:
            enriched["risk_level"] = "high"

    return enriched


def collect_runtime_signals(force: bool = False) -> Dict[str, Any]:
    global LAST_AUTO_COLLECT_AT

    with FILE_LOCK:
        current_meta = current_project_meta()
        if not PROGRESS_FILE.exists():
            PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
            seed = default_progress(current_meta)
            PROGRESS_FILE.write_text(json.dumps(seed, ensure_ascii=False, indent=2), encoding="utf-8")

        now_ts = time.time()
        if not force:
            if not AUTO_COLLECT_ENABLED:
                return attach_project_meta(json.loads(PROGRESS_FILE.read_text(encoding="utf-8")), current_meta)
            if now_ts - LAST_AUTO_COLLECT_AT < AUTO_COLLECT_INTERVAL_SECONDS:
                return attach_project_meta(json.loads(PROGRESS_FILE.read_text(encoding="utf-8")), current_meta)

        existing = attach_project_meta(json.loads(PROGRESS_FILE.read_text(encoding="utf-8")), current_meta)
        enriched = apply_git_activity(existing, current_meta)
        updated = normalize_progress(enriched, existing=default_progress(current_meta))
        updated = attach_project_meta(updated, current_meta)

        PROGRESS_FILE.write_text(json.dumps(updated, ensure_ascii=False, indent=2), encoding="utf-8")
        LAST_AUTO_COLLECT_AT = now_ts
        debug_log(
            f"collect_runtime_signals force={force} project_id={updated.get('project_id')} "
            f"commits_today={updated.get('pipeline_metrics', {}).get('commit', {}).get('commits_today', 0)} "
            f"tests_failed={updated.get('pipeline_metrics', {}).get('testing', {}).get('tests_failed', 0)}"
        )
        return updated


def collector_worker(stop_event: threading.Event) -> None:
    while not stop_event.wait(AUTO_COLLECT_INTERVAL_SECONDS):
        try:
            collect_runtime_signals(force=False)
        except Exception as exc:
            debug_log(f"collector_worker error={exc}")


def ensure_project_progress_contract(project_meta: Dict[str, Any], force_bootstrap: bool = False) -> Dict[str, Any]:
    data_file = Path(str(project_meta.get("data_file") or "")).expanduser().resolve()
    data_file.parent.mkdir(parents=True, exist_ok=True)

    reason = ""
    payload: Dict[str, Any]

    if force_bootstrap or not data_file.exists():
        reason = "force bootstrap" if force_bootstrap else "missing file"
        payload = build_bootstrap_progress(project_meta)
    else:
        try:
            raw = json.loads(data_file.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("invalid root type")
            normalized = normalize_progress(raw, existing=default_progress(project_meta))
            payload = attach_project_meta(normalized, project_meta)
            required = {"project", "progress_percent", "pipeline_metrics", "collaborators", "human_intervention"}
            if any(key not in payload for key in required):
                reason = "missing required keys"
                payload = build_bootstrap_progress(project_meta)
        except Exception:
            reason = "invalid json"
            payload = build_bootstrap_progress(project_meta)

    payload = apply_git_activity(payload, project_meta)
    payload = normalize_progress(payload, existing=default_progress(project_meta))
    payload = attach_project_meta(payload, project_meta)

    data_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if reason:
        debug_log(f"ensure_project_progress_contract bootstrap reason={reason} data_file={data_file}")
    return payload


def select_or_create_project(payload: Dict[str, Any]) -> Dict[str, Any]:
    registry = load_registry()
    projects = registry.setdefault("projects", {})

    project_id = sanitize_key(payload.get("project_id") or "")
    project_name = str(payload.get("project_name") or payload.get("name") or "").strip()
    project_path = str(payload.get("project_path") or payload.get("path") or "").strip()
    debug_log(
        f"select_or_create_project incoming project_id={project_id or '-'} project_name={project_name or '-'} project_path={project_path or '-'}"
    )

    # If caller provides project metadata, prioritize deterministic ID derivation.
    # This avoids accidental collapse into a generic "project" slot.
    if (project_name or project_path) and (not project_id or project_id == "project"):
        project_id = project_id_for(project_name or Path(project_path or "project").name or "project", project_path)

    if project_id:
        project_path = policy_canonicalize_project_path(project_id, project_path, BASE_DIR)

    if project_id and project_id in projects:
        selected = projects[project_id]
    else:
        if not project_id:
            project_id = project_id_for(project_name or Path(project_path or "project").name or "project", project_path)
        selected = projects.get(project_id)
        if not isinstance(selected, dict):
            selected = {
                "id": project_id,
                "name": project_name or project_id,
                "path": project_path,
                "data_file": str(resolve_project_data_file(project_id, project_path)),
            }
        else:
            if project_name:
                selected["name"] = project_name
            if project_path:
                selected["path"] = project_path
            selected.setdefault(
                "data_file",
                str(resolve_project_data_file(project_id, str(selected.get("path") or ""))),
            )

    if project_name:
        selected["name"] = project_name
    if project_path:
        selected["path"] = project_path
    selected["id"] = project_id
    selected["data_file"] = str(
        resolve_project_data_file(
            project_id,
            str(selected.get("path") or ""),
            str(selected.get("data_file") or ""),
        )
    )

    force_bootstrap = bool(payload.get("bootstrap") or payload.get("force_bootstrap"))
    projects[project_id] = selected
    registry["current_project_id"] = project_id
    save_registry(registry)
    return set_current_project(selected, force_bootstrap=force_bootstrap)


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def default_progress(project_meta: Dict[str, Any] | None = None) -> Dict[str, Any]:
    meta = project_meta or current_project_meta()
    return {
        "project_id": str(meta.get("id") or "default"),
        "project": str(meta.get("name") or DEFAULT_PROJECT_NAME),
        "project_path": str(meta.get("path") or ""),
        "phase": "Phase 1 - Pilot",
        "task": "Initialize live dashboard",
        "progress_percent": 0,
        "status": "green",
        "risk_level": "low",
        "failed_checks": 0,
        "blockers": [],
        "next_milestone": "Dashboard connected to real task updates",
        "pipeline_metrics": {
            "development": {
                "tasks_planned": 10,
                "tasks_done": 0,
                "velocity_points": 0,
            },
            "testing": {
                "tests_passed": 0,
                "tests_failed": 0,
                "coverage_percent": 0,
                "regressions": 0,
            },
            "commit": {
                "commits_today": 0,
                "prs_open": 0,
                "review_pending": 0,
                "avg_pr_cycle_minutes": 0,
            },
            "ci": {
                "build_success_rate": 100,
                "deploy_success_rate": 100,
                "last_build_status": "success",
            },
            "quality": {
                "defect_escape": 0,
                "rollback_count": 0,
            },
            "governance": {
                "decision_logs_24h": 0,
                "gate_pass_rate_percent": 100,
                "human_response_sla_percent": 100,
                "review_requests_24h": 0,
                "unresolved_human_reviews": 0,
                "traceability_coverage_percent": 100,
                "transparency_score": 100,
                "controllability_score": 100,
                "objective_defined": True,
                "events_24h": 0,
                "ai_task_started_24h": 0,
                "ai_task_completed_24h": 0,
                "ai_task_stopped_24h": 0,
                "ai_task_stop_rate_percent": 0,
                "human_authorization_requests_24h": 0,
                "human_authorization_approved_24h": 0,
                "human_authorization_denied_24h": 0,
                "pending_authorization_requests_24h": 0,
                "authorization_approval_rate_percent": 100,
                "human_confirmations_24h": 0,
                "human_skips_24h": 0,
                "human_stops_24h": 0,
                "human_confirmation_rate_percent": 100,
                "human_interactions_24h": 0,
                "human_interaction_rate_percent": 0,
                "ai_behavior_events_24h": 0,
                "human_behavior_events_24h": 0,
                "system_behavior_events_24h": 0,
                "behavior_events_total_24h": 0,
                "ai_behavior_ratio_percent": 0,
                "human_behavior_ratio_percent": 0,
                "ai_behavior_type_counts_24h": {},
                "human_behavior_type_counts_24h": {},
                "system_behavior_type_counts_24h": {},
                "interaction_traceability_percent": 100,
                "process_observability_score": 100,
                "objective_progress_score": 100,
                "human_collaboration_quality_score": 100,
                "risk_control_score": 100,
                "overall_governance_score": 100,
                "data_quality_tier": "C",
                "governance_recommendations": [],
            },
        },
        "collaborators": [
            {
                "id": "ai-builder",
                "name": "AI Builder",
                "role": "development",
                "status": "active",
                "current_task": "Initialize dashboard",
                "progress_percent": 0,
                "commits_today": 0,
                "tests_passed": 0,
                "tests_failed": 0,
                "prs_open": 0,
                "reviews_pending": 0,
                "needs_human": False,
                "note": "Bootstrapping",
                "last_update": now_iso(),
            }
        ],
        "recent_events": [],
        "last_update": now_iso(),
        "human_intervention": {
            "recommended": False,
            "reason": "No immediate intervention needed.",
        },
    }


def parse_iso(value: str) -> dt.datetime | None:
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=dt.timezone.utc)
        return parsed.astimezone(dt.timezone.utc)
    except Exception:
        return None


def clamp_int(value: Any, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except Exception:
        parsed = minimum
    return max(minimum, min(maximum, parsed))


def normalize_pipeline_metrics(raw: Any) -> Dict[str, Any]:
    metrics = raw if isinstance(raw, dict) else {}
    development = metrics.get("development") if isinstance(metrics.get("development"), dict) else {}
    testing = metrics.get("testing") if isinstance(metrics.get("testing"), dict) else {}
    commit = metrics.get("commit") if isinstance(metrics.get("commit"), dict) else {}
    ci = metrics.get("ci") if isinstance(metrics.get("ci"), dict) else {}
    quality = metrics.get("quality") if isinstance(metrics.get("quality"), dict) else {}
    governance = metrics.get("governance") if isinstance(metrics.get("governance"), dict) else {}

    last_build_status = str(ci.get("last_build_status", "success")).lower()
    if last_build_status not in {"success", "failed", "running"}:
        last_build_status = "running"

    data_quality_tier = str(governance.get("data_quality_tier", "C")).upper()
    if data_quality_tier not in {"A", "B", "C"}:
        data_quality_tier = "C"

    raw_recommendations = governance.get("governance_recommendations") if isinstance(governance.get("governance_recommendations"), list) else []
    normalized_recommendations: list[Dict[str, Any]] = []
    for item in raw_recommendations[:5]:
        if not isinstance(item, dict):
            continue
        normalized_recommendations.append(
            {
                "dimension": str(item.get("dimension") or "governance"),
                "priority": max(0, int(item.get("priority", 0))),
                "reason": str(item.get("reason") or ""),
                "action": str(item.get("action") or ""),
            }
        )

    def _normalize_behavior_type_counts(value: Any) -> Dict[str, int]:
        if not isinstance(value, dict):
            return {}
        normalized: Dict[str, int] = {}
        for key, count in value.items():
            name = str(key or "").strip().lower()
            if not name:
                continue
            normalized[name] = max(0, int(count or 0))
        return normalized

    return {
        "development": {
            "tasks_planned": max(0, int(development.get("tasks_planned", 0))),
            "tasks_done": max(0, int(development.get("tasks_done", 0))),
            "velocity_points": max(0, int(development.get("velocity_points", 0))),
        },
        "testing": {
            "tests_passed": max(0, int(testing.get("tests_passed", 0))),
            "tests_failed": max(0, int(testing.get("tests_failed", 0))),
            "coverage_percent": clamp_int(testing.get("coverage_percent", 0), 0, 100),
            "regressions": max(0, int(testing.get("regressions", 0))),
        },
        "commit": {
            "commits_today": max(0, int(commit.get("commits_today", 0))),
            "prs_open": max(0, int(commit.get("prs_open", 0))),
            "review_pending": max(0, int(commit.get("review_pending", 0))),
            "avg_pr_cycle_minutes": max(0, int(commit.get("avg_pr_cycle_minutes", 0))),
        },
        "ci": {
            "build_success_rate": clamp_int(ci.get("build_success_rate", 100), 0, 100),
            "deploy_success_rate": clamp_int(ci.get("deploy_success_rate", 100), 0, 100),
            "last_build_status": last_build_status,
        },
        "quality": {
            "defect_escape": max(0, int(quality.get("defect_escape", 0))),
            "rollback_count": max(0, int(quality.get("rollback_count", 0))),
        },
        "governance": {
            "decision_logs_24h": max(0, int(governance.get("decision_logs_24h", 0))),
            "gate_pass_rate_percent": clamp_int(governance.get("gate_pass_rate_percent", 100), 0, 100),
            "human_response_sla_percent": clamp_int(governance.get("human_response_sla_percent", 100), 0, 100),
            "review_requests_24h": max(0, int(governance.get("review_requests_24h", 0))),
            "unresolved_human_reviews": max(0, int(governance.get("unresolved_human_reviews", 0))),
            "traceability_coverage_percent": clamp_int(governance.get("traceability_coverage_percent", 100), 0, 100),
            "transparency_score": clamp_int(governance.get("transparency_score", 100), 0, 100),
            "controllability_score": clamp_int(governance.get("controllability_score", 100), 0, 100),
            "objective_defined": bool(governance.get("objective_defined", True)),
            "events_24h": max(0, int(governance.get("events_24h", 0))),
            "ai_task_started_24h": max(0, int(governance.get("ai_task_started_24h", 0))),
            "ai_task_completed_24h": max(0, int(governance.get("ai_task_completed_24h", 0))),
            "ai_task_stopped_24h": max(0, int(governance.get("ai_task_stopped_24h", 0))),
            "ai_task_stop_rate_percent": clamp_int(governance.get("ai_task_stop_rate_percent", 0), 0, 100),
            "human_authorization_requests_24h": max(0, int(governance.get("human_authorization_requests_24h", 0))),
            "human_authorization_approved_24h": max(0, int(governance.get("human_authorization_approved_24h", 0))),
            "human_authorization_denied_24h": max(0, int(governance.get("human_authorization_denied_24h", 0))),
            "pending_authorization_requests_24h": max(0, int(governance.get("pending_authorization_requests_24h", 0))),
            "authorization_approval_rate_percent": clamp_int(governance.get("authorization_approval_rate_percent", 100), 0, 100),
            "human_confirmations_24h": max(0, int(governance.get("human_confirmations_24h", 0))),
            "human_skips_24h": max(0, int(governance.get("human_skips_24h", 0))),
            "human_stops_24h": max(0, int(governance.get("human_stops_24h", 0))),
            "human_confirmation_rate_percent": clamp_int(governance.get("human_confirmation_rate_percent", 100), 0, 100),
            "human_interactions_24h": max(0, int(governance.get("human_interactions_24h", 0))),
            "human_interaction_rate_percent": clamp_int(governance.get("human_interaction_rate_percent", 0), 0, 100),
            "ai_behavior_events_24h": max(0, int(governance.get("ai_behavior_events_24h", 0))),
            "human_behavior_events_24h": max(0, int(governance.get("human_behavior_events_24h", 0))),
            "system_behavior_events_24h": max(0, int(governance.get("system_behavior_events_24h", 0))),
            "behavior_events_total_24h": max(0, int(governance.get("behavior_events_total_24h", 0))),
            "ai_behavior_ratio_percent": clamp_int(governance.get("ai_behavior_ratio_percent", 0), 0, 100),
            "human_behavior_ratio_percent": clamp_int(governance.get("human_behavior_ratio_percent", 0), 0, 100),
            "ai_behavior_type_counts_24h": _normalize_behavior_type_counts(governance.get("ai_behavior_type_counts_24h")),
            "human_behavior_type_counts_24h": _normalize_behavior_type_counts(governance.get("human_behavior_type_counts_24h")),
            "system_behavior_type_counts_24h": _normalize_behavior_type_counts(governance.get("system_behavior_type_counts_24h")),
            "interaction_traceability_percent": clamp_int(governance.get("interaction_traceability_percent", 100), 0, 100),
            "process_observability_score": clamp_int(governance.get("process_observability_score", 100), 0, 100),
            "objective_progress_score": clamp_int(governance.get("objective_progress_score", 100), 0, 100),
            "human_collaboration_quality_score": clamp_int(governance.get("human_collaboration_quality_score", 100), 0, 100),
            "risk_control_score": clamp_int(governance.get("risk_control_score", 100), 0, 100),
            "overall_governance_score": clamp_int(governance.get("overall_governance_score", 100), 0, 100),
            "data_quality_tier": data_quality_tier,
            "governance_recommendations": normalized_recommendations,
        },
    }


def normalize_collaborators(raw: Any) -> list[Dict[str, Any]]:
    collaborators = raw if isinstance(raw, list) else []
    normalized: list[Dict[str, Any]] = []

    for idx, item in enumerate(collaborators):
        if not isinstance(item, dict):
            continue

        status = str(item.get("status", "active")).lower()
        if status not in {"active", "blocked", "idle"}:
            status = "idle"

        role = str(item.get("role", "development")).lower()
        if role not in {"development", "testing", "review", "release", "ops"}:
            role = "development"

        normalized.append(
            {
                "id": str(item.get("id") or f"collaborator-{idx + 1}"),
                "name": str(item.get("name") or f"Collaborator {idx + 1}"),
                "role": role,
                "status": status,
                "current_task": str(item.get("current_task") or ""),
                "progress_percent": clamp_int(item.get("progress_percent", 0), 0, 100),
                "commits_today": max(0, int(item.get("commits_today", 0))),
                "tests_passed": max(0, int(item.get("tests_passed", 0))),
                "tests_failed": max(0, int(item.get("tests_failed", 0))),
                "prs_open": max(0, int(item.get("prs_open", 0))),
                "reviews_pending": max(0, int(item.get("reviews_pending", 0))),
                "needs_human": bool(item.get("needs_human", False)),
                "note": str(item.get("note") or ""),
                "last_update": str(item.get("last_update") or now_iso()),
            }
        )

    return normalized


def normalize_events(raw: Any) -> list[Dict[str, Any]]:
    events = raw if isinstance(raw, list) else []
    normalized: list[Dict[str, Any]] = []
    for item in events[:20]:
        if not isinstance(item, dict):
            continue
        severity = str(item.get("severity", "info")).lower()
        if severity not in {"info", "warning", "critical"}:
            severity = "info"
        normalized.append(
            {
                "time": str(item.get("time") or now_iso()),
                "type": str(item.get("type") or "update"),
                "actor": str(item.get("actor") or "system"),
                "message": str(item.get("message") or ""),
                "severity": severity,
            }
        )
    return normalized


def minutes_since(timestamp: str) -> int:
    parsed = parse_iso(timestamp)
    if parsed is None:
        return 0
    return max(0, int((dt.datetime.now(dt.timezone.utc) - parsed).total_seconds() // 60))


def intervention_owner_for_role(role: str) -> str:
    normalized_role = str(role or "development").strip().lower()
    owner_map = {
        "governance": "governance-owner",
        "testing": "qa-owner",
        "ops": "ops-owner",
        "review": "review-owner",
        "development": "dev-owner",
        "release": "release-owner",
    }
    return owner_map.get(normalized_role, f"{sanitize_key(normalized_role) or 'workflow'}-owner")


def intervention_due_for_priority(priority: int) -> str:
    now = dt.datetime.now(dt.timezone.utc)
    if priority >= 90:
        due = now + dt.timedelta(hours=2)
    elif priority >= 75:
        due = now + dt.timedelta(hours=8)
    else:
        due = now + dt.timedelta(hours=24)
    return due.replace(microsecond=0).isoformat()


def make_intervention_item(scope: str, target: str, role: str, priority: int, reason: str, action: str) -> Dict[str, Any]:
    safe_priority = max(0, min(99, int(priority)))
    return {
        "scope": scope,
        "target": target,
        "role": role,
        "owner": intervention_owner_for_role(role),
        "priority": safe_priority,
        "status": "open",
        "due": intervention_due_for_priority(safe_priority),
        "reason": reason,
        "action": action,
    }


def build_intervention_queue(progress: Dict[str, Any]) -> list[Dict[str, Any]]:
    queue: list[Dict[str, Any]] = []

    for blocker in progress.get("blockers", []):
        queue.append(
            make_intervention_item(
                scope="global",
                target="project",
                role="governance",
                priority=72,
                reason=f"Open blocker: {blocker}",
                action="Assign owner and ETA, then post mitigation update.",
            )
        )

    pipeline = progress.get("pipeline_metrics") if isinstance(progress.get("pipeline_metrics"), dict) else {}
    testing = pipeline.get("testing") if isinstance(pipeline.get("testing"), dict) else {}
    ci = pipeline.get("ci") if isinstance(pipeline.get("ci"), dict) else {}
    governance = pipeline.get("governance") if isinstance(pipeline.get("governance"), dict) else {}

    regressions = int(testing.get("regressions", 0))
    if regressions > 0:
        queue.append(
            make_intervention_item(
                scope="global",
                target="testing",
                role="testing",
                priority=min(95, 70 + regressions * 5),
                reason=f"{regressions} regression(s) detected",
                action="Trigger human review for regression triage and rollback decision.",
            )
        )

    last_build_status = str(ci.get("last_build_status", "running")).lower()
    if last_build_status == "failed":
        queue.append(
            make_intervention_item(
                scope="global",
                target="ci",
                role="ops",
                priority=90,
                reason="Latest CI build failed",
                action="Pause merges and investigate failed checks before next deploy.",
            )
        )

    failed_checks = int(progress.get("failed_checks", 0))
    if failed_checks > 0:
        queue.append(
            make_intervention_item(
                scope="global",
                target="quality",
                role="review",
                priority=min(95, 75 + failed_checks * 3),
                reason=f"{failed_checks} failed check(s)",
                action="Fix blocking checks and rerun validation pipeline.",
            )
        )

    unresolved_reviews = int(governance.get("unresolved_human_reviews", 0))
    if unresolved_reviews > 0:
        queue.append(
            make_intervention_item(
                scope="global",
                target="human-review",
                role="governance",
                priority=min(99, 78 + unresolved_reviews * 4),
                reason=f"{unresolved_reviews} unresolved human review request(s)",
                action="Close open review requests with explicit decision records.",
            )
        )

    controllability = int(governance.get("controllability_score", 100))
    if controllability < 60:
        queue.append(
            make_intervention_item(
                scope="global",
                target="governance",
                role="governance",
                priority=88,
                reason=f"controllability score is low ({controllability})",
                action="Run governance checkpoint: objectives, gates, and response SLA must be refreshed.",
            )
        )

    for collaborator in progress.get("collaborators", []):
        if not isinstance(collaborator, dict):
            continue

        score = 0
        reasons: list[str] = []
        status = str(collaborator.get("status", "idle")).lower()
        needs_human = bool(collaborator.get("needs_human", False))
        tests_failed = int(collaborator.get("tests_failed", 0))
        reviews_pending = int(collaborator.get("reviews_pending", 0))
        stale_minutes = minutes_since(str(collaborator.get("last_update", "")))

        if status == "blocked":
            score += 50
            reasons.append("blocked")
        if needs_human:
            score += 35
            reasons.append("human requested")
        if tests_failed > 0:
            score += min(20, tests_failed * 4)
            reasons.append(f"tests failed: {tests_failed}")
        if reviews_pending > 0:
            score += min(12, reviews_pending * 3)
            reasons.append(f"reviews pending: {reviews_pending}")
        if stale_minutes > 20:
            score += min(10, stale_minutes // 10)
            reasons.append(f"stale update: {stale_minutes}m")

        if reasons:
            queue.append(
                make_intervention_item(
                    scope="collaborator",
                    target=str(collaborator.get("name", "unknown")),
                    role=str(collaborator.get("role", "development")),
                    priority=min(99, score),
                    reason=", ".join(reasons),
                    action=str(collaborator.get("note", "Review and support this collaborator"))
                    or "Review and support this collaborator",
                )
            )

    queue.sort(key=lambda item: item.get("priority", 0), reverse=True)
    return queue[:10]


def merge_payload(existing: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    merged = deepcopy(existing)

    for key, value in payload.items():
        if key == "pipeline_metrics" and isinstance(value, dict):
            base_pipeline = merged.get("pipeline_metrics") if isinstance(merged.get("pipeline_metrics"), dict) else {}
            new_pipeline = deepcopy(base_pipeline)
            for section, section_value in value.items():
                if isinstance(section_value, dict):
                    base_section = new_pipeline.get(section) if isinstance(new_pipeline.get(section), dict) else {}
                    base_section.update(section_value)
                    new_pipeline[section] = base_section
            merged["pipeline_metrics"] = new_pipeline
            continue

        if key == "recent_events_append" and isinstance(value, list):
            current_events = merged.get("recent_events") if isinstance(merged.get("recent_events"), list) else []
            merged["recent_events"] = current_events + value
            continue

        if key == "collaborators_upsert" and isinstance(value, list):
            current_collaborators = merged.get("collaborators") if isinstance(merged.get("collaborators"), list) else []
            index_by_id: dict[str, int] = {}
            for idx, collaborator in enumerate(current_collaborators):
                if isinstance(collaborator, dict):
                    index_by_id[str(collaborator.get("id", ""))] = idx

            updated_list = list(current_collaborators)
            for candidate in value:
                if not isinstance(candidate, dict):
                    continue
                candidate_id = str(candidate.get("id", "")).strip()
                if candidate_id and candidate_id in index_by_id:
                    base = updated_list[index_by_id[candidate_id]]
                    if isinstance(base, dict):
                        merged_candidate = dict(base)
                        merged_candidate.update(candidate)
                        updated_list[index_by_id[candidate_id]] = merged_candidate
                else:
                    updated_list.append(candidate)

            merged["collaborators"] = updated_list
            continue

        merged[key] = value

    return merged


def evaluate_intervention(progress: Dict[str, Any]) -> Dict[str, Any]:
    reasons = []

    blockers = progress.get("blockers") or []
    if blockers:
        reasons.append(f"{len(blockers)} blocker(s) open")

    risk_level = str(progress.get("risk_level", "low")).lower()
    if risk_level in {"high", "critical"}:
        reasons.append(f"risk level is {risk_level}")

    failed_checks = int(progress.get("failed_checks", 0))
    if failed_checks > 0:
        reasons.append(f"{failed_checks} check(s) failed")

    pipeline = progress.get("pipeline_metrics") if isinstance(progress.get("pipeline_metrics"), dict) else {}
    testing = pipeline.get("testing") if isinstance(pipeline.get("testing"), dict) else {}
    ci = pipeline.get("ci") if isinstance(pipeline.get("ci"), dict) else {}
    if int(testing.get("regressions", 0)) > 0:
        reasons.append(f"{int(testing.get('regressions', 0))} regression(s) detected")
    if str(ci.get("last_build_status", "success")).lower() == "failed":
        reasons.append("last CI build failed")

    collaborators = progress.get("collaborators") if isinstance(progress.get("collaborators"), list) else []
    blocked_collaborators = []
    for item in collaborators:
        if not isinstance(item, dict):
            continue
        if bool(item.get("needs_human", False)) or str(item.get("status", "")).lower() == "blocked":
            blocked_collaborators.append(str(item.get("name", "unknown")))
    if blocked_collaborators:
        reasons.append("collaborator escalation: " + ", ".join(blocked_collaborators))

    last_update = parse_iso(str(progress.get("last_update", "")))
    if last_update is not None:
        stale_minutes = (dt.datetime.now(dt.timezone.utc) - last_update).total_seconds() / 60.0
        if stale_minutes > 15:
            reasons.append(f"no updates for {int(stale_minutes)} minutes")

    queue = build_intervention_queue(progress)
    if queue:
        top_items = "; ".join(item.get("reason", "") for item in queue[:3] if item.get("reason"))
        reasons.append(f"priority queue active ({top_items})")

    if reasons:
        return {
            "recommended": True,
            "reason": "Intervention recommended: " + "; ".join(reasons) + ".",
        }

    return {
        "recommended": False,
        "reason": "No immediate intervention needed.",
    }


def normalize_progress(payload: Dict[str, Any], existing: Dict[str, Any] | None = None) -> Dict[str, Any]:
    current = merge_payload(existing or default_progress(), payload)

    progress_percent = int(current.get("progress_percent", 0))
    current["progress_percent"] = max(0, min(100, progress_percent))

    status = str(current.get("status", "green")).lower()
    if status not in {"green", "yellow", "red"}:
        status = "yellow"
    current["status"] = status

    risk_level = str(current.get("risk_level", "low")).lower()
    if risk_level not in {"low", "medium", "high", "critical"}:
        risk_level = "medium"
    current["risk_level"] = risk_level

    blockers = current.get("blockers")
    if not isinstance(blockers, list):
        blockers = []
    current["blockers"] = [str(item) for item in blockers if str(item).strip()]

    current["pipeline_metrics"] = normalize_pipeline_metrics(current.get("pipeline_metrics"))
    current["collaborators"] = normalize_collaborators(current.get("collaborators"))
    current["recent_events"] = normalize_events(current.get("recent_events"))

    current["failed_checks"] = max(0, int(current.get("failed_checks", 0)))
    current["intervention_queue"] = build_intervention_queue(current)
    current["last_update"] = now_iso()
    current["human_intervention"] = evaluate_intervention(current)
    return current


def attach_project_meta(progress: Dict[str, Any], project_meta: Dict[str, Any] | None = None) -> Dict[str, Any]:
    meta = project_meta or current_project_meta()
    progress = deepcopy(progress)
    project_id = str(meta.get("id") or "default")
    raw_path = str(meta.get("path") or "")
    progress["project_id"] = project_id
    progress["project"] = str(meta.get("name") or progress.get("project") or DEFAULT_PROJECT_NAME)
    progress["project_path"] = policy_mask_project_path(project_id, raw_path)
    progress["project_path_configured"] = bool(raw_path.strip())
    return progress


def project_selector_from_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "project_id": payload.get("project_id"),
        "project_name": payload.get("project_name") or payload.get("project") or payload.get("name"),
        "project_path": payload.get("project_path") or payload.get("path"),
    }


def build_governance_event_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "time": payload.get("time"),
        "type": payload.get("type"),
        "actor": payload.get("actor"),
        "message": payload.get("message"),
        "severity": payload.get("severity"),
        "objective_id": payload.get("objective_id"),
        "task_id": payload.get("task_id"),
        "request_id": payload.get("request_id"),
        "gate": payload.get("gate"),
        "result": payload.get("result"),
        "workflow_id": payload.get("workflow_id"),
        "run_id": payload.get("run_id"),
        "step_id": payload.get("step_id"),
        "interaction_id": payload.get("interaction_id"),
        "decision": payload.get("decision"),
        "channel": payload.get("channel"),
        "target": payload.get("target"),
        "duration_ms": payload.get("duration_ms"),
    }


def read_progress() -> Dict[str, Any]:
    with FILE_LOCK:
        if not PROGRESS_FILE.exists():
            PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
            data = default_progress(current_project_meta())
            atomic_write_json(PROGRESS_FILE, data)
            debug_log(f"read_progress initialized data_file={PROGRESS_FILE}")
            return data
        data = attach_project_meta(load_json_with_recovery(PROGRESS_FILE, default_progress(current_project_meta())))
        debug_log(
            f"read_progress project_id={data.get('project_id')} project={data.get('project')} data_file={PROGRESS_FILE} progress={data.get('progress_percent')}"
        )
        return data


def write_progress(payload: Dict[str, Any]) -> Dict[str, Any]:
    with FILE_LOCK:
        validate_progress_payload(payload)
        project_selector = project_selector_from_payload(payload)
        target_meta = current_project_meta()
        if any(str(project_selector.get(key) or "").strip() for key in ("project_id", "project_name", "project_path")):
            target_meta = select_or_create_project(project_selector)

        existing = read_progress()
        updated = normalize_progress(payload, existing=existing)
        updated = attach_project_meta(updated, target_meta)
        atomic_write_json(PROGRESS_FILE, updated)
        debug_log(
            f"write_progress project_id={updated.get('project_id')} project={updated.get('project')} data_file={PROGRESS_FILE} progress={updated.get('progress_percent')}"
        )
        return updated


def file_hash(path: Path) -> str:
    if not path.exists():
        return ""
    content = path.read_bytes()
    return hashlib.sha256(content).hexdigest()


class Handler(BaseHTTPRequestHandler):
    server_version = "FrameworkDashboard/1.0"

    def _send_json(self, data: Dict[str, Any], code: int = HTTPStatus.OK) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_text(self, text: str, code: int = HTTPStatus.OK, content_type: str = "text/plain; charset=utf-8") -> None:
        body = text.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/" or path == "/index.html":
            index_file = WEB_DIR / "index.html"
            if not index_file.exists():
                self._send_text("index.html not found", code=HTTPStatus.NOT_FOUND)
                return
            self._send_text(index_file.read_text(encoding="utf-8"), content_type="text/html; charset=utf-8")
            return

        if path == "/api/progress":
            debug_log("GET /api/progress")
            collect_runtime_signals(force=False)
            self._send_json(read_progress())
            return

        if path == "/api/health":
            debug_log("GET /api/health")
            self._send_json(health_snapshot())
            return

        if path == "/api/project":
            registry = load_registry()
            current_id = registry.get("current_project_id", "default")
            projects = list(registry.get("projects", {}).values()) if isinstance(registry.get("projects"), dict) else []
            public_projects = [public_project_meta(item) for item in projects]
            debug_log(f"GET /api/project current_project_id={current_id} projects={len(projects)}")
            self._send_json({
                "current_project_id": current_id,
                "current_project": public_project_meta(current_project_meta()),
                "projects": public_projects,
            })
            return

        if path == "/api/projects":
            registry = load_registry()
            projects = list(registry.get("projects", {}).values()) if isinstance(registry.get("projects"), dict) else []
            self._send_json({
                "projects": [public_project_meta(item) for item in projects],
                "current_project_id": registry.get("current_project_id", "default"),
            })
            return

        if path == "/api/intervention-queue":
            progress = read_progress()
            queue = progress.get("intervention_queue")
            if not isinstance(queue, list):
                queue = build_intervention_queue(progress)
            self._send_json({"queue": queue, "count": len(queue)})
            return

        if path == "/api/governance":
            progress = read_progress()
            pipeline = progress.get("pipeline_metrics") if isinstance(progress.get("pipeline_metrics"), dict) else {}
            governance = pipeline.get("governance") if isinstance(pipeline.get("governance"), dict) else {}
            evidence = [
                item
                for item in (progress.get("recent_events") if isinstance(progress.get("recent_events"), list) else [])
                if isinstance(item, dict)
                and str(item.get("type") or "")
                in {
                    "objective_set",
                    "plan_committed",
                    "task_started",
                    "task_completed",
                    "task_stopped",
                    "gate_passed",
                    "gate_failed",
                    "human_review_requested",
                    "human_review_resolved",
                    "decision_logged",
                    "rollback",
                    "auth_prompted",
                    "auth_approved",
                    "auth_denied",
                    "action_confirmed",
                    "action_skipped",
                    "action_stopped",
                }
            ]
            self._send_json(
                {
                    "project": progress.get("project"),
                    "project_id": progress.get("project_id"),
                    "governance": governance,
                    "intervention": progress.get("human_intervention"),
                    "queue": progress.get("intervention_queue"),
                    "evidence": evidence[:20],
                }
            )
            return

        if path == "/api/stream":
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.end_headers()

            last_hash = ""
            try:
                while True:
                    collect_runtime_signals(force=False)
                    current_hash = file_hash(PROGRESS_FILE)
                    if current_hash != last_hash:
                        payload = json.dumps(read_progress(), ensure_ascii=False)
                        self.wfile.write(f"data: {payload}\n\n".encode("utf-8"))
                        self.wfile.flush()
                        last_hash = current_hash
                    else:
                        self.wfile.write(b": keep-alive\n\n")
                        self.wfile.flush()
                    time.sleep(2)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                return

        self._send_text("Not found", code=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(content_length)
            payload = json.loads(raw.decode("utf-8")) if raw else {}
            if not isinstance(payload, dict):
                raise validation_error("payload must be a JSON object")

            if parsed.path == "/api/project":
                debug_log(f"POST /api/project payload={payload}")
                selected = select_or_create_project(payload)
                registry = load_registry()
                self._send_json({
                    "current_project_id": registry.get("current_project_id", "default"),
                    "current_project": public_project_meta(selected),
                    "projects": [
                        public_project_meta(item)
                        for item in (list(registry.get("projects", {}).values()) if isinstance(registry.get("projects"), dict) else [])
                    ],
                })
                return

            if parsed.path == "/api/collect":
                debug_log(f"POST /api/collect payload={payload}")
                project_selector = {
                    "project_id": payload.get("project_id"),
                    "project_name": payload.get("project_name") or payload.get("project") or payload.get("name"),
                    "project_path": payload.get("project_path") or payload.get("path"),
                }
                if any(str(project_selector.get(key) or "").strip() for key in ("project_id", "project_name", "project_path")):
                    select_or_create_project(project_selector)
                updated = collect_runtime_signals(force=True)
                self._send_json(updated)
                return

            if parsed.path == "/api/governance/event":
                debug_log(f"POST /api/governance/event payload={payload}")
                project_selector = {
                    "project_id": payload.get("project_id"),
                    "project_name": payload.get("project_name") or payload.get("project") or payload.get("name"),
                    "project_path": payload.get("project_path") or payload.get("path"),
                }
                if any(str(project_selector.get(key) or "").strip() for key in ("project_id", "project_name", "project_path")):
                    select_or_create_project(project_selector)

                current_meta = current_project_meta()
                project_root = policy_resolve_project_root(
                    str(current_meta.get("id") or "default"),
                    str(current_meta.get("path") or ""),
                    BASE_DIR,
                )
                event_payload = build_governance_event_payload(payload)
                stored_event = append_governance_event(project_root=project_root, event=event_payload)
                updated = collect_runtime_signals(force=True)
                self._send_json({"event": stored_event, "progress": updated})
                return

            if parsed.path != "/api/progress":
                self._send_text("Not found", code=HTTPStatus.NOT_FOUND)
                return

            debug_log(f"POST /api/progress payload_keys={sorted(payload.keys())}")
            # Route incoming progress to the intended project when metadata is provided.
            project_selector = {
                "project_id": payload.get("project_id"),
                "project_name": payload.get("project_name") or payload.get("project") or payload.get("name"),
                "project_path": payload.get("project_path") or payload.get("path"),
            }
            if any(str(project_selector.get(key) or "").strip() for key in ("project_id", "project_name", "project_path")):
                select_or_create_project(project_selector)

            updated = write_progress(payload)
            self._send_json(updated)
        except ValueError as exc:
            self._send_json({"error": str(exc)}, code=HTTPStatus.BAD_REQUEST)
        except Exception as exc:
            self._send_json({"error": str(exc)}, code=HTTPStatus.INTERNAL_SERVER_ERROR)


class DashboardHTTPServer(ThreadingHTTPServer):
    def handle_error(self, request, client_address):
        _, exc, _ = sys.exc_info()
        if isinstance(exc, ConnectionAbortedError):
            return
        super().handle_error(request, client_address)


def _listening_process_hint(host: str, port: int) -> str:
    commands: list[list[str]] = []
    if os.name == "nt":
        commands.append(["netstat", "-ano", "-p", "tcp"])
    else:
        commands.append(["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN"])
        commands.append(["ss", "-ltnp"])

    for command in commands:
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
                timeout=3,
            )
        except Exception:
            continue

        if result.returncode != 0 or not result.stdout.strip():
            continue

        lines = [line.strip() for line in result.stdout.splitlines() if str(port) in line]
        if not lines:
            continue

        if os.name == "nt":
            normalized_host = host if host not in {"0.0.0.0", "::"} else ""
            filtered = [
                line for line in lines if f":{port}" in line and (not normalized_host or normalized_host in line or "0.0.0.0" in line)
            ]
            if filtered:
                return filtered[0]
        else:
            return lines[0]

    return ""


def _format_bind_error(host: str, port: int, exc: OSError) -> str:
    winerror = getattr(exc, "winerror", None)
    err_no = getattr(exc, "errno", None)

    if winerror == 10048 or err_no == errno.EADDRINUSE:
        lines = [
            f"Failed to start dashboard: {host}:{port} is already in use.",
            "Choose a different --port or stop the existing listener first.",
        ]
        listener = _listening_process_hint(host, port)
        if listener:
            lines.append(f"Listener hint: {listener}")
        elif os.name == "nt":
            lines.append(f"Check listener: netstat -ano -p tcp | findstr :{port}")
        else:
            lines.append(f"Check listener: lsof -nP -iTCP:{port} -sTCP:LISTEN")
        return "\n".join(lines)

    if winerror == 10013 or err_no == errno.EACCES:
        return (
            f"Failed to start dashboard: access denied when binding {host}:{port}.\n"
            "Try a different port or run with sufficient permissions."
        )

    if err_no in {errno.EADDRNOTAVAIL, 10049}:
        return (
            f"Failed to start dashboard: host {host} is not available on this machine.\n"
            "Use a valid local interface address or 127.0.0.1."
        )

    return f"Failed to start dashboard on {host}:{port}: {exc}"


def run() -> int:
    global PROGRESS_FILE
    global DEFAULT_PROJECT_NAME
    global AUTO_COLLECT_ENABLED
    global AUTO_COLLECT_INTERVAL_SECONDS

    parser = argparse.ArgumentParser(description="Run live progress dashboard server")
    parser.add_argument("--host", default=os.getenv("DASHBOARD_HOST", "127.0.0.1"), help="Bind host")
    parser.add_argument("--port", type=int, default=int(os.getenv("DASHBOARD_PORT", "8765")), help="Bind port")
    parser.add_argument("--data-file", default=str(PROGRESS_FILE), help="Path to live progress JSON file")
    parser.add_argument(
        "--collect-interval-seconds",
        type=int,
        default=AUTO_COLLECT_INTERVAL_SECONDS,
        help="Auto-collect interval for git/test signals",
    )
    parser.add_argument(
        "--disable-auto-collect",
        action="store_true",
        help="Disable periodic git/test metric collection",
    )
    parser.add_argument(
        "--default-project",
        default=DEFAULT_PROJECT_NAME,
        help="Default project name used when initializing a new data file",
    )
    args = parser.parse_args()

    PROGRESS_FILE = Path(args.data_file).expanduser().resolve()
    DEFAULT_PROJECT_NAME = args.default_project
    AUTO_COLLECT_INTERVAL_SECONDS = max(5, int(args.collect_interval_seconds))
    AUTO_COLLECT_ENABLED = (not bool(args.disable_auto_collect)) and AUTO_COLLECT_ENABLED

    registry = load_registry()
    current = registry.get("projects", {}).get(registry.get("current_project_id", "default")) if isinstance(registry.get("projects"), dict) else None
    if isinstance(current, dict) and current.get("data_file"):
        PROGRESS_FILE = Path(str(current.get("data_file"))).expanduser().resolve()

    PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
    WEB_DIR.mkdir(parents=True, exist_ok=True)
    if not PROGRESS_FILE.exists():
        atomic_write_json(PROGRESS_FILE, default_progress(current if isinstance(current, dict) else None))

    collect_runtime_signals(force=True)

    try:
        server = DashboardHTTPServer((args.host, args.port), Handler)
    except OSError as exc:
        print(_format_bind_error(args.host, args.port, exc), file=sys.stderr)
        return 1

    collector_stop_event = threading.Event()
    collector_thread: threading.Thread | None = None
    if AUTO_COLLECT_ENABLED:
        collector_thread = threading.Thread(target=collector_worker, args=(collector_stop_event,), daemon=True)
        collector_thread.start()

    print(f"Dashboard running at http://{args.host}:{args.port}")
    print(f"Progress data file: {PROGRESS_FILE}")
    print(f"Auto collector: {'enabled' if AUTO_COLLECT_ENABLED else 'disabled'} ({AUTO_COLLECT_INTERVAL_SECONDS}s)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        collector_stop_event.set()
        if collector_thread is not None and collector_thread.is_alive():
            collector_thread.join(timeout=2)
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
