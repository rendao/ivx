#!/usr/bin/env python3
"""Minimal release smoke check for IVX 0.2.0.

This script launches the dashboard server, pushes progress/collaborator/CI/governance updates,
and reads back the resulting state from the public API.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
DEFAULT_REPORT = ROOT / ".ivx" / "data" / "release-smoke-0.2.0.md"


def _build_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    env = os.environ.copy()
    pythonpath = env.get("PYTHONPATH", "")
    pieces = [str(SRC_DIR)]
    if pythonpath:
        pieces.append(pythonpath)
    env["PYTHONPATH"] = os.pathsep.join(pieces)
    if extra:
        env.update(extra)
    return env


def _wait_json(url: str, timeout_seconds: int) -> dict:
    deadline = time.time() + timeout_seconds
    last_error = ""
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            last_error = str(exc)
            time.sleep(0.5)
    raise TimeoutError(f"Timed out waiting for {url}: {last_error}")


def _run_module(module: str, args: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", module, *args],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _run_script(script: str, args: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, script, *args],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _write_report(report_file: Path, payload: dict) -> None:
    report_file.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# IVX 0.2.0 Smoke Report",
        "",
        f"- Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S %z')}",
        f"- Base URL: {payload['base_url']}",
        f"- Progress: {payload['progress_percent']}%",
        f"- Status: {payload['status']}",
        f"- Risk: {payload['risk_level']}",
        f"- Project: {payload['project']}",
        f"- Project Path: {payload['project_path']}",
        "",
        "## Checks",
        f"- Health: {payload['health_status']}",
        f"- Collaborator count: {payload['collaborators_count']}",
        f"- Recent events: {payload['recent_events_count']}",
        f"- CI status: {payload['ci_status']}",
        f"- Governance events: {payload['governance_events_count']}",
    ]
    report_file.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the IVX 0.2.0 smoke check.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8790)
    parser.add_argument("--timeout", type=int, default=45)
    parser.add_argument("--report-file", default=str(DEFAULT_REPORT))
    args = parser.parse_args()

    base_url = f"http://{args.host}:{args.port}"
    progress_url = f"{base_url}/api/progress"
    health_url = f"{base_url}/api/health"

    report_file = Path(args.report_file)
    if not report_file.is_absolute():
        report_file = (ROOT / report_file).resolve()

    env = _build_env()

    with tempfile.TemporaryDirectory(prefix="ivx-smoke-") as temp_dir:
        temp_root = Path(temp_dir)
        temp_project = temp_root / "smoke-project"
        temp_project.mkdir(parents=True, exist_ok=True)
        data_file = temp_root / "dashboard-state.json"

        server_cmd = [
            str(ROOT / "app.py"),
            "--host",
            args.host,
            "--port",
            str(args.port),
            "--data-file",
            str(data_file),
            "--disable-auto-collect",
            "--default-project",
            "release-smoke",
        ]
        server_proc = subprocess.Popen(
            [sys.executable, *server_cmd],
            cwd=str(ROOT),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        try:
            health = _wait_json(health_url, args.timeout)
            if str(health.get("service") or "") != "up":
                raise RuntimeError(f"Unexpected health response: {health}")

            install_check = _run_script(
                "app.py",
                ["--help"],
                env,
            )
            if install_check.returncode != 0:
                raise RuntimeError(f"Startup help check failed: {install_check.stderr or install_check.stdout}")

            merge_json = temp_root / "merge.json"
            merge_json.write_text(json.dumps({"project_path": str(temp_project)}, ensure_ascii=False, indent=2), encoding="utf-8")

            progress_push = _run_module(
                "ivx.push_live_progress",
                [
                    "--url",
                    progress_url,
                    "--project",
                    "release-smoke",
                    "--phase",
                    "Smoke Phase",
                    "--task",
                    "Verify release chain",
                    "--progress",
                    "67",
                    "--status",
                    "yellow",
                    "--risk",
                    "medium",
                    "--failed-checks",
                    "0",
                    "--next-milestone",
                    "Readback validated",
                    "--event-actor",
                    "SmokeRunner",
                    "--event-message",
                    "Smoke progress push",
                    "--event-severity",
                    "info",
                    "--merge-json",
                    str(merge_json),
                ],
                env,
            )
            if progress_push.returncode != 0:
                raise RuntimeError(progress_push.stderr or progress_push.stdout)

            collaborator_push = _run_module(
                "ivx.push_collaborator_update",
                [
                    "--url",
                    progress_url,
                    "--id",
                    "smoke-dev",
                    "--name",
                    "Smoke Dev",
                    "--role",
                    "development",
                    "--status",
                    "active",
                    "--task",
                    "Smoke collaborator update",
                    "--progress",
                    "67",
                    "--commits",
                    "1",
                    "--tests-passed",
                    "1",
                    "--tests-failed",
                    "0",
                    "--prs-open",
                    "0",
                    "--reviews-pending",
                    "0",
                    "--event-message",
                    "Smoke collaborator push",
                ],
                env,
            )
            if collaborator_push.returncode != 0:
                raise RuntimeError(collaborator_push.stderr or collaborator_push.stdout)

            ci_push = _run_module(
                "ivx.push_ci_result",
                [
                    "--url",
                    progress_url,
                    "--build-status",
                    "success",
                    "--build-success-rate",
                    "100",
                    "--deploy-success-rate",
                    "100",
                    "--failed-checks",
                    "0",
                    "--regressions",
                    "0",
                    "--message",
                    "Smoke CI push",
                ],
                env,
            )
            if ci_push.returncode != 0:
                raise RuntimeError(ci_push.stderr or ci_push.stdout)

            governance_push = _run_module(
                "ivx.push_governance_event",
                [
                    "--url",
                    f"{base_url}/api/governance/event",
                    "--type",
                    "decision_logged",
                    "--actor",
                    "smoke-runner",
                    "--message",
                    "Smoke governance event",
                    "--severity",
                    "info",
                    "--project-name",
                    "release-smoke",
                    "--project-path",
                    str(temp_project),
                ],
                env,
            )
            if governance_push.returncode != 0:
                raise RuntimeError(governance_push.stderr or governance_push.stdout)

            readback = _wait_json(progress_url, args.timeout)
            health_after = _wait_json(health_url, args.timeout)

            project_name = str(readback.get("project") or "")
            project_path = str(readback.get("project_path") or "")
            collaborators = readback.get("collaborators") if isinstance(readback.get("collaborators"), list) else []
            recent_events = readback.get("recent_events") if isinstance(readback.get("recent_events"), list) else []
            pipeline = readback.get("pipeline_metrics") if isinstance(readback.get("pipeline_metrics"), dict) else {}
            ci = pipeline.get("ci") if isinstance(pipeline.get("ci"), dict) else {}
            governance = pipeline.get("governance") if isinstance(pipeline.get("governance"), dict) else {}

            smoke_payload = {
                "base_url": base_url,
                "progress_percent": int(readback.get("progress_percent", 0)),
                "status": str(readback.get("status") or ""),
                "risk_level": str(readback.get("risk_level") or ""),
                "project": project_name,
                "project_path": project_path,
                "health_status": str(health_after.get("status") or ""),
                "collaborators_count": len(collaborators),
                "recent_events_count": len(recent_events),
                "ci_status": str(ci.get("last_build_status") or ""),
                "governance_events_count": int(governance.get("events_24h", 0)),
            }

            if smoke_payload["progress_percent"] != 67:
                raise RuntimeError(f"Unexpected progress percent: {smoke_payload['progress_percent']}")
            if smoke_payload["health_status"] not in {"ok", "degraded"}:
                raise RuntimeError(f"Unexpected health status: {smoke_payload['health_status']}")
            if smoke_payload["ci_status"] != "success":
                raise RuntimeError(f"Unexpected CI status: {smoke_payload['ci_status']}")
            if smoke_payload["collaborators_count"] < 1:
                raise RuntimeError("Collaborator update did not land")
            if smoke_payload["recent_events_count"] < 3:
                raise RuntimeError("Expected progress, collaborator, and CI events")

            _write_report(report_file, smoke_payload)
            print(json.dumps(smoke_payload, ensure_ascii=False, indent=2))
            print(f"Smoke report written to: {report_file}")

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
                    print("[server output]")
                    print(tail)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())