# Django Commerce Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first executable Django backend for the clothing commerce mall from the approved requirements, API references, and DB model design.

**Architecture:** Create a Django + Django REST Framework project with focused apps for catalog and commerce. Implement the first API slice around product listings, variants, guest carts, order creation, and payment attempts, using `ProductListing` as the customer-facing sale object separate from the Sabangnet product master.

**Tech Stack:** Python 3.12, Django 5.x, Django REST Framework, pytest, pytest-django, SQLite for local development.

---

### Task 1: Test Harness

**Files:**
- Create: `requirements.txt`
- Create: `pytest.ini`
- Create: `tests/test_catalog_api.py`
- Create: `tests/test_commerce_api.py`

- [ ] **Step 1: Write failing API tests**

Create tests that prove the target public API shape:

```python
def test_active_listing_list_returns_customer_facing_product(api_client, listing):
    response = api_client.get("/api/catalog/listings/")
    assert response.status_code == 200
    assert response.json()["results"][0]["display_name"] == listing.display_name
```

```python
def test_guest_cart_add_uses_listing_variant_and_price_snapshot(api_client, listing_variant):
    response = api_client.post("/api/commerce/cart/items/", {
        "listing_variant_id": listing_variant.id,
        "quantity": 2,
    }, format="json", HTTP_X_GUEST_KEY="guest-1")
    assert response.status_code == 201
    assert response.json()["quantity"] == 2
    assert response.json()["unit_price_snapshot"] == listing_variant.listing.selling_price_snapshot
```

- [ ] **Step 2: Run tests to verify red**

Run: `.venv/bin/python -m pytest tests/test_catalog_api.py tests/test_commerce_api.py -q`
Expected: fail because Django project and apps do not exist.

### Task 2: Django Project And Models

**Files:**
- Create: `manage.py`
- Create: `sequenz/settings.py`
- Create: `sequenz/urls.py`
- Create: `catalog/models.py`
- Create: `commerce/models.py`
- Create: app config and migration package files

- [ ] **Step 1: Implement minimal Django project**

Create a Django project configured for DRF, SQLite, and local tests.

- [ ] **Step 2: Implement catalog models**

Add `Brand`, `Category`, `Product`, `ProductVariant`, `ProductListing`, and `ProductListingVariant`.

- [ ] **Step 3: Implement commerce models**

Add `Cart`, `CartItem`, `Order`, `OrderItem`, `PaymentAttempt`, and `Payment`.

- [ ] **Step 4: Run migrations in test database through pytest**

Run: `.venv/bin/python -m pytest tests/test_catalog_api.py tests/test_commerce_api.py -q`
Expected: fail only because API views do not exist.

### Task 3: Public APIs

**Files:**
- Create: `catalog/serializers.py`
- Create: `catalog/views.py`
- Create: `catalog/urls.py`
- Create: `commerce/serializers.py`
- Create: `commerce/views.py`
- Create: `commerce/urls.py`
- Modify: `sequenz/urls.py`

- [ ] **Step 1: Implement listing list/detail API**

Expose `/api/catalog/listings/` and `/api/catalog/listings/<id>/`.

- [ ] **Step 2: Implement guest cart add/list API**

Expose `/api/commerce/cart/items/` using `X-Guest-Key`.

- [ ] **Step 3: Implement order creation API**

Expose `/api/commerce/orders/` from current cart snapshot.

- [ ] **Step 4: Verify tests pass**

Run: `.venv/bin/python -m pytest -q`
Expected: all tests pass.

### Task 4: Verification

**Files:**
- Modify as needed.

- [ ] **Step 1: Run Django checks**

Run: `.venv/bin/python manage.py check`
Expected: no issues.

- [ ] **Step 2: Run tests**

Run: `.venv/bin/python -m pytest -q`
Expected: all tests pass.

- [ ] **Step 3: Commit**

Run:

```bash
git add .
git commit -m "feat: scaffold django commerce backend"
```
