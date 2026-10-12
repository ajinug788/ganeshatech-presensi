"""Rate limit login ringan berbasis cache (TDIP AUTH-07).

Tanpa dependensi tambahan: hitung percobaan gagal per (username/email, IP)
di cache Django; maksimum 10 gagal per 5 menit.
"""
import time

from django.core.cache import cache

MAX_FAILURES = 10
WINDOW_SECONDS = 5 * 60  # 5 menit


def _client_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        # Ambil IP pertama (klien asli) — Nginx menyetel ini di production.
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "") or ""


def _cache_key(identifier, ip):
    return f"login-fail:{identifier.lower()}:{ip}"


def _window_start_key(identifier, ip):
    return f"login-fail-start:{identifier.lower()}:{ip}"


def is_locked(identifier, ip):
    """True bila identifier+IP sudah mencapai batas kegagalan."""
    return cache.get(_cache_key(identifier, ip), 0) >= MAX_FAILURES


def register_failure(identifier, ip=None):
    """Catat satu percobaan gagal. Kembalikan jumlah gagal saat ini."""
    ip = ip or ""
    key = _cache_key(identifier, ip)
    start_key = _window_start_key(identifier, ip)

    now = time.time()
    start = cache.get(start_key)
    if start is None or now - start > WINDOW_SECONDS:
        # Jendela baru.
        cache.set(start_key, now, WINDOW_SECONDS)
        cache.set(key, 1, WINDOW_SECONDS)
        return 1
    count = cache.get(key, 0) + 1
    sisa = max(int(WINDOW_SECONDS - (now - start)), 1)
    cache.set(key, count, sisa)
    return count


def reset_failures(identifier, ip=None):
    """Bersihkan hitungan gagal (mis. setelah login sukses)."""
    ip = ip or ""
    cache.delete(_cache_key(identifier, ip))
    cache.delete(_window_start_key(identifier, ip))


def check_request(request, identifier):
    """Bila melebihi batas, kembalikan message error; selain itu None."""
    if is_locked(identifier, _client_ip(request)):
        return "Terlalu banyak percobaan gagal. Coba lagi dalam beberapa menit."
    return None
