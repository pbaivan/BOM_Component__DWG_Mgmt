from __future__ import annotations

import argparse
import json
import statistics
import time
from dataclasses import asdict, dataclass
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
    args = parser.parse_args()

    report = run_benchmark(
        base_url=args.base_url,
        category=args.category,
        component=args.component,
        runs=max(1, args.runs),
        timeout_seconds=max(1, args.timeout),
    )

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["summary"]["fail_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
