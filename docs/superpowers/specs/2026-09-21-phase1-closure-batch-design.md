# Phase 1 Closure Batch Design

## Scope and evidence

This Closure Batch addresses only the two active residual categories recorded in
`docs/deindustrialization_phase1_final_acceptance.md`:

1. stale active API and authorization references; and
2. reusable-core imports of Maintenance Planning.

Maintenance Planning is not stale. It has registered API routers, a runtime
binding and dispatcher, and a Temporal worker registration guarded by
`multi_agent_planning_enabled`. It remains a retained Industrial Reference
Application domain.

Historical migrations, prior audit reports, and `__pycache__` files are outside
the active-residual scan.

## A. Active API and authorization residuals

| Reference | Active path | Domain | Action |
| --- | --- | --- | --- |
| `contracts/openapi.json` | two exported paths: `repair-work-order-options`, `repair-work-order-proposals` | removed Repair Work Order surface | remove stale generated paths and their four unreferenced schemas |
| `web/generated/api/schema.d.ts` | corresponding generated endpoint and schema declarations | removed Repair Work Order surface | remove stale generated declarations |
| `src/industrial_ops_agent/auth/policy.py` | `work_order.execute` enum, role grant and OPA-enforced action | removed write surface; the remaining caller is a read projection | authorize those two retained read projections with `work_order.read`, then remove `work_order.execute` |
| `src/industrial_ops_agent/auth/policy.py`, `infra/opa/policy.rego` | `agent_collaboration.*` definitions/grants | no endpoint, service, route binding, or other active caller | remove the definitions and grants |
| `infra/opa/policy.rego` | `alert_candidate.*` and `predictive_outcome.record` grants | no active action definition, endpoint, service, or route binding | remove stale OPA policy entries |

There is no active FastAPI route source, router include, request/response model
source, or handwritten web client that serves either stale Repair Work Order
path. The contract and generated declaration are stale artifacts, not a source
route deletion.

## B. Reusable-core dependency audit

| Reusable module | Imported Maintenance Planning symbol | Concrete runtime use | Classification | Ownership after change |
| --- | --- | --- | --- | --- |
| `model_gateway/governance.py` | `diagnosis_for_agent`, `record_disclosure`, Council and Contribution records | associates inference rows with a Diagnosis or council, blocks prohibited disclosure, and records a Maintenance Review exposure | Type 2 — Maintenance Planning policy | a Maintenance Planning inference-reader decorator, composed by the API application |
| `orchestration/workflows.py` | Maintenance Planning activity/input/dispatch exception | defines council payload, Temporal activity, workflow, and lazy dispatcher | Type 2 — Maintenance Planning workflow semantics | `maintenance_planning/temporal.py` |
| `orchestration/runner.py` | Maintenance Planning activity and workflow | constructs the council activity and registers it on the worker | Type 2 — Maintenance Planning worker extension | a domain extension registered by the composition entrypoint |

`runtime.py` and `api/app.py` are composition roots and may assemble retained
domain implementations. The existing `workorders/service.py` import is a
legacy-domain read boundary, not reusable core; it is not moved in this batch.

## C. Minimal ownership design

### Inference list disclosure

`ModelGatewayGovernanceService` becomes a pure Model Gateway reader. Its only
new reusable seam is a transaction-aware inference read: it performs its normal
authorization and query in a caller-owned SQLAlchemy transaction when one is
provided, or opens its own transaction for ordinary callers. It has no
Maintenance Planning import, record, policy version, council, assignment, or
review rule.

`maintenance_planning/model_inference_reader.py` owns
`MaintenancePlanningInferenceReader`. It starts the transaction, delegates the
generic query, derives Diagnosis/council lineage, and invokes the existing
Maintenance Review disclosure policy before the inference records leave the
transaction. Thus the existing atomic order is retained:

```text
authorize + list inference rows + resolve maintenance lineage + record disclosure + return
```

The API composition root installs that reader in application state. The Model
Gateway route depends only on the one-method neutral `ModelInferenceReader`
contract; it does not import a domain policy. This is not a re-export or a
facade: the policy code, persistence records, and disclosure behavior all move
to their actual Maintenance Planning owner.

### Temporal worker

`orchestration/workflows.py` retains only generic recognition, diagnosis, and
knowledge workflows. `maintenance_planning/temporal.py` owns the unchanged
council payload, Temporal workflow name, activity name, retry policy, and lazy
dispatcher. It may import `LazyTemporalClient` from generic orchestration; the
reverse import is removed.

`orchestration/worker_extensions.py` introduces only two generic worker
composition values: a runtime context containing the already-built generic
resources and a registration containing workflow/activity callables. It has no
Maintenance Planning language or imports. `orchestration/runner.py` builds the
generic worker and accepts an optional registration factory. The new
`orchestration/entrypoint.py` is the explicit composition root: it imports the
Maintenance Planning registration factory and passes it to the generic runner.
The worker's Docker, Compose, and Helm commands point at that entrypoint.

The preserved direction is:

```text
maintenance_planning/temporal.py -> orchestration generic APIs
orchestration/entrypoint.py -> maintenance_planning + orchestration runner
orchestration/runner.py -X-> maintenance_planning
orchestration/workflows.py -X-> maintenance_planning
model_gateway/governance.py -X-> maintenance_planning
```

## D. Files expected to change

Production and deployment files:

- `src/industrial_ops_agent/model_gateway/governance.py`
- `src/industrial_ops_agent/maintenance_planning/model_inference_reader.py` (new)
- `src/industrial_ops_agent/api/app.py`
- `src/industrial_ops_agent/api/dependencies.py`
- `src/industrial_ops_agent/api/routes/model_gateway.py`
- `src/industrial_ops_agent/orchestration/workflows.py`
- `src/industrial_ops_agent/orchestration/runner.py`
- `src/industrial_ops_agent/orchestration/worker_extensions.py` (new)
- `src/industrial_ops_agent/orchestration/entrypoint.py` (new)
- `src/industrial_ops_agent/maintenance_planning/temporal.py` (new)
- `src/industrial_ops_agent/runtime.py`
- `src/industrial_ops_agent/auth/policy.py`
- `src/industrial_ops_agent/workorders/service.py`
- `infra/opa/policy.rego`
- `compose.lite.yaml`, `docker/ai-worker.Dockerfile`, and the worker command in
  `infra/helm/industrial-ops-application/templates/deployments.yaml`
- `contracts/openapi.json`
- `web/generated/api/schema.d.ts`

Verification and reporting files:

- `scripts/deindustrialization_phase1_closure_smoke.py` (new red-to-green
  structural regression smoke)
- `docs/deindustrialization_phase1_final_acceptance.md`

No Alembic migration is expected.

## E. Verification plan

1. First add and run the Closure smoke in its failing state. It will check the
   two stale OpenAPI paths/schemas, stale authorization values, the core import
   direction, Maintenance Planning temporal ownership, composition entrypoint,
   and unchanged retained worker registration names.
2. Implement the smallest changes above and rerun that smoke green.
3. Run all existing Batch 1 through 3E smoke scripts, Final Golden Path,
   OpenAPI JSON validation, authorization and active-route inventories, tool and
   runtime inventories, the core dependency scan, changed-file Ruff,
   `py_compile`/`compileall`, focused mypy, and Alembic head.
4. Record the known non-blocking limitations without modification:
   `NOT RUN — no disposable PostgreSQL environment available`; full FastAPI
   import remains blocked only by the existing missing local `PIL` dependency if
   it persists.

## Self-review

- No business domain is deleted, and no new product capability is introduced.
- The generic pieces contain neither Maintenance Planning records nor policy
  semantics.
- The Model Gateway endpoint retains its response contract and atomic disclosure
  behavior.
- The retained council workflow keeps its external Temporal names and retry
  policy; only ownership and registration direction change.
- The design adds no empty migration, re-export, alias module, generic `utils`,
  Prompt framework, or unrelated cleanup.
