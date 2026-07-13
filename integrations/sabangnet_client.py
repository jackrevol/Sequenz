import base64
import json
import ssl
import time
from dataclasses import dataclass
from urllib import error, parse, request

import bcrypt
from django.conf import settings


class SabangnetApiError(Exception):
    def __init__(self, message, *, code="", status=None):
        super().__init__(message)
        self.code = str(code or "")
        self.status = status


@dataclass(frozen=True)
class SabangnetBulkResult:
    total_count: int
    success_count: int
    fail_count: int
    errors: tuple[str, ...] = ()

    @property
    def all_succeeded(self):
        return self.fail_count == 0

    @property
    def item_results_available(self):
        return self.total_count > 0


class SabangnetApiClient:
    """Shared OAuth and JSON transport for the Sabangnet sandbox/API."""

    def __init__(
        self,
        *,
        base_url=None,
        token_url=None,
        client_id=None,
        client_secret=None,
        client_type=None,
        auth_mode=None,
        bearer_token=None,
        service_account_id=None,
        timeout=None,
        verify_ssl=None,
        urlopen=None,
    ):
        self.base_url = (base_url or settings.SABANGNET_API_BASE_URL).rstrip("/")
        self.token_url = token_url or settings.SABANGNET_TOKEN_URL or (
            f"{self.base_url}/oauth2/token" if self.base_url else ""
        )
        self.client_id = client_id or settings.SABANGNET_CLIENT_ID
        self.client_secret = client_secret or settings.SABANGNET_CLIENT_SECRET
        self.client_type = client_type or settings.SABANGNET_CLIENT_TYPE
        self.auth_mode = auth_mode or settings.SABANGNET_AUTH_MODE
        self.service_account_id = service_account_id or settings.SABANGNET_SVC_ACCOUNT_ID
        self.timeout = timeout if timeout is not None else settings.SABANGNET_TIMEOUT_SECONDS
        self.verify_ssl = settings.SABANGNET_VERIFY_SSL if verify_ssl is None else verify_ssl
        self._configured_bearer_token = bearer_token or settings.SABANGNET_BEARER_TOKEN
        self._access_token = self._configured_bearer_token
        self._token_expires_at = float("inf") if self._access_token else 0
        self._urlopen = urlopen or request.urlopen

    def get_access_token(self, *, force_refresh=False):
        if self._configured_bearer_token:
            return self._configured_bearer_token
        if not force_refresh and self._access_token and time.monotonic() < self._token_expires_at:
            return self._access_token
        self._validate_oauth_configuration()
        timestamp = str(int(time.time() * 1000))
        value = f"{self.client_id}_{timestamp}".encode()
        try:
            hashed = bcrypt.hashpw(value, self.client_secret.encode())
        except ValueError as exc:
            raise SabangnetApiError("사방넷 Client Secret 형식이 올바르지 않습니다.", code="CONFIG_SECRET") from exc
        secret_sign = base64.b64encode(hashed).decode()
        body = parse.urlencode(
            {
                "grant_type": "client_credentials",
                "clientType": self.client_type,
                "clientCd": self.client_id,
                "timestamp": timestamp,
                "secretSign": secret_sign,
                "authMode": self.auth_mode,
            }
        ).encode()
        payload, _ = self._send(
            request.Request(
                self.token_url,
                data=body,
                method="POST",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        )
        token = str(payload.get("access_token") or "") if isinstance(payload, dict) else ""
        if not token:
            raise SabangnetApiError("사방넷 토큰 응답에 access_token이 없습니다.", code="AUTH_TOKEN_EMPTY")
        expires_in = _positive_int(payload.get("expires_in"), default=300)
        self._access_token = token
        self._token_expires_at = time.monotonic() + max(expires_in - 60, 1)
        return token

    def request_json(self, method, path, *, query=None, json_body=None):
        if not self.base_url:
            raise SabangnetApiError("SABANGNET_API_BASE_URL이 설정되지 않았습니다.", code="CONFIG_BASE_URL")
        if not self.service_account_id:
            raise SabangnetApiError("SABANGNET_SVC_ACCOUNT_ID가 설정되지 않았습니다.", code="CONFIG_SERVICE_ACCOUNT")
        query_string = f"?{parse.urlencode(query)}" if query else ""
        normalized_path = path if path.startswith("/") else f"/{path}"
        url = f"{self.base_url}/v3/sb{normalized_path}{query_string}"
        body = json.dumps(json_body, ensure_ascii=False).encode() if json_body is not None else None
        for attempt in range(2):
            headers = {
                "Authorization": f"Bearer {self.get_access_token(force_refresh=attempt == 1)}",
                "Accept": "application/json",
                "X-Svc-Acnt-Id": self.service_account_id,
            }
            if body is not None:
                headers["Content-Type"] = "application/json"
            try:
                payload, _ = self._send(request.Request(url, data=body, method=method, headers=headers))
                return payload
            except SabangnetApiError as exc:
                if attempt == 0 and exc.status == 401 and not self._configured_bearer_token:
                    self._access_token = ""
                    self._token_expires_at = 0
                    continue
                raise
        raise SabangnetApiError("사방넷 요청 재시도에 실패했습니다.")

    def _validate_oauth_configuration(self):
        missing = []
        if not self.token_url:
            missing.append("SABANGNET_TOKEN_URL")
        if not self.client_id:
            missing.append("SABANGNET_CLIENT_ID")
        if not self.client_secret:
            missing.append("SABANGNET_CLIENT_SECRET")
        if missing:
            raise SabangnetApiError(f"사방넷 OAuth 환경변수가 설정되지 않았습니다: {', '.join(missing)}", code="CONFIG_OAUTH")
        if self.auth_mode not in {"PRODUCTION", "SANDBOX"}:
            raise SabangnetApiError("SABANGNET_AUTH_MODE는 PRODUCTION 또는 SANDBOX여야 합니다.", code="CONFIG_AUTH_MODE")
        if len(self.client_secret) != 29 or not self.client_secret.startswith(("$2a$", "$2b$", "$2y$")):
            raise SabangnetApiError("사방넷 Client Secret 형식이 올바르지 않습니다.", code="CONFIG_SECRET")

    def _send(self, http_request):
        context = None if self.verify_ssl else ssl._create_unverified_context()
        try:
            with self._urlopen(http_request, timeout=self.timeout, context=context) as response:
                status = getattr(response, "status", 200)
                payload = _decode_json(response.read())
        except error.HTTPError as exc:
            payload = _decode_json(exc.read(), allow_invalid=True)
            code, message = _error_details(payload)
            label = f"{code}: {message}" if code and message else message or f"HTTP {exc.code}"
            raise SabangnetApiError(f"사방넷 API 요청이 실패했습니다 ({label}).", code=code, status=exc.code) from exc
        except (error.URLError, TimeoutError) as exc:
            raise SabangnetApiError("사방넷 API에 연결하지 못했습니다.", code="NETWORK") from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SabangnetApiError("사방넷 API 응답이 올바른 JSON이 아닙니다.", code="INVALID_JSON") from exc
        code, message = _error_details(payload)
        if code and code not in {"200", "206"}:
            raise SabangnetApiError(
                f"사방넷 API 요청이 실패했습니다 ({code}: {message or '알 수 없는 오류'}).",
                code=code,
                status=status,
            )
        return payload, status


def unwrap_response(payload):
    if isinstance(payload, dict) and "code" in payload:
        for key in ("response", "data"):
            if key in payload:
                return payload[key]
    return payload


def extract_data_list(payload):
    payload = unwrap_response(payload)
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []
    for key in (
        "data_list", "processed_data_list", "items", "results", "details",
        "orders", "products", "categories", "data",
    ):
        value = payload.get(key)
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            rows = extract_data_list(value)
            if rows:
                return rows
    return []


def response_count(payload):
    response = unwrap_response(payload)
    if isinstance(response, dict):
        for key in (
            "total_count", "processed_count", "totalCount", "processedCount",
            "totalItemCnt", "curItemCnt",
        ):
            if key in response:
                return _positive_int(response[key], default=0)
    return len(extract_data_list(payload))


def parse_bulk_result(payload):
    data = unwrap_response(payload)
    if not isinstance(data, dict):
        return SabangnetBulkResult(total_count=0, success_count=0, fail_count=0)
    rows = data.get("results") if isinstance(data.get("results"), list) else []
    row_successes = sum(row.get("status") is True for row in rows if isinstance(row, dict))
    row_failures = sum(row.get("status") is False for row in rows if isinstance(row, dict))
    errors = tuple(
        str(row.get("errorMessage") or row.get("message"))[:500]
        for row in rows
        if isinstance(row, dict) and row.get("status") is False and (row.get("errorMessage") or row.get("message"))
    )
    total = _first_count(data, "totalCount", "total_count", default=len(rows))
    success = _first_count(data, "successCount", "success_count", default=row_successes)
    failed = _first_count(data, "failCount", "failureCount", "fail_count", default=row_failures)
    if total == 0 and success + failed:
        total = success + failed
    return SabangnetBulkResult(total_count=total, success_count=success, fail_count=failed, errors=errors)


def ensure_bulk_success(payload, *, operation):
    result = parse_bulk_result(payload)
    if not result.all_succeeded:
        raise SabangnetApiError(
            f"사방넷 {operation} 처리 중 {result.total_count}건 중 {result.fail_count}건이 실패했습니다.",
            code="BULK_PARTIAL_FAILURE",
        )
    return result


def _decode_json(body, *, allow_invalid=False):
    try:
        return json.loads(body.decode())
    except (UnicodeDecodeError, json.JSONDecodeError):
        if allow_invalid:
            return {}
        raise


def _error_details(payload):
    if not isinstance(payload, dict):
        return "", ""
    code = str(payload.get("code") or payload.get("error") or "")
    message = str(payload.get("message") or payload.get("error_description") or "")
    return code, message


def _positive_int(value, *, default):
    try:
        return max(int(value), 0)
    except (TypeError, ValueError):
        return default


def _first_count(payload, *keys, default):
    for key in keys:
        if key in payload:
            return _positive_int(payload[key], default=default)
    return default
