from django.core.management.base import BaseCommand, CommandError

from integrations.sabangnet_products import SabangnetProductClient, SabangnetProductError, sync_product_safely


class Command(BaseCommand):
    help = "Fetch and synchronize one product from Sabangnet."

    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument("--product-code")
        group.add_argument("--custom-product-code")

    def handle(self, *args, **options):
        try:
            payload = SabangnetProductClient().fetch_product(
                product_code=options["product_code"], custom_product_code=options["custom_product_code"]
            )
            product = sync_product_safely(payload)
        except SabangnetProductError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(f"Synchronized {product.sabangnet_product_code}: {product.name}"))
