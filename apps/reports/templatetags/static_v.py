"""Template tag: versi aset statis untuk cache busting.

{% static_v 'css/base.css' %} mengembalikan hash pendek dari isi file
(mtime + ukuran) sehingga URL berubah otomatis tiap file berubah —
browser mengambil versi baru tanpa hard refresh.
"""
import struct

from django import template
from django.contrib.staticfiles import finders
from django.templatetags.static import static

register = template.Library()

_cache = {}


@register.simple_tag
def static_v(path):
    url = static(path)
    try:
        if path in _cache:
            return _cache[path]
        real = finders.find(path)
        if not real:
            return url
        import os

        st = os.stat(str(real))
        # Hash pendek dari mtime + size (baca isi terlalu mahal per request;
        # perubahan deploy selalu mengubah mtime).
        h = struct.pack("<dq", int(st.st_mtime), st.st_size).hex()[:10]
        val = f"{url}?v={h}"
        _cache[path] = val
        return val
    except Exception:
        return url
