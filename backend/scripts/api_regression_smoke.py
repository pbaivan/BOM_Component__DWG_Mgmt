from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx


@dataclass
class CheckResult:
    name: str
    status: str
    detail: str
    http_status: int | None = None


def _is_json_response(resp: httpx.Response) -> bool:
    return resp.headers.get("content-type", "").lower().startswith("application/json")


def _run_request(
    client: httpx.Client,
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    data: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
    files: dict[str, Any] | None = None,
) -> httpx.Response:
    return client.request(method, path, params=params, data=data, json=json_body, files=files)


def _wait_for_health(base_url: str, timeout_seconds: int) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with httpx.Client(base_url=base_url, timeout=2.0) as client:
                resp = client.get("/api/health")
                if resp.status_code == 200:
                    return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def _start_local_server(base_url: str) -> subprocess.Popen[str]:
    parsed = urlparse(base_url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 8000

    backend_root = Path(__file__).resolve().parents[1]
    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        host,
        "--port",
        str(port),
    ]
    return subprocess.Popen(
        cmd,
        cwd=str(backend_root),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def _stop_server(process: subprocess.Popen[str] | None) -> None:
    if process is None:
        return
    if process.poll() is not None:
        return

    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()


def run_smoke(
    base_url: str,
    timeout_seconds: int,
    category: str,
    component: str,
    strict_sharepoint: bool,
) -> tuple[list[CheckResult], bool]:
    results: list[CheckResult] = []

    def add_result(name: str, status: str, detail: str, http_status: int | None = None) -> None:
        results.append(CheckResult(name=name, status=status, detail=detail, http_status=http_status))

    def try_request(
        name: str,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
    ) -> httpx.Response | None:
        try:
            return _run_request(
                client,
                method,
                path,
                params=params,
                data=data,
                json_body=json_body,
                files=files,
            )
        except Exception as exc:
            add_result(name, "fail", f"request error: {type(exc).__name__}: {exc}")
            return None

    record_id: str | None = None

    with httpx.Client(base_url=base_url, timeout=timeout_seconds) as client:
        health = try_request("health", "GET", "/api/health")
        if health is None:
            return results, False
        if health.status_code == 200:
            add_result("health", "pass", "health endpoint reachable", health.status_code)
        else:
            add_result("health", "fail", f"unexpected status: {health.status_code}", health.status_code)
            return results, False

        create_record = try_request("save_new_record", "POST", "/api/save/new-record")
        if create_record is None:
            return results, False
        if create_record.status_code == 200 and _is_json_response(create_record):
            body = create_record.json()
            record_id = str(body.get("record_id") or "").strip()
            if record_id:
                add_result("save_new_record", "pass", f"record created: {record_id}", create_record.status_code)
            else:
                add_result("save_new_record", "fail", "record_id missing", create_record.status_code)
        else:
            add_result("save_new_record", "fail", "failed to create record", create_record.status_code)

        if not record_id:
            return results, False

        csv_bytes = b"parent,component,qty\nROOT,COMP-001,1\n"
        upload = try_request(
            "upload",
            "POST",
            "/api/upload",
            data={"record_id": record_id},
            files={"file": ("smoke.csv", csv_bytes, "text/csv")},
        )
        if upload is not None and upload.status_code == 200:
            add_result("upload", "pass", "upload endpoint succeeded", upload.status_code)
        else:
            add_result("upload", "fail", "upload endpoint failed", None if upload is None else upload.status_code)

        metadata = try_request(
            "save_metadata",
            "POST",
            "/api/save/metadata",
            json_body={
                "record_id": record_id,
                "file_name": "smoke.csv",
                "upload_date": "2026-04-10",
                "version": "v1",
            },
        )
        if metadata is not None and metadata.status_code == 200:
            add_result("save_metadata", "pass", "metadata saved", metadata.status_code)
        else:
            add_result("save_metadata", "fail", "metadata save failed", None if metadata is None else metadata.status_code)

        table = try_request("save_table", "GET", f"/api/save/table/{record_id}", params={"offset": 0, "limit": 10})
        if table is not None and table.status_code == 200 and _is_json_response(table):
            rows = table.json().get("rows") or []
            add_result("save_table", "pass", f"rows returned: {len(rows)}", table.status_code)
        else:
            add_result("save_table", "fail", "saved table fetch failed", None if table is None else table.status_code)

        download = try_request("save_file_download", "GET", f"/api/save/file/{record_id}/download")
        if download is not None and download.status_code == 200 and len(download.content) > 0:
            add_result("save_file_download", "pass", f"bytes: {len(download.content)}", download.status_code)
        else:
            add_result("save_file_download", "fail", "download failed", None if download is None else download.status_code)

        save_list = try_request("save_list", "GET", "/api/save/list", params={"limit": 5})
        if save_list is not None and save_list.status_code == 200 and _is_json_response(save_list):
            count = len(save_list.json().get("records") or [])
            add_result("save_list", "pass", f"records returned: {count}", save_list.status_code)
        else:
            add_result("save_list", "fail", "list failed", None if save_list is None else save_list.status_code)

        search = try_request("search", "GET", "/api/search", params={"category": category, "component": component})
        search_results: list[dict[str, Any]] = []
        if search is not None and search.status_code == 200 and _is_json_response(search):
            body = search.json()
            search_results = body.get("results") or []
            add_result("search", "pass", f"results: {len(search_results)}", search.status_code)
        else:
            add_result("search", "fail", "search failed", None if search is None else search.status_code)

        if not search_results:
            if strict_sharepoint:
                add_result("sp_file", "fail", "search returned no results; cannot test sp_file")
            else:
                add_result("sp_file", "skip", "search returned no results; skipped")
        else:
            first = search_results[0]
            sp_file = try_request(
                "sp_file",
                "GET",
                "/api/sp_file",
                params={
                    "drive_id": first.get("drive_id", ""),
                    "item_id": first.get("item_id", ""),
                    "filename": first.get("name", "file"),
                    "mode": "preview",
                },
            )
            if sp_file is not None and sp_file.status_code == 200 and len(sp_file.content) > 0:
                add_result("sp_file", "pass", f"bytes: {len(sp_file.content)}", sp_file.status_code)
            else:
                add_result("sp_file", "fail", "sp_file failed", None if sp_file is None else sp_file.status_code)

    passed = all(item.status != "fail" for item in results)
    return results, passed


def main() -> int:
    parser = argparse.ArgumentParser(description="Reusable API regression smoke test.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="Backend base URL")
    parser.add_argument("--timeout", type=int, default=120, help="Request timeout in seconds")
    parser.add_argument("--startup-timeout", type=int, default=40, help="Startup wait timeout when starting server")
    parser.add_argument("--category", default="Drawings", help="Category used for /api/search")
    parser.add_argument("--component", default="FB", help="Component used for /api/search")
    parser.add_argument("--start-server", action="store_true", help="Start local uvicorn before running tests")
    parser.add_argument(
        "--allow-empty-search",
        action="store_true",
        help="Do not fail when /api/search returns zero results",
    )
    args = parser.parse_args()

    process: subprocess.Popen[str] | None = None
    try:
        if args.start_server:
            process = _start_local_server(args.base_url)
            ready = _wait_for_health(args.base_url, args.startup_timeout)
            if not ready:
                tail = ""
                if process.poll() is not None and process.stdout is not None:
                    tail = process.stdout.read()[-4000:]
                print(
                    json.dumps(
                        {
                            "status": "error",
                            "message": "server did not become ready",
                            "server_output_tail": tail,
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
                )
                return 2

        results, passed = run_smoke(
            base_url=args.base_url,
            timeout_seconds=args.timeout,
            category=args.category,
            component=args.component,
            strict_sharepoint=not args.allow_empty_search,
        )

        output = {
            "status": "pass" if passed else "fail",
            "base_url": args.base_url,
            "checks": [asdict(item) for item in results],
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0 if passed else 1
    finally:
        _stop_server(process)


if __name__ == "__main__":
    raise SystemExit(main())
