"""Penandaan absent otomatis (Tahap 6) — siap cron.

Pemakaian:
    .venv/bin/python manage.py mark_absent                 # semua org aktif
    .venv/bin/python manage.py mark_absent --org <slug>    # satu org
"""
from django.core.management.base import BaseCommand
from django.utils import timezone as dj_timezone
from zoneinfo import ZoneInfo

from apps.reports.services import mark_absent
from apps.tenants.models import Organization

_WIB_TZ = ZoneInfo("Asia/Jakarta")


class Command(BaseCommand):
    help = "Tandai absent untuk hari yang sudah lewat window check-in tanpa kehadiran."

    def add_arguments(self, parser):
        parser.add_argument("--org", dest="org_slug", default=None, help="Slug organisasi (default: semua org aktif).")
        parser.add_argument("--lookback", type=int, default=60, help="Jumlah hari ke belakang (default 60).")

    def handle(self, *args, **options):
        orgs = Organization.objects.filter(status="active")
        if options["org_slug"]:
            orgs = orgs.filter(slug=options["org_slug"])
        total = 0
        for org in orgs:
            created = mark_absent(
                organization=org,
                lookback_days=options["lookback"],
                now=dj_timezone.now(),
            )
            if created:
                self.stdout.write(f"{org.slug}: {created} AttendanceDay absent dibuat.")
            total += created
        self.stdout.write(self.style.SUCCESS(f"Selesai: {total} hari ditandai absent."))
