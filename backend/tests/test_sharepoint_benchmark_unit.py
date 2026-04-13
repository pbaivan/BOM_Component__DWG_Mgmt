from __future__ import annotations

import unittest

from scripts.sharepoint_search_benchmark import build_comparison


class SharePointBenchmarkComparisonTests(unittest.TestCase):
    def test_latency_regression_is_flagged(self) -> None:
        baseline = {
            "runs": 10,
            "summary": {
                "avg_elapsed_ms": 100.0,
                "p95_elapsed_ms": 150.0,
                "fail_count": 0,
            },
        }
        current = {
            "runs": 10,
            "summary": {
                "avg_elapsed_ms": 130.0,
                "p95_elapsed_ms": 190.0,
                "fail_count": 0,
            },
        }

        comparison = build_comparison(
            current_report=current,
            baseline_report=baseline,
            max_latency_regression_pct=20.0,
            max_fail_rate_increase=0.1,
        )

        self.assertTrue(comparison["regression"])
        self.assertGreaterEqual(len(comparison["reasons"]), 1)

    def test_no_regression_when_within_thresholds(self) -> None:
        baseline = {
            "runs": 10,
            "summary": {
                "avg_elapsed_ms": 100.0,
                "p95_elapsed_ms": 150.0,
                "fail_count": 1,
            },
        }
        current = {
            "runs": 10,
            "summary": {
                "avg_elapsed_ms": 115.0,
                "p95_elapsed_ms": 165.0,
                "fail_count": 1,
            },
        }

        comparison = build_comparison(
            current_report=current,
            baseline_report=baseline,
            max_latency_regression_pct=20.0,
            max_fail_rate_increase=0.1,
        )

        self.assertFalse(comparison["regression"])
        self.assertEqual(comparison["reasons"], [])

    def test_fail_rate_regression_is_flagged(self) -> None:
        baseline = {
            "runs": 10,
            "summary": {
                "avg_elapsed_ms": 100.0,
                "p95_elapsed_ms": 150.0,
                "fail_count": 0,
            },
        }
        current = {
            "runs": 10,
            "summary": {
                "avg_elapsed_ms": 100.0,
                "p95_elapsed_ms": 150.0,
                "fail_count": 3,
            },
        }

        comparison = build_comparison(
            current_report=current,
            baseline_report=baseline,
            max_latency_regression_pct=25.0,
            max_fail_rate_increase=0.1,
        )

        self.assertTrue(comparison["regression"])
        self.assertTrue(any("fail_rate" in reason for reason in comparison["reasons"]))


if __name__ == "__main__":
    unittest.main()
