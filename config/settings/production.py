"""Production: DEBUG off, semua secret dari environment (TDIP §13)."""
from .base import *  # noqa: F401,F403

DEBUG = False

# Hardening (TDIP §13.1; HTTPS diaktifkan via env di belakang reverse proxy)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = env.bool("DJANGO_SECURE_SSL_REDIRECT", default=True)
SECURE_HSTS_SECONDS = env.int("DJANGO_SECURE_HSTS_SECONDS", default=0)  # 31536000 setelah TLS stabil
