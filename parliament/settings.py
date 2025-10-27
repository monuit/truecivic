"""
Production settings for truecivic Django application on Railway
"""

import dj_database_url
import os
from .default_settings import *

# Debug must be False in production
DEBUG = os.getenv('DEBUG', 'False') == 'True'

# Security settings for production
default_hosts = 'truecivic.ca,www.truecivic.ca,truecivic-ca.up.railway.app,localhost,127.0.0.1'
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', default_hosts).split(',')
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-placeholder-change-me')

RECAPTCHA_PUBLIC_KEY = os.getenv(
    'RECAPTCHA_PUBLIC_KEY', 'dummy-public-key-change-me')
RECAPTCHA_PRIVATE_KEY = os.getenv(
    'RECAPTCHA_PRIVATE_KEY', 'dummy-private-key-change-me')

# Database configuration - Railway provides DATABASE_URL via postgres service

if os.getenv('DATABASE_URL'):
    DATABASES = {
        'default': dj_database_url.config(
            default=os.getenv('DATABASE_URL'),
            conn_max_age=600,
            conn_health_checks=True,
        )
    }
else:
    # Fallback to PostgreSQL environment variables from Railway
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.getenv('PGDATABASE', 'railway'),
            'USER': os.getenv('PGUSER', 'postgres'),
            'PASSWORD': os.getenv('PGPASSWORD', ''),
            'HOST': os.getenv('PGHOST', 'localhost'),
            'PORT': os.getenv('PGPORT', '5432'),
            'CONN_MAX_AGE': 600,
        }
    }

# Redis caching from Railway (fall back to in-memory cache if no Redis URL)
REDIS_URL = os.getenv('REDIS_URL')

if REDIS_URL:
    CACHES = {
        'default': {
            'BACKEND': 'django_redis.cache.RedisCache',
            'LOCATION': REDIS_URL,
            'OPTIONS': {
                'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            }
        }
    }
    SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
    SESSION_CACHE_ALIAS = 'default'
else:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'truecivic-default'
        }
    }
    SESSION_ENGINE = 'django.contrib.sessions.backends.db'

# Static files handling for production
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(os.path.dirname(PROJ_ROOT), 'staticfiles')
COMPRESS_ROOT = STATIC_ROOT

# Enable WhiteNoise for static files
MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')

# Security headers
SECURE_SSL_REDIRECT = not DEBUG
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True

CSRF_TRUSTED_ORIGINS = os.getenv(
    'CSRF_TRUSTED_ORIGINS', 'https://truecivic.ca,https://www.truecivic.ca'
).split(',')

# Email configuration
PARLIAMENT_SEND_EMAIL = True
# Change to proper email backend
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Site configuration
fallback_host = ALLOWED_HOSTS[0] if ALLOWED_HOSTS[0] != '*' else 'truecivic.ca'
SITE_URL = os.getenv('SITE_URL', f'https://{fallback_host}')

# Logging configuration for production
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': os.getenv('DJANGO_LOG_LEVEL', 'INFO'),
            'propagate': False,
        },
    },
}

# Enable offline compressor bundles produced during image build
COMPRESS_ENABLED = True
COMPRESS_OFFLINE = True

# Hansard cache directory
HANSARD_CACHE_DIR = os.path.join(os.path.dirname(PROJ_ROOT), 'hansard-cache')

print(
    f"Django settings loaded: DEBUG={DEBUG}, DATABASES configured: {bool(DATABASES.get('default'))}")
