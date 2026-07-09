import pytest
from django.core.management import call_command

from catalog.models import Brand, Category, Product, ProductListing, ProductVariant
from commerce.models import Order
from integrations.models import SabangnetOrderSubmission
from integrations.sabangnet import (
    SabangnetClientError,
    SabangnetResponse,
    build_order_payload,
    process_pending_order_submissions,
    submit_order_submission,
)


class RecordingSabangnetClient:
    def __init__(self, response=None, error=None):
        self.response = response or SabangnetResponse(sabangnet_order_no="SB-ORDER-1000", raw_summary={"ok": True})
        self.error = error
        self.payloads = []

    def submit_order(self, payload):
        self.payloads.append(payload)
        if self.error:
            raise self.error
        return self.response


@pytest.fixture
def listing_variant(db):
    brand = Brand.objects.create(name="Sequenz", slug="sequenz-sabangnet", sort_order=1)
    category = Category.objects.create(name="Outerwear", slug="outerwear-sabangnet", level=1, sort_order=1)
    product = Product.objects.create(
        brand=brand,
        category=category,
        sabangnet_product_code="SB-SUBMIT-1000",
        custom_product_code="SEQ-SUBMIT-1000",
        name="Worker Jacket",
        consumer_price=129000,
        selling_price=119000,
        tax_code="TAXABLE",
        supply_status="IN_SUPPLY",
    )
    variant = ProductVariant.objects.create(
        product=product,
        variant_code="SEQ-SUBMIT-1000-BLK-M",
        barcode="880000009999",
        option_display_name="Black / M",
        additional_amount=0,
        stock_quantity=3,
        safety_stock_quantity=1,
        supply_status="SALE",
    )
    listing = ProductListing.objects.create(
        product=product,
        listing_code="LIST-SUBMIT-1000",
        sales_channel="main_mall",
        status="active",
        display_name="Worker Jacket",
        slug="worker-jacket",
        consumer_price_snapshot=129000,
        selling_price_snapshot=119000,
        price_source="sabangnet",
    )
    return listing.variants.create(
        variant=variant,
        status="active",
        additional_amount_snapshot=0,
        stock_display_policy="show",
        sort_order=1,
    )


@pytest.fixture
def paid_order(api_client, listing_variant):
    api_client.post(
        "/api/commerce/cart/items/",
        {"listing_variant_id": listing_variant.id, "quantity": 2},
        format="json",
        HTTP_X_GUEST_KEY="sabangnet-worker-guest",
    )
    order_response = api_client.post(
        "/api/commerce/orders/",
        {
            "buyer_name": "Hong Gildong",
            "buyer_phone": "01012345678",
            "buyer_email": "buyer@example.com",
            "recipient_name": "Kim Receiver",
            "recipient_phone": "01087654321",
            "postal_code": "06000",
            "address1": "Seoul",
            "address2": "Gangnam",
            "delivery_memo": "door",
        },
        format="json",
        HTTP_X_GUEST_KEY="sabangnet-worker-guest",
    )
    order = Order.objects.get(order_number=order_response.json()["order_number"])
    api_client.post(
        "/api/commerce/payments/toss/confirm/",
        {
            "order_number": order.order_number,
            "payment_key": "pay_sabangnet_worker",
            "amount": order.payment_amount,
            "method": "card",
        },
        format="json",
    )
    order.refresh_from_db()
    return order


@pytest.mark.django_db
def test_build_order_payload_uses_order_and_item_snapshots(paid_order):
    payload = build_order_payload(paid_order)

    assert payload["shop_order_no"] == paid_order.order_number
    assert payload["buyer"]["name"] == "Hong Gildong"
    assert payload["receiver"]["name"] == "Kim Receiver"
    assert payload["amounts"]["payment_amount"] == paid_order.payment_amount
    assert payload["items"] == [
        {
            "line_no": str(paid_order.items.first().id),
            "listing_code": "LIST-SUBMIT-1000",
            "sabangnet_product_code": "SB-SUBMIT-1000",
            "custom_product_code": "SEQ-SUBMIT-1000",
            "barcode": "880000009999",
            "product_name": "Worker Jacket",
            "option_name": "Black / M",
            "quantity": 2,
            "unit_price": 119000,
            "line_total": 238000,
        }
    ]


@pytest.mark.django_db
def test_submit_order_submission_marks_success_and_records_sabangnet_number(paid_order):
    submission = paid_order.sabangnet_submission
    client = RecordingSabangnetClient(
        SabangnetResponse(sabangnet_order_no="SB-ORDER-2000", raw_summary={"result": "success"})
    )

    result = submit_order_submission(submission, client)

    assert len(client.payloads) == 1
    assert client.payloads[0]["shop_order_no"] == paid_order.order_number
    submission.refresh_from_db()
    paid_order.refresh_from_db()
    assert result.status == SabangnetOrderSubmission.Status.SENT
    assert submission.status == SabangnetOrderSubmission.Status.SENT
    assert submission.sabangnet_order_no == "SB-ORDER-2000"
    assert submission.attempt_count == 1
    assert submission.last_error_message == ""
    assert paid_order.sabangnet_status == "sent"


@pytest.mark.django_db
def test_submit_order_submission_marks_failure_without_changing_paid_order(paid_order):
    submission = paid_order.sabangnet_submission
    client = RecordingSabangnetClient(error=SabangnetClientError("temporary sabangnet outage"))

    result = submit_order_submission(submission, client)

    submission.refresh_from_db()
    paid_order.refresh_from_db()
    assert result.status == SabangnetOrderSubmission.Status.FAILED
    assert submission.status == SabangnetOrderSubmission.Status.FAILED
    assert submission.attempt_count == 1
    assert submission.sabangnet_order_no == ""
    assert submission.last_error_message == "temporary sabangnet outage"
    assert paid_order.status == Order.Status.PAID
    assert paid_order.sabangnet_status == "failed"


@pytest.mark.django_db
def test_submit_order_submission_skips_already_sent_submission(paid_order):
    submission = paid_order.sabangnet_submission
    submission.status = SabangnetOrderSubmission.Status.SENT
    submission.sabangnet_order_no = "SB-ORDER-ALREADY"
    submission.save(update_fields=["status", "sabangnet_order_no", "updated_at"])
    client = RecordingSabangnetClient()

    result = submit_order_submission(submission, client)

    submission.refresh_from_db()
    assert result.status == SabangnetOrderSubmission.Status.SENT
    assert client.payloads == []
    assert submission.attempt_count == 0
    assert submission.sabangnet_order_no == "SB-ORDER-ALREADY"


@pytest.mark.django_db
def test_process_pending_order_submissions_submits_pending_records(paid_order):
    client = RecordingSabangnetClient()

    processed = process_pending_order_submissions(client, limit=10)

    assert processed == 1
    assert len(client.payloads) == 1
    paid_order.sabangnet_submission.refresh_from_db()
    assert paid_order.sabangnet_submission.status == SabangnetOrderSubmission.Status.SENT


@pytest.mark.django_db
def test_submit_sabangnet_orders_command_dry_run_reports_pending_count(paid_order, capsys):
    call_command("submit_sabangnet_orders", "--dry-run")

    captured = capsys.readouterr()
    assert "1 Sabangnet order submissions would be processed." in captured.out
