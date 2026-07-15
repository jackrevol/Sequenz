import pytest
from django.contrib import admin
from django.conf import settings
from django.test import override_settings

from catalog.models import Brand, ProductListing
from commerce.models import Order, Payment
from integrations.models import SabangnetOrderExport


@pytest.mark.django_db
def test_storefront_is_available(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"SEQUENZ" in response.content
    assert b"productGrid" in response.content
    assert b"skip-link" in response.content
    assert b"site-footer" in response.content
    assert b"favicon.svg" in response.content


@pytest.mark.django_db
def test_container_health_endpoint_checks_database(client):
    response = client.get("/healthz/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.django_db
@override_settings(
    TOSS_CLIENT_KEY="",
    TOSS_SECRET_KEY="",
    SABANGNET_CLIENT_ID="",
    SABANGNET_CLIENT_SECRET="",
    SABANGNET_BEARER_TOKEN="",
    SABANGNET_SVC_ACCOUNT_ID="",
)
def test_storefront_and_health_are_available_without_external_credentials(client):
    assert client.get("/").status_code == 200
    assert client.get("/healthz/").status_code == 200


@pytest.mark.django_db
def test_product_uses_dedicated_detail_page(client, listing_variant):
    response = client.get(f"/products/{listing_variant.listing_id}/")
    assert response.status_code == 200
    assert b"product-page" in response.content
    assert b"siteSidebar" in response.content
    assert str(listing_variant.listing_id).encode() in response.content
    assert b"site-footer" in response.content


@pytest.mark.django_db
def test_storefront_has_isolated_responsive_layout(client):
    response = client.get("/")

    assert b'class="storefront-page"' in response.content
    assert b'class="storefront-main"' in response.content
    stylesheet = (settings.BASE_DIR / "static/storefront/store.css").read_text()
    script = (settings.BASE_DIR / "static/storefront/store.js").read_text()
    assert ".hero.has-media" in stylesheet
    assert "background-size:cover" in stylesheet
    assert "globalThis.crypto?.randomUUID" in script
    assert "hero.classList.add('has-media')" in script


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("url", "page_kind"),
    [
        ("/cart/", "cart"),
        ("/checkout/", "checkout"),
        ("/account/", "account"),
        ("/support/", "support"),
        ("/orders/SEQ-TEST-001/", "order"),
        ("/content/lookbooks/summer-edit/", "content"),
    ],
)
def test_storefront_flows_have_dedicated_pages(client, url, page_kind):
    response = client.get(url)

    assert response.status_code == 200
    assert f'data-page="{page_kind}"'.encode() in response.content
    assert b'id="pageContent"' in response.content


@pytest.mark.django_db
def test_home_navigation_uses_pages_instead_of_dialogs(client):
    response = client.get("/")

    assert b'href="/cart/"' in response.content
    assert b'href="/account/"' in response.content
    assert b'href="/support/"' in response.content
    assert b"<dialog" not in response.content


def test_operational_models_are_registered_in_admin():
    assert Brand in admin.site._registry
    assert ProductListing in admin.site._registry
    assert Order in admin.site._registry
    assert Payment in admin.site._registry
    assert SabangnetOrderExport in admin.site._registry
