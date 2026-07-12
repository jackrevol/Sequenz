import base64
import json

import pytest

from integrations.toss import TossPaymentError, confirm_toss_payment


def test_toss_confirm_uses_basic_auth_with_trailing_colon(monkeypatch, settings):
    settings.TOSS_SECRET_KEY = "test_sk_example"
    settings.TOSS_CONFIRM_URL = "https://example.test/confirm"
    captured = {}

    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self): return b'{"status":"DONE","totalAmount":1000}'

    def fake_urlopen(http_request, timeout):
        captured["request"] = http_request
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr("integrations.toss.request.urlopen", fake_urlopen)
    result = confirm_toss_payment("pay_1", "ORDER-1", 1000)

    expected = base64.b64encode(b"test_sk_example:").decode()
    assert captured["request"].headers["Authorization"] == f"Basic {expected}"
    assert json.loads(captured["request"].data) == {"paymentKey": "pay_1", "orderId": "ORDER-1", "amount": 1000}
    assert result["status"] == "DONE"


def test_toss_confirm_requires_secret_key(settings):
    settings.TOSS_SECRET_KEY = ""
    with pytest.raises(TossPaymentError) as exc:
        confirm_toss_payment("pay_1", "ORDER-1", 1000)
    assert exc.value.code == "TOSS_NOT_CONFIGURED"
