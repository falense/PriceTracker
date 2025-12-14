"""Storage layer for price history and fetch logs."""

import json
import re
import sqlite3
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional, Any
from urllib.parse import urljoin, urlparse

import structlog

from .models import ExtractionResult, Product, ValidationResult

logger = structlog.get_logger()


class PriceStorage:
    """Store product prices and fetch history in shared SQLite database."""

    def __init__(self, db_path: str = "../db.sqlite3"):
        """
        Initialize storage with database path.

        Args:
            db_path: Path to shared SQLite database (created by Django)
        """
        self.db_path = Path(db_path)
        logger.info("storage_initialized", db_path=str(self.db_path))

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        if not self.db_path.exists():
            logger.warning("database_not_found", db_path=str(self.db_path))
            raise FileNotFoundError(
                f"Database not found at {self.db_path}. "
                "Run Django migrations first: python WebUI/manage.py migrate"
            )

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_product_by_id(self, product_id: str) -> Optional[Product]:
        """
        Get a specific product by ID.

        Args:
            product_id: Product UUID (with or without hyphens)

        Returns:
            Product object or None if not found
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # SQLite stores UUIDs without hyphens, so remove them for the query
        product_id_clean = product_id.replace('-', '')

        query = """
            SELECT id, url, domain, name, current_price, currency,
                   check_interval, last_checked, active, priority
            FROM app_product
            WHERE id = ?
            AND active = 1
        """

        try:
            cursor.execute(query, (product_id_clean,))
            row = cursor.fetchone()

            if not row:
                logger.warning("product_not_found", product_id=product_id)
                return None

            product = Product(
                product_id=row["id"],
                url=row["url"],
                domain=row["domain"],
                name=row["name"],
                current_price=Decimal(str(row["current_price"]))
                if row["current_price"]
                else None,
                currency=row["currency"] or "USD",
                check_interval=row["check_interval"] or 3600,
                last_checked=datetime.fromisoformat(row["last_checked"])
                if row["last_checked"]
                else None,
                active=bool(row["active"]),
                priority=row["priority"] or "normal",
            )

            logger.info("product_loaded", product_id=product_id)
            return product

        finally:
            conn.close()

    def get_products_to_fetch(self) -> List[Product]:
        """
        Get products due for fetching based on check_interval.

        Returns:
            List of Product objects that need price checking
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        query = """
            SELECT id, url, domain, name, current_price, currency,
                   check_interval, last_checked, active, priority
            FROM app_product
            WHERE active = 1
            AND (
                last_checked IS NULL
                OR datetime(last_checked, '+' || check_interval || ' seconds') <= datetime('now')
            )
            ORDER BY priority DESC, last_checked ASC NULLS FIRST
        """

        try:
            cursor.execute(query)
            rows = cursor.fetchall()

            products = []
            for row in rows:
                products.append(
                    Product(
                        product_id=row["id"],
                        url=row["url"],
                        domain=row["domain"],
                        name=row["name"],
                        current_price=Decimal(str(row["current_price"]))
                        if row["current_price"]
                        else None,
                        currency=row["currency"] or "USD",
                        check_interval=row["check_interval"] or 3600,
                        last_checked=datetime.fromisoformat(row["last_checked"])
                        if row["last_checked"]
                        else None,
                        active=bool(row["active"]),
                        priority=row["priority"] or "normal",
                    )
                )

            logger.info("products_loaded", count=len(products))
            return products

        finally:
            conn.close()

    def get_products_without_images(
        self, limit: Optional[int] = None
    ) -> List[Product]:
        """
        Get active products where image_url is NULL.

        Args:
            limit: Maximum number of products to return (None for all)

        Returns:
            List of Product objects without images
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        query = """
            SELECT id, url, domain, name, current_price, currency,
                   check_interval, last_checked, active, priority
            FROM app_product
            WHERE active = 1
            AND (image_url IS NULL OR image_url = '')
            ORDER BY priority DESC, created_at DESC
        """

        if limit:
            query += f" LIMIT {int(limit)}"

        try:
            cursor.execute(query)
            rows = cursor.fetchall()

            products = []
            for row in rows:
                products.append(
                    Product(
                        product_id=row["id"],
                        url=row["url"],
                        domain=row["domain"],
                        name=row["name"],
                        current_price=Decimal(str(row["current_price"]))
                        if row["current_price"]
                        else None,
                        currency=row["currency"] or "USD",
                        check_interval=row["check_interval"] or 3600,
                        last_checked=datetime.fromisoformat(row["last_checked"])
                        if row["last_checked"]
                        else None,
                        active=bool(row["active"]),
                        priority=row["priority"] or "normal",
                    )
                )

            logger.info("products_without_images_loaded", count=len(products))
            return products

        finally:
            conn.close()

    def update_product_image(self, product_id: str, image_url: str) -> None:
        """
        Update only the image_url field for a product.

        Args:
            product_id: Product UUID
            image_url: Image URL to set
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                UPDATE app_product
                SET image_url = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    image_url,
                    datetime.utcnow().isoformat(),
                    product_id,
                ),
            )

            conn.commit()
            logger.info(
                "product_image_updated",
                product_id=product_id,
                image_url=image_url,
            )

        except Exception as e:
            conn.rollback()
            logger.error(
                "product_image_update_failed",
                product_id=product_id,
                error=str(e),
            )
            raise
        finally:
            conn.close()

    def save_price(
        self,
        product_id: str,
        extraction: ExtractionResult,
        validation: ValidationResult,
        product_url: Optional[str] = None,
    ) -> None:
        """
        Save extracted price to history.

        Args:
            product_id: Product UUID
            extraction: Extracted data
            validation: Validation result
            product_url: Product URL for normalizing relative image URLs
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Extract numeric price value
            price_value = None
            currency = "USD"

            if extraction.price and extraction.price.value:
                match = re.search(r"(\d+\.?\d*)", extraction.price.value)
                if match:
                    price_value = float(match.group(1))

            # Extract availability
            available = True
            if extraction.availability and extraction.availability.value:
                avail_text = extraction.availability.value.lower()
                available = "stock" in avail_text or "available" in avail_text

            # Extract and normalize image URL
            image_url = None
            if extraction.image and extraction.image.value:
                image_url = extraction.image.value.strip()
                # Normalize relative URLs to absolute
                if image_url and not image_url.startswith(('http://', 'https://')):
                    if product_url:
                        parsed = urlparse(product_url)
                        base_url = f"{parsed.scheme}://{parsed.netloc}"
                        image_url = urljoin(base_url, image_url)
                    else:
                        logger.warning(
                            "relative_image_url_without_base",
                            product_id=product_id,
                            image_url=image_url,
                        )
                        image_url = None  # Can't normalize without base URL

            # Store in price_history table
            cursor.execute(
                """
                INSERT INTO app_pricehistory
                (product_id, price, currency, available, extracted_data,
                 confidence, recorded_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    product_id,
                    price_value,
                    currency,
                    available,
                    json.dumps(extraction.model_dump(), default=str),
                    validation.confidence,
                    datetime.utcnow().isoformat(),
                ),
            )

            # Update product's current_price, availability, image_url, and last_checked
            cursor.execute(
                """
                UPDATE app_product
                SET current_price = ?,
                    available = ?,
                    image_url = CASE
                        WHEN ? IS NOT NULL THEN ?
                        ELSE image_url
                    END,
                    last_checked = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    price_value,
                    available,
                    image_url,  # For WHEN condition
                    image_url,  # For THEN clause
                    datetime.utcnow().isoformat(),
                    datetime.utcnow().isoformat(),
                    product_id,
                ),
            )

            conn.commit()
            logger.info(
                "price_saved",
                product_id=product_id,
                price=price_value,
                confidence=validation.confidence,
                image_extracted=image_url is not None,
            )

        except Exception as e:
            conn.rollback()
            logger.error("price_save_failed", product_id=product_id, error=str(e))
            raise
        finally:
            conn.close()

    def log_fetch(
        self,
        product_id: str,
        success: bool,
        extraction_method: Optional[str] = None,
        errors: Optional[List[str]] = None,
        warnings: Optional[List[str]] = None,
        duration_ms: Optional[int] = None,
    ) -> None:
        """
        Log fetch attempt for debugging and monitoring.

        Args:
            product_id: Product UUID
            success: Whether fetch succeeded
            extraction_method: Method that worked (css, xpath, jsonld, meta)
            errors: List of errors encountered
            warnings: List of warnings
            duration_ms: Time taken in milliseconds
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                INSERT INTO app_fetchlog
                (product_id, success, extraction_method, errors, warnings,
                 duration_ms, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    product_id,
                    success,
                    extraction_method,
                    json.dumps(errors or []),
                    json.dumps(warnings or []),
                    duration_ms,
                    datetime.utcnow().isoformat(),
                ),
            )

            conn.commit()
            logger.debug("fetch_logged", product_id=product_id, success=success)

        except Exception as e:
            conn.rollback()
            logger.error("fetch_log_failed", product_id=product_id, error=str(e))
        finally:
            conn.close()

    def get_latest_price(self, product_id: str) -> Optional[Dict[str, Any]]:
        """
        Get most recent price for product.

        Args:
            product_id: Product UUID

        Returns:
            Dict with price data or None if no history
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                SELECT price, currency, available, extracted_data,
                       confidence, recorded_at
                FROM app_pricehistory
                WHERE product_id = ?
                ORDER BY recorded_at DESC
                LIMIT 1
                """,
                (product_id,),
            )

            row = cursor.fetchone()
            if row:
                return {
                    "price": row["price"],
                    "currency": row["currency"],
                    "available": bool(row["available"]),
                    "extracted_data": json.loads(row["extracted_data"]),
                    "confidence": row["confidence"],
                    "recorded_at": row["recorded_at"],
                }

            return None

        finally:
            conn.close()

    def get_pattern_success_stats(self, domain: str) -> Dict[str, Any]:
        """
        Get pattern success statistics for a domain.

        Args:
            domain: Domain name (e.g., "amazon.com")

        Returns:
            Dict with success_rate, total_attempts, successful_attempts
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                SELECT success_rate, total_attempts, successful_attempts
                FROM app_pattern
                WHERE domain = ?
                """,
                (domain,),
            )

            row = cursor.fetchone()
            if row:
                return {
                    "success_rate": row["success_rate"],
                    "total_attempts": row["total_attempts"],
                    "successful_attempts": row["successful_attempts"],
                }

            return {"success_rate": 0.0, "total_attempts": 0, "successful_attempts": 0}

        finally:
            conn.close()

    def update_pattern_stats(self, domain: str, success: bool) -> None:
        """
        Update pattern usage statistics.

        Args:
            domain: Domain name
            success: Whether pattern extraction succeeded
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                UPDATE app_pattern
                SET total_attempts = total_attempts + 1,
                    successful_attempts = successful_attempts + ?,
                    success_rate = CAST(successful_attempts + ? AS REAL) /
                                   (total_attempts + 1),
                    updated_at = ?
                WHERE domain = ?
                """,
                (1 if success else 0, 1 if success else 0, datetime.utcnow().isoformat(), domain),
            )

            conn.commit()
            logger.debug("pattern_stats_updated", domain=domain, success=success)

        except Exception as e:
            conn.rollback()
            logger.error("pattern_stats_update_failed", domain=domain, error=str(e))
        finally:
            conn.close()
