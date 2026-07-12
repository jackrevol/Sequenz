import zipfile
from io import BytesIO
from xml.etree import ElementTree

import pytest
from django.core.management import call_command

from catalog.models import Brand, Category, Product, ProductListing, ProductVariant
from commerce.models import Order
from commerce.inventory import consume_order_inventory
from integrations.models import SabangnetOrderExport
from integrations.sabangnet import SABANGNET_ORDER_COLUMNS, build_order_rows, build_order_workbook
from integrations.sabangnet_automation import SEQUENCE_TARGET, classify_registration_message
from integrations.sabangnet_products import sync_order_products


@pytest.fixture(autouse=True)
def fake_toss_confirm(monkeypatch):
    monkeypatch.setattr(
        "commerce.views.confirm_toss_payment",
        lambda payment_key, order_id, amount: {
            "paymentKey": payment_key, "orderId": order_id, "status": "DONE",
            "method": "카드", "totalAmount": amount, "balanceAmount": amount,
        },
    )


@pytest.fixture
def paid_order(api_client, db):
    api_client.credentials(HTTP_X_GUEST_KEY="sabangnet-export-guest")
    brand = Brand.objects.create(name="Sequenz", slug="sequenz-export", sort_order=1)
    category = Category.objects.create(name="Outerwear", slug="outerwear-export", level=1, sort_order=1)
    product = Product.objects.create(
        brand=brand,
        category=category,
        sabangnet_product_code="SB-EXPORT-1000",
        custom_product_code="SEQ-EXPORT-1000",
        name="Export Jacket",
        consumer_price=129000,
        selling_price=119000,
        tax_code="TAXABLE",
        supply_status="IN_SUPPLY",
    )
    variant = ProductVariant.objects.create(
        product=product,
        variant_code="SEQ-EXPORT-1000-BLK-M",
        barcode="880000009999",
        option_display_name="Black / M",
        stock_quantity=3,
        safety_stock_quantity=1,
        supply_status="SALE",
    )
    listing = ProductListing.objects.create(
        product=product,
        listing_code="LIST-EXPORT-1000",
        sales_channel="main_mall",
        status="active",
        display_name="Export Jacket",
        slug="export-jacket",
        consumer_price_snapshot=129000,
        selling_price_snapshot=119000,
        price_source="sabangnet",
    )
    listing_variant = listing.variants.create(
        variant=variant,
        status="active",
        additional_amount_snapshot=0,
        stock_display_policy="show",
        sort_order=1,
    )
    api_client.post(
        "/api/commerce/cart/items/",
        {"listing_variant_id": listing_variant.id, "quantity": 2},
        format="json",
        HTTP_X_GUEST_KEY="sabangnet-export-guest",
    )
    response = api_client.post(
        "/api/commerce/orders/",
        {
            "buyer_name": "Hong Gildong",
            "buyer_phone": "01012345678",
            "recipient_name": "Kim Receiver",
            "recipient_phone": "01087654321",
            "postal_code": "06000",
            "address1": "Seoul",
            "address2": "Gangnam",
        },
        format="json",
        HTTP_X_GUEST_KEY="sabangnet-export-guest",
    )
    order = Order.objects.get(order_number=response.json()["order_number"])
    api_client.post(
        "/api/commerce/payments/toss/confirm/",
        {"order_number": order.order_number, "payment_key": "pay_export", "amount": order.payment_amount},
        format="json",
    )
    order.refresh_from_db()
    return order


@pytest.mark.django_db
def test_build_order_rows_matches_changeable_sabangnet_columns(paid_order):
    assert [name for name, _ in SABANGNET_ORDER_COLUMNS] == [
        "상품명", "상품코드", "주문번호", "수취인명", "수취인우편번호", "수취인주소", "주문금액", "수량"
    ]
    assert build_order_rows(paid_order) == [{
        "product_name": "Export Jacket / Black / M",
        "product_code": "SEQ-EXPORT-1000",
        "order_number": paid_order.order_number,
        "recipient_name": "Kim Receiver",
        "postal_code": "06000",
        "recipient_address": "Seoul Gangnam",
        "order_amount": 238000,
        "quantity": 2,
    }]


@pytest.mark.django_db
def test_workbook_is_valid_xlsx_and_keeps_postal_code_as_text(paid_order):
    workbook = build_order_workbook(build_order_rows(paid_order))
    with zipfile.ZipFile(BytesIO(workbook)) as archive:
        root = ElementTree.fromstring(archive.read("xl/worksheets/sheet1.xml"))
    ns = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    assert root.find('.//x:c[@r="A1"]', ns).find(".//x:t", ns).text == "Export Jacket / Black / M"
    cell = root.find('.//x:c[@r="E1"]', ns)
    assert cell.attrib["t"] == "inlineStr"
    assert cell.find(".//x:t", ns).text == "06000"


@pytest.mark.django_db
def test_export_command_writes_file_and_excludes_order_from_next_export(paid_order, tmp_path):
    output = tmp_path / "sabangnet-orders.xlsx"
    call_command("export_sabangnet_orders", str(output))

    assert output.read_bytes().startswith(b"PK")
    export = SabangnetOrderExport.objects.get(order=paid_order)
    paid_order.refresh_from_db()
    assert export.status == SabangnetOrderExport.Status.GENERATED
    assert export.row_count == 1
    assert paid_order.sabangnet_status == "file_generated"

    second = tmp_path / "sabangnet-orders-2.xlsx"
    call_command("export_sabangnet_orders", str(second))
    export.refresh_from_db()
    assert export.filename == output.name


@pytest.mark.django_db
def test_registered_export_refreshes_sabangnet_stock_then_releases_reservation(paid_order):
    item = paid_order.items.get()
    variant = item.listing_variant.variant
    variant.refresh_from_db()
    assert variant.stock_quantity == 3
    assert variant.reserved_quantity == 2

    class FakeClient:
        def fetch_product(self, product_code=None, custom_product_code=None):
            assert product_code == "SB-EXPORT-1000"
            return {
                "productCode": product_code,
                "customProductCode": "SEQ-EXPORT-1000",
                "productName": "Export Jacket",
                "consumerPrice": 129000,
                "sellingPrice": 119000,
                "taxCode": "TAXABLE",
                "productSupplyStatusCode": "IN_SUPPLY",
                "optionInfo": {"options": [{
                    "optionDisplayName": "Black / M",
                    "variantCode": "SEQ-EXPORT-1000-BLK-M",
                    "barcode": "880000009999",
                    "stockQuantity": 1,
                    "optionSupplyStatusCode": "SALE",
                }]},
            }

    sync_order_products(paid_order, client=FakeClient())
    assert consume_order_inventory(paid_order) is True

    paid_order.refresh_from_db()
    variant.refresh_from_db()
    assert paid_order.inventory_reservation_status == Order.InventoryReservationStatus.CONSUMED
    assert variant.stock_quantity == 1
    assert variant.reserved_quantity == 0


def test_sequence_target_and_result_classification_are_fixed_to_20316():
    assert SEQUENCE_TARGET.mall_label == "시퀸즈 [20316]"
    assert SEQUENCE_TARGET.excel_form_serial == "20316"
    assert classify_registration_message("등록 성공") == "registered"
    assert classify_registration_message("이미 등록된 자료입니다.") == "duplicate"
    assert classify_registration_message("데이터에 문제가 있습니다.") == "failed"
    assert classify_registration_message("새로운 메시지") == "unknown"
