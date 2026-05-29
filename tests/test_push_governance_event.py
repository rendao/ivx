import json
import sys
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from ivx import push_governance_event


class _FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return b"{}"


class PushGovernanceEventTests(unittest.TestCase):
    def test_extended_event_payload_is_sent(self) -> None:
        captured = {}

        def fake_urlopen(request, timeout=10):
            captured["data"] = request.data
            captured["url"] = request.full_url
            return _FakeResponse()

        argv = [
            "push_governance_event.py",
            "--url",
            "http://127.0.0.1:8789/api/governance/event",
            "--type",
            "auth_prompted",
            "--message",
            "authorization needed",
            "--workflow-id",
            "wf-2",
            "--run-id",
            "run-2",
            "--step-id",
            "step-2",
            "--interaction-id",
            "int-2",
            "--decision",
            "wait",
            "--channel",
            "popup",
            "--target",
            "git-push",
            "--duration-ms",
            "2500",
        ]

        with mock.patch.object(sys, "argv", argv):
            with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
                code = push_governance_event.main()

        self.assertEqual(code, 0)
        body = json.loads(captured["data"].decode("utf-8"))
        self.assertEqual(body.get("type"), "auth_prompted")
        self.assertEqual(body.get("workflow_id"), "wf-2")
        self.assertEqual(body.get("run_id"), "run-2")
        self.assertEqual(body.get("step_id"), "step-2")
        self.assertEqual(body.get("interaction_id"), "int-2")
        self.assertEqual(body.get("decision"), "wait")
        self.assertEqual(body.get("channel"), "popup")
        self.assertEqual(body.get("target"), "git-push")
        self.assertEqual(body.get("duration_ms"), 2500)


if __name__ == "__main__":
    unittest.main()
