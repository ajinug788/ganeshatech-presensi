"""Cleanup file yatim & aset yatim (TDIP v1.2 §11.2, Tahap 4).

- File yatim: file di private_media tanpa MediaAsset → dihapus.
- Aset yatim: MediaAsset tanpa file → record dihapus (file sudah hilang).

Management command: python manage.py cleanup_media [--dry-run]
"""
import logging

from django.core.management.base import BaseCommand

from apps.media_assets.models import MediaAsset
from apps.media_assets.services import hapus_file, iter_stored_keys

logger = logging.getLogger(__name__)


def cleanup_media(*, dry_run=False):
    """Bersihkan file yatim dan aset yatim. Return ringkasan dict."""
    known_keys = set(MediaAsset.objects.values_list("storage_key", flat=True))

    orphan_files = [k for k in iter_stored_keys() if k not in known_keys]
    orphan_assets = []
    for asset in MediaAsset.objects.iterator():
        from apps.media_assets.services import file_exists

        if not file_exists(asset.storage_key):
            orphan_assets.append(asset)

    if not dry_run:
        for key in orphan_files:
            hapus_file(key)
        for asset in orphan_assets:
            asset.delete()

    return {
        "orphan_files": orphan_files,
        "orphan_assets": [str(a.pk) for a in orphan_assets],
        "dry_run": dry_run,
    }


class Command(BaseCommand):
    help = "Hapus file yatim (tanpa MediaAsset) dan MediaAsset tanpa file."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true", help="Hanya laporkan, jangan hapus."
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        result = cleanup_media(dry_run=dry_run)
        mode = "DRY-RUN" if dry_run else "CLEANED"
        self.stdout.write(
            f"[{mode}] file yatim: {len(result['orphan_files'])} — "
            f"{result['orphan_files']}"
        )
        self.stdout.write(
            f"[{mode}] aset tanpa file: {len(result['orphan_assets'])} — "
            f"{result['orphan_assets']}"
        )
