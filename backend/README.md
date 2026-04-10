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

## CI trigger

Repository includes a manual GitHub Actions workflow:
- .github/workflows/backend-regression-smoke.yml

Run it from Actions -> backend-regression-smoke -> Run workflow.
Provide a reachable base_url and configure required repository secrets for DB/SharePoint integration.
