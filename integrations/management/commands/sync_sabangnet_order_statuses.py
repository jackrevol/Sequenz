from datetime import date, timedelta

from django.core.management.base import BaseCommand, CommandError

from integrations.sabangnet_status import SabangnetOrderStatusClient, SabangnetStatusError, sync_order_status_rows


class Command(BaseCommand):
    help = "Synchronize internal fulfillment statuses from Sabangnet order lookup."

    def add_arguments(self, parser):
        parser.add_argument("--start-date")
        parser.add_argument("--end-date")
        parser.add_argument("--page", type=int, default=1)
        parser.add_argument("--per-page", type=int, default=100)
        parser.add_argument("--max-pages", type=int, default=100)

    def handle(self, *args, **options):
        end_date = options["end_date"] or date.today().isoformat()
        start_date = options["start_date"] or (date.today() - timedelta(days=7)).isoformat()
        try:
            client = SabangnetOrderStatusClient()
            totals = {"matched": 0, "updated": 0, "unknown_statuses": 0}
            page = options["page"]
            for _ in range(options["max_pages"]):
                rows = client.fetch_orders(start_date, end_date, page=page, per_page=options["per_page"])
                result = sync_order_status_rows(rows)
                for key in totals:
                    totals[key] += getattr(result, key)
                if len(rows) < options["per_page"]:
                    break
                page += 1
        except SabangnetStatusError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(
            self.style.SUCCESS(
                f"Matched {totals['matched']}, updated {totals['updated']}, unknown statuses {totals['unknown_statuses']}."
            )
        )
