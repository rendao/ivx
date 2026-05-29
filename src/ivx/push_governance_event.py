#!/usr/bin/env python3
"""Push governance/control events to dashboard.

Use this script from AI/editor workflows to make process decisions observable and controllable.
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.request


def main() -> int:
    parser = argparse.ArgumentParser(description="Push governance event to dashboard")
    parser.add_argument(
        "--url",
        default=os.getenv("DASHBOARD_GOVERNANCE_URL", "http://127.0.0.1:8765/api/governance/event"),
        help="Dashboard governance event API URL",
    )
    parser.add_argument(
        "--type",
        required=True,
        choices=[
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
        ],
    )
    parser.add_argument("--time", default="")
    parser.add_argument("--actor", default="ai-editor")
    parser.add_argument("--message", required=True)
    parser.add_argument("--severity", choices=["info", "warning", "critical"], default="info")
    parser.add_argument("--objective-id", default="")
    parser.add_argument("--task-id", default="")
    parser.add_argument("--request-id", default="")
    parser.add_argument("--gate", default="")
    parser.add_argument("--result", default="")
    parser.add_argument("--workflow-id", default="")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--step-id", default="")
    parser.add_argument("--interaction-id", default="")
    parser.add_argument("--decision", default="")
    parser.add_argument("--channel", default="")
    parser.add_argument("--target", default="")
    parser.add_argument("--duration-ms", type=int)
    parser.add_argument("--project-id", default="")
    parser.add_argument("--project-name", default="")
    parser.add_argument("--project-path", default="")
    args = parser.parse_args()

    payload = {
        "type": args.type,
        "actor": args.actor,
        "message": args.message,
        "severity": args.severity,
    }
    if args.time:
        payload["time"] = args.time

    if args.objective_id:
        payload["objective_id"] = args.objective_id
    if args.task_id:
        payload["task_id"] = args.task_id
    if args.request_id:
        payload["request_id"] = args.request_id
    if args.gate:
        payload["gate"] = args.gate
    if args.result:
        payload["result"] = args.result
    if args.workflow_id:
        payload["workflow_id"] = args.workflow_id
    if args.run_id:
        payload["run_id"] = args.run_id
    if args.step_id:
        payload["step_id"] = args.step_id
    if args.interaction_id:
        payload["interaction_id"] = args.interaction_id
    if args.decision:
        payload["decision"] = args.decision
    if args.channel:
        payload["channel"] = args.channel
    if args.target:
        payload["target"] = args.target
    if args.duration_ms is not None:
        payload["duration_ms"] = max(0, int(args.duration_ms))

    if args.project_id:
        payload["project_id"] = args.project_id
    if args.project_name:
        payload["project_name"] = args.project_name
    if args.project_path:
        payload["project_path"] = args.project_path

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
