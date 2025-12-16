"""Load extraction patterns from storage."""

import json
import sqlite3
from pathlib import Path
from typing import Optional

import structlog

from .models import ExtractionPattern, FieldPattern, PatternSelector

logger = structlog.get_logger(__name__).bind(service='fetcher')


class PatternLoader:
    """Load extraction patterns for products from shared database."""

    def __init__(self, db_path: str = "../db.sqlite3"):
        """
        Initialize pattern loader.

        Args:
            db_path: Path to shared SQLite database (created by Django)
        """
        self.db_path = Path(db_path)
        logger.info("pattern_loader_initialized", db_path=str(self.db_path))

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        if not self.db_path.exists():
            logger.error("database_not_found", db_path=str(self.db_path))
            raise FileNotFoundError(
                f"Database not found at {self.db_path}. "
                "Run Django migrations first: python WebUI/manage.py migrate"
            )

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def load_pattern(self, domain: str) -> Optional[ExtractionPattern]:
        """
        Load pattern for a specific domain.

        Args:
            domain: Domain name (e.g., "amazon.com" or "www.amazon.com")

        Returns:
            ExtractionPattern object or None if not found
        """
        # Normalize domain by removing www prefix for consistency
        normalized_domain = domain.replace('www.', '').lower()

        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                SELECT domain, pattern_json, created_at, updated_at
                FROM app_pattern
                WHERE domain = ?
                """,
                (normalized_domain,),
            )

            row = cursor.fetchone()

            if not row:
                logger.warning("pattern_not_found", domain=domain, normalized_domain=normalized_domain)
                return None

            pattern_data = json.loads(row["pattern_json"])

            # Parse pattern structure
            patterns = {}
            for field_name, field_config in pattern_data.get("patterns", {}).items():
                # Parse primary selector
                primary_config = field_config["primary"]
                primary = PatternSelector(
                    type=primary_config["type"],
                    selector=primary_config["selector"],
                    attribute=primary_config.get("attribute"),
                    confidence=primary_config.get("confidence", 1.0),
                )

                # Parse fallback selectors
                fallbacks = []
                for fallback_config in field_config.get("fallbacks", []):
                    fallbacks.append(
                        PatternSelector(
                            type=fallback_config["type"],
                            selector=fallback_config["selector"],
                            attribute=fallback_config.get("attribute"),
                            confidence=fallback_config.get("confidence", 0.5),
                        )
                    )

                patterns[field_name] = FieldPattern(primary=primary, fallbacks=fallbacks)

            pattern = ExtractionPattern(
                store_domain=row["domain"],
                patterns=patterns,
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )

            logger.info("pattern_loaded", domain=domain, fields=list(patterns.keys()))
            return pattern

        except Exception as e:
            logger.error("pattern_load_failed", domain=domain, error=str(e))
            raise
        finally:
            conn.close()

    def pattern_exists(self, domain: str) -> bool:
        """
        Check if pattern exists for domain.

        Args:
            domain: Domain name

        Returns:
            True if pattern exists, False otherwise
        """
        # Normalize domain by removing www prefix for consistency
        normalized_domain = domain.replace('www.', '').lower()

        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                SELECT COUNT(*) as count
                FROM app_pattern
                WHERE domain = ?
                """,
                (normalized_domain,),
            )

            row = cursor.fetchone()
            exists = row["count"] > 0
            logger.debug("pattern_existence_checked", domain=domain, normalized_domain=normalized_domain, exists=exists)
            return exists

        finally:
            conn.close()

    def get_all_domains(self) -> list[str]:
        """
        Get list of all domains with patterns.

        Returns:
            List of domain names
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT domain FROM app_pattern ORDER BY domain")
            domains = [row["domain"] for row in cursor.fetchall()]
            logger.info("domains_loaded", count=len(domains))
            return domains

        finally:
            conn.close()
