from django.contrib import admin

from .models import SabangnetOrderExport


@admin.register(SabangnetOrderExport)
class SabangnetOrderExportAdmin(admin.ModelAdmin):
    list_display = ("order", "status", "filename", "row_count", "generated_at", "updated_at")
    list_filter = ("status", "generated_at")
    search_fields = ("order__order_number", "filename")
    readonly_fields = ("order", "status", "generated_at", "filename", "row_count", "payload_summary", "created_at", "updated_at")
