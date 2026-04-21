import logging
import sys

import structlog


def configure_logging(log_level: str = "INFO") -> None:
    """Configure structlog with JSON output and stdlib integration."""
    log_level_num = getattr(logging, log_level.upper(), logging.INFO)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            # add_logger_name is omitted: it requires a stdlib Logger (.name
            # attribute) but we use PrintLoggerFactory which creates PrintLogger
            # objects.  The module name is already embedded by get_logger(__name__).
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level_num),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )

    # Route stdlib logging through structlog so uvicorn/sqlalchemy logs are captured
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level_num,
    )


def get_logger(name: str) -> structlog.BoundLogger:
    return structlog.get_logger(name)
