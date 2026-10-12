# Deindustrialization Batch 1.5 — Maintenance Review Boundary Plan

## Decision

Extract only two domain-neutral mechanisms into `governance/review_boundary.py`:

1. `lock_subject`, the tenant/subject concurrency lock.  Its implementation uses
   only generic persistence and PostgreSQL locking primitives.
2. `ReviewBoundary`, a minimal protocol through which a reusable service can ask
   for a guarded read, record a disclosure, or raise a boundary denial.  The
   protocol accepts an opaque `DisclosureRequest`; it neither enumerates nor
   interprets source domains.

`maintenance_planning/review_boundary.py` will own
`MaintenanceReviewBoundary`.  It delegates to the existing Maintenance Planning
policy in `review_isolation.py`; it alone maps opaque request source kinds to the
existing draft/incident disclosure rules and policy errors.  Policy version,
assignment, council, evaluation, blind-review, source resolution, and all
Maintenance Planning records remain in `maintenance_planning/review_isolation.py`.

Dependency direction after this batch:

```text
Media / Memory Governance services -> ReviewBoundary protocol
MaintenanceReviewBoundary -> Maintenance Planning policy and records
API composition root -> MaintenanceReviewBoundary injected into reusable services
```

## Caller classification

| Classification | Callers | Decision |
| --- | --- | --- |
| KEEP / reusable | `media/service.py`, `memory_governance/service.py`, `api/errors.py` | Migrate to the generic lock/protocol.  Media and governed memory are reusable platform capabilities; their externally visible behaviour and the Maintenance policy decision remain unchanged. |
| MOVE / Industrial Diagnosis reference application | diagnosis APIs/services, agent events, collaboration, cost operations, model gateway governance, trace operations | Do not migrate in Batch 1.5.  Their diagnosis/incident semantics are not evidence of a reusable review capability.  In particular, `diagnosis_for_agent` remains reference-app logic. |
| DELETE later / industrial after-sales surface | tools gateway, workorders, customer portal, supplier, field/realtime and related incident operations | Do not migrate merely to remove an import.  These paths retain their current policy dependency until their scheduled domain decision. |
| Maintenance Planning | all `maintenance_planning` callers | Keep in-domain.  `review_isolation.py` remains the policy and persistence owner. |

## Minimal protocol

`DisclosureRequest` carries opaque source type/ids and exposed resource metadata.
`ReviewBoundary` has only:

- `guarded_read(...)` for a policy-guarded transaction boundary;
- `record_disclosure(...)` for a policy-owned disclosure record;
- `deny(...)` to preserve policy-specific conflict mapping when a reusable service
  discovers that its source binding is invalid.

No current API is copied wholesale as a protocol.  `diagnosis_for_agent`, source
resolution, eligibility, exposure records, assignment checks, and all evaluation
rules are absent.

## Implementation steps

1. Add the generic protocol, request value object, base conflict, and move
   `lock_subject` into `governance/review_boundary.py`.
2. Add `MaintenanceReviewBoundary` as the Maintenance Planning adapter over the
   existing policy helpers; make `ReviewIsolationConflict` a policy-specific
   subtype of the generic base conflict.
3. Inject the implementation from `api/app.py` via `api/dependencies.py` into the
   Media and Memory routes.  Media may be constructed for its authorization-free
   upload path without the boundary, but all human review reads require the
   injected capability.
4. Replace only the reusable Media/Memory imports and calls.  Update the generic
   API exception handler to catch the base boundary conflict.
5. Add a focused Batch 1.5 boundary smoke before implementation and use it to
   verify protocol ownership, injection, and import direction.
6. Update Batch 1 report/follow-ups, including the PostgreSQL status required for
   this batch.

## Files expected to change

- `src/industrial_ops_agent/governance/review_boundary.py` (new)
- `src/industrial_ops_agent/maintenance_planning/review_boundary.py` (new)
- `src/industrial_ops_agent/maintenance_planning/review_isolation.py`
- `src/industrial_ops_agent/media/service.py`
- `src/industrial_ops_agent/memory_governance/service.py`
- `src/industrial_ops_agent/api/app.py`
- `src/industrial_ops_agent/api/dependencies.py`
- `src/industrial_ops_agent/api/errors.py`
- `src/industrial_ops_agent/api/routes/uploads.py`
- `src/industrial_ops_agent/api/routes/memories.py`
- `scripts/deindustrialization_batch15_review_boundary_smoke.py` (new)
- `docs/deindustrialization_batch1_report.md`
- `docs/deindustrialization_batch1_followups.md`

## Verification

Run the Batch 1 Golden Path and boundary smokes, the new Batch 1.5 smoke, affected
imports, Ruff, Python compilation, focused mypy, and a mechanical import scan.
The PostgreSQL item is recorded as `NOT RUN — no disposable PostgreSQL environment available`; Docker Desktop is unavailable and no disposable PostgreSQL service is present, so no infrastructure will be created.
