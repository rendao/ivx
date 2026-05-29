from __future__ import annotations

import json
import os
import re
import subprocess
import time
import xml.etree.ElementTree as ET
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


UNITTEST_PROBE_INTERVAL_SECONDS = max(60, int(os.getenv("DASHBOARD_UNITTEST_PROBE_INTERVAL_SECONDS", "180") or "180"))
UNITTEST_PROBE_TIMEOUT_SECONDS = max(5, int(os.getenv("DASHBOARD_UNITTEST_PROBE_TIMEOUT_SECONDS", "60") or "60"))
_UNITTEST_PROBE_CACHE: Dict[str, Dict[str, Any]] = {}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _iter_limited_candidates(root: Path, patterns: list[str], limit: int) -> list[Path]:
    found: list[Path] = []
    seen: set[Path] = set()
    for pattern in patterns:
        for candidate in root.glob(pattern):
            resolved = candidate.resolve()
            if resolved in seen or not resolved.is_file():
                continue
            seen.add(resolved)
            found.append(resolved)
            if len(found) >= limit:
                return found
    return found


def collect_git_activity(project_root: Path, event_limit: int = 10) -> Dict[str, Any]:
    root = project_root.resolve()
    if not root.exists() or not root.is_dir():
        return {"events": [], "commits_today": 0, "total_commits": 0}

    if not (root / ".git").exists():
        return {"events": [], "commits_today": 0, "total_commits": 0}

    events: list[Dict[str, Any]] = []
    commits_today = 0
    total_commits = 0

    try:
        log_cmd = subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "log",
                "--max-count",
                str(max(1, event_limit)),
                "--date=iso-strict",
                "--pretty=format:%cI%x1f%an%x1f%s",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=6,
        )
        if log_cmd.returncode == 0:
            for line in log_cmd.stdout.splitlines():
                parts = line.split("\x1f")
                if len(parts) < 3:
                    continue
                timestamp = parts[0].strip() or now_iso()
                author = parts[1].strip() or "git"
                subject = parts[2].strip() or "commit"
                events.append(
                    {
                        "time": timestamp,
                        "type": "commit",
                        "actor": author,
                        "message": subject,
                        "severity": "info",
                    }
                )
    except Exception:
        events = []

    try:
        count_cmd = subprocess.run(
            ["git", "-C", str(root), "rev-list", "--count", "--since=midnight", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
            timeout=4,
        )
        if count_cmd.returncode == 0:
            commits_today = max(0, int((count_cmd.stdout or "0").strip() or "0"))
    except Exception:
        commits_today = 0

    try:
        total_cmd = subprocess.run(
            ["git", "-C", str(root), "rev-list", "--count", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
            timeout=4,
        )
        if total_cmd.returncode == 0:
            total_commits = max(0, int((total_cmd.stdout or "0").strip() or "0"))
    except Exception:
        total_commits = 0

    return {"events": events, "commits_today": commits_today, "total_commits": total_commits}


def collect_test_activity(project_root: Path) -> Dict[str, Any]:
    root = project_root.resolve()
    if not root.exists() or not root.is_dir():
        return {
            "tests_passed": 0,
            "tests_failed": 0,
            "coverage_percent": 0,
            "regressions": 0,
            "report_found": False,
            "source": "none",
        }

    junit_patterns = [
        "**/junit*.xml",
        "**/pytest*.xml",
        "**/test-results*.xml",
        "**/nosetests*.xml",
        "**/TEST-*.xml",
    ]
    coverage_patterns = ["**/coverage.xml", "**/cobertura.xml"]

    tests_total = 0
    failures_total = 0
    errors_total = 0
    skipped_total = 0
    report_found = False

    for xml_path in _iter_limited_candidates(root, junit_patterns, limit=20):
        try:
            tree = ET.parse(xml_path)
            xml_root = tree.getroot()
            report_found = True

            suites: list[ET.Element] = []
            if xml_root.tag.endswith("testsuite"):
                suites = [xml_root]
            elif xml_root.tag.endswith("testsuites"):
                suites = [elem for elem in xml_root if elem.tag.endswith("testsuite")]

            if not suites:
                continue

            for suite in suites:
                tests_total += int(float(suite.attrib.get("tests", "0") or "0"))
                failures_total += int(float(suite.attrib.get("failures", "0") or "0"))
                errors_total += int(float(suite.attrib.get("errors", "0") or "0"))
                skipped_total += int(float(suite.attrib.get("skipped", "0") or "0"))
        except Exception:
            continue

    tests_failed = max(0, failures_total + errors_total)
    tests_passed = max(0, tests_total - tests_failed - skipped_total)

    coverage_percent = 0
    for coverage_path in _iter_limited_candidates(root, coverage_patterns, limit=3):
        try:
            tree = ET.parse(coverage_path)
            xml_root = tree.getroot()
            report_found = True

            line_rate = xml_root.attrib.get("line-rate")
            if line_rate is not None:
                coverage_percent = max(0, min(100, int(round(float(line_rate) * 100))))
                break

            lines_valid = xml_root.attrib.get("lines-valid")
            lines_covered = xml_root.attrib.get("lines-covered")
            if lines_valid is not None and lines_covered is not None:
                valid = float(lines_valid)
                covered = float(lines_covered)
                if valid > 0:
                    coverage_percent = max(0, min(100, int(round((covered / valid) * 100))))
                    break
        except Exception:
            continue

    regressions = tests_failed

    if not report_found:
        cache_dir = root / ".pytest_cache" / "v" / "cache"
        lastfailed_path = cache_dir / "lastfailed"
        nodeids_path = cache_dir / "nodeids"
        failed_from_cache = 0
        total_from_cache = 0

        try:
            if lastfailed_path.exists():
                raw = json.loads(lastfailed_path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    failed_from_cache = len([k for k, v in raw.items() if v])
        except Exception:
            failed_from_cache = 0

        try:
            if nodeids_path.exists():
                raw = json.loads(nodeids_path.read_text(encoding="utf-8"))
                if isinstance(raw, list):
                    total_from_cache = len(raw)
        except Exception:
            total_from_cache = 0

        if failed_from_cache > 0 or total_from_cache > 0:
            tests_failed = max(tests_failed, failed_from_cache)
            if total_from_cache > 0:
                tests_passed = max(tests_passed, total_from_cache - tests_failed)
            regressions = max(regressions, tests_failed)
            return {
                "tests_passed": tests_passed,
                "tests_failed": tests_failed,
                "coverage_percent": coverage_percent,
                "regressions": regressions,
                "report_found": False,
                "source": "pytest_cache",
            }

    if not report_found:
        unittest_probe = _collect_unittest_probe_activity(root)
        if unittest_probe is not None:
            return unittest_probe

    return {
        "tests_passed": tests_passed,
        "tests_failed": tests_failed,
        "coverage_percent": coverage_percent,
        "regressions": regressions,
        "report_found": report_found,
        "source": "report_xml",
    }


def _collect_unittest_probe_activity(project_root: Path) -> Dict[str, Any] | None:
    tests_dir = project_root / "tests"
    if not tests_dir.exists() or not tests_dir.is_dir():
        return None

    root_key = str(project_root.resolve())
    now_ts = time.time()
    cached = _UNITTEST_PROBE_CACHE.get(root_key)
    if isinstance(cached, dict):
        cached_at = float(cached.get("at", 0.0) or 0.0)
        cached_result = cached.get("result")
        if isinstance(cached_result, dict) and now_ts - cached_at < UNITTEST_PROBE_INTERVAL_SECONDS:
            return dict(cached_result)

    test_command = os.getenv("DASHBOARD_TEST_COMMAND", "").strip()
    if not test_command:
        test_command = "python -m unittest discover -s tests -v"

    try:
        completed = subprocess.run(
            test_command,
            cwd=str(project_root),
            capture_output=True,
            text=True,
            check=False,
            timeout=UNITTEST_PROBE_TIMEOUT_SECONDS,
            shell=True,
        )
    except Exception:
        return None

    output = "\n".join([completed.stdout or "", completed.stderr or ""]).strip()
    parsed = _parse_unittest_output(output)
    if parsed is None:
        return None

    probe_result = {
        "tests_passed": parsed["tests_passed"],
        "tests_failed": parsed["tests_failed"],
        "coverage_percent": 0,
        "regressions": parsed["tests_failed"],
        "report_found": False,
        "source": "unittest_probe",
    }
    _UNITTEST_PROBE_CACHE[root_key] = {"at": now_ts, "result": probe_result}
    return dict(probe_result)


def _parse_unittest_output(output: str) -> Dict[str, int] | None:
    if not output:
        return None

    ran_match = re.search(r"Ran\s+(\d+)\s+tests?", output)
    if not ran_match:
        return None

    total_tests = max(0, int(ran_match.group(1)))
    failed = 0
    errors = 0
    skipped = 0

    failed_match = re.search(r"FAILED\s*\(([^)]*)\)", output)
    if failed_match:
        for segment in failed_match.group(1).split(","):
            part = segment.strip().lower()
            if part.startswith("failures="):
                failed = max(0, int(part.split("=", 1)[1] or "0"))
            elif part.startswith("errors="):
                errors = max(0, int(part.split("=", 1)[1] or "0"))
            elif part.startswith("skipped="):
                skipped = max(0, int(part.split("=", 1)[1] or "0"))
    else:
        ok_match = re.search(r"OK\s*\(([^)]*)\)", output)
        if ok_match:
            for segment in ok_match.group(1).split(","):
                part = segment.strip().lower()
                if part.startswith("skipped="):
                    skipped = max(0, int(part.split("=", 1)[1] or "0"))

    tests_failed = max(0, failed + errors)
    tests_passed = max(0, total_tests - tests_failed - skipped)
    return {
        "tests_passed": tests_passed,
        "tests_failed": tests_failed,
    }


def apply_repository_signals(payload: Dict[str, Any], project_root: Path) -> Dict[str, Any]:
    enriched = deepcopy(payload)
    activity = collect_git_activity(project_root)
    test_activity = collect_test_activity(project_root)

    auto_mode = (
        str(enriched.get("task") or "").strip().lower() == "auto-constructed dashboard contract"
        or str(enriched.get("phase") or "").strip().lower().startswith("phase 0 - auto discovery")
    )

    events = activity.get("events") if isinstance(activity, dict) else []
    commits_today = int(activity.get("commits_today", 0)) if isinstance(activity, dict) else 0

    if isinstance(events, list) and events:
        enriched["recent_events"] = events

    pipeline = enriched.get("pipeline_metrics") if isinstance(enriched.get("pipeline_metrics"), dict) else {}
    commit = pipeline.get("commit") if isinstance(pipeline.get("commit"), dict) else {}
    testing = pipeline.get("testing") if isinstance(pipeline.get("testing"), dict) else {}
    commit["commits_today"] = commits_today
    detected_tests_passed = int(test_activity.get("tests_passed", 0))
    detected_tests_failed = int(test_activity.get("tests_failed", 0))
    detected_coverage = int(test_activity.get("coverage_percent", 0))
    detected_regressions = int(test_activity.get("regressions", 0))
    test_source = str(test_activity.get("source") or "none")

    has_detected_testing_signal = test_source in {"report_xml", "pytest_cache", "unittest_probe"}
    if (
        auto_mode
        or has_detected_testing_signal
        or int(testing.get("tests_passed", 0)) == 0
        and int(testing.get("tests_failed", 0)) == 0
        and int(testing.get("coverage_percent", 0)) == 0
    ):
        testing["tests_passed"] = detected_tests_passed
        testing["tests_failed"] = detected_tests_failed
        testing["coverage_percent"] = detected_coverage
        testing["regressions"] = detected_regressions

    pipeline["commit"] = commit
    pipeline["testing"] = testing
    enriched["pipeline_metrics"] = pipeline

    collaborators = enriched.get("collaborators") if isinstance(enriched.get("collaborators"), list) else []
    if collaborators and isinstance(collaborators[0], dict):
        collaborators[0]["commits_today"] = commits_today
    enriched["collaborators"] = collaborators

    if detected_tests_failed > 0:
        enriched["failed_checks"] = max(int(enriched.get("failed_checks", 0)), detected_tests_failed)
        if str(enriched.get("status", "green")).lower() == "green":
            enriched["status"] = "yellow"
        if str(enriched.get("risk_level", "low")).lower() in {"low", "medium"}:
            enriched["risk_level"] = "high"

    if test_source == "pytest_cache":
        fallback_event = {
            "time": now_iso(),
            "type": "testing_signal",
            "actor": "dashboard",
            "message": "Testing KPI derived from .pytest_cache (low confidence). Prefer junit/coverage xml reports.",
            "severity": "warning",
        }
        current_events = enriched.get("recent_events") if isinstance(enriched.get("recent_events"), list) else []
        if not any(isinstance(evt, dict) and evt.get("type") == "testing_signal" for evt in current_events):
            enriched["recent_events"] = [fallback_event, *current_events][:20]

    if test_source == "unittest_probe":
        probe_event = {
            "time": now_iso(),
            "type": "testing_signal",
            "actor": "dashboard",
            "message": "Testing KPI derived from unittest command probe. Consider exporting junit/coverage artifacts for higher confidence.",
            "severity": "warning",
        }
        current_events = enriched.get("recent_events") if isinstance(enriched.get("recent_events"), list) else []
        if not any(isinstance(evt, dict) and evt.get("type") == "testing_signal" for evt in current_events):
            enriched["recent_events"] = [probe_event, *current_events][:20]

    if auto_mode:
        total_commits = int(activity.get("total_commits", 0)) if isinstance(activity, dict) else 0
        latest_message = ""
        if isinstance(events, list) and events and isinstance(events[0], dict):
            latest_message = str(events[0].get("message") or "").strip()

        if total_commits >= 300:
            phase = "Phase 4 - Optimization"
        elif total_commits >= 120:
            phase = "Phase 3 - Stabilization"
        elif total_commits >= 40:
            phase = "Phase 2 - Scaling"
        elif total_commits >= 8:
            phase = "Phase 1 - Active Development"
        else:
            phase = "Phase 0 - Auto Discovery"

        progress = min(95, max(5, int(5 + min(total_commits, 180) * 0.45 + min(commits_today, 12) * 2)))

        enriched["phase"] = phase
        enriched["task"] = latest_message or "Collecting project activity"
        enriched["progress_percent"] = progress
        if detected_tests_passed + detected_tests_failed > 0:
            enriched["next_milestone"] = "Keep test reports publishing into .ivx/data for KPI continuity"
        else:
            enriched["next_milestone"] = "Publish normalized progress payload from project pipeline"

    return enriched
