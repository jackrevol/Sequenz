import pytest

from integrations.sabangnet_client import SabangnetApiError, parse_bulk_result
from integrations.sabangnet_mutations import SabangnetMutationClient


class FakeApiClient:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def request_json(self, method, path, *, json_body=None, query=None):
        self.calls.append((method, path, json_body))
        return self.payload


def test_bulk_result_uses_item_statuses_and_counts():
    result = parse_bulk_result({
        "code": 206,
        "data": {
            "totalCount": 2,
            "successCount": 1,
            "failCount": 1,
            "results": [
                {"status": True, "errorMessage": None},
                {"status": False, "errorMessage": "상태변경 불가"},
            ],
        },
    })

    assert result.total_count == 2
    assert result.success_count == 1
    assert result.fail_count == 1
    assert result.errors == ("상태변경 불가",)
    assert result.all_succeeded is False
    assert result.item_results_available is True


def test_mutation_client_rejects_item_level_failure_even_when_envelope_is_successful():
    api = FakeApiClient({
        "code": 200,
        "data": {
            "totalCount": 1,
            "successCount": 0,
            "failCount": 1,
            "results": [{"status": False, "errorMessage": "invalid transition"}],
        },
    })
    client = SabangnetMutationClient(api)

    with pytest.raises(SabangnetApiError, match="1건이 실패") as captured:
        client.change_order_statuses([{"sbOrderNo": "1", "targetStatusCode": "ORDER_CONFIRM"}])

    assert captured.value.code == "BULK_PARTIAL_FAILURE"


def test_mutation_client_builds_confirmed_waybill_request():
    api = FakeApiClient({
        "code": 200,
        "data": {"totalCount": 1, "successCount": 1, "failCount": 0, "results": [{"status": True}]},
    })
    client = SabangnetMutationClient(api)

    result = client.save_waybills(
        [{"sbOrderNo": "1", "deliveryCompanyCode": "CJGLS", "wayBillNo": "123"}],
        force_update=True,
    )

    assert result.all_succeeded is True
    assert api.calls == [(
        "POST",
        "/waybill",
        {
            "forceUpdateYn": "Y",
            "waybillList": [{"sbOrderNo": "1", "deliveryCompanyCode": "CJGLS", "wayBillNo": "123"}],
        },
    )]


def test_stub_acknowledgement_without_item_results_is_marked_unverified():
    result = parse_bulk_result({"code": 200, "message": "OK", "data": {}})

    assert result.all_succeeded is True
    assert result.item_results_available is False
    assert result.total_count == 0
