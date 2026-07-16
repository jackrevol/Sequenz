from django.db import transaction
from django.utils import timezone

from .models import ExternalApiLog, IntegrationJob, OperationsAuditLog
from .sabangnet_products import SabangnetProductClient, sync_product_safely


MANUAL_PRODUCT_SYNC_JOB_TYPE = "manual_product_sync"
ALLOWED_IDENTIFIER_TYPES = {"product_code", "custom_product_code"}


def enqueue_manual_product_sync(*, codes, identifier_type, requested_by, ip_address=None):
    if identifier_type not in ALLOWED_IDENTIFIER_TYPES:
        raise ValueError("지원하지 않는 상품 식별 방식입니다.")
    return IntegrationJob.objects.create(
        provider="sabangnet",
        job_type=MANUAL_PRODUCT_SYNC_JOB_TYPE,
        status=IntegrationJob.Status.QUEUED,
        total_count=len(codes),
        requested_by=requested_by,
        request_summary={
            "codes": list(codes),
            "identifier_type": identifier_type,
            "ip_address": ip_address,
        },
    )


def claim_next_manual_product_sync_job():
    with transaction.atomic():
        job = (
            IntegrationJob.objects.select_for_update()
            .filter(job_type=MANUAL_PRODUCT_SYNC_JOB_TYPE, status=IntegrationJob.Status.QUEUED)
            .order_by("created_at")
            .first()
        )
        if job is None:
            return None
        job.status = IntegrationJob.Status.RUNNING
        job.started_at = timezone.now()
        job.save(update_fields=["status", "started_at"])
        return job.pk


def run_manual_product_sync_job(job_id, *, client=None):
    job = IntegrationJob.objects.select_related("requested_by").get(pk=job_id)
    if job.job_type != MANUAL_PRODUCT_SYNC_JOB_TYPE:
        raise ValueError("수동 상품 동기화 작업이 아닙니다.")
    if job.status == IntegrationJob.Status.QUEUED:
        job.status = IntegrationJob.Status.RUNNING
        job.started_at = timezone.now()
        job.save(update_fields=["status", "started_at"])
    elif job.status != IntegrationJob.Status.RUNNING:
        return job

    summary = job.request_summary if isinstance(job.request_summary, dict) else {}
    codes = summary.get("codes") if isinstance(summary.get("codes"), list) else []
    identifier_type = summary.get("identifier_type", "product_code")
    if identifier_type not in ALLOWED_IDENTIFIER_TYPES or not codes:
        return fail_manual_product_sync_job(job, "동기화할 상품코드 또는 식별 방식이 올바르지 않습니다.")

    client = client or SabangnetProductClient()
    errors = []
    for index, code in enumerate(codes, start=1):
        try:
            payload = client.fetch_product(**{identifier_type: code})
            sync_product_safely(payload)
            job.success_count += 1
        except Exception as exc:
            job.failure_count += 1
            safe_error = str(exc)[:500]
            errors.append(f"{code}: {safe_error}")
            ExternalApiLog.objects.create(
                provider="sabangnet",
                job=job,
                operation=MANUAL_PRODUCT_SYNC_JOB_TYPE,
                request_summary={"identifier_type": identifier_type, "product_identifier": code},
                error_code=getattr(exc, "code", "SYNC_FAILED") or "SYNC_FAILED",
                error_message=safe_error,
            )
        if index % 10 == 0:
            job.error_summary = "\n".join(errors)[-2000:]
            job.save(update_fields=["success_count", "failure_count", "error_summary"])

    job.status = (
        IntegrationJob.Status.SUCCEEDED if job.failure_count == 0
        else IntegrationJob.Status.FAILED if job.success_count == 0
        else IntegrationJob.Status.PARTIAL
    )
    job.error_summary = "\n".join(errors)[-2000:]
    job.finished_at = timezone.now()
    job.save(update_fields=["success_count", "failure_count", "status", "error_summary", "finished_at"])
    OperationsAuditLog.objects.create(
        actor=job.requested_by,
        action="sabangnet_product_manual_sync",
        target_type="Product",
        target_id="bulk",
        before_summary={"requested_count": len(codes), "identifier_type": identifier_type},
        after_summary={"success_count": job.success_count, "failure_count": job.failure_count, "job_id": job.pk},
        ip_address=summary.get("ip_address") or None,
    )
    return job


def fail_manual_product_sync_job(job, message):
    job.status = IntegrationJob.Status.FAILED
    job.error_summary = str(message)[:2000]
    job.finished_at = timezone.now()
    job.save(update_fields=["status", "error_summary", "finished_at"])
    return job
