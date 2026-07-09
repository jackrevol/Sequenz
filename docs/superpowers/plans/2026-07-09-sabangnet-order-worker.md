# Sabangnet Order Worker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Process paid-order Sabangnet submission records into deterministic payloads, mark success/failure, and expose a management command for retries.

**Architecture:** The public Sabangnet docs currently confirm order lookup, but not the exact mall-order registration endpoint. This slice keeps live API transport behind a small client interface and implements a deterministic worker around `SabangnetOrderSubmission`; tests use a fake client so later endpoint changes only affect the client class.

**Tech Stack:** Django 5, pytest-django, standard library JSON/urllib, SQLite local database.

---

### Task 1: Payload Builder And Submission Service

**Files:**
- Create: `tests/test_sabangnet_order_worker.py`
- Create: `integrations/sabangnet.py`
- Modify: `integrations/models.py`

- [x] **Step 1: Write failing tests**

Add tests proving:

- a paid order submission is sent with order, buyer, receiver, amount, and item snapshots
- a successful client response marks the submission `sent` and order `sabangnet_status=sent`
- a client failure marks the submission `failed`, increments attempts, stores a safe error, and keeps the order paid
- an already sent submission is not sent again

- [x] **Step 2: Verify red**

Run: `.venv/bin/python -m pytest tests/test_sabangnet_order_worker.py -q`

Expected: fail because `integrations.sabangnet` does not exist.

- [x] **Step 3: Implement minimal service**

Add:

- `SabangnetClientError`
- `SabangnetResponse`
- `build_order_payload(order)`
- `submit_order_submission(submission, client)`
- `process_pending_order_submissions(client, limit=50)`

The service must not log or return secret values. It must not call live Sabangnet unless a concrete client is explicitly passed.

- [x] **Step 4: Verify green**

Run: `.venv/bin/python -m pytest tests/test_sabangnet_order_worker.py -q`

Expected: pass.

### Task 2: Management Command

**Files:**
- Create: `integrations/management/__init__.py`
- Create: `integrations/management/commands/__init__.py`
- Create: `integrations/management/commands/submit_sabangnet_orders.py`
- Modify: `tests/test_sabangnet_order_worker.py`

- [x] **Step 1: Write failing command test**

Add a test proving the command can run in dry-run mode and reports pending count without submitting.

- [x] **Step 2: Verify red**

Run: `.venv/bin/python -m pytest tests/test_sabangnet_order_worker.py -q`

Expected: fail because the command does not exist.

- [x] **Step 3: Implement command**

Add `submit_sabangnet_orders` with:

- `--limit`
- `--dry-run`

Dry-run prints how many pending/retrying submissions would be processed. Non-dry-run uses the default client placeholder and fails clearly until live credentials and endpoint mapping are configured.

- [x] **Step 4: Verify green**

Run: `.venv/bin/python -m pytest tests/test_sabangnet_order_worker.py -q`

Expected: pass.

### Task 3: Full Verification And Commit

**Files:**
- Update this plan checkboxes.

- [x] **Step 1: Run full tests**

Run: `.venv/bin/python -m pytest -q`

Expected: pass.

- [x] **Step 2: Run Django check**

Run: `.venv/bin/python manage.py check`

Expected: no issues.

- [x] **Step 3: Commit**

Run:

```bash
git add .
git commit -m "feat: add sabangnet order worker"
```
