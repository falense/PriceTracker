"""
Business logic services for WebUI - Multi-Store Support.

These services coordinate complex operations between models, tasks, and external systems.
"""

from .models import (
    Product,
    Store,
    ProductListing,
    UserSubscription,
    Notification,
    PriceHistory,
    AdminFlag,
    normalize_name,
    ReferralCode,
    ReferralVisit,
    UserTierHistory,
)
from .utils.currency import format_price
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db.models import Max, Q
from django.db import transaction
from urllib.parse import urlparse, urlunparse
from decimal import Decimal
from datetime import timedelta
import uuid
import logging
import hashlib
import secrets
import random
import string

User = get_user_model()
logger = logging.getLogger(__name__)


class TierLimitReached(Exception):
    """Raised when user tries to add product but is at tier limit."""
    pass

PLACEHOLDER_PRODUCT_PREFIX = "Product from "


def strip_url_fragment(url):
    """
    Remove fragment (everything after #) from URL.

    Preserves:
    - Query parameters
    - Path case
    - Trailing slashes

    Example:
        https://shop.com/product?ref=123#reviews -> https://shop.com/product?ref=123

    Args:
        url: URL string to process

    Returns:
        URL without fragment, or original URL if parsing fails
    """
    try:
        parsed = urlparse(url)
        # Remove fragment by setting it to empty string
        normalized = parsed._replace(fragment='')
        return urlunparse(normalized)
    except Exception as e:
        logger.warning(f"Failed to strip fragment from URL {url}: {e}")
        return url


def get_url_base_for_comparison(url):
    """
    Get normalized URL base for duplicate detection.

    Removes:
    - Fragment (everything after #)
    - Query parameters (everything after ?)

    Preserves:
    - Path case
    - Trailing slashes

    Example:
        https://shop.com/product?ref=123#reviews -> https://shop.com/product

    Args:
        url: URL string to process

    Returns:
        Normalized URL without query params or fragment, or original URL if parsing fails
    """
    try:
        parsed = urlparse(url)
        # Remove both query and fragment
        normalized = parsed._replace(query='', fragment='')
        return urlunparse(normalized)
    except Exception as e:
        logger.warning(f"Failed to normalize URL {url}: {e}")
        return url


def find_matching_product(name, brand=None):
    """
    Find existing product by normalized name.
    Returns None if no match found.
    """
    # Guard: placeholder names are not meaningful identifiers and should never be used for matching.
    if name and name.startswith(PLACEHOLDER_PRODUCT_PREFIX):
        return None

    canonical = normalize_name(name)

    # Exact canonical name match
    products = Product.objects.filter(canonical_name=canonical)

    if brand:
        # Prefer brand match if available
        products = products.filter(brand__iexact=brand)

    return products.first()


class ProductService:
    """Business logic for product management with multi-store support."""

    @staticmethod
    def add_product_for_user(
        user: User, url: str, priority: str = "normal", target_price=None
    ):
        """
        Add product subscription for user.

        This is the main entry point. It handles:
        1. Parse URL and identify store
        2. Check if listing already exists
        3. Check if product already exists (by matching)
        4. Create Store/Product/Listing as needed
        5. Create or update UserSubscription
        6. Trigger pattern generation if needed
        7. Trigger initial price fetch (after pattern exists)

        Args:
            user: User object
            url: Product URL to track
            priority: 'high', 'normal', or 'low'
            target_price: Optional target price for alerts

        Returns:
            Tuple of (Product, UserSubscription, ProductListing, bool):
                product, subscription, listing, and created flag
        """
        # === TIER CHECK - MUST BE FIRST ===
        can_add, error_message = TierService.check_can_add_product(user)
        if not can_add:
            raise TierLimitReached(error_message)
        # === END TIER CHECK ===

        # Step 0: Normalize URL
        # Strip fragment (everything after #) for storage
        url = strip_url_fragment(url)
        # Get base URL (without query params) for duplicate detection
        url_base = get_url_base_for_comparison(url)

        # Step 1: Parse URL and get/create Store
        parsed = urlparse(url)
        domain = parsed.netloc.replace("www.", "").lower()

        if not domain:
            raise ValueError("Invalid URL: Could not extract domain")

        # Get default currency for this domain
        from app.utils.currency import get_currency_from_domain

        default_currency, _ = get_currency_from_domain(domain)

        store, store_created = Store.objects.get_or_create(
            domain=domain,
            defaults={
                "name": domain.replace(".com", "").replace(".", " ").title(),
                "active": True,
                "currency": default_currency,  # Set currency based on domain
            },
        )

        if store_created:
            logger.info(f"Created new store: {store.name} (currency: {store.currency})")

        # Step 2: Check if listing exists (using url_base for duplicate detection)
        listing = ProductListing.objects.filter(url_base=url_base).first()

        if listing:
            # Listing exists, reuse product
            product = listing.product
            logger.info(f"Found existing listing for {product.name} at {store.name}")
        else:
            # Step 3: Extract product name (placeholder, will be updated after first fetch)
            # Important: do not attempt to match/merge based on placeholder naming.
            # Make the placeholder unique per listing so multiple products from the same store
            # don't collapse into a single Product before the first fetch updates the title.
            placeholder_suffix = uuid.uuid4().hex[:8]
            product_name = (
                f"{PLACEHOLDER_PRODUCT_PREFIX}{domain} ({placeholder_suffix})"
            )
            canonical = normalize_name(product_name)

            product = Product.objects.create(
                name=product_name,
                canonical_name=canonical,
                subscriber_count=0,
            )
            logger.info(f"Created new product: {product.name}")

            # Create listing
            listing = ProductListing.objects.create(
                product=product,
                store=store,
                url=url,
                url_base=url_base,  # Store normalized URL for duplicate detection
                active=True,
                currency=store.currency,  # Inherit currency from store
            )
            logger.info(
                f"Created new listing: {listing} (currency: {listing.currency})"
            )

        # Step 5: Create or update subscription
        priority_map = {"high": 3, "normal": 2, "low": 1}
        priority_value = priority_map.get(priority, 2)

        subscription, created = UserSubscription.objects.get_or_create(
            user=user,
            product=product,
            defaults={
                "priority": priority_value,
                "target_price": target_price,
            },
        )

        if not created:
            # Update existing subscription
            subscription.priority = max(subscription.priority, priority_value)
            if target_price:
                subscription.target_price = target_price
            subscription.active = True
            subscription.save()
            logger.info(f"Updated subscription for {user.username}")
        else:
            logger.info(f"Created subscription for {user.username}")

        # Update product subscriber count
        product.subscriber_count = product.subscriptions.filter(active=True).count()
        product.save()

        # Step 6: Ensure extractor exists
        from .models import ExtractorVersion
        if not ExtractorVersion.objects.filter(domain=domain, is_active=True).exists():
            logger.info(f"No active extractor found for {domain}, triggering generation")
            ProductService._trigger_pattern_generation(url, domain, str(listing.id))
        else:
            ProductService._trigger_fetch_listing(str(listing.id))

        return product, subscription, listing, created

    @staticmethod
    def _trigger_pattern_generation(url: str, domain: str, listing_id: str = None):
        """
        Trigger ExtractorPatternAgent to generate patterns.

        Args:
            url: Product URL to analyze
            domain: Domain name
            listing_id: Optional listing ID for tracking

        Returns:
            str: Task ID
        """
        try:
            from app.tasks import generate_pattern

            task = generate_pattern.delay(url, domain, listing_id)
            logger.info(f"Pattern generation task {task.id} started for {domain}")
            return task.id
        except ImportError:
            logger.warning("Task module not available yet")
            return None
        except Exception as e:
            logger.error(f"Failed to trigger pattern generation for {domain}: {e}")
            # Create admin flag
            AdminFlag.objects.create(
                flag_type="pattern_generation_failed",
                domain=domain,
                url=url,
                error_message=str(e),
                status="pending",
            )
            raise

    @staticmethod
    def _trigger_fetch_listing(listing_id: str):
        """
        Trigger immediate price fetch for listing.

        Args:
            listing_id: ProductListing UUID as string

        Returns:
            str: Task ID
        """
        try:
            from app.tasks import fetch_listing_price

            task = fetch_listing_price.delay(listing_id)
            logger.info(f"Price fetch task {task.id} started for listing {listing_id}")
            return task.id
        except ImportError:
            logger.warning("Task module not available yet")
            return None
        except Exception as e:
            logger.error(f"Failed to trigger price fetch for listing {listing_id}: {e}")
            raise

    @staticmethod
    def update_subscription_settings(subscription: UserSubscription, **kwargs):
        """
        Update subscription settings.

        Args:
            subscription: UserSubscription instance to update
            **kwargs: Fields to update (priority, target_price, notify_on_drop, etc.)

        Returns:
            UserSubscription: Updated subscription instance
        """
        allowed_fields = [
            "priority",
            "target_price",
            "notify_on_drop",
            "notify_on_restock",
            "notify_on_target",
            "active",
        ]

        for field, value in kwargs.items():
            if field in allowed_fields:
                setattr(subscription, field, value)

        subscription.save()

        # Update product subscriber count if active status changed
        if "active" in kwargs:
            product = subscription.product
            product.subscriber_count = product.subscriptions.filter(active=True).count()
            product.save()

        logger.info(f"Updated settings for subscription {subscription.id}")
        return subscription

    @staticmethod
    def get_user_subscriptions(user: User, active_only=True):
        """
        Get all product subscriptions for a user.

        Args:
            user: User object
            active_only: Only return active subscriptions

        Returns:
            QuerySet of UserSubscription with prefetched relations
        """
        qs = UserSubscription.objects.filter(user=user)

        if active_only:
            qs = qs.filter(active=True)

        # Prefetch related data for efficiency
        qs = qs.select_related("product").prefetch_related(
            "product__listings", "product__listings__store"
        )

        return qs.order_by("-last_viewed", "-created_at")

    @staticmethod
    def get_best_prices_for_subscription(subscription: UserSubscription):
        """
        Get best prices across all stores for a subscribed product.

        Returns:
            List of dicts with store, price, availability info
        """
        listings = (
            subscription.product.listings.filter(active=True)
            .select_related("store")
            .order_by("current_price")
        )

        prices = []
        for listing in listings:
            if listing.current_price:
                prices.append(
                    {
                        "store": listing.store,
                        "listing": listing,
                        "price": listing.current_price,
                        "currency": listing.currency,
                        "available": listing.available,
                        "total_price": listing.total_price,
                        "last_checked": listing.last_checked,
                    }
                )

        return prices


class PriorityAggregationService:
    """Calculate effective priorities and due products."""

    @staticmethod
    def get_products_due_for_check():
        """
        Get products that need checking based on aggregated priority.

        Returns:
            List of (Product, priority_int, [listings]) tuples
        """
        now = timezone.now()
        intervals = {3: 900, 2: 3600, 1: 86400}

        # Get products with active subscriptions
        products = (
            Product.objects.filter(subscriptions__active=True)
            .annotate(max_priority=Max("subscriptions__priority"))
            .distinct()
        )

        due_products = []

        for product in products:
            check_interval = intervals[product.max_priority]
            cutoff_time = now - timedelta(seconds=check_interval)

            # Get listings needing check
            listings = product.listings.filter(active=True).filter(
                Q(last_checked__isnull=True) | Q(last_checked__lt=cutoff_time)
            )

            if listings.exists():
                due_products.append((product, product.max_priority, list(listings)))

        return due_products

    @staticmethod
    def get_priority_stats():
        """
        Get statistics about priority distribution.
        Useful for monitoring and dashboards.
        """
        from django.db.models import Count

        stats = (
            Product.objects.filter(subscriptions__active=True)
            .annotate(max_priority=Max("subscriptions__priority"))
            .aggregate(
                high=Count("id", filter=Q(max_priority=3)),
                normal=Count("id", filter=Q(max_priority=2)),
                low=Count("id", filter=Q(max_priority=1)),
                total=Count("id"),
            )
        )

        return {
            "high": stats["high"],
            "normal": stats["normal"],
            "low": stats["low"],
            "total": stats["total"],
            "checks_per_hour": (
                stats["high"] * 4  # Every 15 min = 4 per hour
                + stats["normal"] * 1  # Every hour = 1 per hour
                + stats["low"] / 24  # Every day = 1/24 per hour
            ),
        }


class NotificationService:
    """Create and manage notifications for multi-store tracking."""

    @staticmethod
    def check_subscriptions_for_listing(
        listing: ProductListing, old_price: Decimal = None
    ):
        """
        Check all subscriptions for product and create notifications.

        Called after price fetch for a listing.

        Args:
            listing: ProductListing that was just fetched
            old_price: Previous price (if known)

        Returns:
            List of created notifications
        """
        notifications = []
        product = listing.product

        # Get all active subscriptions
        for subscription in product.subscriptions.filter(active=True):
            # Price drop
            if (
                old_price
                and listing.current_price
                and listing.current_price < old_price
            ):
                if subscription.notify_on_drop:
                    notif = NotificationService._create_price_drop_notification(
                        subscription, listing, old_price, listing.current_price
                    )
                    if notif:
                        notifications.append(notif)

            # Target price reached
            if subscription.notify_on_target and subscription.target_price:
                if (
                    listing.current_price
                    and listing.current_price <= subscription.target_price
                ):
                    notif = NotificationService._create_target_reached_notification(
                        subscription, listing
                    )
                    if notif:
                        notifications.append(notif)

            # Restock
            if subscription.notify_on_restock and listing.available:
                # Check if previously unavailable
                was_unavailable = (
                    PriceHistory.objects.filter(listing=listing, available=False)
                    .order_by("-recorded_at")
                    .first()
                )

                if was_unavailable:
                    notif = NotificationService._create_restock_notification(
                        subscription, listing
                    )
                    if notif:
                        notifications.append(notif)

        return notifications

    @staticmethod
    def _create_price_drop_notification(
        subscription: UserSubscription,
        listing: ProductListing,
        old_price: Decimal,
        new_price: Decimal,
    ):
        """Create price drop notification."""
        # Avoid duplicates (within 1 hour)
        recent = Notification.objects.filter(
            subscription=subscription,
            listing=listing,
            notification_type="price_drop",
            created_at__gte=timezone.now() - timedelta(hours=1),
        ).exists()

        if recent:
            return None

        drop_amount = old_price - new_price
        drop_percent = (drop_amount / old_price) * 100

        old_price_formatted = format_price(
            float(old_price), currency_code=listing.currency
        )
        new_price_formatted = format_price(
            float(new_price), currency_code=listing.currency
        )

        message = (
            f"{listing.product.name} at {listing.store.name} dropped from "
            f"{old_price_formatted} to {new_price_formatted} "
            f"(-{drop_percent:.1f}%)"
        )

        notification = Notification.objects.create(
            user=subscription.user,
            subscription=subscription,
            listing=listing,
            notification_type="price_drop",
            message=message,
            old_price=old_price,
            new_price=new_price,
        )

        logger.info(f"Created price drop notification for {subscription}")
        return notification

    @staticmethod
    def _create_target_reached_notification(
        subscription: UserSubscription, listing: ProductListing
    ):
        """Create target price notification."""
        # Avoid duplicates (within 24 hours)
        recent = Notification.objects.filter(
            subscription=subscription,
            listing=listing,
            notification_type="target_reached",
            created_at__gte=timezone.now() - timedelta(hours=24),
        ).exists()

        if recent:
            return None

        current_formatted = format_price(
            float(listing.current_price), currency_code=listing.currency
        )
        target_formatted = format_price(
            float(subscription.target_price), currency_code=listing.currency
        )

        message = (
            f"{listing.product.name} at {listing.store.name} reached your target price! "
            f"Now {current_formatted} (target: {target_formatted})"
        )

        notification = Notification.objects.create(
            user=subscription.user,
            subscription=subscription,
            listing=listing,
            notification_type="target_reached",
            message=message,
            new_price=listing.current_price,
        )

        logger.info(f"Created target reached notification for {subscription}")
        return notification

    @staticmethod
    def _create_restock_notification(
        subscription: UserSubscription, listing: ProductListing
    ):
        """Create restock notification."""
        # Avoid duplicates (within 24 hours)
        recent = Notification.objects.filter(
            subscription=subscription,
            listing=listing,
            notification_type="restock",
            created_at__gte=timezone.now() - timedelta(hours=24),
        ).exists()

        if recent:
            return None

        message = f"{listing.product.name} is back in stock at {listing.store.name}!"
        if listing.current_price:
            price_formatted = format_price(
                float(listing.current_price), domain=listing.store.domain
            )
            message += f" Price: {price_formatted}"

        notification = Notification.objects.create(
            user=subscription.user,
            subscription=subscription,
            listing=listing,
            notification_type="restock",
            message=message,
            new_price=listing.current_price,
        )

        logger.info(f"Created restock notification for {subscription}")
        return notification

    @staticmethod
    def mark_all_as_read(user: User):
        """
        Mark all notifications as read for user.

        Args:
            user: User whose notifications to mark

        Returns:
            int: Number of notifications marked
        """
        count = Notification.objects.filter(user=user, read=False).update(
            read=True, read_at=timezone.now()
        )

        logger.info(f"Marked {count} notifications as read for user {user.username}")
        return count


class SubscriptionStatusService:
    """Detect subscription data fetching status."""

    @staticmethod
    def is_being_added(subscription: UserSubscription) -> bool:
        """
        Check if subscription is waiting for store pattern generation and initial fetch.

        Returns True when product metadata is not yet populated, which indicates
        the store is being added and data hasn't been fetched yet.

        Detection criteria (all must be true):
        - Product has no image_url (indicates no successful data fetch)
        - No listing has been checked yet (last_checked is None)
        - No listing has a price (current_price is None)

        Args:
            subscription: UserSubscription to check

        Returns:
            bool: True if waiting for initial data fetch (store being added)
        """
        listings = subscription.product.listings.all()

        for listing in listings:
            # Check if essential metadata is missing (indicates no successful fetch yet)
            is_unpopulated = (
                listing.current_price is None
                and subscription.product.image_url is None
                and listing.last_checked is None
            )

            if is_unpopulated:
                return True

        return False

    @staticmethod
    def get_store_name(subscription: UserSubscription) -> str:
        """
        Get the store name for display in loading message.

        Args:
            subscription: UserSubscription to get store from

        Returns:
            str: Store name or fallback text
        """
        listing = subscription.product.listings.first()
        if listing:
            return listing.store.name
        return "the store"


class ProductSimilarityService:
    """Fuzzy matching service to find similar products."""

    # Thresholds
    NAME_SIMILARITY_THRESHOLD = 75  # Token set ratio minimum
    BRAND_BOOST = 15  # Bonus points for brand match
    MODEL_BOOST = 20  # Bonus points for model number match
    MAX_CANDIDATES = 200  # Limit candidate pool for performance

    @classmethod
    def find_similar_products(cls, target_product, limit=5, exclude_ids=None):
        """
        Find products similar to target_product using fuzzy matching.

        Args:
            target_product: Product instance to find matches for
            limit: Maximum number of similar products to return
            exclude_ids: List of product IDs to exclude from results

        Returns:
            List of tuples: [(product, similarity_score), ...]
            Sorted by similarity score (highest first)
        """
        from rapidfuzz import fuzz

        exclude_ids = exclude_ids or []
        exclude_ids.append(target_product.id)

        # Step 1: Exact matches on EAN/UPC (100% confidence)
        exact_matches = []
        if target_product.ean:
            exact_matches.extend(
                Product.objects.filter(ean=target_product.ean)
                .exclude(id__in=exclude_ids)
            )
        if target_product.upc:
            exact_matches.extend(
                Product.objects.filter(upc=target_product.upc)
                .exclude(id__in=exclude_ids)
            )

        results = [(p, 100.0) for p in exact_matches]

        # Step 2: Fuzzy name matching with boosting
        # Get candidate pool (limit for performance)
        candidates = (
            Product.objects.exclude(id__in=exclude_ids)
            .order_by('-subscriber_count', '-updated_at')[:cls.MAX_CANDIDATES]
        )

        target_name = target_product.canonical_name or target_product.name
        target_brand = (target_product.brand or '').lower()
        target_model = (target_product.model_number or '').lower()

        for candidate in candidates:
            # Base similarity: token set ratio (handles word order differences)
            candidate_name = candidate.canonical_name or candidate.name
            base_score = fuzz.token_set_ratio(target_name, candidate_name)

            if base_score < cls.NAME_SIMILARITY_THRESHOLD:
                continue

            # Calculate boosted score
            score = float(base_score)

            # Brand match boost
            if target_brand and candidate.brand:
                if target_brand == candidate.brand.lower():
                    score = min(100, score + cls.BRAND_BOOST)

            # Model number match boost
            if target_model and candidate.model_number:
                if target_model == candidate.model_number.lower():
                    score = min(100, score + cls.MODEL_BOOST)

            results.append((candidate, score))

        # Sort by score and return top N
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:limit]


class ProductRelationService:
    """Service for managing product relation votes."""

    @staticmethod
    def vote_on_relation(user, product_id_1, product_id_2, weight):
        """
        Record or update user's vote on product similarity.

        Args:
            user: User instance
            product_id_1, product_id_2: UUIDs of products to relate
            weight: -1 (different), 0 (dismissed), 1 (same)

        Returns:
            ProductRelation instance
        """
        from .models import ProductRelation

        # Normalize product order
        p1, p2 = ProductRelation.normalize_product_ids(product_id_1, product_id_2)

        # Create or update relation
        relation, created = ProductRelation.objects.update_or_create(
            user=user,
            product_1_id=p1,
            product_2_id=p2,
            defaults={'weight': weight}
        )

        logger.info(
            f"User {user.username} voted {weight} on products {p1} ↔ {p2}"
        )

        return relation

    @staticmethod
    def get_user_vote(user, product_id_1, product_id_2):
        """Get user's existing vote on a product pair, if any."""
        from .models import ProductRelation

        p1, p2 = ProductRelation.normalize_product_ids(product_id_1, product_id_2)

        try:
            relation = ProductRelation.objects.get(
                user=user,
                product_1_id=p1,
                product_2_id=p2
            )
            return relation.weight
        except ProductRelation.DoesNotExist:
            return None

    @staticmethod
    def get_aggregate_votes(product_id_1, product_id_2):
        """
        Get aggregate vote statistics for a product pair.

        Returns:
            dict: {
                'total_votes': int,
                'upvotes': int,
                'downvotes': int,
                'dismissed': int,
                'score': float (-1.0 to 1.0)
            }
        """
        from .models import ProductRelation
        from django.db.models import Count, Q

        p1, p2 = ProductRelation.normalize_product_ids(product_id_1, product_id_2)

        relations = ProductRelation.objects.filter(
            product_1_id=p1,
            product_2_id=p2
        )

        stats = relations.aggregate(
            total=Count('id'),
            upvotes=Count('id', filter=Q(weight=1)),
            downvotes=Count('id', filter=Q(weight=-1)),
            dismissed=Count('id', filter=Q(weight=0))
        )

        total_votes = stats['total'] or 0
        upvotes = stats['upvotes'] or 0
        downvotes = stats['downvotes'] or 0

        # Calculate weighted score
        if total_votes > 0:
            score = (upvotes - downvotes) / total_votes
        else:
            score = 0.0

        return {
            'total_votes': total_votes,
            'upvotes': upvotes,
            'downvotes': downvotes,
            'dismissed': stats['dismissed'] or 0,
            'score': score
        }


class TierService:
    """Business logic for user tier management and enforcement."""

    @staticmethod
    def check_can_add_product(user) -> tuple[bool, str]:
        """
        Check if user can add another product.
        Also checks if referral tier has expired and downgrades if needed.

        Returns:
            Tuple of (can_add: bool, message: str)
        """
        # Check if referral tier has expired
        if (user.referral_tier_source == 'referral' and
            user.referral_tier_expires_at and
            user.referral_tier_expires_at <= timezone.now()):

            # Tier has expired - downgrade to free
            logger.info(
                f"Referral tier expired for {user.username}, downgrading to free",
                extra={'user_id': user.id, 'expired_at': user.referral_tier_expires_at.isoformat()}
            )

            old_tier = user.tier
            user.tier = 'free'
            user.referral_tier_source = 'none'
            user.referral_tier_expires_at = None
            user.save()

            # Log tier change
            UserTierHistory.objects.create(
                user=user,
                old_tier=old_tier,
                new_tier='free',
                source='expiration',
                notes='Referral tier expired'
            )

        if user.is_at_product_limit():
            limit = user.get_product_limit()
            tier_display = user.get_tier_display()

            from .constants import (
                TIER_SUPPORTER_NAME,
                TIER_SUPPORTER_LIMIT,
                TIER_ULTIMATE_NAME
            )

            if user.tier == 'free':
                message = (
                    f"Du har nådd grensen på {limit} produkter for {tier_display}. "
                    f"Oppgrader til {TIER_SUPPORTER_NAME} ({TIER_SUPPORTER_LIMIT} produkter) "
                    f"eller {TIER_ULTIMATE_NAME} (ubegrenset) for å følge flere produkter."
                )
            elif user.tier == 'supporter':
                message = (
                    f"Du har nådd grensen på {limit} produkter for {tier_display}. "
                    f"Oppgrader til {TIER_ULTIMATE_NAME} for ubegrenset produkter."
                )
            else:
                message = f"Du har nådd grensen på {limit} produkter."

            return (False, message)

        return (True, "")

    @staticmethod
    def get_user_tier_info(user) -> dict:
        """Get comprehensive tier information for templates."""
        limit = user.get_product_limit()
        current_count = user.subscriptions.filter(active=True).count()

        if limit is None:  # Unlimited
            remaining = None
            percentage_used = 0.0
        else:
            remaining = max(0, limit - current_count)
            percentage_used = (current_count / limit * 100) if limit > 0 else 0.0

        return {
            'tier': user.tier,
            'tier_display': user.get_tier_display(),
            'limit': limit,
            'limit_display': user.get_product_limit_display(),
            'current_count': current_count,
            'remaining': remaining,
            'at_limit': user.is_at_product_limit(),
            'percentage_used': percentage_used,
        }


class ReferralService:
    """Business logic for referral system - tracking visits and granting rewards."""

    @staticmethod
    def generate_code():
        """
        Generate a unique 12-character referral code.
        Format: Uppercase letters and numbers only for clarity.
        """
        while True:
            # Generate 12-character code (uppercase + digits)
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))

            # Check if unique
            if not ReferralCode.objects.filter(code=code).exists():
                return code

    @staticmethod
    def get_client_ip(request):
        """
        Extract client IP address from request.
        Handles X-Forwarded-For header for proxied requests.
        """
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            # Take the first IP in the chain (original client)
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

    @staticmethod
    def hash_ip_address(ip_address):
        """
        Hash IP address for privacy (GDPR compliance).
        Uses SHA256 with a daily rotating salt for 7-day deduplication window.
        """
        if not ip_address:
            return None

        # Use date as salt (rotates daily)
        # This allows same IP to be "new" after ~7 days naturally
        from datetime import date
        salt = date.today().isoformat()

        # Create hash
        hash_input = f"{salt}:{ip_address}".encode('utf-8')
        return hashlib.sha256(hash_input).hexdigest()

    @staticmethod
    def is_unique_visit(referral_code, request):
        """
        Check if this visit should be counted as unique.
        Uses hybrid deduplication: logged-in user > cookie > IP hash.

        Returns: tuple (is_unique: bool, duplicate_reason: str)
        """
        # Check 1: Authenticated user
        if request.user.is_authenticated:
            # Check if this user has visited this referral code before
            previous_visit = ReferralVisit.objects.filter(
                referral_code=referral_code,
                visitor_user=request.user
            ).exists()

            if previous_visit:
                return (False, "logged_in_duplicate")

        # Check 2: Cookie (primary method)
        cookie_id = request.COOKIES.get('ref_visitor_id')
        if cookie_id:
            # Check if this cookie visited within 7 days
            seven_days_ago = timezone.now() - timedelta(days=7)
            recent_cookie_visit = ReferralVisit.objects.filter(
                referral_code=referral_code,
                visitor_cookie_id=cookie_id,
                visited_at__gte=seven_days_ago
            ).exists()

            if recent_cookie_visit:
                return (False, "cookie_duplicate")

        # Check 3: IP hash (backup method)
        ip_address = ReferralService.get_client_ip(request)
        ip_hash = ReferralService.hash_ip_address(ip_address)

        if ip_hash:
            seven_days_ago = timezone.now() - timedelta(days=7)
            recent_ip_visit = ReferralVisit.objects.filter(
                referral_code=referral_code,
                visitor_ip_hash=ip_hash,
                visited_at__gte=seven_days_ago
            ).exists()

            if recent_ip_visit:
                return (False, "ip_duplicate")

        # Passed all checks - this is a unique visit
        return (True, "unique")

    @staticmethod
    def check_and_grant_reward(referral_code):
        """
        Check if user has reached a reward milestone (every 3 unique visits).
        If yes, grant Supporter tier for 30 days.

        Returns: bool - True if reward was granted, False otherwise
        """
        user = referral_code.user
        unique_visits = referral_code.unique_visits

        # Check if this is a reward milestone (multiple of 3)
        if unique_visits % 3 != 0:
            return False

        # Check if reward was already granted for this milestone
        # (prevent double-granting if called twice)
        if referral_code.last_reward_granted_at:
            # If we already granted at this exact count, skip
            last_granted_count = (referral_code.unique_visits // 3) * 3
            if last_granted_count == unique_visits:
                # Already granted for this milestone
                return False

        # Skip if user has non-referral tier source (payment/admin) or higher tier
        if user.referral_tier_source in ['payment', 'admin']:
            logger.info(
                f"Skipping referral reward for {user.username} - has {user.referral_tier_source} tier source",
                extra={'user_id': user.id, 'tier_source': user.referral_tier_source, 'unique_visits': unique_visits}
            )
            return False

        # Skip if user has higher tier than supporter
        if user.tier == 'ultimate':
            logger.info(
                f"Skipping referral reward for {user.username} - already has ultimate tier",
                extra={'user_id': user.id, 'tier': user.tier, 'unique_visits': unique_visits}
            )
            return False

        # Grant reward using transaction for safety
        with transaction.atomic():
            # Re-fetch user with lock to prevent race conditions
            user = User.objects.select_for_update().get(id=user.id)

            old_tier = user.tier
            old_expires_at = user.referral_tier_expires_at

            # Grant Supporter tier for 30 days from NOW (RESET, not extend)
            user.tier = 'supporter'
            user.referral_tier_source = 'referral'
            user.referral_tier_expires_at = timezone.now() + timedelta(days=30)
            user.referral_tier_granted_count += 1
            user.save()

            # Update referral code
            referral_code.last_reward_granted_at = timezone.now()
            referral_code.save()

            # Log tier change to audit history
            UserTierHistory.objects.create(
                user=user,
                old_tier=old_tier,
                new_tier='supporter',
                source='referral',
                notes=f'Earned via referral code {referral_code.code} - {unique_visits} unique visits'
            )

            logger.info(
                f"Granted referral reward to {user.username}",
                extra={
                    'user_id': user.id,
                    'unique_visits': unique_visits,
                    'old_tier': old_tier,
                    'new_tier': 'supporter',
                    'expires_at': user.referral_tier_expires_at.isoformat()
                }
            )

        # Create notification
        try:
            NotificationService.create_notification(
                user=user,
                notification_type='info',
                title='Belønning opptjent!',
                message=f'Du har tjent 30 dager med Støttebruker-nivå gjennom henvisningssystemet! '
                        f'({unique_visits} unike besøk)',
                priority=2
            )
        except Exception as e:
            logger.error(f"Failed to create referral reward notification: {e}")

        return True
