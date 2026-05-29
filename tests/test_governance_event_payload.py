import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from ivx.server.service import build_governance_event_payload


class GovernanceEventPayloadTests(unittest.TestCase):
    def test_extended_fields_are_passed_through(self) -> None:
        payload = {
            "type": "auth_prompted",
            "actor": "ai-agent",
            "message": "Need approval",
            "request_id": "REQ-9",
            "interaction_id": "INT-9",
            "workflow_id": "wf-1",
            "run_id": "run-1",
            "step_id": "step-1",
            "decision": "wait",
            "channel": "editor-popup",
            "target": "filesystem",
            "duration_ms": 1234,
        }

        event_payload = build_governance_event_payload(payload)
        self.assertEqual(event_payload.get("interaction_id"), "INT-9")
        self.assertEqual(event_payload.get("workflow_id"), "wf-1")
        self.assertEqual(event_payload.get("run_id"), "run-1")
        self.assertEqual(event_payload.get("step_id"), "step-1")
        self.assertEqual(event_payload.get("decision"), "wait")
        self.assertEqual(event_payload.get("channel"), "editor-popup")
        self.assertEqual(event_payload.get("target"), "filesystem")
        self.assertEqual(event_payload.get("duration_ms"), 1234)


if __name__ == "__main__":
    unittest.main()
