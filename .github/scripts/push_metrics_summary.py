#!/usr/bin/env python3
"""Push GitHub Actions metrics summary to IVX dashboard.

This script is intentionally non-blocking when dashboard URL is not configured,
so repositories can keep CI green while adopting metrics gradually.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import urllib.request


def _status_to_visuals(build_status: str) -> tuple[str, str, str]:
    normalized = str(build_status or "").strip().lower()
    if normalized == "failed":
        return "red", "high", "CI failed"
    if normalized == "running":
        return "yellow", "medium", "CI running"
    return "green", "low", "CI passed"


def _build_run_url() -> str:
    server = os.getenv("GITHUB_SERVER_URL", "https://github.com").rstrip("/")
    repo = os.getenv("GITHUB_REPOSITORY", "").strip()
    run_id = os.getenv("GITHUB_RUN_ID", "").strip()
    if not repo or not run_id:
        return ""
    return f"{server}/{repo}/actions/runs/{run_id}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Push GitHub CI metrics summary to IVX dashboard API.")
    parser.add_argument("--summary-file", default="artifacts/ci/output/metrics-summary.json", help="Metrics summary JSON path.")
    parser.add_argument("--url", default=os.getenv("DASHBOARD_API_URL", ""), help="Dashboard /api/progress URL.")
    parser.add_argument("--project", default=os.getenv("DASHBOARD_PROJECT_NAME", ""), help="Dashboard project name.")
    parser.add_argument("--project-id", default=os.getenv("DASHBOARD_PROJECT_ID", ""), help="Dashboard project id.")
    parser.add_argument("--project-path", default=os.getenv("DASHBOARD_PROJECT_PATH", ""), help="Dashboard project path.")
    parser.add_argument("--phase", default=os.getenv("DASHBOARD_PHASE", "Phase 2 - Delivery"), help="Progress phase label.")
    parser.add_argument("--task", default=os.getenv("DASHBOARD_TASK", "GitHub CI validation"), help="Progress task label.")
    parser.add_argument("--progress-percent", type=int, default=int(os.getenv("DASHBOARD_PROGRESS_PERCENT", "70")), help="Progress percent (0-100).")
    args = parser.parse_args()

    summary_path = Path(args.summary_file).resolve()
    if not summary_path.is_file():
        raise FileNotFoundError(f"Summary file not found: {summary_path}")

    raw_summary = json.loads(summary_path.read_text(encoding="utf-8"))
    pipeline = raw_summary.get("pipeline_metrics") if isinstance(raw_summary.get("pipeline_metrics"), dict) else {}
    ci = pipeline.get("ci") if isinstance(pipeline.get("ci"), dict) else {}

    build_status = str(ci.get("last_build_status", "success"))
    status, risk_level, headline = _status_to_visuals(build_status)
    run_url = _build_run_url()
    message = headline if not run_url else f"{headline}: {run_url}"

    if not args.url.strip():
        print("DASHBOARD_API_URL is not configured; skip metrics push.")
        print(f"Summary available at: {summary_path}")
        return 0

    payload = {
        "project": args.project or "default",
        "project_id": args.project_id or None,
        "project_path": args.project_path or None,
        "phase": args.phase,
        "task": args.task,
        "progress_percent": max(0, min(100, int(args.progress_percent))),
        "status": status,
        "risk_level": risk_level,
        "pipeline_metrics": pipeline,
        "recent_events_append": [
            {
                "time": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                "type": "ci",
                "actor": "github-actions",
                "message": message,
                "severity": "critical" if build_status == "failed" else ("warning" if build_status == "running" else "info"),
            }
        ],
    }

    clean_payload = {k: v for k, v in payload.items() if v is not None}
    body = json.dumps(clean_payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        args.url,
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=10) as response:
        print(response.read().decode("utf-8"))

    print(f"Pushed metrics summary from: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())