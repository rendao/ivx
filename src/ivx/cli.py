#!/usr/bin/env python3
"""Command entrypoint for dashboard package-style usage.

Examples:
- python dashboard/main.py serve --host 127.0.0.1 --port 8765
- python dashboard/main.py integrate --project-path E:/path/to/project
- python dashboard/main.py push-progress --phase "CI" --task "Build" --progress 50 --status yellow --risk medium
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import random
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from .app import main as app_main
from .push_ci_result import main as push_ci_main
from .push_collaborator_update import main as push_collaborator_main
from .push_governance_event import main as push_governance_main
from .push_live_progress import main as push_progress_main


ROOT = Path(__file__).resolve().parent


def _run_callable(callable_main, args: list[str]) -> int:
    old_argv = sys.argv
    try:
        sys.argv = [old_argv[0], *args]
        return int(callable_main())
    finally:
        sys.argv = old_argv


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def _parse_ports(raw: str) -> list[int]:
    ports: list[int] = []
    for part in raw.split(","):
        value = part.strip()
        if value:
            ports.append(int(value))
    return ports


def _is_port_free(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
            return True
        except OSError:
            return False


def _pick_port(host: str, candidates: list[int]) -> int:
    for port in candidates:
        if _is_port_free(host, port):
            return port
    for _ in range(40):
        port = random.randint(20000, 26000)
        if _is_port_free(host, port):
            return port
    raise RuntimeError("Failed to find a free port")


def _wait_dashboard_ready(url: str, timeout_seconds: int) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as response:
                if response.status == 200:
                    return
        except Exception:
            time.sleep(0.5)
    raise TimeoutError(f"Dashboard did not become ready in {timeout_seconds}s: {url}")


def _get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def _write_report(
    report_file: Path,
    target_project_path: Path,
    host: str,
    port: int,
    selected_fields: dict,
    project_name: str,
    phase: str,
    task: str,
) -> None:
    report_file.parent.mkdir(parents=True, exist_ok=True)
    report = f"""# Dashboard Integration Report

## Timestamp
- {_now_iso()}

## Target Project
- Path: {target_project_path.as_posix()}
- Project Name: {project_name}

## Dashboard Endpoint
- Base URL: http://{host}:{port}
- Progress API: http://{host}:{port}/api/progress

## Contract Push
- phase: {phase}
- task: {task}

## Readback Snapshot
- project: {selected_fields.get('project', '')}
- phase: {selected_fields.get('phase', '')}
- task: {selected_fields.get('task', '')}
- progress_percent: {selected_fields.get('progress_percent', '')}
- status: {selected_fields.get('status', '')}
- risk_level: {selected_fields.get('risk_level', '')}
- last_update: {selected_fields.get('last_update', '')}

## Outcome
- Integration test completed successfully.
- Target project can emit minimum dashboard contract.
"""
    report_file.write_text(report, encoding="utf-8")


def _print_help() -> None:
    print("Dashboard CLI")
    print("Usage:")
    print("  python -m ivx serve [server args]")
    print("  python -m ivx integrate|i [integration args]")
    print("  python -m ivx push-progress [progress args]")
    print("  python -m ivx push-collaborator [collaborator args]")
    print("  python -m ivx push-ci [ci args]")
    print("  python -m ivx push-governance [governance event args]")
    print("")
    print("Examples:")
    print("  python -m ivx serve --host 127.0.0.1 --port 8789")
    print("  python -m ivx i -p E:/YanXin/psy-2026/mini")


def _run_integration(args: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Integrate a target project with dashboard and verify contract")
    parser.add_argument("-p", "--project-path", required=True, help="Absolute path to target project")
    parser.add_argument("-n", "--project-name", default="", help="Dashboard project name (default: target folder name)")
    parser.add_argument("-H", "--host", default="127.0.0.1", help="Dashboard host")
    parser.add_argument("-P", "--ports", default="8765,8788,8799,8800,8810", help="Comma-separated candidate ports")
    parser.add_argument("-f", "--phase", default="Pilot Integration")
    parser.add_argument("-t", "--task", default="Contract push")
    parser.add_argument("-g", "--progress", type=int, default=25)
    parser.add_argument("-s", "--status", choices=["green", "yellow", "red"], default="yellow")
    parser.add_argument("-r", "--risk", choices=["low", "medium", "high", "critical"], default="medium")
    parser.add_argument("-a", "--event-actor", default="Integration")
    parser.add_argument("-m", "--event-message", default="Initial dashboard contract push")
    parser.add_argument(
        "-o",
        "--report-file",
        default="docs/19_dashboard_integration_report.md",
        help="Report path relative to framework repo or absolute path",
    )
    parsed = parser.parse_args(args)

    workspace_root = Path.cwd()
    target_project_path = Path(parsed.project_path).expanduser().resolve()
    if not target_project_path.exists() or not target_project_path.is_dir():
        raise SystemExit(f"Target project path not found: {target_project_path}")

    project_name = parsed.project_name.strip() or target_project_path.name
    candidate_ports = _parse_ports(parsed.ports)
    selected_port = _pick_port(parsed.host, candidate_ports)

    server_cmd = [
        sys.executable,
        "-m",
        "ivx.app",
        "--host",
        parsed.host,
        "--port",
        str(selected_port),
        "--default-project",
        project_name,
    ]

    print(f"[INFO] Target project: {target_project_path}")
    print(f"[INFO] Selected dashboard port: {selected_port}")
    print(f"[INFO] Starting dashboard server: {' '.join(server_cmd)}")

    server_proc = subprocess.Popen(
        server_cmd,
        cwd=str(workspace_root),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    try:
        base_url = f"http://{parsed.host}:{selected_port}"
        progress_url = f"{base_url}/api/progress"

        _wait_dashboard_ready(progress_url, timeout_seconds=25)
        print(f"[OK] Dashboard is ready: {progress_url}")

        env = os.environ.copy()
        env["DASHBOARD_API_URL"] = progress_url
        env["DASHBOARD_PROJECT"] = project_name

        push_cmd = [
            sys.executable,
            "-m",
            "ivx.push_live_progress",
            "--phase",
            parsed.phase,
            "--task",
            parsed.task,
            "--progress",
            str(parsed.progress),
            "--status",
            parsed.status,
            "--risk",
            parsed.risk,
            "--event-actor",
            parsed.event_actor,
            "--event-message",
            parsed.event_message,
        ]

        print(f"[INFO] Pushing minimum contract: {' '.join(push_cmd)}")
        push_completed = subprocess.run(
            push_cmd,
            cwd=str(target_project_path),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        if push_completed.returncode != 0:
            print(push_completed.stdout)
            print(push_completed.stderr)
            raise RuntimeError("Contract push failed")

        print("[OK] Contract push completed")

        progress = _get_json(progress_url)
        selected = {
            "project": progress.get("project"),
            "phase": progress.get("phase"),
            "task": progress.get("task"),
            "progress_percent": progress.get("progress_percent"),
            "status": progress.get("status"),
            "risk_level": progress.get("risk_level"),
            "last_update": progress.get("last_update"),
        }
        print("[OK] Readback:")
        print(json.dumps(selected, ensure_ascii=False, indent=2))

        report_file = Path(parsed.report_file)
        if not report_file.is_absolute():
            report_file = (workspace_root / report_file).resolve()

        _write_report(
            report_file=report_file,
            target_project_path=target_project_path,
            host=parsed.host,
            port=selected_port,
            selected_fields=selected,
            project_name=project_name,
            phase=parsed.phase,
            task=parsed.task,
        )
        print(f"[OK] Report written: {report_file}")

    finally:
        if server_proc.poll() is None:
            server_proc.terminate()
            try:
                server_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server_proc.kill()

        if server_proc.stdout is not None:
            tail = server_proc.stdout.read().strip()
            if tail:
                print("[INFO] Dashboard server output tail:")
                print(tail)

    return 0


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] in {"-h", "--help", "help"}:
        _print_help()
        return 0

    command = sys.argv[1]
    rest = sys.argv[2:]

    if command == "serve":
        return _run_callable(app_main, rest)
    if command in {"integrate", "i"}:
        return _run_integration(rest)
    if command == "push-progress":
        return _run_callable(push_progress_main, rest)
    if command == "push-collaborator":
        return _run_callable(push_collaborator_main, rest)
    if command == "push-ci":
        return _run_callable(push_ci_main, rest)
    if command == "push-governance":
        return _run_callable(push_governance_main, rest)

    print(f"Unknown command: {command}")
    _print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
