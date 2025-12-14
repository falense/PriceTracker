"""Storage tools for persisting extraction patterns to Django database."""

from claude_agent_sdk import tool
from typing import Any, Dict
import json
import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# Setup Django
DJANGO_PATH = Path(__file__).parent.parent.parent.parent / "WebUI"
sys.path.insert(0, str(DJANGO_PATH))

# Configure Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

try:
    import django
    django.setup()

    # Import Django models after setup
    from app.models import Pattern
    from django.utils import timezone
    from django.db import transaction

    logger.info("Django ORM initialized successfully")
    DJANGO_AVAILABLE = True
except Exception as e:
    logger.error(f"Failed to initialize Django ORM: {e}")
    logger.warning("Storage tools will not function correctly without Django")
    DJANGO_AVAILABLE = False


@tool(
    "save_pattern",
    "Save or update an extraction pattern in the database",
    {"domain": str, "patterns": dict, "confidence": float}
)
async def save_pattern_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Save extraction patterns to Django database.

    Args:
        domain: The store domain (e.g., "amazon.com")
        patterns: Dictionary of extraction patterns
        confidence: Overall confidence score (0.0-1.0)

    Returns:
        Dictionary with success status and message
    """
    if not DJANGO_AVAILABLE:
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "success": False,
                    "error": "Django ORM not available"
                }, indent=2)
            }],
            "isError": True
        }

    domain = args["domain"]
    patterns = args["patterns"]
    confidence = args.get("confidence", 0.0)

    logger.info(f"Saving patterns for domain: {domain} (confidence={confidence})")

    try:
        # Store confidence in metadata
        pattern_data = {
            "patterns": patterns,
            "metadata": {
                "confidence_score": confidence,
                "generated_at": timezone.now().isoformat()
            }
        }

        with transaction.atomic():
            pattern_obj, created = Pattern.objects.update_or_create(
                domain=domain,
                defaults={
                    'pattern_json': pattern_data,
                    'last_validated': timezone.now()
                }
            )

        action = "created" if created else "updated"
        message = f"Successfully {action} pattern for {domain} (ID: {pattern_obj.id})"

        logger.info(message)

        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "success": True,
                    "message": message,
                    "domain": domain,
                    "pattern_id": pattern_obj.id,
                    "confidence": confidence,
                    "created": created
                }, indent=2)
            }]
        }

    except Exception as e:
        logger.error(f"Error saving pattern for {domain}: {e}")
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "success": False,
                    "error": str(e),
                    "domain": domain
                }, indent=2)
            }],
            "isError": True
        }


@tool(
    "load_pattern",
    "Load an extraction pattern from the database",
    {"domain": str}
)
async def load_pattern_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Load extraction patterns from Django database.

    Args:
        domain: The store domain to load patterns for

    Returns:
        Dictionary with patterns or error message
    """
    if not DJANGO_AVAILABLE:
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "success": False,
                    "error": "Django ORM not available"
                }, indent=2)
            }],
            "isError": True
        }

    domain = args["domain"]

    logger.info(f"Loading patterns for domain: {domain}")

    try:
        pattern_obj = Pattern.objects.get(domain=domain)

        # Extract data
        pattern_data = pattern_obj.pattern_json
        confidence = pattern_data.get("metadata", {}).get("confidence_score", 0.0)
        patterns = pattern_data.get("patterns", pattern_data)

        result = {
            "success": True,
            "domain": domain,
            "patterns": patterns,
            "confidence": confidence,
            "success_rate": pattern_obj.success_rate,
            "total_attempts": pattern_obj.total_attempts,
            "successful_attempts": pattern_obj.successful_attempts,
            "created_at": pattern_obj.created_at.isoformat(),
            "updated_at": pattern_obj.updated_at.isoformat(),
            "last_validated": pattern_obj.last_validated.isoformat() if pattern_obj.last_validated else None
        }

        logger.info(f"Loaded patterns for {domain} (success_rate={pattern_obj.success_rate:.2f})")

        return {
            "content": [{
                "type": "text",
                "text": json.dumps(result, indent=2)
            }]
        }

    except Pattern.DoesNotExist:
        logger.info(f"No patterns found for domain: {domain}")

        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "success": False,
                    "message": f"No patterns found for domain: {domain}",
                    "domain": domain
                }, indent=2)
            }]
        }

    except Exception as e:
        logger.error(f"Error loading pattern for {domain}: {e}")
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "success": False,
                    "error": str(e),
                    "domain": domain
                }, indent=2)
            }],
            "isError": True
        }


@tool(
    "list_patterns",
    "List all stored extraction patterns",
    {}
)
async def list_patterns_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    List all stored patterns in the database.

    Returns:
        Dictionary with list of patterns
    """
    if not DJANGO_AVAILABLE:
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "success": False,
                    "error": "Django ORM not available"
                }, indent=2)
            }],
            "isError": True
        }

    logger.info("Listing all patterns")

    try:
        pattern_objs = Pattern.objects.all().order_by('-success_rate', '-updated_at')

        patterns = []
        for pattern_obj in pattern_objs:
            # Extract confidence from metadata if available
            confidence = 0.0
            if isinstance(pattern_obj.pattern_json, dict):
                confidence = pattern_obj.pattern_json.get("metadata", {}).get("confidence_score", 0.0)

            patterns.append({
                "domain": pattern_obj.domain,
                "confidence": confidence,
                "success_rate": pattern_obj.success_rate,
                "total_attempts": pattern_obj.total_attempts,
                "successful_attempts": pattern_obj.successful_attempts,
                "created_at": pattern_obj.created_at.isoformat(),
                "updated_at": pattern_obj.updated_at.isoformat(),
                "last_validated": pattern_obj.last_validated.isoformat() if pattern_obj.last_validated else None,
                "is_healthy": pattern_obj.is_healthy
            })

        logger.info(f"Found {len(patterns)} stored patterns")

        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "success": True,
                    "count": len(patterns),
                    "patterns": patterns
                }, indent=2)
            }]
        }

    except Exception as e:
        logger.error(f"Error listing patterns: {e}")
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "success": False,
                    "error": str(e)
                }, indent=2)
            }],
            "isError": True
        }


@tool(
    "delete_pattern",
    "Delete an extraction pattern from the database",
    {"domain": str}
)
async def delete_pattern_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Delete a pattern from the database.

    Args:
        domain: The store domain to delete patterns for

    Returns:
        Dictionary with success status
    """
    if not DJANGO_AVAILABLE:
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "success": False,
                    "error": "Django ORM not available"
                }, indent=2)
            }],
            "isError": True
        }

    domain = args["domain"]

    logger.info(f"Deleting patterns for domain: {domain}")

    try:
        with transaction.atomic():
            deleted_count, _ = Pattern.objects.filter(domain=domain).delete()

        if deleted_count > 0:
            message = f"Deleted pattern for {domain}"
            success = True
        else:
            message = f"No pattern found for {domain}"
            success = False

        logger.info(message)

        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "success": success,
                    "message": message,
                    "domain": domain,
                    "deleted_count": deleted_count
                }, indent=2)
            }]
        }

    except Exception as e:
        logger.error(f"Error deleting pattern for {domain}: {e}")
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "success": False,
                    "error": str(e),
                    "domain": domain
                }, indent=2)
            }],
            "isError": True
        }


@tool(
    "update_pattern_stats",
    "Update pattern success statistics after usage",
    {"domain": str, "success": bool}
)
async def update_pattern_stats_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update pattern usage statistics.

    Args:
        domain: The store domain
        success: Whether the extraction was successful

    Returns:
        Dictionary with updated stats
    """
    if not DJANGO_AVAILABLE:
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "success": False,
                    "error": "Django ORM not available"
                }, indent=2)
            }],
            "isError": True
        }

    domain = args["domain"]
    success = args["success"]

    logger.info(f"Updating pattern stats for {domain}: success={success}")

    try:
        pattern_obj = Pattern.objects.get(domain=domain)
        pattern_obj.record_attempt(success=success)

        message = f"Updated stats for {domain}: {pattern_obj.success_rate:.1%} success rate"
        logger.info(message)

        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "success": True,
                    "message": message,
                    "domain": domain,
                    "success_rate": pattern_obj.success_rate,
                    "total_attempts": pattern_obj.total_attempts,
                    "successful_attempts": pattern_obj.successful_attempts,
                    "is_healthy": pattern_obj.is_healthy
                }, indent=2)
            }]
        }

    except Pattern.DoesNotExist:
        message = f"No pattern found for {domain}"
        logger.warning(message)

        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "success": False,
                    "message": message,
                    "domain": domain
                }, indent=2)
            }]
        }

    except Exception as e:
        logger.error(f"Error updating pattern stats for {domain}: {e}")
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "success": False,
                    "error": str(e),
                    "domain": domain
                }, indent=2)
            }],
            "isError": True
        }
