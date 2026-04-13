# Backend Notes

## Step3 status

Step3 is complete with these boundaries:
- App entry and lifecycle in app/main.py
- HTTP routes in app/routes/*
- SharePoint integration in app/services/sharepoint_service.py
- BOM domain split into dedicated modules:
	- app/services/bom_models.py
	- app/services/bom_utils.py
	- app/services/bom_parser.py
	- app/services/bom_records_service.py
- app/services/bom_data.py is retained as a compatibility facade for legacy imports

## API regression smoke test

Reusable regression script covers these endpoint flows:
- /api/health
- /api/save/new-record
- /api/upload
- /api/save/metadata
- /api/save/table/{record_id}
- /api/save/file/{record_id}/download
- /api/save/list
- /api/search
- /api/sp_file

Run with local server auto-start:
python scripts/api_regression_smoke.py --start-server --category Drawings --component FB

Run against an existing server:
python scripts/api_regression_smoke.py --base-url http://127.0.0.1:8000 --category Drawings --component FB

One-command PowerShell wrapper:
powershell -ExecutionPolicy Bypass -File scripts/run_regression.ps1 -StartServer

Allow empty search result without failing sp_file check:
python scripts/api_regression_smoke.py --start-server --allow-empty-search

Exit codes:
- 0: all checks pass
- 1: one or more checks fail
- 2: local server did not become ready

## CI quick gate (Stage 3A)

Repository includes a pull-request quick check workflow:
- .github/workflows/pr-quick-check.yml

It runs:
- Frontend lint and build (frontend/bom-frontend)
- Backend compile check and app wiring verification (no external DB/SharePoint required)

## CI manual integration

Repository also includes a manual real-integration workflow:
- .github/workflows/backend-regression-smoke.yml

Run it from Actions -> backend-regression-smoke -> Run workflow.
Provide a reachable base_url and configure required repository secrets for DB/SharePoint integration.

## Stage 3B SharePoint service status

SharePoint logic has been split into dedicated modules:
- app/services/sharepoint_auth.py
- app/services/sharepoint_search.py
- app/services/sharepoint_file_proxy.py
- app/services/sharepoint_utils.py

`app/services/sharepoint_service.py` is retained as a compatibility facade.

Search across multiple target URLs now uses controlled parallelism:
- `SHAREPOINT_TARGET_CONCURRENCY` (default: 4)
- `SHAREPOINT_SEARCH_TIMEOUT_SECONDS` (default: 30)
- `SHAREPOINT_MAX_FOLDER_SCAN` (default: 1200)

Token acquisition now uses an in-memory cache to reduce repeated MSAL token requests:
- `SHAREPOINT_TOKEN_MIN_TTL_SECONDS` (default: 120, minimum: 30)

Search diagnostics are available as an opt-in response extension:
- `GET /api/search?category=...&component=...&include_debug=true`
- Default response shape is unchanged when `include_debug` is omitted.

Performance benchmark helper:
- `python scripts/sharepoint_search_benchmark.py --base-url http://127.0.0.1:8000 --category Drawings --component FB --runs 5`
- Output includes `avg_elapsed_ms`, `p95_elapsed_ms`, pass/fail counts, and per-iteration details.

Benchmark baseline comparison workflow:
- Generate current benchmark report:
	- `python scripts/sharepoint_search_benchmark.py --base-url http://127.0.0.1:8000 --category Drawings --component FB --runs 5 --output data/perf/sharepoint_current.json`
- Compare current report against baseline (exit code `2` if regression exceeds thresholds):
	- `python scripts/sharepoint_search_benchmark.py --input-report data/perf/sharepoint_current.json --baseline data/perf/sharepoint_baseline.json`
- Promote current report as new baseline:
	- `python scripts/sharepoint_search_benchmark.py --input-report data/perf/sharepoint_current.json --write-baseline data/perf/sharepoint_baseline.json`

Threshold controls:
- `--max-latency-regression-pct` (default: `20.0`)
- `--max-fail-rate-increase` (default: `0.10`, equals 10%)

## Stage 5A observability status

Backend request observability now includes:
- Per-request `X-Request-ID` response header.
- Structured JSON logs for request summary (`method`, `path`, `status_code`, `elapsed_ms`, `client_ip`).
- Error responses include `request_id` so frontend and logs can be correlated quickly.

Log level can be controlled via:
- `BOM_LOG_LEVEL` (default: `INFO`)

## Stage 5B quality gate status

Backend tests now include:
- Unit tests for BOM utilities and observability formatting.
- Contract tests verifying `X-Request-ID` response header and error-body `request_id` consistency.
- Unit tests for benchmark baseline-comparison regression rules.

Run tests:
- `python -m unittest discover -s tests -p "test_*.py"`

## Real-site test readiness

When moving from local `http://localhost:5173` to a real website for colleague testing:
- Set frontend `VITE_API_BASE_URL` to the public backend URL (optional if frontend/backend are same origin).
- Configure backend `BOM_ALLOWED_ORIGINS` to include the real frontend origin(s), for example `https://bom-uat.yourcompany.com`.
- Keep local origins if needed for dev, e.g. `http://127.0.0.1:5173,http://localhost:5173`.
- Verify reachability with `GET /api/health` from the deployed frontend network.
