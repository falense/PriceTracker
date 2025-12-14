"""
Admin service layer for Celery monitoring and management.
"""
from config.celery import app as celery_app
from celery.result import AsyncResult
import redis
import logging

logger = logging.getLogger('app')


class CeleryMonitorService:
    """Service for monitoring Celery workers and tasks."""

    @staticmethod
    def get_registered_tasks():
        """Get list of all registered task names from workers."""
        try:
            inspector = celery_app.control.inspect()
            registered = inspector.registered() or {}

            # Flatten all registered tasks from all workers
            all_tasks = set()
            for worker, tasks in registered.items():
                all_tasks.update(tasks)

            return list(all_tasks)
        except Exception as e:
            logger.warning(f"Error getting registered tasks: {e}")
            return []

    @staticmethod
    def get_worker_stats():
        """
        Get worker status and active/scheduled tasks.

        Returns:
            dict: Dictionary containing workers, active, scheduled, and registered tasks
        """
        try:
            inspector = celery_app.control.inspect()

            stats = {
                'workers': inspector.stats() or {},
                'active': inspector.active() or {},
                'scheduled': inspector.scheduled() or {},
                'registered': inspector.registered() or {},
            }

            logger.debug(f"Retrieved worker stats: {len(stats['workers'])} workers active")
            return stats

        except Exception as e:
            logger.error(f"Error retrieving worker stats: {e}", exc_info=True)
            return {
                'workers': {},
                'active': {},
                'scheduled': {},
                'registered': {},
                'error': str(e)
            }

    @staticmethod
    def get_recent_tasks(limit=50):
        """
        Get recent task results from Redis backend.

        Args:
            limit: Maximum number of tasks to retrieve

        Returns:
            list: List of task dictionaries with id, name, status, result, and date
        """
        try:
            import json
            from datetime import datetime

            redis_client = redis.from_url('redis://redis:6379/0')
            keys = redis_client.keys('celery-task-meta-*')

            tasks = []
            for key in keys[:limit * 2]:  # Get more keys to ensure we have enough completed tasks
                try:
                    task_id = key.decode().replace('celery-task-meta-', '')

                    # Get raw task metadata from Redis
                    raw_data = redis_client.get(key)
                    if not raw_data:
                        continue

                    # Parse the stored task metadata
                    task_data = json.loads(raw_data.decode('utf-8'))

                    # Extract task information
                    status = task_data.get('status')
                    date_done = task_data.get('date_done')

                    # Only include completed tasks
                    if not date_done:
                        continue

                    # Parse date_done
                    if isinstance(date_done, str):
                        try:
                            date_done = datetime.fromisoformat(date_done.replace('Z', '+00:00'))
                        except:
                            date_done = datetime.now()

                    # Get task name from metadata
                    task_name = task_data.get('name') or task_data.get('task')

                    # Try to infer task name from result structure
                    if not task_name:
                        result_data = task_data.get('result', {})
                        if isinstance(result_data, dict):
                            # Infer from result structure
                            if 'priority' in result_data and 'count' in result_data:
                                task_name = 'app.tasks.fetch_prices_by_priority'
                            elif 'task' in result_data:
                                task_name = result_data.get('task')

                    # Get result string
                    result = task_data.get('result', '')
                    if isinstance(result, dict):
                        # Format dict results nicely
                        if 'exc_message' in result:
                            result = result['exc_message'][:100]
                        else:
                            # Show key-value pairs
                            result = ', '.join(f"{k}: {v}" for k, v in list(result.items())[:3])[:100]
                    else:
                        result = str(result)[:100]

                    # Format display name - show full task name or mark as inferred
                    if task_name:
                        # Shorten long task names for display
                        display_name = task_name.replace('app.tasks.', '').replace('config.', '')
                    else:
                        display_name = 'unknown task'

                    tasks.append({
                        'task_id': task_id,
                        'task_name': display_name,
                        'status': status or 'UNKNOWN',
                        'result': result,
                        'date_done': date_done,
                    })
                except Exception as e:
                    logger.warning(f"Error processing task {key}: {e}")
                    continue

            # Sort by date and limit
            tasks.sort(key=lambda x: x['date_done'], reverse=True)
            logger.debug(f"Retrieved {len(tasks[:limit])} recent tasks")
            return tasks[:limit]

        except Exception as e:
            logger.error(f"Error retrieving recent tasks: {e}", exc_info=True)
            return []
