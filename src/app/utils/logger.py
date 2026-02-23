"""
Centralized Structured Logging

JSON-formatted logs with run_id correlation.
Strategic logging — node boundaries, cache events, HITL, warnings only.
"""

import logging
import json
import sys
from datetime import datetime, timezone


class JSONFormatter(logging.Formatter):
    """JSON log formatter for structured, machine-parseable output."""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Attach extra fields (run_id, node, tokens, etc.)
        for key in (
            "run_id",
            "node",
            "model",
            "prompt_commit_hash",
            "tokens",
            "duration_ms",
            "risk_level",
            "alerts",
            "cache_key",
            "event",
        ):
            value = getattr(record, key, None)
            if value is not None:
                log_data[key] = value

        if record.exc_info and record.exc_info[0] is not None:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, ensure_ascii=False)


def setup_logging(level: int = logging.INFO) -> None:
    """
    Configure root logger with JSON formatter.
    Call once at application startup.
    """
    root = logging.getLogger()

    # Avoid duplicate handlers on hot reload
    if any(
        isinstance(h, logging.StreamHandler) and isinstance(h.formatter, JSONFormatter)
        for h in root.handlers
    ):
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())

    root.setLevel(level)
    root.addHandler(handler)

    # Quiet down noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("google").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a named logger instance."""
    return logging.getLogger(name)
