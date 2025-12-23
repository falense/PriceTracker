"""Storage layer for price history and fetch logs."""

import html
import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

import structlog

from .models import ExtractionResult, Product, ValidationResult
from .git_utils import get_current_commit_hash, get_commit_info

logger = structlog.get_logger(__name__).bind(service="fetcher")


def format_datetime_for_django_sqlite(dt: datetime = None) -> str:
    """
    Format datetime for Django SQLite compatibility.

    Django's SQLite backend converts timezone-aware datetimes to format:
    "YYYY-MM-DD HH:MM:SS.mmmmmm" (space separator, no timezone suffix)

    This is different from .isoformat() which produces:
    "YYYY-MM-DDTHH:MM:SS.mmmmmm" (T separator)

    SQLite stores datetimes as TEXT and does lexicographic comparison,
    so we must use the same format Django uses to ensure queries work correctly.

    Args:
        dt: Datetime to format (defaults to current UTC time)

    Returns:
        Formatted datetime string compatible with Django SQLite backend
    """
    if dt is None:
        dt = datetime.now(dt_timezone.utc)

    # Use Django's format: "YYYY-MM-DD HH:MM:SS.mmmmmm"
    # This is what Django's adapt_datetimefield_value() produces
    return dt.strftime('%Y-%m-%d %H:%M:%S.%f')


def parse_availability(availability_text: Optional[str]) -> bool:
    """
    Parse availability text into boolean in-stock status.

    Handles various formats from different stores:
    - English: "In Stock", "Out of Stock", "Available", "Not available"
    - Norwegian: "På lager", "Ikke på lager", "Utsolgt"
    - Numeric: "50+", ">100", "20 stk"
    - Schema.org: "InStock", "OutOfStock", "PreOrder"

    Args:
        availability_text: Raw availability string from extractor

    Returns:
        True if product is in stock, False otherwise
    """
    if not availability_text:
        return False

    text = availability_text.lower().strip()

    # Check out of stock indicators first (highest priority)
    # Must check these before positive patterns to avoid false positives
    # e.g., "Out of Stock" contains "stock" but should return False
    out_of_stock_patterns = [
        "out of stock", "ikke på lager", "utsolgt",
        "not available", "unavailable", "sold out",
        "outofstock", "discontinued", "slutt på lager"
    ]
    for pattern in out_of_stock_patterns:
        if pattern in text:
            return False

    # Check in stock indicators
    in_stock_patterns = [
        "in stock", "på lager", "available",
        "instock", "stocked", "in store", "tilgjengelig",
        "pre-order", "pre order"  # Pre-order counts as available
    ]
    for pattern in in_stock_patterns:
        if pattern in text:
            return True

    # Check for numeric quantities (e.g., "50+", ">100", "20 stk")
    # If there's a number, assume it means quantity in stock
    if re.search(r'\d+', text):
        return True

    # Check schema.org values (lowercase)
    if text in ["instock", "limitedavailability", "preorder", "limited availability"]:
        return True
    if text in ["outofstock", "discontinuedavailability", "soldout"]:
        return False

    # Default: assume unavailable if unclear
    # Conservative approach - better to show "out of stock" than give false hope
    return False


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

    @staticmethod
    def _normalize_product_name(name: str) -> str:
        """
        Normalize product name for matching (mirrors WebUI/app/models.py:normalize_name).
        """
        if not name:
            return ""
        normalized = re.sub(r"[^\w\s]", "", name.lower())
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized

    def get_or_create_extractor_version(
        self,
        extractor_module: str,
        commit_hash: Optional[str] = None,
    ) -> Optional[int]:
        """
        Get or create an ExtractorVersion record.

        Args:
            extractor_module: Python module name (e.g., "python_extractor")
            commit_hash: Git commit hash (defaults to current HEAD)

        Returns:
            ExtractorVersion ID (primary key), or None if git info unavailable
        """
        # Use provided commit hash or get current HEAD
        if not commit_hash:
            commit_hash = get_current_commit_hash()

        if not commit_hash:
            logger.warning("could_not_determine_git_commit")
            return None

        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Check if version already exists
            cursor.execute(
                """
                SELECT id FROM app_extractorversion
                WHERE commit_hash = ? AND extractor_module = ?
                """,
                (commit_hash, extractor_module),
            )
            row = cursor.fetchone()

            if row:
                logger.debug("found_existing_version", version_id=row["id"])
                return row["id"]

            # Get commit info
            commit_info = get_commit_info(commit_hash)

            # Prepare metadata
            metadata = {}
            commit_message = ""
            commit_author = ""
            commit_date = None

            if commit_info:
                metadata = {
                    'branch': commit_info.get('branch'),
                    'tags': commit_info.get('tags', []),
                }
                commit_message = commit_info.get('message', '')
                commit_author = commit_info.get('author', '')
                commit_date = commit_info.get('date')

            # Format commit_date for Django SQLite
            commit_date_str = None
            if commit_date:
                commit_date_str = format_datetime_for_django_sqlite(commit_date)

            # Create new version
            cursor.execute(
                """
                INSERT INTO app_extractorversion
                (commit_hash, extractor_module, commit_message, commit_author,
                 commit_date, metadata, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    commit_hash,
                    extractor_module,
                    commit_message,
                    commit_author,
                    commit_date_str,
                    json.dumps(metadata),
                    format_datetime_for_django_sqlite(),
                ),
            )

            conn.commit()
            version_id = cursor.lastrowid

            logger.info(
                "created_extractor_version",
                version_id=version_id,
                commit_hash=commit_hash[:7],
                extractor_module=extractor_module,
            )

            return version_id

        except Exception as e:
            conn.rollback()
            logger.exception(
                "extractor_version_creation_failed",
                commit_hash=commit_hash,
                error=str(e)
            )
            return None
        finally:
            conn.close()

    def log_operation(
        self,
        service: str,
        level: str,
        event: str,
        message: str = "",
        context: Optional[Dict[str, Any]] = None,
        listing_id: Optional[str] = None,
        product_id: Optional[str] = None,
        task_id: Optional[str] = None,
        filename: Optional[str] = None,
        duration_ms: Optional[int] = None,
    ) -> None:
        """
        Log an operation to the OperationLog table.

        Args:
            service: Service name ('celery', 'fetcher', 'extractor')
            level: Log level ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')
            event: Structured event name (e.g., 'fetch_started', 'extraction_success')
            message: Human-readable message
            context: Structured context data (all log fields as JSON)
            listing_id: ProductListing UUID
            product_id: Product UUID
            task_id: Celery task ID for correlation
            filename: Source file (e.g., 'fetcher.py', 'storage.py')
            duration_ms: Operation duration in milliseconds
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Clean UUIDs (remove hyphens)
            listing_id_clean = listing_id.replace("-", "") if listing_id else None
            product_id_clean = product_id.replace("-", "") if product_id else None

            cursor.execute(
                """
                INSERT INTO app_operationlog
                (service, level, event, message, context, listing_id, product_id,
                 task_id, filename, duration_ms, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    service,
                    level,
                    event,
                    message,
                    json.dumps(context or {}),
                    listing_id_clean,
                    product_id_clean,
                    task_id,
                    filename,
                    duration_ms,
                    format_datetime_for_django_sqlite(),
                ),
            )

            conn.commit()
            logger.debug("operation_logged", event_name=event, log_level=level)

        except Exception as e:
            conn.rollback()
            logger.exception("operation_log_failed", event_name=event, error=str(e))
        finally:
            conn.close()

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

    def get_product_by_listing_id(self, listing_id: str) -> Optional[Product]:
        """
        Get a product by listing ID, with the listing's URL and store info.

        Args:
            listing_id: ProductListing UUID (with or without hyphens)

        Returns:
            Product object with listing URL or None if not found
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # SQLite stores UUIDs without hyphens, so remove them for the query
        listing_id_clean = listing_id.replace("-", "")

        query = """
            SELECT
                p.id as product_id,
                p.name,
                p.image_url,
                l.url,
                l.current_price,
                l.currency,
                l.last_checked,
                l.active,
                s.domain
            FROM app_productlisting l
            INNER JOIN app_product p ON l.product_id = p.id
            INNER JOIN app_store s ON l.store_id = s.id
            WHERE l.id = ?
            AND l.active = 1
        """

        try:
            cursor.execute(query, (listing_id_clean,))
            row = cursor.fetchone()

            if not row:
                logger.warning("listing_not_found", listing_id=listing_id)
                return None

            product = Product(
                product_id=row["product_id"],
                url=row["url"],
                domain=row["domain"],
                name=row["name"],
                image_url=row["image_url"],
                current_price=Decimal(str(row["current_price"])) if row["current_price"] else None,
                currency=row["currency"] or "USD",
                check_interval=3600,  # Default, will be determined by priority
                last_checked=datetime.fromisoformat(row["last_checked"])
                if row["last_checked"]
                else None,
                active=bool(row["active"]),
                priority="normal",  # Default
                listing_id=listing_id,  # Store the listing ID for saving results
            )

            logger.info(
                "product_loaded_from_listing", listing_id=listing_id, product_id=row["product_id"]
            )
            return product

        finally:
            conn.close()

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
        product_id_clean = product_id.replace("-", "")

        query = """
            SELECT id, url, domain, name, image_url, current_price, currency,
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
                image_url=row["image_url"],
                current_price=Decimal(str(row["current_price"])) if row["current_price"] else None,
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
            SELECT id, url, domain, name, image_url, current_price, currency,
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
                        image_url=row["image_url"],
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

    def get_products_without_images(self, limit: Optional[int] = None) -> List[Product]:
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
            SELECT id, url, domain, name, image_url, current_price, currency,
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
                        image_url=row["image_url"],
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
                    format_datetime_for_django_sqlite(),
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
            logger.exception(
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
        listing_id: Optional[str] = None,
    ) -> None:
        """
        Save extracted price to history.

        Args:
            product_id: Product UUID
            extraction: Extracted data
            validation: Validation result
            product_url: Product URL for normalizing relative image URLs
            listing_id: ProductListing UUID (for multi-store support)
        """
        # Get or create extractor version before opening transaction
        extractor_version_id = self.get_or_create_extractor_version("python_extractor")

        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Extract numeric price value
            price_value = None
            currency = "USD"  # default fallback

            # Use extracted currency if available
            if extraction.currency and extraction.currency.value:
                currency = extraction.currency.value

            if extraction.price and extraction.price.value:
                match = re.search(r"(\d+\.?\d*)", extraction.price.value)
                if match:
                    price_value = float(match.group(1))

            # Extract availability using improved parsing logic
            available = parse_availability(
                extraction.availability.value if extraction.availability else None
            )

            # Extract and normalize image URL
            image_url = None
            if extraction.image and extraction.image.value:
                image_url = extraction.image.value.strip()
                # Unescape HTML entities (&amp; -> &)
                image_url = html.unescape(image_url)
                # Normalize relative URLs to absolute
                if image_url and not image_url.startswith(("http://", "https://")):
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

            if listing_id:
                # New multi-store schema: save to listing
                listing_id_clean = listing_id.replace("-", "")

                # Store in price_history table (linked to listing)
                cursor.execute(
                    """
                    INSERT INTO app_pricehistory
                    (listing_id, price, currency, available, extracted_data,
                     confidence, recorded_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        listing_id_clean,
                        price_value,
                        currency,
                        available,
                        json.dumps(extraction.model_dump(), default=str),
                        validation.confidence,
                        format_datetime_for_django_sqlite(),
                    ),
                )

                # Update listing's current_price, availability, last_checked, and extractor_version
                cursor.execute(
                    """
                    UPDATE app_productlisting
                    SET current_price = ?,
                        currency = ?,
                        available = ?,
                        last_checked = ?,
                        extractor_version_id = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        price_value,
                        currency,
                        available,
                        format_datetime_for_django_sqlite(),
                        extractor_version_id,
                        format_datetime_for_django_sqlite(),
                        listing_id_clean,
                    ),
                )

                # Update product title and image if we have them
                title = None
                if extraction.title and extraction.title.value:
                    title = extraction.title.value.strip()

                if title or image_url:
                    # Build dynamic update query based on what we have
                    update_fields = []
                    update_values = []

                    if title:
                        # Update name if it's still the placeholder format "Product from domain"
                        update_fields.append("""
                            name = CASE
                                WHEN name LIKE 'Product from %' THEN ?
                                ELSE name
                            END
                        """)
                        update_values.append(title)

                        # Keep canonical_name in sync for placeholder products.
                        # Existing data may have a real name but still a placeholder canonical_name
                        # if it was updated outside Django (direct SQL from the fetcher).
                        canonical_title = self._normalize_product_name(title)
                        update_fields.append("""
                            canonical_name = CASE
                                WHEN canonical_name LIKE 'product from %'
                                  OR canonical_name IS NULL
                                  OR canonical_name = '' THEN ?
                                ELSE canonical_name
                            END
                        """)
                        update_values.append(canonical_title)

                    if image_url:
                        # Always update image_url with latest extracted value
                        update_fields.append("image_url = ?")
                        update_values.append(image_url)

                    # Always update updated_at
                    update_fields.append("updated_at = ?")
                    update_values.append(format_datetime_for_django_sqlite())

                    # Add product_id for WHERE clause
                    update_values.append(product_id)

                    query = f"""
                        UPDATE app_product
                        SET {",".join(update_fields)}
                        WHERE id = ?
                    """

                    cursor.execute(query, tuple(update_values))

                logger.info(
                    "price_saved",
                    product_id=product_id,
                    listing_id=listing_id,
                    price=price_value,
                    confidence=validation.confidence,
                    title_extracted=title is not None,
                    image_extracted=image_url is not None,
                )

                # Log to OperationLog for unified monitoring
                self.log_operation(
                    service="fetcher",
                    level="INFO",
                    event="price_saved",
                    message=f"Price saved: {currency}{price_value}",
                    context={
                        "price": price_value,
                        "currency": currency,
                        "available": available,
                        "confidence": validation.confidence,
                        "extractor_version_id": extractor_version_id,
                        "extraction_method": extraction.price.method if extraction.price else None,
                    },
                    listing_id=listing_id,
                    product_id=product_id,
                    filename="storage.py",
                )
            else:
                # Fallback to old single-store schema
                logger.warning("listing_id_missing_using_fallback", product_id=product_id)
                # This path is kept for backwards compatibility but shouldn't be used

            conn.commit()

        except Exception as e:
            conn.rollback()
            logger.exception(
                "price_save_failed", product_id=product_id, listing_id=listing_id, error=str(e)
            )
            raise
        finally:
            conn.close()


    def get_latest_price(
        self, product_id: str = None, listing_id: str = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get most recent price for product or listing.

        Args:
            product_id: Product UUID (legacy, checks all listings for product)
            listing_id: ProductListing UUID (preferred for multi-store)

        Returns:
            Dict with price data or None if no history
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            if listing_id:
                # New multi-store schema: query by listing_id
                listing_id_clean = listing_id.replace("-", "")
                cursor.execute(
                    """
                    SELECT price, currency, available, extracted_data,
                           confidence, recorded_at
                    FROM app_pricehistory
                    WHERE listing_id = ?
                    ORDER BY recorded_at DESC
                    LIMIT 1
                    """,
                    (listing_id_clean,),
                )
            elif product_id:
                # Legacy: get latest across all listings for this product
                product_id_clean = product_id.replace("-", "")
                cursor.execute(
                    """
                    SELECT ph.price, ph.currency, ph.available, ph.extracted_data,
                           ph.confidence, ph.recorded_at
                    FROM app_pricehistory ph
                    INNER JOIN app_productlisting l ON ph.listing_id = l.id
                    WHERE l.product_id = ?
                    ORDER BY ph.recorded_at DESC
                    LIMIT 1
                    """,
                    (product_id_clean,),
                )
            else:
                logger.warning("get_latest_price called without product_id or listing_id")
                return None

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

    def update_last_checked(self, listing_id: str) -> None:
        """
        Update last_checked timestamp for a listing.

        This should be called after every fetch attempt, regardless of success or failure.
        This prevents listings with failing patterns from being retried infinitely.

        Args:
            listing_id: ProductListing UUID (with or without hyphens)
        """
        try:
            listing_id_clean = listing_id.replace("-", "")

            conn = sqlite3.connect(self.db_path, timeout=30.0)
            cursor = conn.cursor()

            cursor.execute(
                """
                UPDATE app_productlisting
                SET last_checked = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    format_datetime_for_django_sqlite(),
                    format_datetime_for_django_sqlite(),
                    listing_id_clean,
                ),
            )

            conn.commit()
            conn.close()
            logger.debug("last_checked_updated", listing_id=listing_id)

        except sqlite3.Error as e:
            logger.error("update_last_checked_failed", listing_id=listing_id, error=str(e))
            raise

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
                (1 if success else 0, 1 if success else 0, format_datetime_for_django_sqlite(), domain),
            )

            conn.commit()
            logger.debug("pattern_stats_updated", domain=domain, success=success)

        except Exception as e:
            conn.rollback()
            logger.exception("pattern_stats_update_failed", domain=domain, error=str(e))
        finally:
            conn.close()
