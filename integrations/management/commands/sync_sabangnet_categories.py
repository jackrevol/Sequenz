from django.core.management.base import BaseCommand, CommandError

from integrations.sabangnet_categories import SabangnetCategoryClient, SabangnetCategoryError, sync_categories


class Command(BaseCommand):
    help = "사방넷 마이카테고리를 내부 카테고리로 동기화합니다."

    def handle(self, *args, **options):
        try:
            categories = sync_categories(SabangnetCategoryClient().fetch_categories())
        except SabangnetCategoryError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(f"{len(categories)}개 카테고리를 동기화했습니다."))
