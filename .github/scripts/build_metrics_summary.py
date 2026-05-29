import argparse
import datetime as dt
import json
from pathlib import Path
import xml.etree.ElementTree as ET


def parse_junit(path: Path) -> dict:
    try:
        root = ET.parse(path).getroot()
    except Exception:
        return {}

    if root.tag == "testsuite":
        suites = [root]
    else:
        suites = [node for node in root.iter("testsuite")]
    if not suites:
        return {}

    tests = 0
    failures = 0
    errors = 0
    skipped = 0
    duration_seconds = 0.0

    for suite in suites:
        tests += int(float(suite.attrib.get("tests", 0) or 0))
        failures += int(float(suite.attrib.get("failures", 0) or 0))
        errors += int(float(suite.attrib.get("errors", 0) or 0))
        skipped += int(float(suite.attrib.get("skipped", 0) or 0))
        duration_seconds += float(suite.attrib.get("time", 0) or 0)

    failed_total = failures + errors
    passed = max(0, tests - failed_total - skipped)
    return {
        "tests_total": tests,
        "tests_passed": passed,
        "tests_failed": failed_total,
        "tests_skipped": skipped,
        "duration_seconds": round(duration_seconds, 3),
    }


def parse_coverage(path: Path) -> dict:
    try:
        root = ET.parse(path).getroot()
    except Exception:
        return {}

    line_rate = root.attrib.get("line-rate")
    if line_rate is None:
        return {}

    try:
        coverage_percent = round(float(line_rate) * 100, 2)
    except Exception:
        return {}

    return {"coverage_percent": coverage_percent}


def collect_files(input_dir: Path) -> tuple[list[Path], list[Path], list[Path]]:
    junit_files = sorted(
        [p for p in input_dir.rglob("*.xml") if "junit" in p.name.lower() and p.is_file()]
    )
    coverage_files = sorted(
        [p for p in input_dir.rglob("*.xml") if "coverage" in p.name.lower() and p.is_file()]
    )
    integration_junit = [p for p in junit_files if "integration" in p.name.lower()]
    return junit_files, coverage_files, integration_junit


def build_summary(input_dir: Path) -> dict:
    junit_files, coverage_files, integration_junit = collect_files(input_dir)

    aggregate = {
        "tests_total": 0,
        "tests_passed": 0,
        "tests_failed": 0,
        "tests_skipped": 0,
        "duration_seconds": 0.0,
    }
    for junit in junit_files:
        parsed = parse_junit(junit)
        if not parsed:
            continue
        aggregate["tests_total"] += int(parsed.get("tests_total", 0))
        aggregate["tests_passed"] += int(parsed.get("tests_passed", 0))
        aggregate["tests_failed"] += int(parsed.get("tests_failed", 0))
        aggregate["tests_skipped"] += int(parsed.get("tests_skipped", 0))
        aggregate["duration_seconds"] += float(parsed.get("duration_seconds", 0.0))

    coverage_values = []
    for cov in coverage_files:
        parsed = parse_coverage(cov)
        if "coverage_percent" in parsed:
            coverage_values.append(float(parsed["coverage_percent"]))
    coverage_percent = round(sum(coverage_values) / len(coverage_values), 2) if coverage_values else 0.0

    now = dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")
    return {
        "generated_at": now,
        "source": "github-actions",
        "pipeline_metrics": {
            "testing": {
                "tests_passed": aggregate["tests_passed"],
                "tests_failed": aggregate["tests_failed"],
                "coverage_percent": coverage_percent,
                "regressions": aggregate["tests_failed"],
            },
            "ci": {
                "last_build_status": "success" if aggregate["tests_failed"] == 0 else "failed",
                "build_success_rate": 100 if aggregate["tests_failed"] == 0 else 0,
            },
        },
        "details": {
            "test_report_files": [str(p.as_posix()) for p in junit_files],
            "coverage_report_files": [str(p.as_posix()) for p in coverage_files],
            "integration_reports": [str(p.as_posix()) for p in integration_junit],
            "duration_seconds": round(aggregate["duration_seconds"], 3),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build CI metrics summary for dashboard ingestion.")
    parser.add_argument("--input-dir", default="artifacts/ci/input", help="Directory containing junit/coverage artifacts.")
    parser.add_argument("--output", default="artifacts/ci/output/metrics-summary.json", help="Output summary JSON path.")
    args = parser.parse_args()

    input_dir = Path(args.input_dir).resolve()
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    summary = build_summary(input_dir)
    output.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Wrote metrics summary to: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())