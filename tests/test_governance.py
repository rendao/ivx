import shutil
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from ivx.server.governance import append_governance_event
from ivx.server.governance import derive_governance_metrics
from ivx.server.governance import governance_recent_events


class GovernanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="ivx-governance-"))

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_derive_governance_metrics_from_events(self) -> None:
        append_governance_event(
            self.temp_dir,
            {
                "type": "objective_set",
                "actor": "ai-editor",
                "message": "Set objective O-1",
                "objective_id": "O-1",
            },
        )
        append_governance_event(
            self.temp_dir,
            {
                "type": "task_completed",
                "actor": "ai-editor",
                "message": "Done T-1",
                "objective_id": "O-1",
                "task_id": "T-1",
            },
        )
        append_governance_event(
            self.temp_dir,
            {
                "type": "gate_passed",
                "actor": "ci",
                "message": "Unit tests passed",
                "gate": "unit-test",
                "result": "passed",
            },
        )

        progress = {
            "phase": "Phase 1",
            "task": "Task A",
            "failed_checks": 0,
            "blockers": [],
            "pipeline_metrics": {"testing": {"regressions": 0}},
        }

        metrics = derive_governance_metrics(progress, self.temp_dir)
        self.assertGreaterEqual(metrics["decision_logs_24h"], 3)
        self.assertEqual(metrics["gate_pass_rate_percent"], 100)
        self.assertEqual(metrics["traceability_coverage_percent"], 100)
        self.assertTrue(metrics["objective_defined"])

    def test_review_request_unresolved_is_counted(self) -> None:
        append_governance_event(
            self.temp_dir,
            {
                "type": "human_review_requested",
                "actor": "ai-editor",
                "message": "Need human confirmation",
                "request_id": "R-1",
            },
        )

        progress = {
            "phase": "Phase 1",
            "task": "Task A",
            "failed_checks": 0,
            "blockers": [],
            "pipeline_metrics": {"testing": {"regressions": 0}},
        }

        metrics = derive_governance_metrics(progress, self.temp_dir)
        self.assertEqual(metrics["unresolved_human_reviews"], 1)
        self.assertTrue(metrics.get("governance_recommendations"))
        recent = governance_recent_events(self.temp_dir, limit=3)
        self.assertEqual(len(recent), 1)

    def test_ai_and_human_interaction_kpis_are_derived(self) -> None:
        events = [
            {
                "type": "task_started",
                "actor": "ai-editor",
                "message": "Start T-2",
                "task_id": "T-2",
            },
            {
                "type": "task_stopped",
                "actor": "ai-editor",
                "message": "Stopped T-2",
                "task_id": "T-2",
            },
            {
                "type": "auth_prompted",
                "actor": "ai-editor",
                "message": "Need authorization",
                "request_id": "REQ-1",
                "interaction_id": "INT-1",
            },
            {
                "type": "auth_approved",
                "actor": "human-operator",
                "message": "Authorization approved",
                "request_id": "REQ-1",
                "interaction_id": "INT-1",
                "duration_ms": 1200,
            },
            {
                "type": "action_skipped",
                "actor": "human-operator",
                "message": "Skip risky action",
                "interaction_id": "INT-2",
            },
        ]

        for event in events:
            append_governance_event(self.temp_dir, event)

        metrics = derive_governance_metrics(
            {
                "phase": "Phase 2",
                "task": "Task B",
                "failed_checks": 0,
                "blockers": [],
                "pipeline_metrics": {"testing": {"regressions": 0}},
            },
            self.temp_dir,
        )

        self.assertEqual(metrics["ai_task_started_24h"], 1)
        self.assertEqual(metrics["ai_task_stopped_24h"], 1)
        self.assertEqual(metrics["ai_task_stop_rate_percent"], 50)
        self.assertEqual(metrics["human_authorization_requests_24h"], 1)
        self.assertEqual(metrics["human_authorization_approved_24h"], 1)
        self.assertEqual(metrics["human_authorization_denied_24h"], 0)
        self.assertEqual(metrics["pending_authorization_requests_24h"], 0)
        self.assertEqual(metrics["authorization_approval_rate_percent"], 100)
        self.assertEqual(metrics["human_skips_24h"], 1)
        self.assertEqual(metrics["human_interactions_24h"], 3)
        self.assertEqual(metrics["human_interaction_rate_percent"], 100)
        self.assertEqual(metrics["ai_behavior_events_24h"], 3)
        self.assertEqual(metrics["human_behavior_events_24h"], 2)
        self.assertEqual(metrics["behavior_events_total_24h"], 5)
        self.assertEqual(metrics["ai_behavior_ratio_percent"], 60)
        self.assertEqual(metrics["human_behavior_ratio_percent"], 40)
        self.assertEqual(metrics["ai_behavior_type_counts_24h"].get("task_started"), 1)
        self.assertEqual(metrics["human_behavior_type_counts_24h"].get("action_skipped"), 1)
        self.assertEqual(metrics["interaction_traceability_percent"], 100)
        self.assertIn(metrics["data_quality_tier"], {"A", "B", "C"})
        self.assertGreaterEqual(metrics["process_observability_score"], 0)
        self.assertLessEqual(metrics["process_observability_score"], 100)
        self.assertGreaterEqual(metrics["objective_progress_score"], 0)
        self.assertLessEqual(metrics["objective_progress_score"], 100)
        self.assertGreaterEqual(metrics["human_collaboration_quality_score"], 0)
        self.assertLessEqual(metrics["human_collaboration_quality_score"], 100)
        self.assertGreaterEqual(metrics["risk_control_score"], 0)
        self.assertLessEqual(metrics["risk_control_score"], 100)
        self.assertGreaterEqual(metrics["overall_governance_score"], 0)
        self.assertLessEqual(metrics["overall_governance_score"], 100)

    def test_event_aliases_are_normalized_to_canonical_types(self) -> None:
        alias_events = [
            {
                "type": "authorization_requested",
                "actor": "ai-editor",
                "message": "Need auth",
                "request_id": "REQ-77",
                "interaction_id": "INT-77",
            },
            {
                "type": "permission_granted",
                "actor": "human-operator",
                "message": "Approved",
                "request_id": "REQ-77",
                "interaction_id": "INT-77",
            },
            {
                "type": "gate",
                "actor": "ci",
                "message": "Gate result",
                "result": "passed",
            },
        ]

        for event in alias_events:
            append_governance_event(self.temp_dir, event)

        recent = governance_recent_events(self.temp_dir, limit=5)
        recent_types = {item.get("type") for item in recent}
        self.assertIn("auth_prompted", recent_types)
        self.assertIn("auth_approved", recent_types)
        self.assertIn("gate_passed", recent_types)

        metrics = derive_governance_metrics(
            {
                "phase": "Phase 2",
                "task": "Task C",
                "failed_checks": 0,
                "blockers": [],
                "pipeline_metrics": {"testing": {"regressions": 0}},
            },
            self.temp_dir,
        )
        self.assertEqual(metrics["human_authorization_requests_24h"], 1)
        self.assertEqual(metrics["human_authorization_approved_24h"], 1)
        self.assertEqual(metrics["gate_pass_rate_percent"], 100)


if __name__ == "__main__":
    unittest.main()
