#!/usr/bin/env python3
"""Unified local workflow checks.

Use this script as the single entry point and call it from shell wrappers:
- python scripts/workflow.py local
- python scripts/workflow.py local --skip-integration
- python scripts/workflow.py weekly-trend --samples 3
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run_step(name: str, cmd: list[str], *, allow_fail: bool = False) -> int:
    print(f"[workflow] {name}: {' '.join(cmd)}")
    completed = subprocess.run(cmd, cwd=str(ROOT), check=False)
    if completed.returncode != 0:
        level = "WARN" if allow_fail else "ERROR"
        print(f"[workflow] {level}: step '{name}' failed with exit code {completed.returncode}")
        if not allow_fail:
            return completed.returncode
    return 0


def check_flake8_available() -> bool:
    completed = subprocess.run(
        [sys.executable, "-m", "flake8", "--version"],
        cwd=str(ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return completed.returncode == 0


def run_local(args: argparse.Namespace) -> int:
    steps: list[tuple[str, list[str], bool]] = [
        (
            "unit tests",
            [sys.executable, "-m", "pytest", "-m", "not integration"],
            False,
        ),
    ]

    if not args.skip_integration:
        steps.append(
            (
                "integration tests",
                [sys.executable, "-m", "pytest", "-m", "integration"],
                False,
            )
        )

    if not args.skip_behavior:
        steps.append(
            (
                "behavior recordability",
                [sys.executable, "tools/behavior_recordability_check.py", "--no-send"],
                False,
            )
        )

    if not args.skip_lint:
        allow_fail = args.lint_non_blocking
        if check_flake8_available():
            steps.append(
                (
                    "lint",
                    [sys.executable, "-m", "flake8", "src/ivx"],
                    allow_fail,
                )
            )
        else:
            print("[workflow] WARN: flake8 not installed, skip lint step.")

    for name, cmd, allow_fail in steps:
        code = run_step(name, cmd, allow_fail=allow_fail)
        if code != 0:
            return code

    print("[workflow] OK: local checks passed")
    return 0


def run_weekly_trend(args: argparse.Namespace) -> int:
    cmd = [
        sys.executable,
        "scripts/weekly_trend_validation.py",
        "--samples",
        str(args.samples),
        "--port-start",
        str(args.port_start),
        "--interval-seconds",
        str(args.interval_seconds),
    ]
    if args.json_output:
        cmd.extend(["--json-output", args.json_output])
    if args.md_output:
        cmd.extend(["--md-output", args.md_output])

    code = run_step("weekly trend validation", cmd)
    if code != 0:
        return code

    print("[workflow] OK: weekly trend validation passed")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run unified local workflow checks.")
    sub = parser.add_subparsers(dest="command", required=True)

    local = sub.add_parser("local", help="Run required local checks")
    local.add_argument("--skip-integration", action="store_true", help="Skip integration test step")
    local.add_argument("--skip-behavior", action="store_true", help="Skip behavior recordability step")
    local.add_argument("--skip-lint", action="store_true", help="Skip lint step")
    local.add_argument(
        "--lint-non-blocking",
        action="store_true",
        help="Do not fail overall command when lint fails",
    )

    weekly = sub.add_parser("weekly-trend", help="Run multi-project weekly trend validation")
    weekly.add_argument("--samples", type=int, default=3, help="Number of pilot samples")
    weekly.add_argument("--port-start", type=int, default=8800, help="Starting port for pilot runs")
    weekly.add_argument("--interval-seconds", type=float, default=0.0, help="Pause between pilot runs")
    weekly.add_argument("--json-output", default="", help="Optional JSON report output path")
    weekly.add_argument("--md-output", default="", help="Optional markdown report output path")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "local":
        return run_local(args)
    if args.command == "weekly-trend":
        return run_weekly_trend(args)
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
