# Deindustrialization Batch 3A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the five peripheral fulfillment domains from production code, API/UI/config/runtime surfaces, and current schema through one forward migration while preserving the Industrial Diagnosis Golden Path.

**Architecture:** Delete supplier collaboration/A2A, refund, procurement, service quotation, and customer notification ownership surfaces. Keep shared approval/audit/gateway primitives and the five Diagnosis read-only tools. Remove the quotation-dependent WorkOrder service-authorization branch only as the direct compatibility change required to drop its FK; do not refactor the remaining WorkOrder/Parts lifecycle.

**Tech Stack:** Python 3.11–3.13, FastAPI, SQLAlchemy, Alembic, TypeScript/Next.js, Ruff, mypy, SQLite rehearsal.

**Spec:** `C:/Users/32313/.codex/attachments/644f30cf-d9ff-4fd7-8387-50f7beeac975/pasted-text.txt`

## Global Constraints

- Do not edit historical Alembic migrations `0001`–`0088`.
- Preserve the Golden Path and the five Diagnosis tools with unchanged schema and behavior.
- Do not enter WorkOrder fulfillment, Parts mutation redesign, Predictive Maintenance, realtime, Kafka/Debezium, GraphRAG, frontend redesign, Model Gateway generalization, Technical Incident Triage, or Batch 3B.
- Do not install or repair `spacy.tokens`, `temporalio.bridge`, `pywintypes`, or PostgreSQL infrastructure.
- Use child-first forward schema deletion and record PostgreSQL as `NOT RUN — no disposable PostgreSQL environment available`.

### Task 1: Baseline and RED deletion smoke

**Files:**
- Create: `scripts/deindustrialization_batch3a_deletion_smoke.py`
- Read: `docs/deindustrialization_batch3a_inventory.md`
- Test: existing Batch 1/1.5/2A/2B/2C smokes

- [ ] **Step 1: Run the current regression baseline.**

Run each existing deindustrialization smoke with `.venv/Scripts/python.exe` and `PYTHONPATH=src`; record output before deletion.

- [ ] **Step 2: Add a failing mechanical smoke.**

Assert that deleted route modules, deleted adapter modules, deleted supplier package, deleted mutation tool IDs, and deleted runtime construction symbols are absent, while the five Diagnosis tool IDs are present. Run it and confirm it fails against the current repository.

### Task 2: Delete supplier collaboration/A2A

**Files:**
- Delete: `src/industrial_ops_agent/collaboration/`, `src/industrial_ops_agent/supplier_sandbox/`, `src/industrial_ops_agent/simulation/supplier_a2a_lab.py`, `src/industrial_ops_agent/simulation/supplier_a2a_lab_cli.py`, `src/industrial_ops_agent/api/routes/collaborations.py`, `web/app/collaboration/page.tsx`
- Modify: `src/industrial_ops_agent/api/app.py`, `src/industrial_ops_agent/runtime.py`, `src/industrial_ops_agent/config.py`, `src/industrial_ops_agent/secrets.py`, `infra/keycloak/m1-realm.json`, `infra/vault/bootstrap.sh`, `scripts/dev_lite.sh`, `src/industrial_ops_agent/persistence/models.py`, `web/lib/api/client.ts`, `web/generated/api/schema.d.ts`
- Test: `scripts/deindustrialization_batch3a_deletion_smoke.py`

- [ ] **Step 1:** Remove only supplier imports, state, route registration, client construction, config/secrets, UI/client surfaces, and two supplier ORM classes.
- [ ] **Step 2:** Run the deletion smoke and preserved Golden Path smoke.

### Task 3: Delete refund, procurement, and notification surfaces

**Files:**
- Delete: `src/industrial_ops_agent/tools/refunds.py`, `src/industrial_ops_agent/tools/procurement.py`, `src/industrial_ops_agent/tools/customer_notifications.py`, `src/industrial_ops_agent/api/routes/refunds.py`, `src/industrial_ops_agent/api/routes/procurement.py`, `src/industrial_ops_agent/api/routes/customer_notifications.py`, `web/components/m2/RefundRequestPanel.tsx`, `web/components/m2/PurchaseRequestPanel.tsx`, `web/components/m2/CustomerNotificationProposalPanel.tsx`
- Modify: `src/industrial_ops_agent/tools/registry.py`, `src/industrial_ops_agent/tools/gateway.py`, `src/industrial_ops_agent/tools/factory.py`, `src/industrial_ops_agent/api/app.py`, `src/industrial_ops_agent/api/routes/approvals.py`, `src/industrial_ops_agent/runtime.py`, `src/industrial_ops_agent/config.py`, `src/industrial_ops_agent/secrets.py`, `src/industrial_ops_agent/persistence/models.py`, `web/app/incidents/[incidentId]/page.tsx`, `web/app/approvals/page.tsx`, `web/lib/api/client.ts`, `web/generated/api/schema.d.ts`, `infra/vault/bootstrap.sh`, `scripts/dev_lite.sh`
- Test: `scripts/deindustrialization_batch3a_deletion_smoke.py`

- [ ] **Step 1:** Remove mutation definitions and only their Gateway/approval route branches; retain generic ToolGateway governance and Parts/WorkOrder/FSM capabilities.
- [ ] **Step 2:** Remove provider construction/injection and UI/API client usage for these three domains.
- [ ] **Step 3:** Run the deletion smoke and all preserved regression smokes.

### Task 4: Delete service quotation with minimal WorkOrder compatibility change

**Files:**
- Delete: `src/industrial_ops_agent/tools/quotations.py`, `web/components/m2/ServiceQuotationPanel.tsx`
- Modify: `src/industrial_ops_agent/tools/registry.py`, `src/industrial_ops_agent/tools/gateway.py`, `src/industrial_ops_agent/tools/factory.py`, `src/industrial_ops_agent/api/routes/approvals.py`, `src/industrial_ops_agent/api/routes/portal.py`, `src/industrial_ops_agent/api/routes/workorders.py`, `src/industrial_ops_agent/workorders/service.py`, `src/industrial_ops_agent/persistence/models.py`, `src/industrial_ops_agent/runtime.py`, `src/industrial_ops_agent/config.py`, `src/industrial_ops_agent/secrets.py`, `web/app/incidents/[incidentId]/page.tsx`, `web/app/portal/cases/[incidentId]/page.tsx`, `web/lib/api/client.ts`, `web/generated/api/schema.d.ts`
- Test: `scripts/deindustrialization_batch3a_deletion_smoke.py`

- [ ] **Step 1:** Remove quotation proposal/customer decision code and tool/provider wiring.
- [ ] **Step 2:** Remove only `SERVICE_AUTHORIZATION`/`ACCEPTED_QUOTATION` and `service_quotation_id` WorkOrder binding needed to eliminate the current FK; preserve Parts reservation and remaining WorkOrder lifecycle.
- [ ] **Step 3:** Run the deletion smoke and WorkOrder/Parts-preservation checks.

### Task 5: Forward migration and schema rehearsal

**Files:**
- Create: `alembic/versions/0089_remove_peripheral_fulfillment.py`
- Modify: `scripts/deindustrialization_batch3a_deletion_smoke.py`

- [ ] **Step 1:** Write migration assertions for child-first deletion of notification receipts/delivery, procurement receipts/fulfillments/requests, refund receipts/requests, quotation decisions/quotations, supplier events/collaboration, plus the WorkOrder quotation FK/column and quotation check binding.
- [ ] **Step 2:** Run SQLite upgrade rehearsal and inspect tables/FKs; verify Alembic head is `0089`.
- [ ] **Step 3:** Record PostgreSQL as not run without creating infrastructure.

### Task 6: Route, dead-reference, and full acceptance verification

**Files:**
- Modify: `scripts/deindustrialization_batch3a_deletion_smoke.py`, `docs/deindustrialization_batch3a_report.md`, `docs/deindustrialization_batch3a_followups.md`

- [ ] **Step 1:** Produce route inventory and mechanical scan classifications; fix stale production references only.
- [ ] **Step 2:** Run all required Batch 1/1.5/2A/2B/2C smokes, deletion smoke, Ruff, `py_compile`, focused mypy, route inventory, Alembic heads, and SQLite rehearsal.
- [ ] **Step 3:** Update the report with deleted/preserved surfaces, Before/After runtime, database, route/tool inventories, environment debt, Golden Path result, and remaining industrial domains.
- [ ] **Step 4:** Declare `Batch 3A deletion goals: PASS` only if every required domain and verification passes; otherwise declare `PARTIAL` or `FAIL` with the exact blocker and do not start Batch 3B.
