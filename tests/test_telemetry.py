import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from ivx.server.telemetry import _parse_unittest_output
from ivx.server.telemetry import _UNITTEST_PROBE_CACHE
from ivx.server.telemetry import _collect_unittest_probe_activity
from ivx.server.telemetry import apply_repository_signals
from ivx.server.telemetry import collect_test_activity


class TelemetryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="ivx-telemetry-"))

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_collect_test_activity_from_junit_and_coverage_xml(self) -> None:
        junit = self.temp_dir / "test-results.xml"
        junit.write_text(
            """
<testsuite tests=\"5\" failures=\"1\" errors=\"1\" skipped=\"1\"></testsuite>
""".strip(),
            encoding="utf-8",
        )

        coverage = self.temp_dir / "coverage.xml"
        coverage.write_text(
            """
<coverage line-rate=\"0.83\"></coverage>
""".strip(),
            encoding="utf-8",
        )

        result = collect_test_activity(self.temp_dir)
        self.assertEqual(result["tests_failed"], 2)
        self.assertEqual(result["tests_passed"], 2)
        self.assertEqual(result["coverage_percent"], 83)
        self.assertEqual(result["source"], "report_xml")

    def test_collect_test_activity_falls_back_to_pytest_cache(self) -> None:
        cache_dir = self.temp_dir / ".pytest_cache" / "v" / "cache"
        cache_dir.mkdir(parents=True, exist_ok=True)

        (cache_dir / "lastfailed").write_text(
            json.dumps({"tests/test_a.py::test_fail": True, "tests/test_b.py::test_ok": False}, ensure_ascii=False),
            encoding="utf-8",
        )
        (cache_dir / "nodeids").write_text(
            json.dumps(["tests/test_a.py::test_fail", "tests/test_b.py::test_ok"], ensure_ascii=False),
            encoding="utf-8",
        )

        result = collect_test_activity(self.temp_dir)
        self.assertEqual(result["tests_failed"], 1)
        self.assertEqual(result["tests_passed"], 1)
        self.assertEqual(result["source"], "pytest_cache")

    def test_parse_unittest_output_for_failed_run(self) -> None:
        output = """
test_a (tests.test_demo.Demo.test_a) ... ok
test_b (tests.test_demo.Demo.test_b) ... FAIL
test_c (tests.test_demo.Demo.test_c) ... ERROR

======================================================================
Ran 3 tests in 0.010s

FAILED (failures=1, errors=1)
""".strip()
        parsed = _parse_unittest_output(output)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["tests_failed"], 2)
        self.assertEqual(parsed["tests_passed"], 1)

    def test_parse_unittest_output_for_ok_with_skipped(self) -> None:
        output = """
Ran 5 tests in 0.015s

OK (skipped=1)
""".strip()
        parsed = _parse_unittest_output(output)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["tests_failed"], 0)
        self.assertEqual(parsed["tests_passed"], 4)

    def test_unittest_probe_cache_isolation_per_project(self) -> None:
        project_a = self.temp_dir / "project_a"
        project_b = self.temp_dir / "project_b"
        (project_a / "tests").mkdir(parents=True, exist_ok=True)
        (project_b / "tests").mkdir(parents=True, exist_ok=True)

        outputs = [
            "Ran 2 tests in 0.001s\n\nOK",
            "Ran 3 tests in 0.001s\n\nFAILED (failures=1)",
        ]

        def fake_run(*args, **kwargs):
            text = outputs.pop(0)
            return mock.Mock(stdout=text, stderr="", returncode=0)

        _UNITTEST_PROBE_CACHE.clear()
        with mock.patch("ivx.server.telemetry.subprocess.run", side_effect=fake_run):
            result_a = _collect_unittest_probe_activity(project_a)
            result_b = _collect_unittest_probe_activity(project_b)

        self.assertIsNotNone(result_a)
        self.assertIsNotNone(result_b)
        self.assertEqual(result_a["tests_passed"], 2)
        self.assertEqual(result_a["tests_failed"], 0)
        self.assertEqual(result_b["tests_passed"], 2)
        self.assertEqual(result_b["tests_failed"], 1)

    def test_apply_repository_signals_overrides_stale_testing_metrics(self) -> None:
        payload = {
            "task": "feature delivery",
            "phase": "Phase 1 - Pilot",
            "pipeline_metrics": {
                "testing": {
                    "tests_passed": 82,
                    "tests_failed": 28,
                    "coverage_percent": 66,
                    "regressions": 28,
                },
                "commit": {},
            },
            "recent_events": [],
            "collaborators": [],
        }

        with mock.patch("ivx.server.telemetry.collect_git_activity", return_value={"events": [], "commits_today": 0, "total_commits": 0}):
            with mock.patch(
                "ivx.server.telemetry.collect_test_activity",
                return_value={
                    "tests_passed": 12,
                    "tests_failed": 0,
                    "coverage_percent": 0,
                    "regressions": 0,
                    "report_found": False,
                    "source": "unittest_probe",
                },
            ):
                updated = apply_repository_signals(payload, project_root=self.temp_dir)

        testing = updated.get("pipeline_metrics", {}).get("testing", {})
        self.assertEqual(testing.get("tests_passed"), 12)
        self.assertEqual(testing.get("tests_failed"), 0)
        self.assertEqual(testing.get("regressions"), 0)

    def test_apply_repository_signals_keeps_existing_testing_when_no_detected_signal(self) -> None:
        payload = {
            "task": "feature delivery",
            "phase": "Phase 1 - Pilot",
            "pipeline_metrics": {
                "testing": {
                    "tests_passed": 19,
                    "tests_failed": 1,
                    "coverage_percent": 75,
                    "regressions": 1,
                },
                "commit": {},
            },
            "recent_events": [],
            "collaborators": [],
        }

        with mock.patch("ivx.server.telemetry.collect_git_activity", return_value={"events": [], "commits_today": 0, "total_commits": 0}):
            with mock.patch(
                "ivx.server.telemetry.collect_test_activity",
                return_value={
                    "tests_passed": 0,
                    "tests_failed": 0,
                    "coverage_percent": 0,
                    "regressions": 0,
                    "report_found": False,
                    "source": "none",
                },
            ):
                updated = apply_repository_signals(payload, project_root=self.temp_dir)

        testing = updated.get("pipeline_metrics", {}).get("testing", {})
        self.assertEqual(testing.get("tests_passed"), 19)
        self.assertEqual(testing.get("tests_failed"), 1)
        self.assertEqual(testing.get("coverage_percent"), 75)
        self.assertEqual(testing.get("regressions"), 1)

    def test_apply_repository_signals_auto_mode_refreshes_testing_even_without_source(self) -> None:
        payload = {
            "task": "auto-constructed dashboard contract",
            "phase": "Phase 0 - Auto Discovery",
            "pipeline_metrics": {
                "testing": {
                    "tests_passed": 32,
                    "tests_failed": 4,
                    "coverage_percent": 61,
                    "regressions": 4,
                },
                "commit": {},
            },
            "recent_events": [],
            "collaborators": [],
        }

        with mock.patch("ivx.server.telemetry.collect_git_activity", return_value={"events": [], "commits_today": 0, "total_commits": 0}):
            with mock.patch(
                "ivx.server.telemetry.collect_test_activity",
                return_value={
                    "tests_passed": 7,
                    "tests_failed": 1,
                    "coverage_percent": 0,
                    "regressions": 1,
                    "report_found": False,
                    "source": "none",
                },
            ):
                updated = apply_repository_signals(payload, project_root=self.temp_dir)

        testing = updated.get("pipeline_metrics", {}).get("testing", {})
        self.assertEqual(testing.get("tests_passed"), 7)
        self.assertEqual(testing.get("tests_failed"), 1)
        self.assertEqual(testing.get("coverage_percent"), 0)
        self.assertEqual(testing.get("regressions"), 1)


if __name__ == "__main__":
    unittest.main()
