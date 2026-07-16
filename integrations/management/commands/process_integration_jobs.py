from django.core.management.base import BaseCommand

from integrations.sabangnet_product_jobs import (
    claim_next_manual_product_sync_job,
    fail_manual_product_sync_job,
    run_manual_product_sync_job,
)
from integrations.models import IntegrationJob


class Command(BaseCommand):
    help = "Process queued external integration jobs."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=1)

    def handle(self, *args, **options):
        processed = 0
        for _ in range(max(options["limit"], 0)):
            job_id = claim_next_manual_product_sync_job()
            if job_id is None:
                break
            try:
                job = run_manual_product_sync_job(job_id)
            except Exception as exc:
                job = IntegrationJob.objects.get(pk=job_id)
                fail_manual_product_sync_job(job, exc)
                self.stderr.write(self.style.ERROR(f"Integration job {job_id} failed: {exc}"))
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Integration job {job_id}: {job.status} "
                        f"({job.success_count} succeeded, {job.failure_count} failed)"
                    )
                )
            processed += 1
        if processed == 0:
            self.stdout.write("No queued integration jobs.")
