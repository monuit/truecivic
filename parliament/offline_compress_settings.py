# A hack used to coax django-compressor to properly generate bundles
import os

from .default_settings import *

DEBUG = False
STATIC_ROOT = os.path.realpath(os.path.join(
    os.path.dirname(PROJ_ROOT), 'staticfiles'))
COMPRESS_ENABLED = True
COMPRESS_OFFLINE = True
COMPRESS_ROOT = STATIC_ROOT

# Use an in-memory SQLite database so offline compression does not require
# external services during image builds.
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

SECRET_KEY = 'compression!'
