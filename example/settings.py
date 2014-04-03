""" Settings for Django project """
import os

PROJECT_PATH = os.path.realpath(os.path.dirname(__file__))
TEMPLATE_DIRS = ( os.path.join(PROJECT_PATH, 'templates'),)

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3', # Add 'postgresql_psycopg2', 'mysql', 'sqlite3' or 'oracle'.
        'NAME': os.path.join(PROJECT_PATH, 'database/database.sqlite3'),                      # Or path to database file if using sqlite3.
        'USER': '',                      # Not used with sqlite3.
        'PASSWORD': '',                  # Not used with sqlite3.
        'HOST': '',                      # Set to empty string for localhost. Not used with sqlite3.
        'PORT': '',                      # Set to empty string for default. Not used with sqlite3.
    }
}

SESSION_ENGINE = 'django.contrib.sessions.backends.signed_cookies'

USE_L10N = True
USE_TZ = True

# Media folder isn't used, but required by models
MEDIA_ROOT = os.path.join(PROJECT_PATH, 'media')
MEDIA_URL = '/media/'

MIDDLEWARE_CLASSES = (
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.middleware.http.ConditionalGetMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
)

ROOT_URLCONF = 'myproj.urls'

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    'django.contrib.messages',
    'swiftbrowser',
    'jfu',
)
TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
   
)
TEMPLATE_CONTEXT_PROCESSORS = {
    'django.core.context_processors.request',
    'django.core.context_processors.static',
}
FILE_UPLOAD_HANDLERS = (
    'progressbarupload.uploadhandler.ProgressBarUploadHandler',
    'django.core.files.uploadhandler.MemoryFileUploadHandler',
    'django.core.files.uploadhandler.TemporaryFileUploadHandler',    
)


LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse'
        }
    },
    'handlers': {
        'mail_admins': {
            'level': 'ERROR',
            'filters': ['require_debug_false'],
            'class': 'django.utils.log.AdminEmailHandler'
        }
    },
    'loggers': {
        'django.request': {
            'handlers': ['mail_admins'],
            'level': 'ERROR',
            'propagate': True,
        },
    }
}
DEFAULT_FILE_STORAGE='swift.storage.SwiftStorage'

SWIFT_AUTH_URL = 'http://127.0.0.1:8080/auth/v2.0/'
SWIFT_AUTH_VERSION = 2 # 2 for keystone
STORAGE_URL = 'http://127.0.0.1:8080/v1/'
BASE_URL = 'http://127.0.0.1'
SWAUTH_URL = 'http://127.0.0.1:8080/auth/v2'
STATIC_DIR = '/var/www/myproj/static'

TIME_ZONE = 'America/Toronto'
LANGUAGE_CODE = 'en-en'
SECRET_KEY = 'DONT_USE_THIS_IN_PRODUCTION'
STATIC_URL = "/static/"
STATIC_ROOT = "/var/www/myproj/static/"

# For django-storage-swift. 
SWIFT_USERNAME = 'username'
SWIFT_TENANT_NAME = 'TENANT'
SWIFT_BASE_URL = BASE_URL
SWIFT_KEY = 'yourkey'
SWIFT_CONTAINER_NAME = '/'

ALLOWED_HOSTS = ['127.0.0.1', 'insert_your_hostname_here']

DEBUG = True