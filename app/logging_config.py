"""
Structured logging configuration using structlog.
- JSON rendering in production (LOG_FORMAT=json, the default)
- Pretty console rendering in dev/test (LOG_FORMAT=pretty or TESTING=1)
- CallsiteParameterAdder uses CallsiteParameter.MODULE / FUNC_NAME enum members
  from structlog.processors (verified live: structlog 25.3.0)
"""
import os
import logging
import structlog
from structlog.processors import CallsiteParameter, CallsiteParameterAdder


def _is_pretty() -> bool:
    return os.getenv("LOG_FORMAT", "json").lower() == "pretty" or os.getenv("TESTING") == "1"


def configure_logging() -> None:
    """
    Configure structlog once at application startup.
    Must be called before any get_logger() usage.
    """
    shared_processors = [
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        CallsiteParameterAdder([CallsiteParameter.MODULE, CallsiteParameter.FUNC_NAME]),
    ]

    if _is_pretty():
        renderer = structlog.dev.ConsoleRenderer()
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=shared_processors + [renderer],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Suppress stdlib root logger noise (structlog handles output)
    logging.basicConfig(level=logging.WARNING, handlers=[logging.NullHandler()])


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a bound structlog logger for the given module name."""
    return structlog.get_logger(name)
