"""
Entry point - run with: uvicorn main:app --reload --port 8000
"""
import uvicorn
from app.main import app  # noqa: F401

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=["app"],
        log_level="info",
    )
