from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import io
import uvicorn
import asyncio
from typing import Optional

app = FastAPI(title="BOM Platform API (Mock Phase)")

# Configure CORS for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage for BOM data
global_bom_data = []
global_columns = []


@app.get("/")
async def root():
    """Welcome page"""
    return {
        "message": "Success! BOM Backend is running.",
        "docs_url": "Visit /docs for API documentation"
    }


@app.post("/api/upload")
async def upload_bom(file: UploadFile = File(...)):
    """Receive and parse uploaded Excel/CSV file"""
    global global_bom_data, global_columns
    contents = await file.read()

    try:
        # Determine file type
        if file.filename.endswith('.csv'):
            df = pd.read_csv(io.BytesIO(contents))
        else:
            df = pd.read_excel(io.BytesIO(contents), engine='openpyxl')

        # Replace NaN values with empty strings to avoid JSON serialization errors
        df = df.fillna("")

        # Extract dynamic columns and row data
        global_columns = df.columns.tolist()
        global_bom_data = df.to_dict(orient="records")

        return {
            "status": "success",
            "rows": len(global_bom_data),
            "columns": global_columns,
            "data": global_bom_data
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/api/search")
async def search_drawings(category: str, component: str):
    """
    Mock API simulating SharePoint Graph API search.
    """
    # Simulate network delay for realistic UI loading
    await asyncio.sleep(0.6)

    mock_drawings = []

    # Generate mock data based on the component number
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

    return {
        "status": "success",
        "mock_category_folder": category,
        "results": mock_drawings
    }


if __name__ == "__main__":
    uvicorn.run("BOM_Backend_API:app", host="0.0.0.0", port=8000, reload=True)