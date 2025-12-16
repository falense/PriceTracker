"""
Centralized structlog configuration for PriceTracker.

This module configures structlog at Django app startup so all imported modules
use consistent logging configuration. This eliminates the need for per-task
logging setup.
"""

import contextvars
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


# Context variable to store event_dict for DatabaseLogHandler
_current_event_dict: contextvars.ContextVar[Dict[str, Any]] = contextvars.ContextVar(
    'current_event_dict', default={}
)


def save_event_dict_to_record(
    logger: logging.Logger, method_name: str, event_dict: EventDict
) -> EventDict:
    """
    Save event_dict to the LogRecord and context variable for DatabaseLogHandler.

    This processor is called twice:
    1. From structlog's processor chain (has bound context like product_id, service)
    2. From ProcessorFormatter's foreign_pre_chain (does NOT have bound context)

    We only save from the first call (when _from_structlog is NOT present)
    because that's when we have the full bound context.
    """
    # Only save if this is NOT from foreign_pre_chain (indicated by _from_structlog)
    # The first call (from structlog) won't have _from_structlog
    if '_from_structlog' not in event_dict:
        _current_event_dict.set(dict(event_dict))

    return event_dict


def get_current_event_dict() -> Dict[str, Any]:
    """Get the current event_dict from context variable storage."""
    return _current_event_dict.get()


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
        save_event_dict_to_record,  # Save context for DatabaseLogHandler
    ]

    # Environment-specific configuration
    if environment == 'development':
        # Development: use render_to_log_kwargs to pass event_dict to stdlib
        # Then ProcessorFormatter renders to console
        processors = shared_processors + [
            structlog.processors.ExceptionRenderer(),
            structlog.stdlib.render_to_log_kwargs,  # Pass event_dict to LogRecord
        ]
        renderer = structlog.dev.ConsoleRenderer(colors=True)
    else:
        # Production/Celery: JSON output for log aggregation
        processors = shared_processors + [
            structlog.processors.format_exc_info,
            structlog.stdlib.render_to_log_kwargs,  # Pass event_dict to LogRecord
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

    # Add DatabaseLogHandler for persistent log storage
    # Enable in all environments (development, production, celery) for debugging and monitoring
    try:
        from app.logging_handlers import DatabaseLogHandler
        db_handler = DatabaseLogHandler(level=logging.INFO)
        logging.getLogger().addHandler(db_handler)

        # Log that database logging is enabled
        logger = structlog.get_logger(__name__)
        logger.debug("database_log_handler_enabled", environment=environment)
    except ImportError:
        # Handler not available yet (e.g., during migrations)
        pass

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
