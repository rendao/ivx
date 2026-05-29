import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from ivx.server.telemetry import apply_repository_signals
from ivx.server.governance import append_governance_event
from ivx.server.service import apply_git_activity

try:
    import pytest

    pytestmark = pytest.mark.integration
except Exception:
    pytestmark = []


class IntegrationDashboardContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="ivx-integration-"))
        (self.temp_dir / ".git").mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_pipeline_shape_is_preserved_after_signal_merge(self) -> None:
        payload = {
            "project": "ivx",
            "phase": "Phase 1 - Pilot",
            "task": "integration telemetry check",
            "pipeline_metrics": {
                "development": {"tasks_planned": 3, "tasks_done": 1, "velocity_points": 2},
                "testing": {"tests_passed": 0, "tests_failed": 0, "coverage_percent": 0, "regressions": 0},
                "commit": {"commits_today": 0, "prs_open": 0, "review_pending": 0, "avg_pr_cycle_minutes": 0},
                "ci": {"build_success_rate": 100, "deploy_success_rate": 100, "last_build_status": "running"},
                "quality": {"defect_escape": 0, "rollback_count": 0},
            },
            "recent_events": [],
            "collaborators": [],
        }

        merged = apply_repository_signals(payload, project_root=self.temp_dir)
        pipeline = merged.get("pipeline_metrics", {})

        self.assertIn("development", pipeline)
        self.assertIn("testing", pipeline)
        self.assertIn("commit", pipeline)
        self.assertIn("ci", pipeline)
        self.assertIn("quality", pipeline)

        # Integration assertion: downstream consumers can serialize the merged contract.
        json.dumps(merged, ensure_ascii=False)

    def test_governance_interaction_kpis_are_projected_to_pipeline(self) -> None:
        append_governance_event(
            self.temp_dir,
            {
                "type": "task_started",
                "message": "Begin risky task",
                "task_id": "T-3",
            },
        )
        append_governance_event(
            self.temp_dir,
            {
                "type": "task_stopped",
                "message": "Stopped by policy",
                "task_id": "T-3",
            },
        )
        append_governance_event(
            self.temp_dir,
            {
                "type": "auth_prompted",
                "message": "Need approval",
                "request_id": "REQ-2",
                "interaction_id": "INT-2",
            },
        )
        append_governance_event(
            self.temp_dir,
            {
                "type": "auth_denied",
                "message": "Denied by operator",
                "request_id": "REQ-2",
                "interaction_id": "INT-2",
            },
        )
        append_governance_event(
            self.temp_dir,
            {
                "type": "action_confirmed",
                "message": "Confirmed follow-up action",
                "interaction_id": "INT-3",
            },
        )

        payload = {
            "project": "ivx",
            "phase": "Phase 2 - Delivery",
            "task": "governance KPI projection",
            "pipeline_metrics": {
                "development": {"tasks_planned": 3, "tasks_done": 2, "velocity_points": 3},
                "testing": {"tests_passed": 0, "tests_failed": 0, "coverage_percent": 0, "regressions": 0},
                "commit": {"commits_today": 0, "prs_open": 0, "review_pending": 0, "avg_pr_cycle_minutes": 0},
                "ci": {"build_success_rate": 100, "deploy_success_rate": 100, "last_build_status": "running"},
                "quality": {"defect_escape": 0, "rollback_count": 0},
                "governance": {},
            },
            "recent_events": [],
            "collaborators": [],
        }
        meta = {"id": "temp", "path": str(self.temp_dir)}

        enriched = apply_git_activity(payload, meta)
        governance = enriched.get("pipeline_metrics", {}).get("governance", {})

        self.assertEqual(governance.get("ai_task_started_24h"), 1)
        self.assertEqual(governance.get("ai_task_stopped_24h"), 1)
        self.assertEqual(governance.get("human_authorization_requests_24h"), 1)
        self.assertEqual(governance.get("human_authorization_denied_24h"), 1)
        self.assertEqual(governance.get("authorization_approval_rate_percent"), 0)
        self.assertEqual(governance.get("human_confirmations_24h"), 1)


if __name__ == "__main__":
    unittest.main()
