from integrations.sabangnet_client import SabangnetApiClient, ensure_bulk_success


class SabangnetMutationClient:
    """Typed entry points for Sabangnet write APIs with item-level failure checks."""

    def __init__(self, api_client=None):
        self.api_client = api_client or SabangnetApiClient()

    def save_categories(self, categories):
        return self._post("/category", {"categories": categories}, "카테고리 저장")

    def upsert_products(self, products):
        return self._post("/product/upsert", {"products": products}, "상품 등록·수정")

    def change_order_statuses(self, orders):
        return self._post("/order-status", {"orders": orders}, "주문 상태 변경")

    def save_waybills(self, waybill_list, *, force_update=False):
        return self._post(
            "/waybill",
            {"forceUpdateYn": "Y" if force_update else "N", "waybillList": waybill_list},
            "운송장 저장",
        )

    def save_cs_answers(self, items):
        return self._post("/cs/answer", {"items": items}, "문의 답변 저장")

    def upsert_additional_products(self, product_info_list):
        return self._post(
            "/additional-product",
            {"productInfoList": product_info_list},
            "추가상품 등록·수정",
        )

    def update_channel_products(self, products):
        return self._post("/channels-product", {"products": products}, "채널상품 등록·수정")

    def _post(self, path, body, operation):
        payload = self.api_client.request_json("POST", path, json_body=body)
        return ensure_bulk_success(payload, operation=operation)
