from django.db import models


class SabangnetOrderExport(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "대기"
        GENERATED = "generated", "파일 생성"
        REGISTERED = "registered", "사방넷 등록 완료"
        FAILED = "failed", "실패"

    order = models.OneToOneField(
        "commerce.Order",
        on_delete=models.PROTECT,
        related_name="sabangnet_export",
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    generated_at = models.DateTimeField(null=True, blank=True)
    filename = models.CharField(max_length=240, blank=True)
    row_count = models.PositiveIntegerField(default=0)
    payload_summary = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class IntegrationJob(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued", "대기"
        RUNNING = "running", "진행 중"
        SUCCEEDED = "succeeded", "성공"
        FAILED = "failed", "실패"
        PARTIAL = "partial", "일부 성공"

    provider = models.CharField(max_length=40, db_index=True)
    job_type = models.CharField(max_length=40, db_index=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.QUEUED, db_index=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    total_count = models.PositiveIntegerField(default=0)
    success_count = models.PositiveIntegerField(default=0)
    failure_count = models.PositiveIntegerField(default=0)
    requested_by = models.ForeignKey("auth.User", null=True, blank=True, on_delete=models.SET_NULL)
    request_summary = models.JSONField(default=dict, blank=True)
    error_summary = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        permissions = [
            ("view_operations_dashboard", "Can view operations dashboard"),
            ("reconcile_payment", "Can reconcile payment"),
            ("retry_integration", "Can retry integration jobs"),
            ("manage_shipping_policy", "Can manage shipping policy"),
            ("view_sensitive_pii", "Can view unmasked customer PII"),
        ]


class ExternalApiLog(models.Model):
    provider = models.CharField(max_length=40, db_index=True)
    job = models.ForeignKey(IntegrationJob, null=True, blank=True, on_delete=models.SET_NULL, related_name="api_logs")
    operation = models.CharField(max_length=80, db_index=True)
    request_summary = models.JSONField(default=dict, blank=True)
    response_status = models.PositiveIntegerField(null=True, blank=True)
    response_summary = models.JSONField(default=dict, blank=True)
    error_code = models.CharField(max_length=80, blank=True, db_index=True)
    error_message = models.CharField(max_length=500, blank=True)
    duration_ms = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]


class OperationsAuditLog(models.Model):
    actor = models.ForeignKey("auth.User", null=True, blank=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=80, db_index=True)
    target_type = models.CharField(max_length=80)
    target_id = models.CharField(max_length=120)
    before_summary = models.JSONField(default=dict, blank=True)
    after_summary = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
