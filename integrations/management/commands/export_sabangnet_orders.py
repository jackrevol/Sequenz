from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from integrations.sabangnet import export_pending_orders, pending_order_export_count


class Command(BaseCommand):
    help = "Export paid orders to a Sabangnet bulk-registration XLSX file."

    def add_arguments(self, parser):
        parser.add_argument("output", nargs="?", help="Output .xlsx path")
        parser.add_argument("--limit", type=int, default=500)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        if options["dry_run"]:
            count = pending_order_export_count()
            self.stdout.write(f"{count} Sabangnet orders would be exported.")
            return
        if not options["output"]:
            raise CommandError("output is required unless --dry-run is used")
        output = Path(options["output"])
        if output.suffix.lower() != ".xlsx":
            raise CommandError("output must have an .xlsx extension")
        _, order_count, row_count = export_pending_orders(
            output.name,
            limit=options["limit"],
            output_path=output,
        )
        self.stdout.write(self.style.SUCCESS(f"Exported {order_count} orders ({row_count} rows) to {output}."))
