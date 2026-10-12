# Phase 1 Closure Batch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the two active final-acceptance residual classes while preserving the retained Industrial Maintenance Planning reference application.

**Architecture:** Generated Repair Work Order artifacts and dead authorization values are removed without restoring their removed routes. Generic Model Gateway and Temporal orchestration become policy-free; Maintenance Planning owns its disclosure and Temporal behavior, and explicit application/worker composition installs the domain implementations.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, Temporal, Rego/OPA, OpenAPI JSON, TypeScript declarations, existing smoke scripts.

**Spec:** `docs/superpowers/specs/2026-09-21-phase1-closure-batch-design.md`

## Global Constraints

- Retain Maintenance Planning as an active Industrial Reference Application domain.
- Delete only active stale routes, generated artifacts, and authorization values established by the audit.
- Use `work_order.read` for retained historical read projections; remove `work_order.execute` with no compatibility alias.
- Do not introduce a generic framework, alias, re-export, schema migration, feature, or unrelated cleanup.
- The generic layer must not import Maintenance Planning.
- No `.git` initialization, commit, or worktree creation; this D-drive clone is the assigned isolated work copy.

## Review Focus

- A stale generated OpenAPI path or schema survives in either contract artifact; Task 1 smoke parses both artifacts and checks both removed paths and their named schemas.
- A removed action still has an active consumer; Task 2 scans policy/OPA and exercises the retained Work Order read authorization path.
- A Model Gateway inference response returns before the domain disclosure transaction; Task 3 uses the actual reader/decorator boundary and preserves one transaction-owned query path.
- Council Temporal identifiers or retry behavior change during ownership movement; Task 4 checks the existing activity/workflow names and dispatcher payload contract.
- A deployment still starts the generic runner directly; Task 5 validates Docker, Compose, and Helm start the composition entrypoint.

### Task 1: Closure structural smoke and stale generated contract cleanup

**Files:**

- Create: `scripts/deindustrialization_phase1_closure_smoke.py`
- Modify: `contracts/openapi.json`
- Modify: `web/generated/api/schema.d.ts`

**Interfaces:**

- Produces: `deindustrialization_phase1_closure_smoke.py`, which exits zero only when all Closure structural invariants hold.

- [ ] **Step 1: Write the failing Closure smoke**

  Parse `contracts/openapi.json`, inspect `components.schemas`, and read the generated TypeScript declaration. Assert that these values are absent:

  ```python
  stale_paths = {
      "/api/v1/incidents/{incident_id}/repair-work-order-options",
      "/api/v1/incidents/{incident_id}/repair-work-order-proposals",
  }
  stale_schemas = {
      "RepairWorkOrderOptionResponse",
      "RepairWorkOrderOptionsEnvelope",
      "RepairWorkOrderOptionsResponse",
      "RepairWorkOrderProposalBody",
  }
  ```

- [ ] **Step 2: Run the smoke and verify RED**

  Run: `PYTHONPATH=src .venv/Scripts/python.exe scripts/deindustrialization_phase1_closure_smoke.py`

  Expected: FAIL identifying at least one stale Repair Work Order path or schema.

- [ ] **Step 3: Delete only the two stale OpenAPI operations and unreferenced schemas**

  Remove both path entries and the four schemas from `contracts/openapi.json`; remove their generated declaration/operation type entries from `web/generated/api/schema.d.ts`. Do not add a source route or modify an unrelated contract.

- [ ] **Step 4: Run the Closure smoke and JSON parse**

  Run: `PYTHONPATH=src .venv/Scripts/python.exe scripts/deindustrialization_phase1_closure_smoke.py`; then parse `contracts/openapi.json` with the project venv.

  Expected: contract assertions for this task pass and JSON parses.

### Task 2: Remove stale authorization values without changing retained read semantics

**Files:**

- Modify: `src/industrial_ops_agent/auth/policy.py`
- Modify: `src/industrial_ops_agent/workorders/service.py`
- Modify: `infra/opa/policy.rego`
- Modify: `scripts/deindustrialization_phase1_closure_smoke.py`

**Interfaces:**

- Consumes: the Closure smoke from Task 1.
- Produces: no `work_order.execute`, `agent_collaboration.*`, `alert_candidate.*`, or `predictive_outcome.record` active authorization definition/mapping.

- [ ] **Step 1: Extend the smoke with authorization behavior checks**

  Assert the removed action values are absent from `Action`, `OPA_ENFORCED_ACTIONS`, and Rego role grants. Assert `WorkOrderService` requests `Action.READ_WORK_ORDER` at its two retained read projections.

- [ ] **Step 2: Run the smoke and verify RED**

  Run the Closure smoke.

  Expected: FAIL on the stale enum, mapping, or OPA value.

- [ ] **Step 3: Apply the minimal authorization cleanup**

  Change only the two read projections from `Action.EXECUTE_WORK_ORDER` to `Action.READ_WORK_ORDER`; remove the `EXECUTE_WORK_ORDER` enum/grant/enforcement entry; remove all four agent collaboration enum values and their role/enforcement grants; remove the two alert and one predictive Rego grants.

- [ ] **Step 4: Run the focused smoke**

  Run the Closure smoke.

  Expected: authorization checks pass and imports remain valid.

### Task 3: Separate Model Gateway inference reads from Maintenance Planning disclosure policy

**Files:**

- Modify: `src/industrial_ops_agent/model_gateway/governance.py`
- Create: `src/industrial_ops_agent/maintenance_planning/model_inference_reader.py`
- Modify: `src/industrial_ops_agent/api/app.py`
- Modify: `src/industrial_ops_agent/api/dependencies.py`
- Modify: `src/industrial_ops_agent/api/routes/model_gateway.py`
- Modify: `scripts/deindustrialization_phase1_closure_smoke.py`

**Interfaces:**

- Produces: neutral `ModelInferenceReader.list_inferences(identity, *, request_id, limit=50)`.
- Produces: Maintenance Planning implementation that performs disclosure within the query transaction.

- [ ] **Step 1: Extend the smoke with import direction and ownership checks**

  AST-parse `model_gateway/governance.py` and assert it imports no `industrial_ops_agent.maintenance_planning` module. Assert the Maintenance reader owns council/contribution lineage and disclosure. Assert API composition stores the reader while the route depends only on the neutral reader contract.

- [ ] **Step 2: Run the smoke and verify RED**

  Run the Closure smoke.

  Expected: FAIL because generic Model Gateway still imports Maintenance Planning.

- [ ] **Step 3: Implement the transaction-aware generic read and Maintenance decorator**

  Preserve authorization, ordering, limit validation, tenant filtering, and atomic disclosure order. Move council/Diagnosis inference association and `record_disclosure` into `MaintenancePlanningInferenceReader`. The generic service must have no Maintenance Planning record or policy imports. Compose the domain reader in `api/app.py`; inject it into the existing Model Gateway route through the neutral one-method contract.

- [ ] **Step 4: Run focused imports and the Closure smoke**

  Run: Closure smoke plus project-v-env imports of the generic governance service, Maintenance reader, API dependencies, and route module.

  Expected: all imports succeed; the generic service remains policy-free.

### Task 4: Move Maintenance Planning Temporal types and registration out of generic orchestration

**Files:**

- Modify: `src/industrial_ops_agent/orchestration/workflows.py`
- Modify: `src/industrial_ops_agent/orchestration/runner.py`
- Create: `src/industrial_ops_agent/orchestration/worker_extensions.py`
- Create: `src/industrial_ops_agent/orchestration/entrypoint.py`
- Create: `src/industrial_ops_agent/maintenance_planning/temporal.py`
- Modify: `src/industrial_ops_agent/runtime.py`
- Modify: `scripts/deindustrialization_phase1_closure_smoke.py`

**Interfaces:**

- Produces: generic `TemporalWorkerRuntime` and `TemporalWorkerRegistration` values with no domain imports.
- Produces: `build_maintenance_planning_worker_registration(runtime)` and `LazyTemporalMaintenancePlanningDispatcher` owned by Maintenance Planning.
- Produces: `orchestration.entrypoint` as the explicit worker composition root.

- [ ] **Step 1: Extend the smoke with worker direction and compatibility checks**

  Assert generic `runner.py` and `workflows.py` import no Maintenance Planning module. Assert Maintenance owns the existing `maintenance_planning_council_activity` and `maintenance_planning_council_workflow` names and keeps the original retry configuration. Assert the composition entrypoint imports both generic runner and Maintenance Planning registration.

- [ ] **Step 2: Run the smoke and verify RED**

  Run the Closure smoke.

  Expected: FAIL on the existing reverse import.

- [ ] **Step 3: Move exact domain Temporal behavior and compose it explicitly**

  Move the council input, Temporal workflow, activity adapter, and lazy dispatcher unchanged into `maintenance_planning/temporal.py`. Keep generic Temporal client and other workflows in `orchestration/workflows.py`. Make `runner.run` accept an optional generic registration factory; the entrypoint imports the Maintenance factory and supplies it. Update runtime to import the domain dispatcher directly.

- [ ] **Step 4: Run the focused worker verification**

  Run Closure smoke, project-v-env imports, and the existing Batch 2C runtime-isolation smoke.

  Expected: all pass; only the composition entrypoint imports both sides.

### Task 5: Point deployed workers at the composition entrypoint and complete acceptance

**Files:**

- Modify: `compose.lite.yaml`
- Modify: `docker/ai-worker.Dockerfile`
- Modify: `infra/helm/industrial-ops-application/templates/deployments.yaml`
- Modify: `scripts/deindustrialization_phase1_closure_smoke.py`
- Modify: `docs/deindustrialization_phase1_final_acceptance.md`

**Interfaces:**

- Consumes: `industrial_ops_agent.orchestration.entrypoint` from Task 4.
- Produces: the deployment commands and final report point to the explicit composition root and record all acceptance results.

- [ ] **Step 1: Extend the smoke with deployment command checks**

  Assert the Dockerfile, Compose worker command, and Helm worker command invoke `industrial_ops_agent.orchestration.entrypoint`, not the generic runner directly.

- [ ] **Step 2: Run the smoke and verify RED**

  Run the Closure smoke.

  Expected: FAIL identifying the old generic worker entrypoint.

- [ ] **Step 3: Change only the three active worker launch commands**

  Replace the module entrypoint in Docker, Compose, and Helm. Do not alter image definitions, resource settings, queues, readiness paths, or unrelated deployment files.

- [ ] **Step 4: Run full acceptance and update the final report**

  Run all Batch 1–3E smokes, Final Golden Path, Closure smoke, OpenAPI parse/generation check where environment permits, authorization inventory, active-route inventory, reusable-core import scan, tool/runtime inventory, changed-file Ruff, `py_compile`/`compileall`, focused mypy, and Alembic head. Record existing non-blocking environment limitations exactly. Mark Phase 1 PASS only if all structural criteria pass.

## Self-review

- Each residual has a dedicated red-to-green check before its implementation.
- The only shared cross-task interfaces are the neutral inference reader and the generic worker registration; their names and ownership are defined in Tasks 3 and 4 before use.
- Deployment changes consume only the composition entrypoint created in Task 4.
- No task requires a database schema change, production service, dependency installation, or expansion beyond the accepted design.
