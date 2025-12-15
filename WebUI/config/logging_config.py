"""
Centralized structlog configuration for PriceTracker.

This module configures structlog at Django app startup so all imported modules
use consistent logging configuration. This eliminates the need for per-task
logging setup.
"""

import logging
import os
import sys
from typing import Any, Dict

import structlog
from structlog.types import EventDict, Processor


def add_app_context(logger: logging.Logger, method_name: str, event_dict: EventDict) -> EventDict:
    """Add application context to log events."""
    event_dict["app"] = "pricetracker"
    return event_dict


def add_request_id(logger: logging.Logger, method_name: str, event_dict: EventDict) -> EventDict:
    """
    Add request ID from Django request context if available.

    This processor can be extended to extract request_id from Django's
    request context once middleware is implemented.
    """
    # TODO: Extract request_id from Django request context when middleware is added
    return event_dict


def configure_structlog(environment: str = None) -> None:
    """
    Configure structlog with environment-appropriate settings.

    Args:
        environment: One of 'development', 'production', or 'celery'.
                    If None, auto-detects based on environment variables.
    """
    if environment is None:
        # Auto-detect environment
        if os.getenv('CELERY_WORKER_NAME'):
            environment = 'celery'
        elif os.getenv('DEBUG', 'True') == 'True':
            environment = 'development'
        else:
            environment = 'production'

    # Common processors for all environments
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        add_app_context,
        add_request_id,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
    ]

    # Environment-specific configuration
    if environment == 'development':
        # Development: colorful console output with key-value pairs
        processors = shared_processors + [
            structlog.processors.ExceptionRenderer(),
            structlog.dev.ConsoleRenderer(colors=True)
        ]
        renderer = structlog.dev.ConsoleRenderer(colors=True)
    else:
        # Production/Celery: JSON output for log aggregation
        processors = shared_processors + [
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer()
        ]
        renderer = structlog.processors.JSONRenderer()

    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Also configure standard library logging to use structlog
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.INFO,
    )

    # Redirect standard library logging through structlog
    logging.getLogger().handlers = []
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(structlog.stdlib.ProcessorFormatter(
        processor=renderer,
        foreign_pre_chain=shared_processors,
    ))
    logging.getLogger().addHandler(handler)

    # Set log levels
    if environment == 'development':
        logging.getLogger().setLevel(logging.DEBUG)
        logging.getLogger('app').setLevel(logging.DEBUG)
    else:
        logging.getLogger().setLevel(logging.INFO)
        logging.getLogger('app').setLevel(logging.INFO)

    # Reduce noise from third-party libraries
    logging.getLogger('django.server').setLevel(logging.WARNING)
    logging.getLogger('django.request').setLevel(logging.WARNING)
    logging.getLogger('celery').setLevel(logging.INFO)

    # Log configuration completion
    logger = structlog.get_logger(__name__)
    logger.info(
        "structlog_configured",
        environment=environment,
        renderer="console" if environment == 'development' else "json"
    )


def get_logger(name: str = None) -> structlog.BoundLogger:
    """
    Get a configured structlog logger.

    Args:
        name: Optional logger name (typically __name__)

    Returns:
        Configured structlog BoundLogger
    """
    return structlog.get_logger(name)
