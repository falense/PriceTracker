"""
Django settings for PriceTracker WebUI.
"""

from pathlib import Path
import os

# Import dj_database_url if available (production)
try:
    import dj_database_url
    HAS_DJ_DATABASE_URL = True
except ImportError:
    HAS_DJ_DATABASE_URL = False

# Build paths inside the project
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-dev-key-change-in-production')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv('DEBUG', 'True') == 'True'

ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')


# Application definition

INSTALLED_APPS = [
    'corsheaders',  # Must be before django.contrib.admin
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'app',
]

# Custom User Model
AUTH_USER_MODEL = 'app.CustomUser'

# Middleware configuration
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
]

# Add WhiteNoise middleware if available (production)
try:
    import whitenoise
    MIDDLEWARE.append('whitenoise.middleware.WhiteNoiseMiddleware')
except ImportError:
    pass

# Continue with rest of middleware
MIDDLEWARE.extend([
    'corsheaders.middleware.CorsMiddleware',  # After Security, before Common
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'app.middleware.BrowserExtensionCSRFMiddleware',  # Before CsrfViewMiddleware
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
])

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'app.context_processors.site_constants',
                'app.context_processors.user_tier_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# Database
# Supports both SQLite (development) and PostgreSQL (production) via DATABASE_URL

if HAS_DJ_DATABASE_URL and os.getenv('DATABASE_URL'):
    # Parse DATABASE_URL if provided (production)
    DATABASES = {
        'default': dj_database_url.config(
            default=f'sqlite:///{BASE_DIR / "db.sqlite3"}',
            conn_max_age=600,
            conn_health_checks=True,
        )
    }
else:
    # Default to SQLite for development
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': os.getenv('DATABASE_PATH', BASE_DIR / 'db.sqlite3'),
            'OPTIONS': {
                'timeout': 30,
            }
        }
    }

# Enable WAL mode for SQLite to improve concurrent access
# This allows multiple readers and one writer simultaneously
def enable_wal_mode(sender, connection, **kwargs):
    """Enable WAL mode on SQLite database for better concurrency."""
    if connection.vendor == 'sqlite':
        cursor = connection.cursor()
        cursor.execute('PRAGMA journal_mode=WAL;')
        # Explicitly set busy_timeout to 30 seconds (30000 ms)
        # This ensures connections wait up to 30s for locks instead of failing immediately
        cursor.execute('PRAGMA busy_timeout=30000;')

from django.db.backends.signals import connection_created
connection_created.connect(enable_wal_mode)


# Password validation

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization

LANGUAGE_CODE = 'nb-NO'

TIME_ZONE = 'Europe/Oslo'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Use WhiteNoise's compressed static file serving in production
if not DEBUG:
    STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Default primary key field type

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Celery Configuration
CELERY_BROKER_URL = os.getenv('REDIS_URL', 'redis://redis:6379/0')
CELERY_RESULT_BACKEND = os.getenv('REDIS_URL', 'redis://redis:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE

# Task tracking for admin monitoring
CELERY_RESULT_EXTENDED = True  # Store additional task metadata including task name
CELERY_TASK_TRACK_STARTED = True  # Track when tasks start
CELERY_TASK_SEND_SENT_EVENT = True  # Enable task-sent events

# MinIO Object Storage
MINIO_ENDPOINT = os.getenv('MINIO_ENDPOINT', 'minio:9000')
MINIO_ACCESS_KEY = os.getenv('MINIO_ROOT_USER', 'minioadmin')
MINIO_SECRET_KEY = os.getenv('MINIO_ROOT_PASSWORD', 'minioadmin')
MINIO_SECURE = os.getenv('MINIO_SECURE', 'False').lower() == 'true'

# Django Storage (for file uploads via django-storages + boto3)
# Use MinIO as S3-compatible backend in production
if not DEBUG:
    DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'

    # AWS SDK configuration for MinIO (S3-compatible)
    AWS_ACCESS_KEY_ID = MINIO_ACCESS_KEY
    AWS_SECRET_ACCESS_KEY = MINIO_SECRET_KEY
    AWS_STORAGE_BUCKET_NAME = os.getenv('AWS_STORAGE_BUCKET_NAME', 'pricetracker-media')
    AWS_S3_REGION_NAME = os.getenv('AWS_S3_REGION_NAME', 'us-east-1')  # MinIO ignores this but boto3 needs it
    AWS_S3_ENDPOINT_URL = os.getenv('AWS_S3_ENDPOINT_URL', f'https://s3.{os.getenv("DOMAIN", "localhost")}')

    # File access control (private files with signed URLs)
    AWS_DEFAULT_ACL = 'private'  # Files require authentication
    AWS_QUERYSTRING_AUTH = True  # Generate signed URLs for file access
    AWS_QUERYSTRING_EXPIRE = 3600  # Signed URLs valid for 1 hour
    AWS_S3_FILE_OVERWRITE = False  # Don't overwrite existing files

    # S3 object parameters (caching, etc.)
    AWS_S3_OBJECT_PARAMETERS = {
        'CacheControl': 'max-age=86400',  # 24 hours
    }

    # Custom domain for MinIO (if using public endpoint)
    AWS_S3_CUSTOM_DOMAIN = os.getenv('AWS_S3_CUSTOM_DOMAIN', None)

# Logging
# Note: Structlog is configured in app/apps.py AppConfig.ready() and config/celery.py
# This minimal Django LOGGING configuration is kept for compatibility but will be
# enhanced by structlog's configuration at startup.
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'simple': {
            'format': '%(levelname)s %(message)s',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
}

# Login URLs
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'

# ========== CORS Configuration for Firefox Addon ==========

# Allow credentials (session cookies) from browser extensions
CORS_ALLOW_CREDENTIALS = True

# Allow Firefox and Chrome extension origins
# Extensions have dynamic UUIDs, so we use regex matching
CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^moz-extension://.*$",  # Firefox extensions
    r"^chrome-extension://.*$",  # Chrome extensions
]

# Allow necessary headers for CSRF protection
CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',  # CRITICAL for CSRF protection
    'x-requested-with',
]

# Expose headers in response (optional, for easier debugging)
CORS_EXPOSE_HEADERS = ['X-CSRFToken']

# CSRF trusted origins for browser extensions
# Django 4.0+ requires explicit CSRF_TRUSTED_ORIGINS for cross-origin POST requests
CSRF_TRUSTED_ORIGINS = os.getenv(
    'CSRF_TRUSTED_ORIGINS',
    'http://localhost:8000,http://127.0.0.1:8000'
).split(',')

# Note: CSRF protection for moz-extension:// origins works differently
# The extension must include the CSRF token from cookies in the X-CSRFToken header

# ========== Production Security Settings ==========

if not DEBUG:
    # HTTPS/SSL Configuration
    SECURE_SSL_REDIRECT = True  # Redirect all HTTP to HTTPS
    SESSION_COOKIE_SECURE = True  # Only send session cookie over HTTPS
    CSRF_COOKIE_SECURE = True  # Only send CSRF cookie over HTTPS

    # HSTS (HTTP Strict Transport Security)
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

    # Proxy configuration (for Traefik)
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

    # Additional security headers
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'SAMEORIGIN'

    # Production logging configuration
    LOGGING['handlers']['file'] = {
        'level': 'INFO',
        'class': 'logging.handlers.RotatingFileHandler',
        'filename': BASE_DIR / 'logs' / 'django.log',
        'maxBytes': 1024 * 1024 * 100,  # 100 MB
        'backupCount': 10,
        'formatter': 'simple',
    }
    LOGGING['root']['handlers'].append('file')
