"""
Logging Configuration — Structured logging with structlog fallback to stdlib.

Respects LOG_LEVEL env var (default INFO) and LOG_FORMAT env var (json for JSON output).
"""

from __future__ import annotations

import logging
import os
import sys

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
LOG_FORMAT = os.environ.get("LOG_FORMAT", "console")  # "console" or "json"

try:
    import structlog

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer()
            if LOG_FORMAT != "json"
            else structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, LOG_LEVEL, logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    _USE_STRUCTLOG = True
except ImportError:
    _USE_STRUCTLOG = False

    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr,
    )


def get_logger(name: str):
    """Get a logger instance. Returns structlog BoundLogger or stdlib Logger."""
    if _USE_STRUCTLOG:
        import structlog

        return structlog.get_logger(name)
    return logging.getLogger(name)
