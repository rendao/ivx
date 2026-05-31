import errno
import json
import io
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

from ivx.server import service


class ServiceContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="ivx-service-contract-"))
        self._original_progress_file = service.PROGRESS_FILE
        self._original_project_state_file = service.PROJECT_STATE_FILE
        self._original_base_dir = service.BASE_DIR
        self._original_default_project_name = service.DEFAULT_PROJECT_NAME

    def tearDown(self) -> None:
        service.PROGRESS_FILE = self._original_progress_file
        service.PROJECT_STATE_FILE = self._original_project_state_file
        service.BASE_DIR = self._original_base_dir
        service.DEFAULT_PROJECT_NAME = self._original_default_project_name
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_validate_progress_payload_rejects_bad_input(self) -> None:
        with self.assertRaises(ValueError):
            service.validate_progress_payload(
                {
                    "status": "blue",
                    "risk_level": "extreme",
                    "progress_percent": 120,
                    "blockers": ["ok", 123],
                }
            )

    def test_atomic_write_recovery_restores_from_backup(self) -> None:
        target = self.temp_dir / "live_progress.json"
        original = {"project": "demo", "progress_percent": 10}
        updated = {"project": "demo-2", "progress_percent": 20}
        service.atomic_write_json(target, original)
        service.atomic_write_json(target, updated)

        target.write_text("{broken json", encoding="utf-8")
        recovered = service.load_json_with_recovery(target, {"project": "fallback"})

        self.assertEqual(recovered["project"], "demo")
        self.assertEqual(json.loads(target.read_text(encoding="utf-8"))["project"], "demo")
        backups = list((target.parent / ".backups").glob("live_progress-*.json"))
        self.assertGreaterEqual(len(backups), 1)

    def test_health_snapshot_reports_project_path_anomaly(self) -> None:
        service.BASE_DIR = self.temp_dir
        service.PROGRESS_FILE = self.temp_dir / "live_progress.json"
        service.PROJECT_STATE_FILE = self.temp_dir / "dashboard_state.json"

        service.atomic_write_json(
            service.PROGRESS_FILE,
            {
                "project_id": "external-1",
                "project": "External",
                "project_path": ".",
                "phase": "Phase 1 - Pilot",
                "task": "Task",
                "progress_percent": 10,
                "status": "green",
                "risk_level": "low",
                "failed_checks": 0,
                "blockers": [],
                "next_milestone": "Next",
                "pipeline_metrics": service.default_progress()["pipeline_metrics"],
                "collaborators": service.default_progress()["collaborators"],
                "recent_events": [],
                "last_update": service.now_iso(),
                "human_intervention": {"recommended": False, "reason": "No immediate intervention needed."},
            },
        )
        service.atomic_write_json(
            service.PROJECT_STATE_FILE,
            {
                "current_project_id": "external-1",
                "projects": {
                    "external-1": {
                        "id": "external-1",
                        "name": "External",
                        "path": str(self.temp_dir / "missing-project"),
                        "data_file": str(service.PROGRESS_FILE),
                    }
                },
            },
        )

        snapshot = service.health_snapshot()
        self.assertIn(snapshot["status"], {"degraded", "unhealthy"})
        self.assertEqual(snapshot["checks"]["project_path"], "missing")

    def test_run_reports_port_conflict_and_returns_one(self) -> None:
        stderr = io.StringIO()
        old_argv = sys.argv
        try:
            sys.argv = ["ivx", "--host", "127.0.0.1", "--port", "8789", "--data-file", str(self.temp_dir / "live_progress.json")]
            with mock.patch.object(service, "collect_runtime_signals") as collect_runtime_signals:
                with mock.patch.object(service, "_listening_process_hint", return_value="TCP 127.0.0.1:8789 LISTENING 4242"):
                    with mock.patch.object(service, "DashboardHTTPServer", side_effect=OSError(errno.EADDRINUSE, "Only one usage", None, 10048)):
                        with mock.patch("sys.stderr", stderr):
                            code = service.run()

            self.assertEqual(code, 1)
            self.assertIn("127.0.0.1:8789 is already in use", stderr.getvalue())
            self.assertIn("Listener hint", stderr.getvalue())
            collect_runtime_signals.assert_called_once_with(force=True)
        finally:
            sys.argv = old_argv

    def test_run_does_not_start_collector_when_bind_fails(self) -> None:
        old_argv = sys.argv
        try:
            sys.argv = ["ivx", "--host", "127.0.0.1", "--port", "8789", "--data-file", str(self.temp_dir / "live_progress.json")]
            with mock.patch.object(service, "collect_runtime_signals"):
                with mock.patch.object(service, "_listening_process_hint", return_value=""):
                    with mock.patch.object(service, "DashboardHTTPServer", side_effect=OSError(errno.EADDRINUSE, "Only one usage", None, 10048)):
                        with mock.patch("threading.Thread") as thread_cls:
                            code = service.run()

            self.assertEqual(code, 1)
            thread_cls.assert_not_called()
        finally:
            sys.argv = old_argv

    def test_intervention_queue_items_include_owner_due_and_status(self) -> None:
        progress = service.default_progress()
        progress["blockers"] = ["manual approval pending"]
        progress["failed_checks"] = 3
        progress["pipeline_metrics"]["ci"]["last_build_status"] = "failed"
        progress["pipeline_metrics"]["governance"]["unresolved_human_reviews"] = 1
        progress["pipeline_metrics"]["governance"]["controllability_score"] = 50

        queue = service.build_intervention_queue(progress)
        self.assertGreaterEqual(len(queue), 1)

        for item in queue:
            self.assertIn("owner", item)
            self.assertIn("due", item)
            self.assertIn("status", item)
            self.assertEqual(item["status"], "open")
            self.assertTrue(str(item["owner"]).endswith("-owner"))
            self.assertIsNotNone(service.parse_iso(str(item["due"])))


if __name__ == "__main__":
    unittest.main()