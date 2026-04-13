from __future__ import annotations

import argparse
import json
import statistics
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import httpx


@dataclass
class IterationResult:
    iteration: int
    status: str
    http_status: int | None
    elapsed_ms: float
    result_count: int
    success_targets: int | None
    failed_targets: int | None
    error: str | None = None


def _safe_pct_delta(*, current: float, baseline: float) -> float | None:
    if baseline <= 0:
        return None
    return round(((current - baseline) / baseline) * 100.0, 2)


def _load_report(path: str) -> dict[str, Any]:
    payload = Path(path).read_text(encoding="utf-8-sig")
    report = json.loads(payload)
    if not isinstance(report, dict):
        raise ValueError(f"invalid report json: {path}")
    return report


def _write_report(path: str, report: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def build_comparison(
    *,
    current_report: dict[str, Any],
    baseline_report: dict[str, Any],
    max_latency_regression_pct: float,
    max_fail_rate_increase: float,
) -> dict[str, Any]:
    current_summary = current_report.get("summary") or {}
    baseline_summary = baseline_report.get("summary") or {}

    current_runs = max(1, int(current_report.get("runs") or 0))
    baseline_runs = max(1, int(baseline_report.get("runs") or 0))

    current_avg = float(current_summary.get("avg_elapsed_ms") or 0.0)
    current_p95 = float(current_summary.get("p95_elapsed_ms") or 0.0)
    current_fail_rate = float(current_summary.get("fail_count") or 0.0) / current_runs

    baseline_avg = float(baseline_summary.get("avg_elapsed_ms") or 0.0)
    baseline_p95 = float(baseline_summary.get("p95_elapsed_ms") or 0.0)
    baseline_fail_rate = float(baseline_summary.get("fail_count") or 0.0) / baseline_runs

    avg_pct_delta = _safe_pct_delta(current=current_avg, baseline=baseline_avg)
    p95_pct_delta = _safe_pct_delta(current=current_p95, baseline=baseline_p95)
    fail_rate_delta = round(current_fail_rate - baseline_fail_rate, 4)

    reasons: list[str] = []
    if avg_pct_delta is not None and avg_pct_delta > max_latency_regression_pct:
        reasons.append(
            f"avg_elapsed_ms regression {avg_pct_delta}% exceeds {max_latency_regression_pct}%"
        )
    if p95_pct_delta is not None and p95_pct_delta > max_latency_regression_pct:
        reasons.append(
            f"p95_elapsed_ms regression {p95_pct_delta}% exceeds {max_latency_regression_pct}%"
        )
    if fail_rate_delta > max_fail_rate_increase:
        reasons.append(
            f"fail_rate regression {round(fail_rate_delta * 100.0, 2)}% exceeds {round(max_fail_rate_increase * 100.0, 2)}%"
        )

    return {
        "regression": len(reasons) > 0,
        "thresholds": {
            "max_latency_regression_pct": max_latency_regression_pct,
            "max_fail_rate_increase": max_fail_rate_increase,
        },
        "baseline_summary": {
            "runs": baseline_runs,
            "avg_elapsed_ms": baseline_avg,
            "p95_elapsed_ms": baseline_p95,
            "fail_rate": round(baseline_fail_rate, 4),
        },
        "current_summary": {
            "runs": current_runs,
            "avg_elapsed_ms": current_avg,
            "p95_elapsed_ms": current_p95,
            "fail_rate": round(current_fail_rate, 4),
        },
        "delta": {
            "avg_elapsed_ms": round(current_avg - baseline_avg, 2),
            "p95_elapsed_ms": round(current_p95 - baseline_p95, 2),
            "avg_elapsed_pct": avg_pct_delta,
            "p95_elapsed_pct": p95_pct_delta,
            "fail_rate": fail_rate_delta,
        },
        "reasons": reasons,
    }


def _p95(values: list[float]) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    sorted_values = sorted(values)
    idx = int(round(0.95 * (len(sorted_values) - 1)))
    return sorted_values[idx]


def run_benchmark(
    *,
    base_url: str,
    category: str,
    component: str,
    runs: int,
    timeout_seconds: int,
) -> dict[str, Any]:
    results: list[IterationResult] = []

    with httpx.Client(base_url=base_url, timeout=timeout_seconds) as client:
        for i in range(1, runs + 1):
            started = time.perf_counter()
            try:
                resp = client.get(
                    "/api/search",
                    params={
                        "category": category,
                        "component": component,
                        "include_debug": "true",
                    },
                )
                elapsed_ms = round((time.perf_counter() - started) * 1000.0, 2)

                if resp.status_code != 200:
                    results.append(
                        IterationResult(
                            iteration=i,
                            status="fail",
                            http_status=resp.status_code,
                            elapsed_ms=elapsed_ms,
                            result_count=0,
                            success_targets=None,
                            failed_targets=None,
                            error=f"http_{resp.status_code}",
                        )
                    )
                    continue

                body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                debug = body.get("debug") if isinstance(body, dict) else None
                result_count = len((body.get("results") or [])) if isinstance(body, dict) else 0

                results.append(
                    IterationResult(
                        iteration=i,
                        status="pass",
                        http_status=resp.status_code,
                        elapsed_ms=elapsed_ms,
                        result_count=result_count,
                        success_targets=(debug or {}).get("success_targets"),
                        failed_targets=(debug or {}).get("failed_targets"),
                    )
                )
            except Exception as exc:
                elapsed_ms = round((time.perf_counter() - started) * 1000.0, 2)
                results.append(
                    IterationResult(
                        iteration=i,
                        status="fail",
                        http_status=None,
                        elapsed_ms=elapsed_ms,
                        result_count=0,
                        success_targets=None,
                        failed_targets=None,
                        error=f"{type(exc).__name__}: {exc}",
                    )
                )

    elapsed_values = [item.elapsed_ms for item in results]
    pass_count = sum(1 for item in results if item.status == "pass")

    return {
        "status": "pass" if pass_count == runs else "partial",
        "base_url": base_url,
        "category": category,
        "component": component,
        "runs": runs,
        "summary": {
            "pass_count": pass_count,
            "fail_count": runs - pass_count,
            "avg_elapsed_ms": round(statistics.mean(elapsed_values), 2) if elapsed_values else 0.0,
            "p95_elapsed_ms": round(_p95(elapsed_values), 2),
            "min_elapsed_ms": round(min(elapsed_values), 2) if elapsed_values else 0.0,
            "max_elapsed_ms": round(max(elapsed_values), 2) if elapsed_values else 0.0,
        },
        "iterations": [asdict(item) for item in results],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark /api/search latency and target diagnostics.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="Backend base URL")
    parser.add_argument("--category", default="Drawings", help="Search category")
    parser.add_argument("--component", default="FB", help="Search component")
    parser.add_argument("--runs", type=int, default=5, help="Benchmark iteration count")
    parser.add_argument("--timeout", type=int, default=60, help="Request timeout in seconds")
    parser.add_argument("--input-report", default="", help="Existing benchmark report JSON path")
    parser.add_argument("--baseline", default="", help="Baseline benchmark report JSON path")
    parser.add_argument("--output", default="", help="Write current report JSON to path")
    parser.add_argument("--write-baseline", default="", help="Write current report as new baseline JSON")
    parser.add_argument(
        "--max-latency-regression-pct",
        type=float,
        default=20.0,
        help="Max allowed avg/p95 latency regression percentage before exit code 2",
    )
    parser.add_argument(
        "--max-fail-rate-increase",
        type=float,
        default=0.10,
        help="Max allowed fail-rate increase (0.10 = 10%%) before exit code 2",
    )
    args = parser.parse_args()

    if args.input_report:
        report = _load_report(args.input_report)
    else:
        report = run_benchmark(
            base_url=args.base_url,
            category=args.category,
            component=args.component,
            runs=max(1, args.runs),
            timeout_seconds=max(1, args.timeout),
        )

    if args.baseline:
        baseline_report = _load_report(args.baseline)
        report["comparison"] = build_comparison(
            current_report=report,
            baseline_report=baseline_report,
            max_latency_regression_pct=max(0.0, args.max_latency_regression_pct),
            max_fail_rate_increase=max(0.0, args.max_fail_rate_increase),
        )

    if args.output:
        _write_report(args.output, report)

    if args.write_baseline:
        _write_report(args.write_baseline, report)

    print(json.dumps(report, ensure_ascii=False, indent=2))

    fail_count = int((report.get("summary") or {}).get("fail_count") or 0)
    if fail_count > 0:
        return 1

    comparison = report.get("comparison") if isinstance(report, dict) else None
    if isinstance(comparison, dict) and comparison.get("regression"):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
