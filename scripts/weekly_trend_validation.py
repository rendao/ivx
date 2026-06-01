#!/usr/bin/env python3
"""Weekly trend validation for multi-project onboarding evidence.

Runs the second-project pilot multiple times and summarizes trend stability.
Outputs both JSON and Markdown reports under .ivx/data by default.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_JSON = ROOT / ".ivx" / "data" / "multi-project-weekly-trend.json"
DEFAULT_MD = ROOT / ".ivx" / "data" / "multi-project-weekly-trend.md"


def run_pilot_once(port: int) -> dict[str, Any]:
    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "second_project_pilot.py"),
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
    ]
    proc = subprocess.run(
        cmd,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"pilot failed on port {port}: {proc.stderr or proc.stdout}")

    text = proc.stdout.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        raise RuntimeError(f"unable to parse pilot JSON output on port {port}: {text}")

    payload = json.loads(text[start : end + 1])
    if not isinstance(payload, dict):
        raise RuntimeError(f"invalid pilot payload on port {port}: {payload}")
    payload["port"] = port
    return payload


def summarize(samples: list[dict[str, Any]]) -> dict[str, Any]:
    if not samples:
        raise ValueError("samples must not be empty")

    project_counts = [int(item.get("project_count", 0)) for item in samples]
    secondary_progress = [int(item.get("secondary_progress_percent", 0)) for item in samples]
    primary_progress = [int(item.get("primary_progress_percent", 0)) for item in samples]
    switch_back_ok = [bool(item.get("switch_back_matches_primary", False)) for item in samples]
    secondary_ci_ok = [str(item.get("secondary_ci_status", "")).lower() == "success" for item in samples]

    stable_project_count = len(set(project_counts)) == 1
    stable_secondary_progress = len(set(secondary_progress)) == 1
    stable_primary_progress = len(set(primary_progress)) == 1

    switch_back_success_rate = int(round((sum(1 for ok in switch_back_ok if ok) / len(switch_back_ok)) * 100))
    ci_success_rate = int(round((sum(1 for ok in secondary_ci_ok if ok) / len(secondary_ci_ok)) * 100))

    overall_pass = (
        min(project_counts) >= 2
        and switch_back_success_rate == 100
        and ci_success_rate == 100
        and stable_secondary_progress
        and stable_primary_progress
    )

    return {
        "samples": samples,
        "sample_count": len(samples),
        "duration_seconds": round(sum(float(item.get("duration_seconds", 0.0)) for item in samples), 3),
        "project_count": {
            "min": min(project_counts),
            "max": max(project_counts),
            "stable": stable_project_count,
        },
        "primary_progress_percent": {
            "values": primary_progress,
            "stable": stable_primary_progress,
        },
        "secondary_progress_percent": {
            "values": secondary_progress,
            "stable": stable_secondary_progress,
        },
        "switch_back_success_rate_percent": switch_back_success_rate,
        "secondary_ci_success_rate_percent": ci_success_rate,
        "overall_pass": overall_pass,
    }


def write_markdown(report: dict[str, Any], output_file: Path) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# IVX Multi-Project Weekly Trend Report",
        "",
        f"- Sample count: {report['sample_count']}",
        f"- Total duration seconds: {report['duration_seconds']}",
        f"- Project count min/max: {report['project_count']['min']} / {report['project_count']['max']}",
        f"- Project count stable: {report['project_count']['stable']}",
        f"- Primary progress stable: {report['primary_progress_percent']['stable']}",
        f"- Secondary progress stable: {report['secondary_progress_percent']['stable']}",
        f"- Switch-back success rate: {report['switch_back_success_rate_percent']}%",
        f"- Secondary CI success rate: {report['secondary_ci_success_rate_percent']}%",
        f"- Overall pass: {report['overall_pass']}",
        "",
        "## Samples",
    ]

    for idx, sample in enumerate(report["samples"], start=1):
        lines.append(
            f"- #{idx} port={sample.get('port')} current_after_secondary={sample.get('current_project_after_secondary')} "
            f"current_after_switch_back={sample.get('current_project_after_switch_back')} "
            f"primary={sample.get('primary_progress_percent')} secondary={sample.get('secondary_progress_percent')}"
        )

    output_file.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run weekly trend validation for multi-project onboarding evidence.")
    parser.add_argument("--samples", type=int, default=3, help="Number of pilot runs to aggregate")
    parser.add_argument("--port-start", type=int, default=8800, help="Starting port; each run uses an incremented port")
    parser.add_argument("--interval-seconds", type=float, default=0.0, help="Pause between runs")
    parser.add_argument("--json-output", default=str(DEFAULT_JSON), help="Output JSON report path")
    parser.add_argument("--md-output", default=str(DEFAULT_MD), help="Output markdown report path")
    args = parser.parse_args()

    if args.samples < 1:
        raise SystemExit("--samples must be >= 1")

    json_output = Path(args.json_output)
    if not json_output.is_absolute():
        json_output = (ROOT / json_output).resolve()

    md_output = Path(args.md_output)
    if not md_output.is_absolute():
        md_output = (ROOT / md_output).resolve()

    started_at = time.perf_counter()
    samples: list[dict[str, Any]] = []
    for i in range(args.samples):
        port = args.port_start + i
        sample_started_at = time.perf_counter()
        sample = run_pilot_once(port)
        sample["duration_seconds"] = round(time.perf_counter() - sample_started_at, 3)
        samples.append(sample)
        if args.interval_seconds > 0 and i < args.samples - 1:
            time.sleep(args.interval_seconds)

    report = summarize(samples)
    report["duration_seconds"] = round(sum(float(item.get("duration_seconds", 0.0)) for item in samples), 3)
    report["elapsed_seconds"] = round(time.perf_counter() - started_at, 3)

    json_output.parent.mkdir(parents=True, exist_ok=True)
    json_output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(report, md_output)

    print(json.dumps({
        "json_output": str(json_output),
        "md_output": str(md_output),
        "overall_pass": report["overall_pass"],
        "sample_count": report["sample_count"],
        "duration_seconds": report["duration_seconds"],
    }, ensure_ascii=False, indent=2))

    return 0 if report["overall_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
