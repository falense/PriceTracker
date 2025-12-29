"""
Admin views package for PriceTracker WebUI.

Contains views restricted to staff users for system administration,
monitoring, and user management.
"""

from .dashboard import admin_dashboard
from .logs import (
    admin_logs,
    operation_log_analytics,
    operation_log_health,
    task_timeline,
)
from .patterns import (
    patterns_status,
)
from .flags import (
    admin_flags_list,
    resolve_admin_flag,
)
from .users import (
    admin_users_list,
    admin_update_user_tier,
    admin_user_detail,
    admin_delete_user,
)

__all__ = [
    'admin_dashboard',
    'admin_logs',
    'operation_log_analytics',
    'operation_log_health',
    'task_timeline',
    'patterns_status',
    'admin_flags_list',
    'resolve_admin_flag',
    'admin_users_list',
    'admin_update_user_tier',
    'admin_user_detail',
    'admin_delete_user',
]
