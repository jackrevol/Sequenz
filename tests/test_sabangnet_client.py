import io
import json
from urllib import error, parse

import pytest
from django.conf import settings

from integrations.sabangnet_client import SabangnetApiClient, SabangnetApiError, extract_data_list, response_count
from integrations.sabangnet_products import _extract_product
from integrations.sabangnet_status import _extract_order_rows


SECRET = "$2a$04$abcdefghijklmnopqrstuu"


def test_sabangnet_environment_urls_are_fixed():
    assert settings.SABANGNET_BASE_URLS == {
        "PRODUCTION": "https://api.sabangnet.co.kr",
        "SANDBOX": "https://sandbox.sabangnet.co.kr",
    }
    assert settings.SABANGNET_API_BASE_URL == "https://api.sabangnet.co.kr"
    assert settings.SABANGNET_TOKEN_URL == "https://api.sabangnet.co.kr/oauth2/token"


class FakeResponse:
    def __init__(self, payload, status=200):
        self.status = status
        self.payload = payload

    def read(self):
        return json.dumps(self.payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_client_issues_oauth_token_and_uses_service_account_header():
    calls = []

    def urlopen(http_request, **kwargs):
        calls.append(http_request)
        if len(calls) == 1:
            return FakeResponse({"access_token": "short-lived-token", "expires_in": 600})
        return FakeResponse({"code": "200", "message": "OK", "response": {"data_list": [{"productCode": "P-1"}]}})

    client = SabangnetApiClient(
        base_url="https://sandbox.example",
        client_id="11111111-1111-1111-1111-111111111111",
        client_secret=SECRET,
        auth_mode="SANDBOX",
        service_account_id="seller-1",
        urlopen=urlopen,
    )

    payload = client.request_json("GET", "/product", query={"productCode": "P-1"})

    token_form = parse.parse_qs(calls[0].data.decode())
    assert calls[0].full_url == "https://sandbox.example/oauth2/token"
    assert token_form["grant_type"] == ["client_credentials"]
    assert token_form["clientType"] == ["SB_APP"]
    assert token_form["authMode"] == ["SANDBOX"]
    assert token_form["secretSign"][0] != SECRET
    assert calls[1].headers["Authorization"] == "Bearer short-lived-token"
    assert calls[1].headers["X-svc-acnt-id"] == "seller-1"
    assert response_count(payload) == 1


def test_client_preserves_external_auth_error_code_without_response_secrets():
    def urlopen(http_request, **kwargs):
        body = json.dumps({"code": "AUTH_008", "message": "허용되지 않은 IP 주소입니다"}).encode()
        raise error.HTTPError(http_request.full_url, 403, "Forbidden", {}, io.BytesIO(body))

    client = SabangnetApiClient(
        base_url="https://sandbox.example",
        client_id="11111111-1111-1111-1111-111111111111",
        client_secret=SECRET,
        urlopen=urlopen,
    )

    with pytest.raises(SabangnetApiError) as captured:
        client.get_access_token()

    assert captured.value.status == 403
    assert captured.value.code == "AUTH_008"
    assert "허용되지 않은 IP" in str(captured.value)
    assert SECRET not in str(captured.value)


def test_real_sabangnet_response_envelope_is_unwrapped_for_sync_parsers():
    product_payload = {
        "code": 200,
        "data": {"productCode": "P-1", "productName": "Jacket"},
    }
    order_payload = {
        "code": 200,
        "data": {"totalItemCnt": 1, "results": [{"SB_ORD_NO": "S-1", "ORDER_STATUS": "001"}]},
    }

    assert _extract_product(product_payload)["productCode"] == "P-1"
    assert _extract_order_rows(order_payload)[0]["SB_ORD_NO"] == "S-1"
    assert extract_data_list(product_payload) == []
    assert response_count(order_payload) == 1


def test_product_notice_details_are_counted_from_sandbox_envelope():
    payload = {"code": 200, "data": {"productInfoNoticeTypeCode": "WEAR", "details": [{"code": "A"}, {"code": "B"}]}}

    assert len(extract_data_list(payload)) == 2
    assert response_count(payload) == 2


def test_service_account_is_required_only_for_business_api_calls():
    client = SabangnetApiClient(
        base_url="https://sandbox.example",
        bearer_token="token",
        service_account_id="",
        urlopen=lambda *args, **kwargs: FakeResponse({}),
    )

    assert client.get_access_token() == "token"
    with pytest.raises(SabangnetApiError, match="SABANGNET_SVC_ACCOUNT_ID") as captured:
        client.request_json("GET", "/category")
    assert captured.value.code == "CONFIG_SERVICE_ACCOUNT"
