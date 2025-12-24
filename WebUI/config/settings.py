"""
Django settings for PriceTracker WebUI.
"""

from pathlib import Path
import os

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

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',  # After Security, before Common
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

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
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# Database
# SQLite for MVP, shared with other components

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.getenv('DATABASE_PATH', BASE_DIR.parent / 'db.sqlite3'),
        'OPTIONS': {
            'timeout': 30,  # Increased timeout for concurrent access
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

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

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

# Allow Firefox extension origins (moz-extension:// protocol)
# Extensions have dynamic UUIDs, so we use regex matching
CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^moz-extension://.*$",  # Firefox extensions
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
CSRF_TRUSTED_ORIGINS = [
    'http://localhost:8000',
    'http://127.0.0.1:8000',
]

# Note: CSRF protection for moz-extension:// origins works differently
# The extension must include the CSRF token from cookies in the X-CSRFToken header
