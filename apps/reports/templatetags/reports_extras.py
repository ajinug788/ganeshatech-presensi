"""Filter template Tahap 6: format waktu lokal WIB."""
from django import template
from django.utils import timezone as dj_timezone
from zoneinfo import ZoneInfo

register = template.Library()

_WIB_TZ = ZoneInfo("Asia/Jakarta")


@register.filter
def localtime_wib(value):
    """DateTimeField aware → 'HH:MM' WIB; kosong bila None."""
    if not value:
        return "—"
    return dj_timezone.localtime(value, _WIB_TZ).strftime("%H:%M")
