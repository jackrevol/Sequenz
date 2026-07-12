import hashlib
import json
from urllib import error, request

from django.conf import settings
from django.db import transaction
from django.utils.text import slugify

from catalog.models import Category


class SabangnetCategoryError(Exception):
    pass


class SabangnetCategoryClient:
    def __init__(self, base_url=None, bearer_token=None, service_account_id=None, timeout=15):
        self.base_url = base_url or settings.SABANGNET_API_BASE_URL
        self.bearer_token = bearer_token or settings.SABANGNET_BEARER_TOKEN
        self.service_account_id = service_account_id or settings.SABANGNET_SVC_ACCOUNT_ID
        self.timeout = timeout

    def fetch_categories(self):
        if not self.base_url or not self.bearer_token or not self.service_account_id:
            raise SabangnetCategoryError("사방넷 카테고리 API 환경변수가 설정되지 않았습니다.")
        http_request = request.Request(
            f"{self.base_url.rstrip('/')}/v3/sb/category",
            headers={"Authorization": f"Bearer {self.bearer_token}", "X-Svc-Acnt-Id": self.service_account_id},
        )
        try:
            with request.urlopen(http_request, timeout=self.timeout) as response:
                return json.loads(response.read().decode())
        except error.HTTPError as exc:
            raise SabangnetCategoryError(f"사방넷 카테고리 조회가 HTTP {exc.code}로 실패했습니다.") from exc
        except (error.URLError, TimeoutError, ValueError) as exc:
            raise SabangnetCategoryError("사방넷 카테고리 응답을 처리하지 못했습니다.") from exc


@transaction.atomic
def sync_categories(payload):
    paths = _category_paths(payload)
    synced = []
    by_code = {item.sabangnet_code: item for item in Category.objects.exclude(sabangnet_code__isnull=True)}
    for path in sorted(paths, key=len):
        parent = None
        for position, row in enumerate(path):
            code = str(_value(row, "code", "categoryCode", default="")).strip()
            name = str(_value(row, "name", "categoryName", default=code)).strip()
            if not code:
                continue
            category = by_code.get(code)
            defaults = {
                "parent": parent,
                "name": name or code,
                "level": int(_value(row, "level", default=position + 1) or position + 1),
                "sort_order": int(_value(row, "sortSrno", default=0) or 0),
                "is_visible": str(_value(row, "useYn", default="Y")).upper() == "Y",
            }
            if category is None:
                category = Category.objects.create(
                    sabangnet_code=code, slug=_unique_slug(name or code, parent), **defaults
                )
                by_code[code] = category
            else:
                for field, value in defaults.items():
                    setattr(category, field, value)
                category.save(update_fields=[*defaults, "updated_at"])
            parent = category
            synced.append(category)
    return list({category.pk: category for category in synced}.values())


def _category_paths(payload):
    paths = []
    if isinstance(payload, list):
        if payload and all(isinstance(row, dict) and _value(row, "code", "categoryCode") for row in payload):
            return [[row] for row in payload]
        for value in payload:
            paths.extend(_category_paths(value))
    elif isinstance(payload, dict):
        category = payload.get("category")
        if isinstance(category, list) and category:
            paths.append(category)
        for key in ("categories", "data", "result", "items"):
            if key in payload:
                paths.extend(_category_paths(payload[key]))
    return paths


def _value(payload, *keys, default=None):
    for key in keys:
        if isinstance(payload, dict) and payload.get(key) is not None:
            return payload[key]
    return default


def _unique_slug(name, parent):
    base = slugify(name, allow_unicode=True) or f"category-{hashlib.sha1(name.encode()).hexdigest()[:8]}"
    candidate = base
    number = 1
    while Category.objects.filter(parent=parent, slug=candidate).exists():
        number += 1
        candidate = f"{base}-{number}"
    return candidate
