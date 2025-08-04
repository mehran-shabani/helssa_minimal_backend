# medogram/medogram/settings.py
from pathlib import Path
import sys
import os

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv('SECRET_KEY', default='django-insecure-change-me')
DEBUG = os.getenv('DEBUG', default=True)

ALLOWED_HOSTS = ['*']

CORS_ALLOWED_ORIGINS = [
    'http://localhost:3000',
    'http://127.0.0.1:3000',
    'https://medogram.ir',
    'https://pwa.medogram.ir',

]
# --------------  CSRF_TRUSTED_ORIGINS  --------------
# از Django 4.0 به بعد باید scheme هم صراحتاً ذکر شود.
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
]
CORS_ALLOW_CREDENTIALS = True


INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'telemedicine.apps.TelemedicineConfig',
    'kavenegar',
    'rest_framework',
    'rest_framework_simplejwt',
    'drf_yasg',
    'corsheaders',
    'simple_history',
    'medagent.apps.MedAgentConfig',
    'certificate.apps.CertificateConfig',
    'down.apps.DownConfig',
    'doctor_online.apps.DoctorOnlineConfig',
    'sub.apps.SubConfig',

]



AUTH_USER_MODEL = 'telemedicine.CustomUser'
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 3,
}

from datetime import timedelta

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(days=15), 
    'REFRESH_TOKEN_LIFETIME': timedelta(days=20), 
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,  
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY, 
    'VERIFYING_KEY': None,
    'AUTH_HEADER_TYPES': ('Bearer',), 
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    'TOKEN_TYPE_CLAIM': 'token_type',
    'JTI_CLAIM': 'jti',

    'SLIDING_TOKEN_REFRESH_EXP_CLAIM': 'refresh_exp',
    'SLIDING_TOKEN_LIFETIME': timedelta(minutes=5),
    'SLIDING_TOKEN_REFRESH_LIFETIME': timedelta(days=1),
}
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
CORS_ALLOW_ALL_ORIGINS = True
ROOT_URLCONF = 'medogram.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates',

                 ],
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

WSGI_APPLICATION = 'medogram.wsgi.application'
# تنظیمات دیتابیس
DATABASES = {
    'default': {
        'ENGINE': os.getenv('DB_ENGINE', default='django.db.backends.sqlite3'),
        'NAME': os.getenv('DB_NAME', default=BASE_DIR / 'db.sqlite3'),
        'USER': os.getenv('DB_USER', default=None),
        'PASSWORD': os.getenv('DB_PASSWORD', default=None),
        'HOST': os.getenv('DB_HOST', default=None),
        'PORT': os.getenv('DB_PORT', default=None),
        'CONN_MAX_AGE': os.getenv('DB_CONN_MAX_AGE', default=0),
        
    }
}






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

# logging
"""
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': 'django_debug.log',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG', 
        },
        'django.db.backends': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
        },
    },
}
"""

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'static'


DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

MEDIA_ROOT = BASE_DIR / 'media'
MEDIA_URL = '/media/'
# Maximum upload file size (10MB)
MAX_UPLOAD_SIZE = 10485760

# Image upload settings
IMAGE_UPLOAD_SETTINGS = {
    'quality': 85,
    'formats': ['JPEG', 'PNG', 'HEIC', 'HEIF'],  
    'max_image_dimension': 4000,
    'min_image_dimension': 300,
}

EMAIL_BACKEND = os.getenv('EMAIL_BACKEND', default=None)
EMAIL_HOST = os.getenv('EMAIL_HOST', default=None)
EMAIL_PORT = os.getenv('EMAIL_PORT', default=None)
EMAIL_USE_SSL = os.getenv('EMAIL_USE_SSL', default=True)
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', default=False)
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', default=None)
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', default=None)


CHATBOT_PLUS_SETTINGS = {"MAX_TITLE_LENGTH": 50}
# pass
TALKBOT_API_KEY = os.getenv('TALKBOT_API_KEY', default='sk-your-api-key-here')
TALKBOT_BASE_URL = os.getenv('TALKBOT_BASE_URL', default='https://api.talkbot.ir')
BITPAY_API_KEY = os.getenv('BITPAY_API_KEY', default='your-bitpay-api-key-here')
KAVEH_NEGAR_API_KEY = os.getenv('KAVEH_NEGAR_API_KEY', default='your-kaveh-negar-api-key-here')
CORS_ALLOW_HEADERS = [
    'authorization',
    'content-type',
    'x-csrftoken',
    'accept'
]
# main_site
SITE_URL = 'https://medogram.ir'
# ChatBot Plus Settings
CHATBOT_PLUS_SETTINGS = {
    'MAX_SESSIONS_PER_USER': 100,
    'MAX_MESSAGES_PER_SESSION': 200,
    'SESSION_TIMEOUT_HOURS': 24,
    'DEFAULT_TOKEN_ESTIMATION_MULTIPLIER': 1.2,
    'MAX_SUMMARY_LENGTH': 2000,
    'MAX_TITLE_LENGTH': 50,
    'ENABLE_CONVERSATION_MEMORY': True,
    'MEMORY_BUFFER_SIZE': 10,
    'MEMORY_MAX_TOKENS': 8000,
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "unique-snowflake",   # نام دلخواه برای ناحیهٔ cache
        "TIMEOUT": None,                  # اختیاری؛ None یعنی بدون انقضا
    }
}

if 'test' in sys.argv:
    TALKBOT_API_KEY = 'test-key'

# Session Configuration
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'default'
