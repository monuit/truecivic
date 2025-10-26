# A hack used to coax django-compressor to properly generate bundles
import os

from .default_settings import *

DEBUG = False
STATIC_ROOT = os.path.realpath(os.path.join(
    os.path.dirname(PROJ_ROOT), 'staticfiles'))
COMPRESS_ENABLED = True
COMPRESS_OFFLINE = True
COMPRESS_ROOT = STATIC_ROOT

# Fallback to an in-memory SQLite database only if no database configuration
# is provided. Railway will inject DATABASE_URL so Postgres remains the default.
if not os.environ.get('DATABASE_URL'):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': ':memory:',
        }
    }

SECRET_KEY = 'compression!'
