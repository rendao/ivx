#!/usr/bin/env python3
"""Push CI build/deploy result into the live dashboard.

This script lives with the dashboard package so it can be reused as a standalone module.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
import os
import urllib.request


def bounded_rate(value: int) -> int:
    return max(0, min(100, value))


def main() -> int:
    parser = argparse.ArgumentParser(description="Push CI result to dashboard")
    parser.add_argument(
        "--url",
        default=os.getenv("DASHBOARD_API_URL", "http://127.0.0.1:8765/api/progress"),
        help="Dashboard API URL",
    )
    parser.add_argument("--build-status", choices=["success", "failed", "running"], required=True)
    parser.add_argument("--build-success-rate", type=int)
    parser.add_argument("--deploy-success-rate", type=int)
    parser.add_argument("--failed-checks", type=int)
    parser.add_argument("--regressions", type=int)
    parser.add_argument("--actor", default="CI Pipeline")
    parser.add_argument("--message", required=True)
    args = parser.parse_args()

    ci_payload = {"last_build_status": args.build_status}
    if args.build_success_rate is not None:
        ci_payload["build_success_rate"] = bounded_rate(args.build_success_rate)
    if args.deploy_success_rate is not None:
        ci_payload["deploy_success_rate"] = bounded_rate(args.deploy_success_rate)

    payload = {
        "pipeline_metrics": {
            "ci": ci_payload,
        },
        "recent_events_append": [
            {
                "time": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                "type": "ci",
                "actor": args.actor,
                "message": args.message,
                "severity": "critical" if args.build_status == "failed" else ("warning" if args.build_status == "running" else "info"),
            }
        ],
    }

    if args.failed_checks is not None:
        payload["failed_checks"] = max(0, args.failed_checks)
    if args.regressions is not None:
        payload.setdefault("pipeline_metrics", {}).setdefault("testing", {})["regressions"] = max(0, args.regressions)

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
