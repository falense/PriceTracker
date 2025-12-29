"""
Shared view helpers for PriceTracker WebUI.

Contains utility functions used across multiple views to reduce code duplication.
"""

from .operation_logs import build_operation_log_context

__all__ = [
    'build_operation_log_context',
]
