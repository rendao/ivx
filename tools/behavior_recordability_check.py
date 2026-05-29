#!/usr/bin/env python3
"""Behavior recordability check script for IVX governance events.

This script does NOT modify existing program code. It only calls the public API.

Usage:
  python tools/behavior_recordability_check.py
  python tools/behavior_recordability_check.py --base-url http://127.0.0.1:8789 --no-send
    python tools/behavior_recordability_check.py --output .ivx/data/behavior-recordability.local.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import uuid
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass
class BehaviorCase:
    category: str
    behavior: str
    event_type: str
    actor: str
    needs_real_source: bool


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def post_json(url: str, payload: dict[str, Any], timeout: int = 10) -> dict[str, Any]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        text = response.read().decode("utf-8")
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
        return {"raw": parsed}
    except Exception:
        return {"raw": text}


def build_payload(case: BehaviorCase, run_id: str, step_index: int) -> dict[str, Any]:
    req_id = f"REQ-CHECK-{run_id}-{step_index:02d}"
    interaction_id = f"INT-CHECK-{run_id}-{step_index:02d}"
    return {
        "time": now_iso(),
        "type": case.event_type,
        "actor": case.actor,
        "message": f"Recordability check: {case.behavior}",
        "severity": "info",
        "request_id": req_id,
        "interaction_id": interaction_id,
        "workflow_id": "behavior-recordability-check",
        "run_id": run_id,
        "step_id": f"step-{step_index:02d}",
        "channel": "script",
        "target": "governance-api",
        "decision": "check",
        "duration_ms": 100,
    }


def behavior_cases() -> list[BehaviorCase]:
    return [
        BehaviorCase("AI", "Authorization prompted", "auth_prompted", "ai-agent", False),
        BehaviorCase("AI", "Task started", "task_started", "ai-agent", False),
        BehaviorCase("AI", "Task completed", "task_completed", "ai-agent", False),
        BehaviorCase("AI", "Task stopped", "task_stopped", "ai-agent", False),
        BehaviorCase("AI", "Decision logged", "decision_logged", "ai-agent", False),
        BehaviorCase("Human", "Authorization approved", "auth_approved", "human-operator", True),
        BehaviorCase("Human", "Authorization denied", "auth_denied", "human-operator", True),
        BehaviorCase("Human", "Action confirmed", "action_confirmed", "human-operator", True),
        BehaviorCase("Human", "Action skipped", "action_skipped", "human-operator", True),
        BehaviorCase("Human", "Action stopped", "action_stopped", "human-operator", True),
        BehaviorCase("Human", "Review requested", "human_review_requested", "human-reviewer", True),
        BehaviorCase("Human", "Review resolved", "human_review_resolved", "human-reviewer", True),
        BehaviorCase("System", "Gate passed", "gate_passed", "ci-system", False),
        BehaviorCase("System", "Gate failed", "gate_failed", "ci-system", False),
    ]


def print_report(rows: list[dict[str, str]]) -> None:
    headers = ["Category", "Behavior", "EventType", "Recordability", "SourceType", "Note"]
    widths = {h: len(h) for h in headers}
    for row in rows:
        for h in headers:
            widths[h] = max(widths[h], len(row[h]))

    def line() -> str:
        return "+" + "+".join("-" * (widths[h] + 2) for h in headers) + "+"

    def render_row(values: dict[str, str]) -> str:
        return "| " + " | ".join(values[h].ljust(widths[h]) for h in headers) + " |"

    print(line())
    print(render_row({h: h for h in headers}))
    print(line())
    for row in rows:
        print(render_row(row))
    print(line())


def write_report_json(
    output_path: Path,
    *,
    base_url: str,
    event_url: str,
    no_send: bool,
    rows: list[dict[str, str]],
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": now_iso(),
        "base_url": base_url,
        "event_url": event_url,
        "mode": "schema_only" if no_send else "api_post",
        "rows": rows,
    }
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Check whether suggested behaviors can be recorded via governance API.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8789", help="Dashboard base URL")
    parser.add_argument("--no-send", action="store_true", help="Do not send events; only evaluate schema-level support")
    parser.add_argument(
        "--output",
        default=".ivx/data/behavior-recordability.local.json",
        help="Output JSON report path (default stays in .ivx/data)",
    )
    args = parser.parse_args()

    event_url = args.base_url.rstrip("/") + "/api/governance/event"
    run_id = uuid.uuid4().hex[:8]

    rows: list[dict[str, str]] = []
    for idx, case in enumerate(behavior_cases(), start=1):
        if args.no_send:
            rows.append(
                {
                    "Category": case.category,
                    "Behavior": case.behavior,
                    "EventType": case.event_type,
                    "Recordability": "SUPPORTED",
                    "SourceType": "REAL_REQUIRED" if case.needs_real_source else "SIM_OR_REAL",
                    "Note": "Schema-level check only",
                }
            )
            continue

        payload = build_payload(case, run_id=run_id, step_index=idx)
        try:
            response = post_json(event_url, payload)
            stored_event = response.get("event") if isinstance(response.get("event"), dict) else {}
            stored_type = str(stored_event.get("type") or "")
            ok = stored_type == case.event_type
            recordability = "RECORDED" if ok else "UNVERIFIED"
            note = "Accepted by API" if ok else "No matching event in response"
        except urllib.error.HTTPError as exc:
            recordability = "FAILED"
            note = f"HTTP {exc.code}"
        except Exception as exc:
            recordability = "FAILED"
            note = str(exc)

        rows.append(
            {
                "Category": case.category,
                "Behavior": case.behavior,
                "EventType": case.event_type,
                "Recordability": recordability,
                "SourceType": "REAL_REQUIRED" if case.needs_real_source else "SIM_OR_REAL",
                "Note": note,
            }
        )

    print(f"Behavior recordability report against: {event_url}")
    print_report(rows)
    output_path = Path(args.output)
    write_report_json(
        output_path,
        base_url=args.base_url,
        event_url=event_url,
        no_send=args.no_send,
        rows=rows,
    )
    print(f"JSON report written to: {output_path.as_posix()}")
    print("SourceType legend: SIM_OR_REAL = can be simulated or real; REAL_REQUIRED = should come from real human action source for production fidelity.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
