"""
Business logic services for WebUI.

These services coordinate complex operations between models, tasks, and external systems.
"""

from .models import Product, Pattern, Notification, PriceHistory, AdminFlag
from .utils.currency import format_price, get_currency_from_domain
from django.utils import timezone
from django.contrib.auth.models import User
from urllib.parse import urlparse
from decimal import Decimal
import uuid
import logging

logger = logging.getLogger(__name__)


class ProductService:
    """Business logic for product management."""

    @staticmethod
    def add_product(user: User, url: str, priority: str = 'normal', target_price=None) -> Product:
        """
        Add new product and trigger pattern generation if needed.

        This is the main entry point for adding products. It handles:
        - Domain extraction
        - Duplicate detection
        - Multi-user product sharing
        - Pattern generation triggering
        - Initial price fetch

        Args:
            user: User object
            url: Product URL to track
            priority: 'high', 'normal', or 'low'
            target_price: Optional target price for alerts

        Returns:
            Product: Created or existing product instance
        """
        # Parse and clean domain
        parsed = urlparse(url)
        domain = parsed.netloc.replace('www.', '').lower()

        if not domain:
            raise ValueError("Invalid URL: Could not extract domain")

        # Check if product already exists for this URL
        existing = Product.objects.filter(url=url, user=user).first()
        if existing:
            # User is re-adding their own product - reactivate if needed
            if not existing.active:
                existing.active = True
                existing.priority = priority
                if target_price:
                    existing.target_price = target_price
                existing.save()
                logger.info(f"Reactivated product {existing.id} for user {user.username}")
            return existing

        # Check if other users are tracking this URL
        other_user_product = Product.objects.filter(url=url).exclude(user=user).first()
        if other_user_product:
            # Clone product for this user (shares pattern)
            product = ProductService._clone_product(other_user_product, user, priority, target_price)
            logger.info(f"Cloned product {product.id} from existing product for user {user.username}")
        else:
            # Create new product with domain-based currency
            currency_code, _ = get_currency_from_domain(domain)
            product = Product.objects.create(
                id=uuid.uuid4(),
                user=user,
                url=url,
                domain=domain,
                name=f"Product from {domain}",  # Temporary name, updated after first fetch
                priority=priority,
                target_price=target_price,
                currency=currency_code,
            )
            logger.info(f"Created new product {product.id} for user {user.username} with currency {currency_code}")

        # Check if pattern exists for domain
        pattern = Pattern.objects.filter(domain=domain).first()
        if not pattern:
            logger.info(f"No pattern found for {domain}, triggering generation")
            ProductService._trigger_pattern_generation(url, domain, str(product.id))
        else:
            logger.info(f"Pattern exists for {domain} (success rate: {pattern.success_rate:.1%})")

        # Trigger immediate price fetch
        ProductService._trigger_fetch(str(product.id))

        return product

    @staticmethod
    def _trigger_pattern_generation(url: str, domain: str, product_id: str = None):
        """
        Trigger ExtractorPatternAgent to generate patterns.
        Uses Celery for async execution.

        Args:
            url: Product URL to analyze
            domain: Domain name
            product_id: Optional product ID for tracking

        Returns:
            str: Task ID
        """
        from .tasks import generate_pattern

        try:
            task = generate_pattern.delay(url, domain, product_id)
            logger.info(f"Pattern generation task {task.id} started for {domain}")
            return task.id
        except Exception as e:
            logger.error(f"Failed to trigger pattern generation for {domain}: {e}")
            # Create admin flag for failed pattern generation
            AdminFlag.objects.create(
                flag_type='pattern_generation_failed',
                domain=domain,
                url=url,
                error_message=str(e),
                status='pending'
            )
            raise

    @staticmethod
    def _trigger_fetch(product_id: str):
        """
        Trigger immediate price fetch for new product.

        Args:
            product_id: Product UUID as string

        Returns:
            str: Task ID
        """
        from .tasks import fetch_product_price

        try:
            task = fetch_product_price.delay(product_id)
            logger.info(f"Price fetch task {task.id} started for product {product_id}")
            return task.id
        except Exception as e:
            logger.error(f"Failed to trigger price fetch for product {product_id}: {e}")
            raise

    @staticmethod
    def _clone_product(source: Product, new_user: User, priority: str = 'normal', target_price=None) -> Product:
        """
        Clone product for different user.

        This allows multiple users to track the same product while sharing
        the extraction pattern.

        Args:
            source: Source product to clone
            new_user: New user to assign product to
            priority: Priority for new product
            target_price: Optional target price

        Returns:
            Product: New product instance
        """
        return Product.objects.create(
            id=uuid.uuid4(),
            user=new_user,
            url=source.url,
            domain=source.domain,
            name=source.name,
            current_price=source.current_price,
            currency=source.currency,
            available=source.available,
            image_url=source.image_url,
            priority=priority,
            target_price=target_price,
            pattern_version=source.pattern_version,
        )

    @staticmethod
    def update_product_settings(product: Product, **kwargs) -> Product:
        """
        Update product settings.

        Args:
            product: Product instance to update
            **kwargs: Fields to update (priority, target_price, notify_on_drop, etc.)

        Returns:
            Product: Updated product instance
        """
        allowed_fields = [
            'priority', 'target_price', 'notify_on_drop',
            'notify_on_restock', 'active'
        ]

        for field, value in kwargs.items():
            if field in allowed_fields:
                setattr(product, field, value)

        product.save()
        logger.info(f"Updated settings for product {product.id}")
        return product

    @staticmethod
    def refresh_price(product: Product):
        """
        Trigger immediate price refresh for product.

        Args:
            product: Product to refresh

        Returns:
            str: Task ID
        """
        return ProductService._trigger_fetch(str(product.id))


class NotificationService:
    """Create and manage notifications."""

    @staticmethod
    def create_price_drop_notification(product: Product, old_price: Decimal, new_price: Decimal):
        """
        Create price drop notification.

        Args:
            product: Product with price change
            old_price: Previous price
            new_price: New (lower) price

        Returns:
            Notification or None if not created
        """
        if not product.notify_on_drop:
            logger.debug(f"Price drop notifications disabled for product {product.id}")
            return None

        if new_price >= old_price:
            logger.debug(f"Price did not drop for product {product.id}")
            return None

        drop_amount = old_price - new_price
        drop_percent = (drop_amount / old_price) * 100

        old_price_formatted = format_price(float(old_price), domain=product.domain)
        new_price_formatted = format_price(float(new_price), domain=product.domain)
        drop_formatted = format_price(float(drop_amount), domain=product.domain)

        message = (
            f"{product.name} dropped from {old_price_formatted} to {new_price_formatted} "
            f"(-{drop_formatted}, -{drop_percent:.1f}%)"
        )

        notification = Notification.objects.create(
            user=product.user,
            product=product,
            notification_type='price_drop',
            message=message,
            old_price=old_price,
            new_price=new_price,
        )

        logger.info(f"Created price drop notification for product {product.id}")
        return notification

    @staticmethod
    def create_target_reached_notification(product: Product):
        """
        Notify when target price is reached.

        Args:
            product: Product that reached target

        Returns:
            Notification or None if not created
        """
        if not product.target_price:
            return None

        if not product.current_price:
            return None

        if product.current_price > product.target_price:
            return None

        # Check if we already notified about this (avoid spam)
        recent_target_notification = Notification.objects.filter(
            product=product,
            notification_type='target_reached',
            created_at__gte=timezone.now() - timezone.timedelta(hours=24)
        ).exists()

        if recent_target_notification:
            logger.debug(f"Already notified about target price for product {product.id} in last 24h")
            return None

        current_formatted = format_price(float(product.current_price), domain=product.domain)
        target_formatted = format_price(float(product.target_price), domain=product.domain)

        message = (
            f"{product.name} reached your target price! "
            f"Now {current_formatted} (target: {target_formatted})"
        )

        notification = Notification.objects.create(
            user=product.user,
            product=product,
            notification_type='target_reached',
            message=message,
            new_price=product.current_price,
        )

        logger.info(f"Created target reached notification for product {product.id}")
        return notification

    @staticmethod
    def create_restock_notification(product: Product):
        """
        Notify when product comes back in stock.

        Args:
            product: Product that was restocked

        Returns:
            Notification or None if not created
        """
        if not product.notify_on_restock:
            return None

        if not product.available:
            return None

        # Check if we already notified about restock recently
        recent_restock_notification = Notification.objects.filter(
            product=product,
            notification_type='restock',
            created_at__gte=timezone.now() - timezone.timedelta(hours=24)
        ).exists()

        if recent_restock_notification:
            logger.debug(f"Already notified about restock for product {product.id} in last 24h")
            return None

        message = f"{product.name} is back in stock!"
        if product.current_price:
            price_formatted = format_price(float(product.current_price), domain=product.domain)
            message += f" Price: {price_formatted}"

        notification = Notification.objects.create(
            user=product.user,
            product=product,
            notification_type='restock',
            message=message,
            new_price=product.current_price,
        )

        logger.info(f"Created restock notification for product {product.id}")
        return notification

    @staticmethod
    def create_price_spike_notification(product: Product, old_price: Decimal, new_price: Decimal):
        """
        Create notification for significant price increase.

        Args:
            product: Product with price increase
            old_price: Previous price
            new_price: New (higher) price

        Returns:
            Notification or None if not created
        """
        if new_price <= old_price:
            return None

        spike_amount = new_price - old_price
        spike_percent = (spike_amount / old_price) * 100

        # Only notify on significant spikes (>20%)
        if spike_percent < 20:
            return None

        old_price_formatted = format_price(float(old_price), domain=product.domain)
        new_price_formatted = format_price(float(new_price), domain=product.domain)
        spike_formatted = format_price(float(spike_amount), domain=product.domain)

        message = (
            f"{product.name} price increased from {old_price_formatted} to {new_price_formatted} "
            f"(+{spike_formatted}, +{spike_percent:.1f}%)"
        )

        notification = Notification.objects.create(
            user=product.user,
            product=product,
            notification_type='price_spike',
            message=message,
            old_price=old_price,
            new_price=new_price,
        )

        logger.info(f"Created price spike notification for product {product.id}")
        return notification

    @staticmethod
    def check_and_create_notifications(product: Product, old_price: Decimal = None):
        """
        Check product state and create appropriate notifications.

        This is called after price fetches to check if any notifications
        should be created.

        Args:
            product: Product to check
            old_price: Previous price (if known)

        Returns:
            list: Created notifications
        """
        notifications = []

        # Price change notifications
        if old_price and product.current_price:
            if product.current_price < old_price:
                notif = NotificationService.create_price_drop_notification(
                    product, old_price, product.current_price
                )
                if notif:
                    notifications.append(notif)
            elif product.current_price > old_price:
                notif = NotificationService.create_price_spike_notification(
                    product, old_price, product.current_price
                )
                if notif:
                    notifications.append(notif)

        # Target price notification
        notif = NotificationService.create_target_reached_notification(product)
        if notif:
            notifications.append(notif)

        # Restock notification (if product was previously unavailable)
        if product.available:
            # Check if product was previously unavailable
            last_history = PriceHistory.objects.filter(
                product=product,
                available=False
            ).order_by('-recorded_at').first()

            if last_history:
                notif = NotificationService.create_restock_notification(product)
                if notif:
                    notifications.append(notif)

        return notifications

    @staticmethod
    def mark_all_as_read(user: User):
        """
        Mark all notifications as read for user.

        Args:
            user: User whose notifications to mark

        Returns:
            int: Number of notifications marked
        """
        count = Notification.objects.filter(
            user=user,
            read=False
        ).update(read=True, read_at=timezone.now())

        logger.info(f"Marked {count} notifications as read for user {user.username}")
        return count
