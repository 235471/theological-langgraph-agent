"""
Theological Agent API

FastAPI backend for the multi-agent theological analysis system.
"""

import time
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Load environment variables for LangSmith and API Keys
load_dotenv()

from app.utils.logger import setup_logging, get_logger
from app.database.connection import check_db_health, close_pool
from app.controller.bible_controller import router as bible_router
from app.controller.analyze_controller import router as analyze_router
from app.controller.debug_controller import router as debug_router
from app.controller.hitl_controller import router as hitl_router

# Initialize structured logging
setup_logging()
logger = get_logger(__name__)

# Track startup time for uptime calculation
_startup_time = time.time()
_app_version = "1.1.0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown events."""
    # --- Startup ---
    logger.info(
        f"Starting Theological Agent API v{_app_version}",
        extra={"event": "startup"},
    )

    yield

    # --- Shutdown ---
    logger.info("Shutting down — closing DB pool", extra={"event": "shutdown"})
    close_pool()


app = FastAPI(
    title="Theological Agent API",
    description="API backend for the multi-agent theological analysis system.",
    version=_app_version,
    lifespan=lifespan,
)

# CORS Middleware (allow Streamlit frontend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(bible_router)
app.include_router(analyze_router)
app.include_router(debug_router)
app.include_router(hitl_router)


@app.get("/", tags=["Health"])
async def root():
    """Root endpoint."""
    return {"status": "ok", "message": "Theological Agent API is running"}


@app.get("/health", tags=["Health"])
async def health_check():
    """
    Enhanced health check with DB connectivity, uptime, and version.
    Designed for external monitoring (e.g., Render, UptimeRobot).
    """
    from datetime import datetime, timezone

    uptime_seconds = int(time.time() - _startup_time)
    db_healthy = check_db_health()

    return {
        "status": "healthy" if db_healthy else "degraded",
        "version": _app_version,
        "uptime_seconds": uptime_seconds,
        "database": "connected" if db_healthy else "disconnected",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
