import hashlib

from django.db import transaction
from django.utils.text import slugify

from catalog.models import Category
from integrations.sabangnet_client import SabangnetApiClient, SabangnetApiError


class SabangnetCategoryError(Exception):
    pass


class SabangnetCategoryClient:
    def __init__(self, base_url=None, bearer_token=None, service_account_id=None, timeout=None, api_client=None):
        self.api_client = api_client or SabangnetApiClient(
            base_url=base_url,
            bearer_token=bearer_token,
            service_account_id=service_account_id,
            timeout=timeout,
        )

    def fetch_categories(self):
        try:
            return self.api_client.request_json("GET", "/category")
        except SabangnetApiError as exc:
            raise SabangnetCategoryError(str(exc)) from exc


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
        for key in ("response", "categories", "data", "data_list", "result", "items"):
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
