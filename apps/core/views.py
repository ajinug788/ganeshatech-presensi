"""Health check sederhana — tidak membocorkan environment/secret (TDIP §13.2)."""
from django.http import JsonResponse


def health(request):
    return JsonResponse({"status": "ok"})
