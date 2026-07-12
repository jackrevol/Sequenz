from django.contrib import admin

from .models import ExternalApiLog, IntegrationJob, OperationsAuditLog, SabangnetOrderExport


@admin.register(SabangnetOrderExport)
class SabangnetOrderExportAdmin(admin.ModelAdmin):
    list_display = ("order", "status", "filename", "row_count", "generated_at", "updated_at")
    list_filter = ("status", "generated_at")
    search_fields = ("order__order_number", "filename")
    readonly_fields = ("order", "status", "generated_at", "filename", "row_count", "payload_summary", "created_at", "updated_at")


@admin.register(IntegrationJob)
class IntegrationJobAdmin(admin.ModelAdmin):
    list_display = ("provider", "job_type", "status", "success_count", "failure_count", "requested_by", "created_at")
    list_filter = ("provider", "job_type", "status")
    readonly_fields = tuple(field.name for field in IntegrationJob._meta.fields)


@admin.register(ExternalApiLog)
class ExternalApiLogAdmin(admin.ModelAdmin):
    list_display = ("provider", "operation", "response_status", "error_code", "duration_ms", "created_at")
    list_filter = ("provider", "operation", "error_code")
    search_fields = ("error_message",)
    readonly_fields = tuple(field.name for field in ExternalApiLog._meta.fields)


@admin.register(OperationsAuditLog)
class OperationsAuditLogAdmin(admin.ModelAdmin):
    list_display = ("actor", "action", "target_type", "target_id", "ip_address", "created_at")
    list_filter = ("action", "target_type")
    search_fields = ("target_id", "actor__username")
    readonly_fields = tuple(field.name for field in OperationsAuditLog._meta.fields)
