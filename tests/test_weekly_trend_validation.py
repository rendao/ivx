import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.weekly_trend_validation import summarize


class WeeklyTrendValidationTests(unittest.TestCase):
    def test_summarize_marks_pass_for_stable_samples(self) -> None:
        samples = [
            {
                "project_count": 3,
                "primary_progress_percent": 22,
                "secondary_progress_percent": 57,
                "switch_back_matches_primary": True,
                "secondary_ci_status": "success",
                "duration_seconds": 1.25,
            },
            {
                "project_count": 3,
                "primary_progress_percent": 22,
                "secondary_progress_percent": 57,
                "switch_back_matches_primary": True,
                "secondary_ci_status": "success",
                "duration_seconds": 1.75,
            },
        ]

        report = summarize(samples)
        self.assertTrue(report["overall_pass"])
        self.assertEqual(report["duration_seconds"], 3.0)
        self.assertEqual(report["switch_back_success_rate_percent"], 100)
        self.assertEqual(report["secondary_ci_success_rate_percent"], 100)
        self.assertTrue(report["secondary_progress_percent"]["stable"])

    def test_summarize_marks_fail_on_switch_back_or_ci_failure(self) -> None:
        samples = [
            {
                "project_count": 3,
                "primary_progress_percent": 22,
                "secondary_progress_percent": 57,
                "switch_back_matches_primary": False,
                "secondary_ci_status": "success",
                "duration_seconds": 1.0,
            },
            {
                "project_count": 3,
                "primary_progress_percent": 22,
                "secondary_progress_percent": 57,
                "switch_back_matches_primary": True,
                "secondary_ci_status": "failed",
                "duration_seconds": 1.0,
            },
        ]

        report = summarize(samples)
        self.assertFalse(report["overall_pass"])
        self.assertLess(report["switch_back_success_rate_percent"], 100)
        self.assertLess(report["secondary_ci_success_rate_percent"], 100)


if __name__ == "__main__":
    unittest.main()
