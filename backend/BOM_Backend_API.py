from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import pandas as pd
import io
import uvicorn
import asyncio
import logging
import os
from pathlib import Path

logger = logging.getLogger("bom_api")

MAX_UPLOAD_BYTES = int(os.getenv("BOM_MAX_UPLOAD_BYTES", str(100 * 1024 * 1024)))
ALLOWED_EXTENSIONS = {".csv", ".xlsx"}
LOCAL_ORIGIN_REGEX = os.getenv(
    "BOM_ALLOWED_ORIGIN_REGEX",
    r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
)


def _get_allowed_origins() -> list[str]:
    raw = os.getenv("BOM_ALLOWED_ORIGINS", "http://127.0.0.1:5173,http://localhost:5173")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]

app = FastAPI(title="BOM Platform API (Mock Phase)")

# Configure CORS to allow React frontend to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=_get_allowed_origins(),
    allow_origin_regex=LOCAL_ORIGIN_REGEX,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"status": "error", "message": str(exc.detail)},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, __: Exception):
    logger.exception("Unhandled server exception.")
    return JSONResponse(
        status_code=500,
        content={"status": "error", "message": "Internal server error."},
    )


@app.get("/")
async def root():
    """Welcome page to verify server is running."""
    return {
        "message": "Success! BOM Backend is running.",
        "docs_url": "Visit /docs for API documentation"
    }


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "service": "bom-backend",
    }


@app.post("/api/upload")
async def upload_bom(file: UploadFile = File(...)):
    """Receive, parse, and extract data/columns from the uploaded Excel/CSV file."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required.")

    extension = Path(file.filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Only .csv and .xlsx files are supported.")

    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=f"File is too large. Max allowed size is {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.")

    try:
        # Determine the correct engine based on file extension
        if extension == '.csv':
            df = pd.read_csv(io.BytesIO(contents))
        else:
            df = pd.read_excel(io.BytesIO(contents), engine='openpyxl')

        # Replace NaN values with empty strings to avoid JSON serialization errors in React
        df = df.fillna("")

        # Extract dynamic columns and row data
        columns = [str(col) for col in df.columns.tolist()]
        rows = df.to_dict(orient="records")

        return {
            "status": "success",
            "rows": len(rows),
            "columns": columns,
            "data": rows
        }
    except HTTPException:
        raise
    except (ValueError, pd.errors.ParserError):
        logger.warning("Upload rejected due to invalid file format: %s", file.filename)
        raise HTTPException(status_code=400, detail="Invalid or corrupted BOM file format.")
    except Exception:
        logger.exception("Unexpected error while processing upload.")
        raise HTTPException(status_code=500, detail="Failed to process BOM file.")


@app.get("/api/search")
async def search_drawings(category: str, component: str):
    """
    Mock API simulating the SharePoint Graph API search behavior.
    """
    # Simulate network delay for realistic UI loading experience
    await asyncio.sleep(0.6)

    mock_drawings = []

    # Generate mock drawing data based on the requested component number
    if component and "-" in component:
        mock_drawings = [
            {
                "id": f"doc_{component}_1",
                "name": f"{component}_Assembly_Drawing.pdf",
                "version": "A01",
                "type": "PDF",
                "date": "2023-10-15"
            },
            {
                "id": f"doc_{component}_2",
                "name": f"{component}_Part_Details.pdf",
                "version": "B02",
                "type": "PDF",
                "date": "2023-11-20"
            },
            {
                "id": f"doc_{component}_3",
                "name": f"{component}_3D_Model.step",
                "version": "Release",
                "type": "CAD",
                "date": "2023-12-01"
            }
        ]
    elif component:
        mock_drawings = [
            {
                "id": f"doc_{component}_4",
                "name": f"{component}_Datasheet.pdf",
                "version": "1.0",
                "type": "PDF",
                "date": "2024-01-10"
            }
        ]

    # Generate a structured array for the SharePoint Breadcrumb path
    sharepoint_path_array = [
        "SharePoint Root",
        "Engineering Documents",
        category if category else "Uncategorized",
        component if component else "Unknown Model",
        "Released Drawings"
    ]

    return {
        "status": "success",
        "mock_category_folder": category,
        "sharepoint_path": sharepoint_path_array,
        "results": mock_drawings
    }


if __name__ == "__main__":
    uvicorn.run("BOM_Backend_API:app", host="0.0.0.0", port=8000, reload=True)