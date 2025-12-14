"""Storage tools for persisting extraction patterns."""

from claude_agent_sdk import tool
from typing import Any, Dict
import json
import sqlite3
from pathlib import Path
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Database path - relative to project root
DB_PATH = Path(__file__).parent.parent.parent / "patterns.db"


def _init_database():
    """Initialize the database schema if it doesn't exist."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS patterns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            domain TEXT UNIQUE NOT NULL,
            pattern_json TEXT NOT NULL,
            confidence REAL DEFAULT 0.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            validation_count INTEGER DEFAULT 0,
            last_validated TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pattern_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            domain TEXT NOT NULL,
            pattern_json TEXT NOT NULL,
            confidence REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            change_reason TEXT
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_domain ON patterns(domain)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_confidence ON patterns(confidence)
    """)

    conn.commit()
    conn.close()
    logger.info(f"Database initialized at {DB_PATH}")


# Initialize database on module load
_init_database()


@tool(
    "save_pattern",
    "Save or update an extraction pattern in the database",
    {"domain": str, "patterns": dict, "confidence": float}
)
async def save_pattern_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Save extraction patterns to SQLite database.

    Args:
        domain: The store domain (e.g., "amazon.com")
        patterns: Dictionary of extraction patterns
        confidence: Overall confidence score (0.0-1.0)

    Returns:
        Dictionary with success status and message
    """
    domain = args["domain"]
    patterns = args["patterns"]
    confidence = args.get("confidence", 0.0)

    logger.info(f"Saving patterns for domain: {domain} (confidence={confidence})")

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Check if pattern already exists
        cursor.execute("SELECT pattern_json FROM patterns WHERE domain = ?", (domain,))
        existing = cursor.fetchone()

        pattern_json = json.dumps(patterns, indent=2)

        if existing:
            # Archive old pattern to history
            old_pattern = existing[0]
            cursor.execute("""
                INSERT INTO pattern_history (domain, pattern_json, confidence, change_reason)
                VALUES (?, ?, ?, ?)
            """, (domain, old_pattern, confidence, "Pattern updated"))

            # Update existing pattern
            cursor.execute("""
                UPDATE patterns
                SET pattern_json = ?, confidence = ?, updated_at = CURRENT_TIMESTAMP
                WHERE domain = ?
            """, (pattern_json, confidence, domain))

            message = f"Updated existing pattern for {domain}"
        else:
            # Insert new pattern
            cursor.execute("""
                INSERT INTO patterns (domain, pattern_json, confidence)
                VALUES (?, ?, ?)
            """, (domain, pattern_json, confidence))

            message = f"Saved new pattern for {domain}"

        conn.commit()
        conn.close()

        logger.info(message)

        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "success": True,
                    "message": message,
                    "domain": domain,
                    "confidence": confidence
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
    Load extraction patterns from SQLite database.

    Args:
        domain: The store domain to load patterns for

    Returns:
        Dictionary with patterns or error message
    """
    domain = args["domain"]

    logger.info(f"Loading patterns for domain: {domain}")

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT pattern_json, confidence, created_at, updated_at, validation_count
            FROM patterns
            WHERE domain = ?
        """, (domain,))

        row = cursor.fetchone()
        conn.close()

        if row:
            patterns = json.loads(row[0])
            result = {
                "success": True,
                "domain": domain,
                "patterns": patterns,
                "confidence": row[1],
                "created_at": row[2],
                "updated_at": row[3],
                "validation_count": row[4]
            }

            logger.info(f"Loaded patterns for {domain} (confidence={row[1]})")

            return {
                "content": [{
                    "type": "text",
                    "text": json.dumps(result, indent=2)
                }]
            }
        else:
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
    logger.info("Listing all patterns")

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT domain, confidence, created_at, updated_at, validation_count
            FROM patterns
            ORDER BY confidence DESC, updated_at DESC
        """)

        rows = cursor.fetchall()
        conn.close()

        patterns = []
        for row in rows:
            patterns.append({
                "domain": row[0],
                "confidence": row[1],
                "created_at": row[2],
                "updated_at": row[3],
                "validation_count": row[4]
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
    domain = args["domain"]

    logger.info(f"Deleting patterns for domain: {domain}")

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Archive to history before deleting
        cursor.execute("SELECT pattern_json, confidence FROM patterns WHERE domain = ?", (domain,))
        row = cursor.fetchone()

        if row:
            cursor.execute("""
                INSERT INTO pattern_history (domain, pattern_json, confidence, change_reason)
                VALUES (?, ?, ?, ?)
            """, (domain, row[0], row[1], "Pattern deleted"))

            cursor.execute("DELETE FROM patterns WHERE domain = ?", (domain,))
            conn.commit()

            message = f"Deleted pattern for {domain}"
            success = True
        else:
            message = f"No pattern found for {domain}"
            success = False

        conn.close()

        logger.info(message)

        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "success": success,
                    "message": message,
                    "domain": domain
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
