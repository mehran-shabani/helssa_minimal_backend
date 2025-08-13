# medogram/settings.py
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv('SECRET_KEY', default='django-insecure-change-me')
DEBUG = False

ALLOWED_HOSTS = ['*']
# cors --------------------
CORS_ALLOWED_ORIGINS = [
    'http://localhost:3000',
    'http://127.0.0.1:3000',
    'https://medogram.ir',
    'https://helssa.ir',
    'https://django-med.chbk.app',
]

CORS_ALLOW_HEADERS = [
    'authorization',
    'content-type',
    'x-csrftoken',
    'accept'
]


CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True
ROOT_URLCONF = 'medogram.urls'


# csrf -------------
CSRF_TRUSTED_ORIGINS = [
    "https://medogram.ir",
    "https://www.medogram.ir",
    "https://helssa.ir",
    "https://www.helssa.ir",
    "https://api.medogram.ir",
    "https://django-med.chbk.app"
]

# فقط در صورت نیاز به به‌اشتراک‌گذاری کوکی‌ها بین دامنه‌ها:
CSRF_COOKIE_DOMAIN = ".medogram.ir"  # اگر تمام زیر دامنه‌ها باید به CSRF cookie دسترسی داشته باشند
CSRF_COOKIE_SAMESITE = "None"        # برای پشتیبانی از cross-origin
CSRF_COOKIE_SECURE = True            # حتماً فعال باشد چون HTTPS دارید


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
    'chatbot.apps.ChatBotConfig',
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
    "default": {
        # موتور پایگاه‌داده (پیش‌فرض: MySQL)
        "ENGINE": os.getenv("DB_ENGINE", 'django.db.backends.sqlite3'),

        # نام پایگاه‌داده
        "NAME": os.getenv("DB_DATABASE", f'{BASE_DIR}, db.sqlite3'),

        # اعتبارسنجی کاربر
        "USER": os.getenv("DB_USERNAME", None),
        "PASSWORD": os.getenv("DB_PASSWORD", None),

        # مشخصات سرور
        "HOST": os.getenv("DB_HOST", None),
        "PORT": os.getenv("DB_PORT", None),

        # نگه‌داری اتصال برحسب ثانیه (اختیاری)
        "CONN_MAX_AGE": int(os.getenv("DB_CONN_MAX_AGE", "0")),

        # گزینه‌های توصیه‌شده برای MySQL
        "OPTIONS": {
            "charset": "utf8mb4",
            "sql_mode": "STRICT_TRANS_TABLES",
        },
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

STATIC_URL = '/static/'
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
EMAIL_USE_SSL = os.getenv('EMAIL_USE_SSL', default=False)
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', default=False)
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', default=None)
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', default=None)



# pass
TALKBOT_API_KEY = os.getenv('TALKBOT_API_KEY', default='sk-your-api-key-here')
TALKBOT_BASE_URL = os.getenv('TALKBOT_BASE_URL', default='https://api.talkbot.ir/v1/')
BITPAY_API_KEY = os.getenv('BITPAY_API_KEY', default='your-bitpay-api-key-here')
KAVEH_NEGAR_API_KEY = os.getenv('KAVEH_NEGAR_API_KEY', default='your-kaveh-negar-api-key-here')


CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "unique-snowflake",   # نام دلخواه برای ناحیهٔ cache
        "TIMEOUT": None,                  # اختیاری؛ None یعنی بدون انقضا
    }
}


# Session Configuration
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'default'


# ---- GapGPT / OpenAI compatible ----
GAPGPT_BASE_URL = os.getenv('GAPGPT_BASE_URL', 'https://api.gapgpt.app/v1')
GAPGPT_API_KEY  = os.getenv('GAPGPT_API_KEY') or os.getenv('OPENAI_API_KEY')

# مدل‌ها
VISION_MODEL_NAME   = os.getenv('VISION_MODEL_NAME', 'gpt-4o')        # برای بینایی
SUMMARY_MODEL_NAME  = os.getenv('SUMMARY_MODEL_NAME', 'o3-mini')      # یا 'gpt-4o-mini'

# توکن‌ها
RESPONSE_MAX_TOKENS = int(os.getenv('RESPONSE_MAX_TOKENS', '1500'))
SUMMARY_MAX_TOKENS  = int(os.getenv('SUMMARY_MAX_TOKENS', '900'))
