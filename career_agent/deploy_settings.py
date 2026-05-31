import os

from .settings import *  # noqa: F401,F403

DEBUG = False
SECRET_KEY = os.getenv(
    "DJANGO_SECRET_KEY",
    "deployment-check-placeholder-set-django-secret-key-before-real-hosting-2026",
)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", "https://localhost")

SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = env_int("DJANGO_SECURE_HSTS_SECONDS", 31536000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", True)
SECURE_HSTS_PRELOAD = env_bool("DJANGO_SECURE_HSTS_PRELOAD", True)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
