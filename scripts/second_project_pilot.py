#!/usr/bin/env python3
"""Second-project onboarding pilot for IVX.

This script validates non-invasive multi-project onboarding by:
1) starting the dashboard server against isolated temp state,
2) pushing updates for a primary and a second project,
3) verifying project registry and readback switching behavior,
4) writing a markdown report for evidence.
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
DEFAULT_REPORT = ROOT / ".ivx" / "data" / "second-project-pilot.md"

PRIMARY_ID = "pilot-primary"
SECOND_ID = "pilot-second"


def _build_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    env = os.environ.copy()
    pythonpath = env.get("PYTHONPATH", "")
    paths = [str(SRC_DIR)]
    if pythonpath:
        paths.append(pythonpath)
    env["PYTHONPATH"] = os.pathsep.join(paths)
    if extra:
        env.update(extra)
    return env


def _http_json(url: str, timeout: int = 10) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _post_json(url: str, payload: dict, timeout: int = 10) -> dict:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _wait_json(url: str, timeout_seconds: int, server_proc: subprocess.Popen[str] | None = None) -> dict:
    deadline = time.time() + timeout_seconds
    last_error = ""
    while time.time() < deadline:
        if server_proc is not None and server_proc.poll() is not None:
            output = ""
            if server_proc.stdout is not None:
                output = server_proc.stdout.read() or ""
            raise RuntimeError(f"Server exited before readiness check. Output:\n{output}")
        try:
            return _http_json(url, timeout=3)
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


def _push_progress(
    *,
    env: dict[str, str],
    progress_url: str,
    project_id: str,
    project_name: str,
    project_path: Path,
    task: str,
    progress_percent: int,
    status: str,
    risk: str,
) -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8", delete=False) as handle:
        merge_path = Path(handle.name)
        handle.write(
            json.dumps(
                {
                    "project_id": project_id,
                    "project_name": project_name,
                    "project_path": str(project_path),
                },
                ensure_ascii=False,
                indent=2,
            )
        )

    try:
        result = _run_module(
            "ivx.push_live_progress",
            [
                "--url",
                progress_url,
                "--project",
                project_name,
                "--phase",
                "Phase 1 - Pilot",
                "--task",
                task,
                "--progress",
                str(progress_percent),
                "--status",
                status,
                "--risk",
                risk,
                "--failed-checks",
                "0",
                "--next-milestone",
                "Cross-project pilot evidence",
                "--event-actor",
                "PilotRunner",
                "--event-message",
                f"Progress update for {project_id}",
                "--event-severity",
                "info",
                "--merge-json",
                str(merge_path),
            ],
            env,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr or result.stdout)
    finally:
        merge_path.unlink(missing_ok=True)


def _write_report(report_file: Path, payload: dict) -> None:
    report_file.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# IVX Second-Project Pilot Report",
        "",
        f"- Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S %z')}",
        f"- Base URL: {payload['base_url']}",
        f"- Project Count: {payload['project_count']}",
        f"- Current Project After Secondary Push: {payload['current_project_after_secondary']}",
        f"- Current Project After Switch Back: {payload['current_project_after_switch_back']}",
        f"- Primary Progress: {payload['primary_progress_percent']}%",
        f"- Secondary Progress: {payload['secondary_progress_percent']}%",
        f"- Secondary CI Status: {payload['secondary_ci_status']}",
        "",
        "## Validation",
        f"- Registry includes primary ID: {payload['has_primary_id']}",
        f"- Registry includes secondary ID: {payload['has_secondary_id']}",
        f"- Switch-back read matches primary: {payload['switch_back_matches_primary']}",
    ]
    report_file.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run second-project onboarding pilot validation.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8792)
    parser.add_argument("--timeout", type=int, default=45)
    parser.add_argument("--report-file", default=str(DEFAULT_REPORT))
    args = parser.parse_args()

    report_file = Path(args.report_file)
    if not report_file.is_absolute():
        report_file = (ROOT / report_file).resolve()

    base_url = f"http://{args.host}:{args.port}"
    progress_url = f"{base_url}/api/progress"
    project_url = f"{base_url}/api/project"
    health_url = f"{base_url}/api/health"

    with tempfile.TemporaryDirectory(prefix="ivx-second-project-") as temp_dir:
        temp_root = Path(temp_dir)
        state_root = temp_root / "state"
        primary_path = temp_root / "primary-project"
        secondary_path = temp_root / "second-project"
        primary_path.mkdir(parents=True, exist_ok=True)
        secondary_path.mkdir(parents=True, exist_ok=True)

        env = _build_env(
            {
                "DASHBOARD_STATE_ROOT": str(state_root),
                "DASHBOARD_AUTO_COLLECT": "0",
                "DASHBOARD_DEFAULT_PROJECT_PATH": str(primary_path),
            }
        )

        server_cmd = [
            sys.executable,
            str(ROOT / "app.py"),
            "--host",
            args.host,
            "--port",
            str(args.port),
            "--data-file",
            str(temp_root / "default-progress.json"),
            "--disable-auto-collect",
            "--default-project",
            "pilot-default",
        ]
        server_proc = subprocess.Popen(
            server_cmd,
            cwd=str(ROOT),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        try:
            health = _wait_json(health_url, args.timeout, server_proc=server_proc)
            if str(health.get("service") or "") != "up":
                raise RuntimeError(f"Unexpected health response: {health}")

            _push_progress(
                env=env,
                progress_url=progress_url,
                project_id=PRIMARY_ID,
                project_name="pilot-primary",
                project_path=primary_path,
                task="Primary project initialized",
                progress_percent=22,
                status="yellow",
                risk="medium",
            )

            _push_progress(
                env=env,
                progress_url=progress_url,
                project_id=SECOND_ID,
                project_name="pilot-second",
                project_path=secondary_path,
                task="Second project onboarded",
                progress_percent=57,
                status="green",
                risk="low",
            )

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
                    "Second-project CI evidence",
                ],
                env,
            )
            if ci_push.returncode != 0:
                raise RuntimeError(ci_push.stderr or ci_push.stdout)

            project_state_after_second = _http_json(project_url)
            readback_second = _http_json(progress_url)

            _post_json(project_url, {"project_id": PRIMARY_ID})
            readback_primary = _http_json(progress_url)

            project_ids = {
                str(item.get("id") or "")
                for item in (project_state_after_second.get("projects") or [])
                if isinstance(item, dict)
            }

            payload = {
                "base_url": base_url,
                "project_count": len(project_ids),
                "current_project_after_secondary": str(project_state_after_second.get("current_project_id") or ""),
                "current_project_after_switch_back": str(readback_primary.get("project_id") or ""),
                "primary_progress_percent": int(readback_primary.get("progress_percent", 0)),
                "secondary_progress_percent": int(readback_second.get("progress_percent", 0)),
                "secondary_ci_status": str(
                    (((readback_second.get("pipeline_metrics") or {}).get("ci") or {}).get("last_build_status") or "")
                ),
                "has_primary_id": PRIMARY_ID in project_ids,
                "has_secondary_id": SECOND_ID in project_ids,
                "switch_back_matches_primary": str(readback_primary.get("project_id") or "") == PRIMARY_ID,
            }

            if payload["project_count"] < 2:
                raise RuntimeError(f"Expected at least 2 projects, got {payload['project_count']}")
            if not payload["has_primary_id"] or not payload["has_secondary_id"]:
                raise RuntimeError(f"Missing expected IDs in registry: {sorted(project_ids)}")
            if payload["secondary_progress_percent"] != 57:
                raise RuntimeError(f"Unexpected secondary progress: {payload['secondary_progress_percent']}")
            if payload["primary_progress_percent"] != 22:
                raise RuntimeError(f"Unexpected primary progress after switch-back: {payload['primary_progress_percent']}")
            if payload["secondary_ci_status"] != "success":
                raise RuntimeError(f"Unexpected secondary CI status: {payload['secondary_ci_status']}")
            if not payload["switch_back_matches_primary"]:
                raise RuntimeError("Switch-back did not restore primary project readback")

            _write_report(report_file, payload)
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            print(f"Pilot report written to: {report_file}")
            return 0

        finally:
            if server_proc.poll() is None:
                server_proc.terminate()
                try:
                    server_proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    server_proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
