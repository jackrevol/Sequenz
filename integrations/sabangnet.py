import io
import zipfile
from xml.sax.saxutils import escape

from django.db import transaction
from django.utils import timezone

from commerce.models import Order

from .models import SabangnetOrderExport


# Keep the external file contract in one place because Sabangnet may change it.
SABANGNET_ORDER_COLUMNS = (
    ("상품명", "product_name"),
    ("상품코드", "product_code"),
    ("주문번호", "order_number"),
    ("수취인명", "recipient_name"),
    ("수취인우편번호", "postal_code"),
    ("수취인주소", "recipient_address"),
    ("주문금액", "order_amount"),
    ("수량", "quantity"),
)


def build_order_rows(order):
    address = " ".join(part.strip() for part in (order.address1, order.address2) if part.strip())
    return [
        {
            "product_name": _product_name_with_option(item),
            "product_code": item.custom_product_code,
            "order_number": order.order_number,
            "recipient_name": order.recipient_name,
            "postal_code": order.postal_code,
            "recipient_address": address,
            # TODO(sabangnet-live-test): Confirm whether ORD_SUM_AMT expects the
            # line total or the full order payment amount for multi-item orders.
            "order_amount": item.line_total,
            "quantity": item.ordered_quantity,
        }
        for item in order.items.order_by("id")
    ]


def build_order_workbook(rows):
    # dataFrRowSrno=0 indicates that data starts on the first row. Sabangnet's
    # configured column labels are metadata, not a header row in the upload.
    # TODO(sabangnet-live-test): Verify this with one disposable test order.
    values = [[row[key] for _, key in SABANGNET_ORDER_COLUMNS] for row in rows]
    return _build_minimal_xlsx(values)


@transaction.atomic
def export_pending_orders(filename, limit=500, output_path=None):
    exports = list(
        SabangnetOrderExport.objects.select_for_update()
        .filter(status=SabangnetOrderExport.Status.PENDING, order__status=Order.Status.PAID)
        .select_related("order")
        .prefetch_related("order__items")
        .order_by("created_at")[:limit]
    )
    rows = [row for export in exports for row in build_order_rows(export.order)]
    workbook = build_order_workbook(rows)
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(workbook)
    generated_at = timezone.now()
    for export in exports:
        export.status = SabangnetOrderExport.Status.GENERATED
        export.generated_at = generated_at
        export.filename = filename
        export.row_count = export.order.items.count()
        export.payload_summary = {
            "order_number": export.order.order_number,
            "row_count": export.row_count,
        }
        export.save(
            update_fields=["status", "generated_at", "filename", "row_count", "payload_summary", "updated_at"]
        )
        # File generation is not proof of registration. The future uploader
        # must set REGISTERED only after parsing a successful Sabangnet result.
        export.order.sabangnet_status = "file_generated"
        export.order.save(update_fields=["sabangnet_status", "updated_at"])
    return workbook, len(exports), len(rows)


def pending_order_export_count():
    return SabangnetOrderExport.objects.filter(
        status=SabangnetOrderExport.Status.PENDING,
        order__status=Order.Status.PAID,
    ).count()


def _build_minimal_xlsx(values):
    sheet_rows = []
    for row_number, row in enumerate(values, start=1):
        cells = []
        for column_number, value in enumerate(row, start=1):
            reference = f"{_column_name(column_number)}{row_number}"
            if isinstance(value, int):
                cells.append(f'<c r="{reference}"><v>{value}</v></c>')
            else:
                cells.append(
                    f'<c r="{reference}" t="inlineStr"><is><t xml:space="preserve">'
                    f"{escape(str(value))}</t></is></c>"
                )
        sheet_rows.append(f'<row r="{row_number}">{"".join(cells)}</row>')

    worksheet = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" '
        'activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>'
        '<cols><col min="1" max="1" width="30" customWidth="1"/>'
        '<col min="2" max="3" width="22" customWidth="1"/>'
        '<col min="4" max="5" width="18" customWidth="1"/>'
        '<col min="6" max="6" width="42" customWidth="1"/>'
        '<col min="7" max="8" width="14" customWidth="1"/></cols>'
        f'<sheetData>{"".join(sheet_rows)}</sheetData><autoFilter ref="A1:H{max(len(values), 1)}"/>'
        '</worksheet>'
    )
    files = {
        "[Content_Types].xml": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '</Types>',
        "_rels/.rels": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        '</Relationships>',
        "xl/workbook.xml": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="사방넷 주문등록" sheetId="1" r:id="rId1"/></sheets></workbook>',
        "xl/_rels/workbook.xml.rels": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
        '</Relationships>',
        "xl/worksheets/sheet1.xml": worksheet,
    }
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for path, contents in files.items():
            archive.writestr(path, contents)
    return output.getvalue()


def _column_name(number):
    result = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        result = chr(65 + remainder) + result
    return result


def _product_name_with_option(item):
    parts = [item.product_name_snapshot.strip()]
    if item.option_name_snapshot.strip():
        parts.append(item.option_name_snapshot.strip())
    return " / ".join(parts)
