"""Helper menulis audit log (TDIP v1.2 §8.2, AUD-02).

Append-only; metadata disaring agar tidak menyimpan data sensitif
(password, foto, koordinat presisi).
"""
from django.db import transaction

from .models import AuditLog

# Key metadata yang dilarang masuk log (data sensitif).
_FORBIDDEN_KEYS = {
    "password",
    "password1",
    "password2",
    "old_password",
    "new_password",
    "photo",
    "foto",
    "latitude",
    "longitude",
    "lat",
    "lng",
    "gps",
    "coordinates",
    "token",
    "secret",
}

_SENSITIVE_SUBSTRINGS = ("password", "token", "secret", "photo", "foto")


def _redact(value):
    """Saring metadata: buang key sensitif, sebutkan tidak lebih."""
    if not isinstance(value, dict):
        return {}
    cleaned = {}
    for key, val in value.items():
        key_lower = str(key).lower()
        if key_lower in _FORBIDDEN_KEYS or any(s in key_lower for s in _SENSITIVE_SUBSTRINGS):
            cleaned[key] = "[diredaksi]"
        else:
            cleaned[key] = val
    return cleaned


@transaction.atomic
def catat_audit(
    *, action, object_type, object_id="", organization=None, actor=None,
    reason="", metadata=None,
):
    """Tulis satu entri audit log. Selalu membuat record baru (append-only)."""
    return AuditLog.objects.create(
        organization=organization,
        actor=actor,
        action=action,
        object_type=object_type,
        object_id=str(object_id or ""),
        reason=reason or "",
        metadata=_redact(metadata or {}),
    )
