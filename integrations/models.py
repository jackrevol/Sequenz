from django.db import models


class SabangnetOrderSubmission(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"
        RETRYING = "retrying", "Retrying"

    order = models.OneToOneField(
        "commerce.Order",
        on_delete=models.PROTECT,
        related_name="sabangnet_submission",
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    sabangnet_order_no = models.CharField(max_length=80, blank=True, db_index=True)
    operation_idempotency_key = models.CharField(max_length=160, db_index=True)
    external_request_id = models.CharField(max_length=160, blank=True, db_index=True)
    attempt_count = models.PositiveIntegerField(default=0)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    next_retry_at = models.DateTimeField(null=True, blank=True)
    terminal_failure_at = models.DateTimeField(null=True, blank=True)
    last_error_message = models.TextField(blank=True)
    payload_summary = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["order", "operation_idempotency_key"],
                name="unique_sabangnet_submission_idempotency",
            )
        ]
