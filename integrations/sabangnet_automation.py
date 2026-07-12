from dataclasses import dataclass, field

from django.conf import settings


@dataclass(frozen=True)
class SabangnetSequenceTarget:
    page_url: str = "https://sbadmin11.sabangnet.co.kr/#/order/order-collect-large"
    mall_label: str = "시퀸즈 [20316]"
    shma_id: str = "chop0001"
    connection_login_id: str = field(default_factory=lambda: settings.SABANGNET_MALL_CONNECTION_LOGIN_ID)
    account_registration_serial: str = field(default_factory=lambda: settings.SABANGNET_ACCOUNT_REGISTRATION_SERIAL)
    excel_form_serial: str = "20316"
    row_selector: str = "tr.el-table__row"
    file_input_selector: str = 'input[type="file"][name="fileUpload00"]'
    save_button_selector: str = "button.sb-save-btn1"
    result_row_selector: str = "div.app-container .sb-border-line2 ul > li"


SEQUENCE_TARGET = SabangnetSequenceTarget()

SUCCESS_MESSAGE = "등록 성공"
DUPLICATE_MESSAGE = "이미 등록된 자료입니다."
KNOWN_FAILURE_MESSAGES = (
    "해당하는 양식이 없습니다.",
    "데이터에 문제가 있습니다.",
    "우편번호 타입이 일치하지 않습니다. 확인바랍니다.",
    "주문번호, 쇼핑몰상품코드, 주문수량은 필수입니다.",
)


def classify_registration_message(message):
    normalized = message.strip()
    if SUCCESS_MESSAGE in normalized:
        return "registered"
    if DUPLICATE_MESSAGE in normalized:
        return "duplicate"
    if any(known in normalized for known in KNOWN_FAILURE_MESSAGES):
        return "failed"
    return "unknown"


def upload_generated_workbook(*args, **kwargs):
    """Upload a generated file after the live-test assumptions are verified."""
    # TODO(sabangnet-auth): Implement environment-variable login without
    # logging credentials, bearer tokens, cookies, or session contents.
    # TODO(sabangnet-selector): Scope file and save controls to the unique row
    # whose text is exactly `시퀸즈 [20316]` before performing any action.
    # TODO(sabangnet-live-test): Verify headerless input, multi-item amount
    # semantics, accepted extension/size, and duplicate-key behavior.
    # TODO(sabangnet-result): Click save only in explicit live mode, collect all
    # result rows, then mark only confirmed successes as REGISTERED.
    raise NotImplementedError("Sabangnet live registration is intentionally disabled pending a controlled test.")
