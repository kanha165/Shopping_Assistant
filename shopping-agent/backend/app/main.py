"""
Main FastAPI application entry point — stateless, no DB, no auth required.
"""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.logger import app_logger
from app.api.routes_search import router as search_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    app_logger.info("=" * 60)
    app_logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    app_logger.info("=" * 60)

    os.makedirs("logs", exist_ok=True)

    # Pre-warm the LangGraph agent
    try:
        from app.agent.graph import get_shopping_graph
        get_shopping_graph()
        app_logger.info("LangGraph agent compiled and ready")
    except Exception as e:
        app_logger.warning(f"Agent pre-warm failed (will retry on first request): {e}")

    # Install Playwright browsers if not present
    try:
        import subprocess
        subprocess.run(
            ["playwright", "install", "chromium", "--with-deps"],
            capture_output=True, timeout=120,
        )
        app_logger.info("Playwright browsers ready")
    except Exception as e:
        app_logger.warning(f"Playwright install skipped: {e}")

    app_logger.info("Application startup complete")
    yield
    app_logger.info("Application shutting down...")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI Shopping & Price Comparison Agent — Amazon, Flipkart, Snapdeal",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    app_logger.error(f"Unhandled exception: {exc} | Path: {request.url.path}")
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal server error occurred. Please try again."},
    )


app.include_router(search_router, prefix="/api")


@app.get("/api/health", tags=["Health"])
async def health_check():
    return {"status": "ok", "app": settings.APP_NAME, "version": settings.APP_VERSION}


@app.get("/api/platforms", tags=["Info"])
async def get_supported_platforms():
    return {
        "platforms": [
            {"id": "amazon",   "name": "Amazon India", "url": "https://www.amazon.in"},
            {"id": "flipkart", "name": "Flipkart",      "url": "https://www.flipkart.com"},
            {"id": "snapdeal", "name": "Snapdeal",      "url": "https://www.snapdeal.com"},
        ]
    }


# Serve frontend
frontend_path = os.path.join(os.path.dirname(__file__), "..", "..", "frontend")
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
