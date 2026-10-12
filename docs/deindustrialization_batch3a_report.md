# Deindustrialization Batch 3A — Peripheral Fulfillment Deletion

## Result

`Batch 3A deletion goals: PASS`

The five requested peripheral domains were removed from the active application
surface:

- Supplier Collaboration / Supplier A2A
- Refund
- Procurement
- Service Quotation
- Customer Notification delivery/proposal capability

No WorkOrder fulfillment redesign, Parts mutation redesign, Predictive
Maintenance, realtime split, Kafka/GraphRAG cleanup, or Multimodal change was
started.

## Deletion boundary

Deleted active surfaces include the supplier collaboration application/API and
sandbox, peripheral adapters, peripheral proposal/receipt routes and gateway
branches, deleted ORM records, provider configuration and secrets, Keycloak and
Vault entries, frontend panels/client exports, generated API contract entries,
and the retired supplier-specific acceptance commands.

The shared `ToolGateway` remains.  Its generic authorization, schema
validation, T2 approval, idempotency, audit, read-only catalog, Parts, FSM,
Equipment Control, and WorkOrder paths remain.  The five Diagnosis read-only
tools remain unchanged in schema, authorization, and behavior.

The separate Expert Collaboration / field collaboration capability remains; it
was verified as distinct from the deleted Supplier Collaboration domain.
`customer_service_updates` also remains because it is the portal result
confirmation record used by the surviving case and Golden Path behavior, not
the deleted provider delivery ledger.

The project acceptance workflow remains available for the surviving flow.  Its
quotation stage and quotation-only receipt fields were removed so it no longer
constructs the deleted Service Quotation capability.

## Persistence migration

Added forward-only Alembic revision:

`alembic/versions/0089_remove_peripheral_fulfillment.py`

Historical revisions `0001` through `0088` were not edited.  The migration:

1. Detaches `work_orders.service_quotation_id` and replaces the creation
   binding with the surviving `COVERED_SERVICE`/Parts rules.
2. Drops dependent receipt/decision tables before their parent tables.
3. Removes the Supplier Collaboration, Customer Notification, Procurement,
   Refund, and Service Quotation tables.

SQLite rehearsal passed with foreign-key/index cleanup checks.  Alembic reports
`0089_remove_peripheral_fulfillment (head)`.

PostgreSQL rehearsal:

`NOT RUN — no disposable PostgreSQL environment available`

No production database or new infrastructure was used.

## Verification evidence

The following all passed on the final working copy:

- Batch 1 Golden Path smoke
- Batch 1 boundary smoke
- Batch 1.5 review boundary smoke
- Batch 2 Multimodal, Retrieval, and Tool smokes
- Batch 2A Recognition, manifest/persistence, and provenance smokes
- Batch 2B dependency, generic applicability, baseline, and retrieval parity smokes
- Batch 2C dependency and runtime-isolation smokes
- Batch 3A deletion smoke
- Batch 3A SQLite migration rehearsal
- Python compilation for `src` and `scripts`
- Ruff on changed Python files
- Focused mypy on the changed deletion/acceptance surfaces
- Static API route inventory for all five deleted route families
- Shell syntax check for `scripts/dev_lite.sh`
- JSON parse check for `contracts/openapi.json`

The deletion smoke verifies that deleted modules/panels are absent, deleted
mutation tool IDs are not registered, the five Diagnosis tool IDs remain
registered, target runtime/config markers are absent from production surfaces,
and the new migration is present.

## Environment limitations

The service-level verification did not require constructing the full FastAPI
application.  Full application/OpenAPI generation was not used because the
existing local dependency chain is unavailable (`PIL`, with the previously
known `spacy.tokens` limitation unchanged).  This is non-blocking for the
Batch 3A structural verification.

The frontend TypeScript check was not run because `web/node_modules` was not
available after the local dependency setup did not complete; no frontend
dependency repair was attempted.  The generated OpenAPI JSON and TypeScript
contract files were syntax-checked and contain no deleted-domain route or
schema markers.

Recorded environment debt remains limited to:

- `spacy.tokens`
- `temporalio.bridge`
- `pywintypes`
- no disposable PostgreSQL environment

No dependency installation or unrelated environment repair was performed.
The working copy has no `.git` metadata; this did not block the batch and no
repository was initialized.

## Final disposition

The active Batch 3A structural goals are complete.  Batch 3B was not started.
