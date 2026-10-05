"""
Main FastAPI application entry point.
"""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.database import create_all_tables
from app.core.logger import app_logger
from app.api.routes_auth import router as auth_router
from app.api.routes_search import router as search_router
from app.api.routes_products import router as products_router
from app.api.routes_agent import router as agent_router
from app.api.routes_orders import router as orders_router


# ── Lifespan (startup / shutdown) ─────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown logic."""
    # ── Startup ──
    app_logger.info("=" * 60)
    app_logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    app_logger.info("=" * 60)

    # Validate required secrets — fail fast if .env is misconfigured
    settings.validate_secrets()

    # Create logs directory
    os.makedirs("logs", exist_ok=True)

    # Create DB tables
    try:
        await create_all_tables()
        app_logger.info("Database ready")
    except Exception as e:
        app_logger.error(f"Database initialization failed: {e}")

    # Pre-warm the LangGraph agent (compiles the graph)
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
            capture_output=True,
            timeout=120,
        )
        app_logger.info("Playwright browsers ready")
    except Exception as e:
        app_logger.warning(f"Playwright install skipped: {e}")

    app_logger.info("Application startup complete")
    yield

    # ── Shutdown ──
    app_logger.info("Application shutting down...")


# ── App Instance ──────────────────────────────────────────────────────────────

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "AI Autonomous Shopping & Price Comparison Agent. "
        "Searches Amazon, Flipkart, Meesho, Myntra, Shopsy, Snapdeal and more."
    ),
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)


# ── Middleware ────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # allow all origins for local dev
    allow_credentials=False,      # must be False when allow_origins=["*"]
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Global Exception Handler ──────────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    app_logger.error(f"Unhandled exception: {exc} | Path: {request.url.path}")
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal server error occurred. Please try again."},
    )


# ── Routes ────────────────────────────────────────────────────────────────────

app.include_router(auth_router, prefix="/api")
app.include_router(search_router, prefix="/api")
app.include_router(products_router, prefix="/api")
app.include_router(agent_router, prefix="/api")
app.include_router(orders_router, prefix="/api")


# ── Health Check ──────────────────────────────────────────────────────────────

@app.get("/api/health", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }


@app.get("/api/platforms", tags=["Info"])
async def get_supported_platforms():
    """List all supported shopping platforms."""
    return {
        "platforms": [
            {"id": "amazon",   "name": "Amazon India",  "url": "https://www.amazon.in",    "category": "all"},
            {"id": "flipkart", "name": "Flipkart",       "url": "https://www.flipkart.com", "category": "all"},
            {"id": "meesho",   "name": "Meesho",         "url": "https://www.meesho.com",   "category": "fashion,home"},
            {"id": "myntra",   "name": "Myntra",         "url": "https://www.myntra.com",   "category": "fashion"},
            {"id": "shopsy",   "name": "Shopsy",         "url": "https://www.shopsy.in",    "category": "all"},
            {"id": "snapdeal", "name": "Snapdeal",       "url": "https://www.snapdeal.com", "category": "all"},
        ]
    }


# ── Serve Frontend (optional - if running fullstack) ─────────────────────────

frontend_path = os.path.join(os.path.dirname(__file__), "..", "..", "frontend")
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
