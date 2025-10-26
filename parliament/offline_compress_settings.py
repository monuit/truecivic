# A hack used to coax django-compressor to properly generate bundles
import os

from .default_settings import *

DEBUG = False
COMPRESS_ENABLED = True
COMPRESS_OFFLINE = True
COMPRESS_ROOT = os.path.join(os.path.dirname(PROJ_ROOT), 'frontend_bundles')

SECRET_KEY = 'compression!'
