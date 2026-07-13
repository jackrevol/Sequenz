from datetime import date, timedelta

from django.core.management.base import BaseCommand, CommandError

from integrations.sabangnet_client import SabangnetApiClient, SabangnetApiError, response_count


READ_ONLY_CHECKS = ("auth", "category", "product_notice", "orders", "claims")


class Command(BaseCommand):
    help = "사방넷 샌드박스의 인증과 읽기 전용 API를 점검합니다. 응답 데이터와 인증정보는 출력하지 않습니다."

    def add_arguments(self, parser):
        parser.add_argument(
            "--checks",
            default=",".join(READ_ONLY_CHECKS),
            help=f"쉼표로 구분한 점검 목록: {', '.join(READ_ONLY_CHECKS)}",
        )
        parser.add_argument("--start-date", default=(date.today() - timedelta(days=7)).strftime("%Y%m%d"))
        parser.add_argument("--end-date", default=date.today().strftime("%Y%m%d"))

    def handle(self, *args, **options):
        checks = [value.strip() for value in options["checks"].split(",") if value.strip()]
        invalid = sorted(set(checks) - set(READ_ONLY_CHECKS))
        if invalid:
            raise CommandError(f"지원하지 않는 점검 항목입니다: {', '.join(invalid)}")
        client = SabangnetApiClient()
        completed = []
        try:
            for check in checks:
                count = self._run_check(client, check, options)
                suffix = "" if count is None else f" (응답 건수 {count})"
                self.stdout.write(self.style.SUCCESS(f"[OK] {check}{suffix}"))
                completed.append(check)
        except SabangnetApiError as exc:
            code = f" [{exc.code}]" if exc.code else ""
            completed_label = ", ".join(completed) or "없음"
            raise CommandError(f"{check} 점검 실패{code}: {exc} 완료 항목: {completed_label}") from exc

    def _run_check(self, client, check, options):
        if check == "auth":
            client.get_access_token()
            return None
        if check == "category":
            return response_count(client.request_json("GET", "/category"))
        if check == "product_notice":
            return response_count(client.request_json("GET", "/product-info-notice/WEAR"))
        body = {
            "startDate": options["start_date"],
            "endDate": options["end_date"],
            "page": 1,
            "perPage": 50,
            "responseItems": ["SB_ORD_NO", "SHOP_ORD_NO"],
        }
        if check == "orders":
            body.update({"dateSearchCondition": 1, "updateOrderStsYn": "N", "responseItems": [*body["responseItems"], "ORDER_STATUS"]})
            return response_count(client.request_json("GET", "/order", json_body=body))
        return response_count(client.request_json("GET", "/claim", json_body=body))
