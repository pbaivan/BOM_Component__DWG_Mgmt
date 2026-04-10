from __future__ import annotations

"""Legacy compatibility entrypoint.

This file is kept so existing startup commands like
`python BOM_Backend_API.py` continue to work after modularization.
"""

import uvicorn

from app.main import app


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
