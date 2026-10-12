from django.contrib import admin

from .models import AuditLog

# AuditLog bersifat append-only: tidak ada aksi tambah/ubah/hapus di admin.
admin.site.register(AuditLog)
