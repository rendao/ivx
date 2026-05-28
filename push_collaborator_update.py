#!/usr/bin/env python3
"""Push a single collaborator update to the live dashboard.

This script lives with the dashboard package so it can be reused as a standalone module.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
import os
import urllib.request


def main() -> int:
    parser = argparse.ArgumentParser(description="Push collaborator update to dashboard")
    parser.add_argument(
        "--url",
        default=os.getenv("DASHBOARD_API_URL", "http://127.0.0.1:8765/api/progress"),
        help="Dashboard API URL",
    )
    parser.add_argument("--id", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--role", choices=["development", "testing", "review", "release", "ops"], required=True)
    parser.add_argument("--status", choices=["active", "blocked", "idle"], required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument("--progress", type=int, required=True)
    parser.add_argument("--commits", type=int, default=0)
    parser.add_argument("--tests-passed", type=int, default=0)
    parser.add_argument("--tests-failed", type=int, default=0)
    parser.add_argument("--prs-open", type=int, default=0)
    parser.add_argument("--reviews-pending", type=int, default=0)
    parser.add_argument("--needs-human", action="store_true")
    parser.add_argument("--note", default="")
    parser.add_argument("--event-message", default="")
    args = parser.parse_args()

    collaborator = {
        "id": args.id,
        "name": args.name,
        "role": args.role,
        "status": args.status,
        "current_task": args.task,
        "progress_percent": max(0, min(100, args.progress)),
        "commits_today": max(0, args.commits),
        "tests_passed": max(0, args.tests_passed),
        "tests_failed": max(0, args.tests_failed),
        "prs_open": max(0, args.prs_open),
        "reviews_pending": max(0, args.reviews_pending),
        "needs_human": bool(args.needs_human),
        "note": args.note,
        "last_update": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    }

    payload = {"collaborators_upsert": [collaborator]}
    if args.event_message:
        payload["recent_events_append"] = [
            {
                "time": collaborator["last_update"],
                "type": "collaborator_update",
                "actor": args.name,
                "message": args.event_message,
                "severity": "warning" if args.needs_human else "info",
            }
        ]

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        args.url,
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=10) as response:
        print(response.read().decode("utf-8"))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
