# Batch 3A Locate-Before-Delete Inventory

This inventory was collected before any Batch 3A deletion.  Historical Alembic
migrations are evidence of schema history and are not deletion targets.

## Supplier Collaboration / Supplier A2A

### Owned surface

- ORM: `SupplierCollaborationRecord` and `SupplierCollaborationEventRecord` in
  `src/industrial_ops_agent/persistence/models.py`.
- Application: `src/industrial_ops_agent/collaboration/service.py`.
- Transport: `src/industrial_ops_agent/collaboration/a2a.py`.
- API: `src/industrial_ops_agent/api/routes/collaborations.py`.
- Supplier sandbox: `src/industrial_ops_agent/supplier_sandbox/`.
- Lab: `src/industrial_ops_agent/simulation/supplier_a2a_lab.py` and its CLI.
- Frontend: `web/app/collaboration/page.tsx` and supplier functions/types in
  `web/lib/api/client.ts` plus generated supplier schemas.
- Runtime/config/secrets: `runtime.py`, `api/app.py`, `config.py`, `secrets.py`,
  Keycloak realm, Vault bootstrap, and supplier commands in `scripts/dev_lite.sh`.
- Historical schema: `alembic/versions/0034_supplier_a2a_collaboration.py`.

### Inbound references and classification

- `api/app.py` imports and registers the supplier collaboration router and stores
  `supplier_agent_client`; this is a deleted API/runtime surface.
- `runtime.py` conditionally constructs `OfficialA2ASupplierAgentClient`; this
  is deleted runtime composition.
- `collaboration/service.py` imports the supplier A2A client, supplier records,
  and review-isolation helpers; all are internal supplier dependencies.
- The similarly named `expert_collaborations` route and
  `WorkOrderExpertCollaboration*` records are a separate field/expert domain and
  are KEEP for this batch.
- No Diagnosis runtime, Recognition, RAG, or five-tool read-only path imports
  supplier collaboration.

## Refund

### Owned surface

- Persistence: `RefundRequestRecord` and `RefundRequestReceiptRecord`.
- Adapter: `src/industrial_ops_agent/tools/refunds.py`.
- API receipt route: `src/industrial_ops_agent/api/routes/refunds.py`.
- Proposal/list/option/receipt/publish execution blocks in
  `api/routes/approvals.py` and `tools/gateway.py`.
- Tool definitions: `refund.request` and `cancel_refund_request` in
  `tools/registry.py`.
- Config/secrets/policy: refund delivery settings, secret names, refund actions,
  Vault bootstrap, and Keycloak-independent provider configuration.
- Frontend: `web/components/m2/RefundRequestPanel.tsx`, incident/approval usage,
  API client functions/types, and generated schemas.
- Historical schema: `0046_refund_requests.py` and
  `0053_enterprise_finance_refund_delivery.py`.

### Inbound references and classification

- `api/app.py` registers the refund router; this is DELETE.
- The approvals router is shared with KEEP WorkOrder/Parts/FSM actions.  Only
  refund-specific models, routes, exception handling, result fields, and helper
  projections may be removed.
- `tools/gateway.py` is a shared class, but refund methods and refund persistence
  records are domain-specific.  The generic authorization/audit/T2 machinery is
  KEEP.
- No Diagnosis read-only tool depends on refund mutation behavior.

## Procurement

### Owned surface

- Persistence: `PurchaseRequestRecord`, `PurchaseRequestReceiptRecord`,
  `PurchaseFulfillmentRecord`, and `PurchaseFulfillmentReceiptRecord`.
- Adapter: `src/industrial_ops_agent/tools/procurement.py`.
- Receipt API: `src/industrial_ops_agent/api/routes/procurement.py`.
- Proposal/list/option/receipt/execution blocks in `api/routes/approvals.py` and
  `tools/gateway.py`.
- Tool definitions: purchase/procurement entries in `tools/registry.py`.
- Factory: procurement adapter construction in `tools/factory.py`; API runtime
  injection in `runtime.py`.
- Config/secrets/Vault/bootstrap, frontend purchase panel/client/generated API.
- Historical schema: `0043_purchase_requests.py`,
  `0052_enterprise_purchase_requisition_delivery.py`, and
  `0055_enterprise_procurement_fulfillment.py`.

### Inbound references and classification

- `parts.availability` is one of the five KEEP Diagnosis tools and is not
  procurement; its read-only definition and synthetic/read adapter remain.
- Parts reservation/issue/material movement is a separate later KEEP scope for
  this batch.  Procurement-specific purchase request/fulfillment records and
  adapters are DELETE, while parts mutation code is not redesigned.
- The shared approvals/gateway/audit primitives are KEEP after removing only
  procurement-specific branches.
- No Recognition, Knowledge, Evidence, or Diagnosis manifest dependency was
  found.

## Service Quotation

### Owned surface

- Persistence: `ServiceQuotationRecord` and `ServiceQuotationDecisionRecord`.
- Adapter: `src/industrial_ops_agent/tools/quotations.py`.
- Staff proposal/list/option blocks in `api/routes/approvals.py` and
  `tools/gateway.py`.
- Customer decision/read blocks in `api/routes/portal.py`.
- Tool definition: service quotation publication in `tools/registry.py`.
- Factory/API runtime quotation adapter construction and config/secrets.
- Frontend quotation panel, incident/portal/work-order quotation references,
  API client functions/types, and generated schemas.
- Historical schema: `0071_governed_service_quotation.py`.

### Inbound references and classification

- `work_orders.service_quotation_id` and the `ACCEPTED_QUOTATION` creation mode
  are a direct FK/business dependency on the quotation table.  This is the one
  cross-domain dependency requiring a minimal compatibility removal from the
  WorkOrder projection/model/creation binding; the WorkOrder fulfillment
  lifecycle itself remains out of scope.
- Migration `0072_governed_repair_work_order_authorization.py` also references
  the quotation table historically/currently and must be handled by the new
  forward migration without editing history.
- Generic model cost/token accounting is unrelated and is KEEP.

## Customer Notification

### Owned surface

- Persistence: `CustomerNotificationDeliveryRecord` and
  `CustomerNotificationReceiptRecord`.
- Adapter: `src/industrial_ops_agent/tools/customer_notifications.py`.
- Receipt API: `src/industrial_ops_agent/api/routes/customer_notifications.py`.
- Option/proposal/receipt/execution blocks in `api/routes/approvals.py` and
  `tools/gateway.py`.
- Tool definitions for customer notification in `tools/registry.py`.
- Factory/API runtime adapter construction, config/secrets, Vault bootstrap.
- Frontend notification panel, incident/approval usage, API client/generated
  schemas.
- Historical schema: `0051_customer_notification_deliveries.py`.

### Inbound references and classification

- `api/app.py` registers the customer notification and receipt router; this is
  DELETE.
- Internal Agent events, SSE/AG-UI, observability, and generic logging are KEEP.
- `customer_service_updates` is a generic portal case-update record used by
  other customer case behavior; only notification delivery/receipt records and
  notification-specific UI/API logic are DELETE.
- No Diagnosis read-only, Recognition, Knowledge, or Agent evidence dependency
  was found.

## Shared components to preserve

- Diagnosis read-only catalog: `asset.get`, `warranty.get`,
  `parts.availability`, `schedule.availability`, `work_orders.history`.
- `ToolGateway` generic registry resolution, schema validation, authorization,
  T2 governance, idempotency, audit recording, and read-only invocation.
- Incident/upload/Recognition/Evidence/Diagnosis/Agent/RAG/Trace/Eval paths.
- WorkOrder, Dispatch/Field, FSM, Equipment Control, Parts mutation, and all
  explicitly deferred domains.
- Historical migrations `0001` through `0088`.
