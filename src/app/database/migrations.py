"""
Alembic migration runner.

Keeps schema evolution versioned while preserving the current psycopg + SQL
service layer (no ORM migration yet).
"""

import os
from pathlib import Path

from alembic import command
from alembic.config import Config

from app.utils.logger import get_logger

logger = get_logger(__name__)


def _normalize_sqlalchemy_url(db_url: str) -> str:
    """
    Normalize DB URL for SQLAlchemy + psycopg dialect.

    Supabase URLs are commonly provided as postgresql://...
    SQLAlchemy should use postgresql+psycopg://...
    """
    if db_url.startswith("postgresql://"):
        return db_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return db_url


def _escape_for_configparser(value: str) -> str:
    # Alembic Config uses configparser interpolation; raw '%' must be escaped.
    return value.replace("%", "%%")


def _repo_root() -> Path:
    # src/app/database/migrations.py -> repo root is 3 levels above "database"
    return Path(__file__).resolve().parents[3]


def run_migrations() -> None:
    """Run Alembic upgrade head using DB_URL from environment."""
    db_url = os.getenv("DB_URL")
    if not db_url:
        raise ValueError("DB_URL not found in environment.")

    root = _repo_root()
    config_path = root / "alembic.ini"
    script_location = root / "alembic"

    if not config_path.exists():
        raise FileNotFoundError(f"Alembic config not found: {config_path}")
    if not script_location.exists():
        raise FileNotFoundError(f"Alembic script location not found: {script_location}")

    cfg = Config(str(config_path))
    cfg.set_main_option("script_location", str(script_location))
    normalized = _normalize_sqlalchemy_url(db_url)
    cfg.set_main_option("sqlalchemy.url", _escape_for_configparser(normalized))

    command.upgrade(cfg, "head")
    logger.info("Database migrations applied", extra={"event": "db_migrations_applied"})
