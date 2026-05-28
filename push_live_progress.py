#!/usr/bin/env python3
"""Push live progress updates to the dashboard API.

This script lives with the dashboard package so it can be reused as a standalone module.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
import os
from pathlib import Path
import urllib.request


def main() -> int:
    parser = argparse.ArgumentParser(description="Push live progress to dashboard")
    parser.add_argument(
        "--url",
        default=os.getenv("DASHBOARD_API_URL", "http://127.0.0.1:8765/api/progress"),
        help="Dashboard API URL",
    )
    parser.add_argument("--project", default=os.getenv("DASHBOARD_PROJECT", "generic-project"))
    parser.add_argument("--phase", required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument("--progress", type=int, required=True)
    parser.add_argument("--status", choices=["green", "yellow", "red"], required=True)
    parser.add_argument("--risk", choices=["low", "medium", "high", "critical"], required=True)
    parser.add_argument("--failed-checks", type=int, default=0)
    parser.add_argument("--blocker", action="append", default=[])
    parser.add_argument("--next-milestone", default="")
    parser.add_argument("--tasks-planned", type=int)
    parser.add_argument("--tasks-done", type=int)
    parser.add_argument("--tests-passed", type=int)
    parser.add_argument("--tests-failed", type=int)
    parser.add_argument("--coverage", type=int)
    parser.add_argument("--commits", type=int)
    parser.add_argument("--prs-open", type=int)
    parser.add_argument("--review-pending", type=int)
    parser.add_argument("--build-status", choices=["success", "failed", "running"])
    parser.add_argument("--event-actor")
    parser.add_argument("--event-type", default="update")
    parser.add_argument("--event-message")
    parser.add_argument("--event-severity", choices=["info", "warning", "critical"], default="info")
    parser.add_argument("--merge-json", help="Optional JSON file for advanced payload fields (collaborators, recent_events, etc.)")
    args = parser.parse_args()

    payload = {
        "project": args.project,
        "phase": args.phase,
        "task": args.task,
        "progress_percent": args.progress,
        "status": args.status,
        "risk_level": args.risk,
        "failed_checks": max(0, args.failed_checks),
        "blockers": args.blocker,
        "next_milestone": args.next_milestone,
    }

    pipeline_metrics = {
        "development": {},
        "testing": {},
        "commit": {},
        "ci": {},
    }

    if args.tasks_planned is not None:
        pipeline_metrics["development"]["tasks_planned"] = max(0, args.tasks_planned)
    if args.tasks_done is not None:
        pipeline_metrics["development"]["tasks_done"] = max(0, args.tasks_done)
    if args.tests_passed is not None:
        pipeline_metrics["testing"]["tests_passed"] = max(0, args.tests_passed)
    if args.tests_failed is not None:
        pipeline_metrics["testing"]["tests_failed"] = max(0, args.tests_failed)
    if args.coverage is not None:
        pipeline_metrics["testing"]["coverage_percent"] = max(0, min(100, args.coverage))
    if args.commits is not None:
        pipeline_metrics["commit"]["commits_today"] = max(0, args.commits)
    if args.prs_open is not None:
        pipeline_metrics["commit"]["prs_open"] = max(0, args.prs_open)
    if args.review_pending is not None:
        pipeline_metrics["commit"]["review_pending"] = max(0, args.review_pending)
    if args.build_status is not None:
        pipeline_metrics["ci"]["last_build_status"] = args.build_status

    if any(pipeline_metrics[key] for key in pipeline_metrics):
        payload["pipeline_metrics"] = pipeline_metrics

    if args.event_actor and args.event_message:
        payload["recent_events_append"] = [
            {
                "time": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                "type": args.event_type,
                "actor": args.event_actor,
                "message": args.event_message,
                "severity": args.event_severity,
            }
        ]

    if args.merge_json:
        merge_path = Path(args.merge_json)
        merged_payload = json.loads(merge_path.read_text(encoding="utf-8"))
        if not isinstance(merged_payload, dict):
            raise SystemExit("--merge-json must point to a JSON object")
        payload.update(merged_payload)

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        args.url,
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=10) as response:
        text = response.read().decode("utf-8")
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
