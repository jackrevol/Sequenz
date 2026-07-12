import pytest
from django.contrib import admin

from catalog.models import Brand, ProductListing
from commerce.models import Order, Payment
from integrations.models import SabangnetOrderExport


@pytest.mark.django_db
def test_storefront_is_available(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"SEQUENZ" in response.content
    assert b"productGrid" in response.content


@pytest.mark.django_db
def test_container_health_endpoint_checks_database(client):
    response = client.get("/healthz/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_operational_models_are_registered_in_admin():
    assert Brand in admin.site._registry
    assert ProductListing in admin.site._registry
    assert Order in admin.site._registry
    assert Payment in admin.site._registry
    assert SabangnetOrderExport in admin.site._registry
