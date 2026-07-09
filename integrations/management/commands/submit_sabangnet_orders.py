from django.core.management.base import BaseCommand

from integrations.sabangnet import SabangnetClient, pending_order_submission_count, process_pending_order_submissions


class Command(BaseCommand):
    help = "Submit paid orders to Sabangnet."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=50)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        limit = options["limit"]
        if options["dry_run"]:
            count = min(pending_order_submission_count(), limit)
            self.stdout.write(f"{count} Sabangnet order submissions would be processed.")
            return

        processed = process_pending_order_submissions(SabangnetClient(), limit=limit)
        self.stdout.write(f"{processed} Sabangnet order submissions processed.")
