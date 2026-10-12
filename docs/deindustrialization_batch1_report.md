# Deindustrialization Phase 1 — Implementation Batch 1 Report

## 1. Changes Made

- `src/industrial_ops_agent/agent/graph.py`
  - Renamed the reusable graph implementation to `AgentGraph`.
  - Added the small `AgentGraphDefinition` input for graph version, action routing,
    domain action mutation, and terminal budget output.
  - Removed all imports of Diagnosis contracts and report types.
- `src/industrial_ops_agent/agent/contracts.py`
  - Added `DIAGNOSIS_GRAPH_DEFINITION`; Industrial Diagnosis now owns its version,
    routes, retrieval-query mutation, and diagnostic budget fallback.
- `src/industrial_ops_agent/orchestration/workflows.py`
  - Constructs `AgentGraph` with the Diagnosis-owned definition.
- `src/industrial_ops_agent/persistence/models.py`
  - Removed `AgentRunRecord.diagnosis_run_id`.
  - Made `DiagnosisRunRecord.agent_run_id` the foreign-key association to
    `agent_runs`.
- `alembic/versions/0087_agent_run_independent_ownership.py`
  - Added the forward-only ownership migration.
- `src/industrial_ops_agent/application/diagnoses.py` and
  `src/industrial_ops_agent/application/agent_runs.py`
  - Create an AgentRun before the DiagnosisRun that owns it.
  - Resolve the Diagnosis association from `DiagnosisRun.agent_run_id` for cancel,
    resume, authorization, and control views.
- `src/industrial_ops_agent/memory_governance/service.py`
  - Reversed its AgentRun/DiagnosisRun join to the new association direction.
- `src/industrial_ops_agent/tools/gateway.py`
  - Made `PartsAdapter` optional at construction.
  - Kept industrial mutation methods intact, but require their adapter only when a
    mutation-oriented parts path is called.
- `scripts/deindustrialization_batch1_golden_path_smoke.py`
  - Added the frozen synthetic Industrial Diagnosis regression.
- `scripts/deindustrialization_batch1_boundary_smoke.py`
  - Added focused boundary checks for Agent ownership, graph injection, and
    adapter-free ToolGateway construction.

No industrial business domain was deleted.

## 2. Dependency Changes

Before:

```text
Agent graph → Diagnosis contracts
AgentRun / Event / Checkpoint persistence → mandatory DiagnosisRun ownership
ToolGateway construction → mandatory PartsAdapter
```

After:

```text
Industrial Diagnosis contracts → AgentGraphDefinition → Agent graph mechanics
Industrial Diagnosis → DiagnosisRun.agent_run_id → independent AgentRun / Event / Checkpoint persistence
ToolGateway construction → registry + authorization + audit + read-only adapter
Industrial mutation paths → optional PartsAdapter, resolved only when invoked
```

## 3. Schema Migration

Migration: `0087_agent_run_independent_ownership`.

- Previous ownership: `agent_runs.diagnosis_run_id` was a required foreign key to
  `diagnosis_runs`.
- New ownership: `diagnosis_runs.agent_run_id` is a required foreign key to
  `agent_runs`; the existing tenant-scoped uniqueness constraint remains.
- Compatibility: Diagnosis still has exactly one associated AgentRun, while a
  generic AgentRun can now be created without a DiagnosisRun. Diagnosis start,
  resume, cancellation, event, checkpoint, and trace lookups use the reverse
  association.
- The migration is forward-only. A downgrade would require deleting or inventing
  ownership for generic AgentRuns, so it intentionally follows the repository's
  irreversible-migration convention and does nothing.

## 4. Verification

| Command / check | Result |
| --- | --- |
| `python scripts/deindustrialization_batch1_golden_path_smoke.py` before structural edits | PASS |
| `python scripts/deindustrialization_batch1_boundary_smoke.py` before edits | Expected RED: `AgentGraph` did not exist |
| `python scripts/deindustrialization_batch1_boundary_smoke.py` after edits | PASS |
| `python scripts/deindustrialization_batch1_golden_path_smoke.py` after edits | PASS |
| Focused SQLite execution of Alembic `0086 → 0087` | PASS; association data retained and reverse FK confirmed |
| `ruff check` for all Batch 1 changed files | PASS |
| `python -m py_compile` for all Batch 1 changed Python files | PASS |
| `alembic heads` | PASS; `0087_agent_run_independent_ownership` is the head |
| Focused mypy for graph/contracts/models/diagnosis/control/memory modules | PASS |
| Mypy including existing `workflows.py` and the large `gateway.py` | NOT clean: 39 findings in existing Temporal typing and unrelated gateway locations; no finding was on a Batch 1 edit line, but a pre-change mypy baseline was unavailable because the tool was not installed |
| Repository-wide `ruff check src` | NOT clean: 51 existing findings outside Batch 1 scope |

The synthetic Golden Path uses the production LangGraph implementation, production
SQLAlchemy models and event/checkpoint stores, registry, ToolGateway,
authorization/audit boundary, and `SyntheticReadonlyAdapter`. It verifies:

- Diagnosis association creation;
- graph prepare/retrieve/decide/tool/final execution;
- `parts.availability` resolution through the read-only adapter;
- structured final report with citation;
- event append and checkpoint save/load;
- cancellation state preventing subsequent event writes;
- schema rejection, authorization/audit, and T2 approval-required behavior without
  a `PartsAdapter`.

## 5. Golden Path Status

```text
PASS
```

## 6. Batch 1.5 — Maintenance Review Boundary

### Ownership audit

`maintenance_planning/review_isolation.py` remains the Maintenance Planning policy
module.  The audit found the following symbols before the boundary extraction:

- Constants: `REVIEW_POLICY_VERSION`, `READER_COVERAGE_DIGEST`.
- Class/value objects: `ReviewIsolationConflict`, `ReviewSource`.
- Generic mechanism extracted: `lock_subject`.
- Policy/source operations retained: `resolve_source`, `_incident_family_key`,
  `_draft_family_key`, `_incident_family`, `source_family_keys`,
  `record_draft_disclosure`, `draft_read_transaction`,
  `incident_read_transaction`, `record_incident_disclosure`, `_assignments`,
  `check_disclosure`, `record_disclosure`, `diagnosis_for_agent`,
  `record_exposure`, `_known_participation`, and `eligibility`.
- Persistence records retained by the policy: `DiagnosisExpertInterventionRecord`,
  `DiagnosisExpertRevisionRecord`, `DiagnosisQualityFeedbackRecord`,
  `DiagnosisRunRecord`, `IdempotencyRecord`, `IncidentDraftRecord`,
  `IncidentRecord`, `IncidentRelationRecord`,
  `MaintenancePlanningBlindJudgmentRecord`, `MaintenancePlanningCouncilRecord`,
  `MaintenancePlanningEvaluationRunRecord`,
  `MaintenancePlanningEvaluationSuiteRecord`, `MaintenanceReviewAssignmentRecord`,
  `MaintenanceReviewExposureRecord`, `MaintenanceReviewPolicyRecord`,
  `ModelInferenceRecord`, `WorkOrderExpertCollaborationRecommendationRecord`,
  `WorkOrderExpertCollaborationRecord`, and `WorkOrderRecord`.

The retained operations read or persist Maintenance Planning policy/version,
assignment, council, evaluation, blind-review, source lineage, and exposure facts.
They are not generic mechanisms.  `diagnosis_for_agent` remains Industrial Diagnosis
reference-application logic; it was not generalized merely because it is small.

### Implemented boundary

- `governance/review_boundary.py` owns only `lock_subject`,
  `DisclosureRequest`, `ReviewBoundaryConflict`, and the three-method
  `ReviewBoundary` protocol (`guarded_read`, `record_disclosure`, `deny`).
  It imports no Maintenance Planning package or record and contains no policy,
  assignment, council, evaluation, or blind-review semantics.
- `maintenance_planning/review_boundary.py` owns
  `MaintenanceReviewBoundary`.  It maps opaque requests to the existing
  Maintenance Planning policy helpers, so policy persistence and policy-specific
  conflict codes remain owned by that domain.
- `api/app.py` is the composition root: it creates the Maintenance implementation
  when no explicit boundary is supplied, stores it in application state, and
  `api/dependencies.py` injects its protocol into reusable API services.
- `media/service.py` and `memory_governance/service.py` now use the generic lock
  and protocol.  Human media reads require the injected boundary; the
  authorization-free media upload path deliberately does not require it.
- `api/errors.py` catches the generic base conflict; the existing Maintenance
  conflict remains its subtype and preserves its response code.

### Caller classification and mechanical dependency result

| Classification | Current callers | Batch 1.5 decision |
| --- | --- | --- |
| KEEP / reusable | Media, Memory Governance, API error boundary | Migrated; none imports `maintenance_planning.review_isolation`. |
| MOVE / Industrial Diagnosis reference application | Diagnosis, incident, speech, diagnosis-feedback, agent-event, collaboration, cost, customer/incident operations, model-gateway governance, trace | Not migrated. These callers use diagnosis/incident policy semantics, including source resolution or diagnosis association; they are not reusable review mechanisms. |
| DELETE later / industrial after-sales surface | Portal, workorders, tools gateway, multimodal realtime | Not migrated. Their current policy imports remain until the later domain deletion/decision; no adapter was introduced solely to erase an import. |
| Maintenance Planning | activation, rollout collection/evidence, evaluation, service | Remains in-domain. |

The mechanical scan still finds direct imports in the latter three groups above.
This is intentional under the Batch 1.5 constraint: the hard boundary is that the
Reusable Capability Layer does not depend on Maintenance Planning, not that every
Industrial Diagnosis or deferred after-sales module must immediately stop doing so.

### PostgreSQL migration rehearsal

`NOT RUN — no disposable PostgreSQL environment available`

Docker Desktop was not reachable, no PostgreSQL process/client was available, and
the supplied compose configuration requires unavailable environment values.  No
database infrastructure was created and no production database was contacted.
`alembic heads` still reports `0087_agent_run_independent_ownership (head)`.

### Batch 1.5 verification

| Command / check | Result |
| --- | --- |
| Batch 1 Golden Path smoke | PASS |
| Batch 1 boundary smoke | PASS |
| Batch 1.5 review-boundary smoke | PASS (was RED before implementation) |
| Python compilation for changed Python files | PASS |
| Ruff for changed files | PASS |
| Focused mypy for changed files | PASS; 10 source files checked |
| Mechanical import scan | PASS for reusable Media, Memory Governance, and API error boundary; remaining imports classified above |
| Alembic head | PASS; 0087 |

## 7. Batch 1 structural goals

```text
PASS
```

## 8. Historical Batch 1 dependency note

At the end of Batch 1, this helper was correctly retained rather than moved
wholesale because it owns Maintenance Planning policy.  Batch 1.5 resolved the
actual reusable-capability reverse dependency without moving those semantics; see
Section 6 and the resolved follow-up.

## 9. Scope Discipline

This batch did not delete or refactor predictive maintenance, Kafka/Debezium,
GraphRAG/Neo4j, supplier A2A, realtime, multimodal asset models, RAG device models,
Model Gateway routes, frontend after-sales features, work-order/parts domains,
fulfillment tables, deployment configuration, README content, or repository naming.

## Checkpoint Status — Non-blocking

The supplied source and the isolated Batch 1 copy contain no `.git` directory.
Therefore no Git worktree or commit checkpoint can be created without initializing a
new, unrelated repository. No Git initialization or push was performed.

The missing Git metadata does not block the Batch 1 structural result.  PostgreSQL
rehearsal remains a deployment-readiness item and is explicitly recorded as not run;
it is not an architecture blocker for this batch.
