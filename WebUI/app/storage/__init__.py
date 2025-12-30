"""
MinIO object storage client for PriceTracker.

Provides artifact storage for HTML, screenshots, and cached product images.
Designed for distributed architecture - path computation requires no database access.
"""

import hashlib
from io import BytesIO
from typing import Optional
from urllib.parse import urlparse
from datetime import timedelta

import structlog
from django.conf import settings
from minio import Minio
from minio.error import S3Error

logger = structlog.get_logger(__name__)


def get_artifact_path(url: str, artifact_type: str = 'html') -> str:
    """
    Compute deterministic S3 path from URL (no DB required).

    Supports distributed architecture where fetchers don't have DB access.
    GHA and external services can compute paths independently.

    Args:
        url: Product URL
        artifact_type: 'html' or 'screenshot'

    Returns:
        S3 object key (e.g., "komplett_no/3f4a5b6c7d8e9f0a/latest.html")

    Examples:
        >>> get_artifact_path("https://komplett.no/product/1234", "html")
        'komplett_no/3f4a5b6c7d8e9f0a/latest.html'
        >>> get_artifact_path("https://komplett.no/product/1234", "screenshot")
        'komplett_no/3f4a5b6c7d8e9f0a/latest.png'
    """
    parsed = urlparse(url)
    domain = parsed.netloc.replace('.', '_').replace('-', '_')

    # 16-char SHA256 hash (collision probability: ~1 in 10^19)
    url_hash = hashlib.sha256(url.encode('utf-8')).hexdigest()[:16]

    if artifact_type == 'html':
        return f"{domain}/{url_hash}/latest.html"
    elif artifact_type == 'screenshot':
        return f"{domain}/{url_hash}/latest.png"
    else:
        raise ValueError(f"Unknown artifact type: {artifact_type}")


def get_image_path(image_url: str) -> str:
    """
    Compute deterministic image cache path from image URL.

    Args:
        image_url: Product image URL

    Returns:
        S3 object key for cached image

    Examples:
        >>> get_image_path("https://example.com/image.jpg")
        '5f2b3a1c4e8d9f0a.jpg'
    """
    # Hash the full URL for uniqueness
    url_hash = hashlib.sha256(image_url.encode('utf-8')).hexdigest()[:16]

    # Try to extract extension from URL
    parsed = urlparse(image_url)
    path = parsed.path.lower()

    if path.endswith('.jpg') or path.endswith('.jpeg'):
        ext = 'jpg'
    elif path.endswith('.png'):
        ext = 'png'
    elif path.endswith('.webp'):
        ext = 'webp'
    elif path.endswith('.gif'):
        ext = 'gif'
    else:
        ext = 'jpg'  # Default fallback

    return f"{url_hash}.{ext}"


class MinIOClient:
    """
    Singleton MinIO client with graceful degradation.

    Features:
    - Automatic bucket creation
    - Connection pooling via singleton pattern
    - Graceful failure handling (returns None instead of raising)
    - Presigned URL generation for public/private access
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True
        self._client = None
        self._available = False

        try:
            # Get configuration from Django settings
            endpoint = settings.MINIO_ENDPOINT
            access_key = settings.MINIO_ACCESS_KEY
            secret_key = settings.MINIO_SECRET_KEY
            secure = settings.MINIO_SECURE

            # Create MinIO client
            self._client = Minio(
                endpoint,
                access_key=access_key,
                secret_key=secret_key,
                secure=secure
            )

            # Test connection and create buckets
            self._initialize_buckets()
            self._available = True

            logger.info(
                "minio_initialized",
                endpoint=endpoint,
                secure=secure,
                buckets=['artifacts', 'screenshots', 'images']
            )

        except Exception as e:
            logger.warning(
                "minio_initialization_failed",
                error=str(e),
                message="MinIO unavailable - artifacts will not be saved"
            )
            self._available = False

    def _initialize_buckets(self):
        """Create required buckets if they don't exist."""
        buckets = ['artifacts', 'screenshots', 'images']

        for bucket in buckets:
            try:
                if not self._client.bucket_exists(bucket):
                    self._client.make_bucket(bucket)
                    logger.info("minio_bucket_created", bucket=bucket)

                    # Make images bucket public for direct access
                    if bucket == 'images':
                        # Public read policy for images bucket
                        policy = {
                            "Version": "2012-10-17",
                            "Statement": [
                                {
                                    "Effect": "Allow",
                                    "Principal": {"AWS": "*"},
                                    "Action": ["s3:GetObject"],
                                    "Resource": [f"arn:aws:s3:::{bucket}/*"]
                                }
                            ]
                        }
                        import json
                        self._client.set_bucket_policy(bucket, json.dumps(policy))
                        logger.info("minio_bucket_public", bucket=bucket)

            except Exception as e:
                logger.error("minio_bucket_creation_failed", bucket=bucket, error=str(e))
                raise

    def health_check(self) -> bool:
        """Check if MinIO is available."""
        return self._available and self._client is not None

    def upload_html(self, object_path: str, html_content: str) -> bool:
        """
        Upload HTML artifact to MinIO.

        Args:
            object_path: S3 object key (from get_artifact_path())
            html_content: HTML string

        Returns:
            True if upload succeeded, False otherwise
        """
        if not self.health_check():
            return False

        try:
            data = html_content.encode('utf-8')
            self._client.put_object(
                'artifacts',
                object_path,
                BytesIO(data),
                length=len(data),
                content_type='text/html'
            )
            logger.debug("html_artifact_uploaded", path=object_path, size=len(data))
            return True

        except Exception as e:
            logger.error("html_upload_failed", path=object_path, error=str(e))
            return False

    def upload_screenshot(self, object_path: str, screenshot_bytes: bytes) -> bool:
        """
        Upload screenshot to MinIO.

        Args:
            object_path: S3 object key (from get_artifact_path())
            screenshot_bytes: PNG image bytes

        Returns:
            True if upload succeeded, False otherwise
        """
        if not self.health_check():
            return False

        try:
            self._client.put_object(
                'screenshots',
                object_path,
                BytesIO(screenshot_bytes),
                length=len(screenshot_bytes),
                content_type='image/png'
            )
            logger.debug("screenshot_uploaded", path=object_path, size=len(screenshot_bytes))
            return True

        except Exception as e:
            logger.error("screenshot_upload_failed", path=object_path, error=str(e))
            return False

    def cache_image(self, image_url: str, image_bytes: bytes, content_type: str = 'image/jpeg') -> bool:
        """
        Cache product image to MinIO.

        Args:
            image_url: Original image URL (used to compute cache key)
            image_bytes: Image data
            content_type: Image MIME type

        Returns:
            True if upload succeeded, False otherwise
        """
        if not self.health_check():
            return False

        try:
            object_path = get_image_path(image_url)
            self._client.put_object(
                'images',
                object_path,
                BytesIO(image_bytes),
                length=len(image_bytes),
                content_type=content_type
            )
            logger.debug("image_cached", url=image_url, path=object_path, size=len(image_bytes))
            return True

        except Exception as e:
            logger.error("image_cache_failed", url=image_url, error=str(e))
            return False

    def get_cached_image_url(self, image_url: str) -> Optional[str]:
        """
        Get presigned URL for cached image if it exists.

        Args:
            image_url: Original image URL

        Returns:
            Presigned URL if cached, None otherwise
        """
        if not self.health_check():
            return None

        try:
            object_path = get_image_path(image_url)

            # Check if object exists
            self._client.stat_object('images', object_path)

            # Generate presigned URL (valid for 1 hour)
            url = self._client.presigned_get_object(
                'images',
                object_path,
                expires=timedelta(hours=1)
            )
            return url

        except S3Error as e:
            if e.code == 'NoSuchKey':
                # Object doesn't exist (cache miss)
                return None
            logger.error("image_url_generation_failed", path=object_path, error=str(e))
            return None

        except Exception as e:
            logger.error("image_url_generation_failed", url=image_url, error=str(e))
            return None

    def is_image_cached(self, image_url: str) -> bool:
        """
        Check if image is already cached.

        Args:
            image_url: Original image URL

        Returns:
            True if cached, False otherwise
        """
        if not self.health_check():
            return False

        try:
            object_path = get_image_path(image_url)
            self._client.stat_object('images', object_path)
            return True

        except S3Error as e:
            if e.code == 'NoSuchKey':
                return False
            return False

        except Exception:
            return False

    def get_artifact_url(self, object_path: str, bucket: str = 'artifacts') -> Optional[str]:
        """
        Get presigned URL for artifact (for debugging/admin access).

        Args:
            object_path: S3 object key
            bucket: Bucket name ('artifacts' or 'screenshots')

        Returns:
            Presigned URL if object exists, None otherwise
        """
        if not self.health_check():
            return None

        try:
            # Check if object exists
            self._client.stat_object(bucket, object_path)

            # Generate presigned URL (valid for 1 hour)
            url = self._client.presigned_get_object(
                bucket,
                object_path,
                expires=timedelta(hours=1)
            )
            return url

        except S3Error as e:
            if e.code == 'NoSuchKey':
                return None
            logger.error("artifact_url_generation_failed", path=object_path, error=str(e))
            return None

        except Exception as e:
            logger.error("artifact_url_generation_failed", path=object_path, error=str(e))
            return None


# Global singleton instance
minio_client = MinIOClient()
