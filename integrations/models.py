from django.db import models


class SabangnetOrderExport(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        GENERATED = "generated", "File generated"
        REGISTERED = "registered", "Registered"
        FAILED = "failed", "Failed"

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
