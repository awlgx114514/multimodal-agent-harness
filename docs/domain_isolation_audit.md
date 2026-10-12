# Domain Isolation Audit

## Scope and method

This is a static audit of the checked-out source tree. No source code,
configuration, database schema, prompt, or runtime deployment was changed.
Findings derive from imports, type signatures, persisted schemas, prompt text,
tool schemas, workflow I/O, and runtime composition. They do not assert that a
path has been exercised successfully in production.

| Classification | Meaning |
| --- | --- |
| Domain-independent | Public contract and implementation contain no Industrial Diagnosis business concept. |
| Mostly reusable | Infrastructure is reusable; coupling is local naming or composition. |
| Partially coupled | Reusable mechanism exists, but its contract, state, or default path embeds industrial assumptions. |
| Strongly industrial-specific | Input/output/state/prompt/tool/workflow implements Industrial Diagnosis business logic. |

## 1. Capability / Domain Dependency Map

| Capability | Classification | Static evidence | Conclusion |
| --- | --- | --- | --- |
| Multimodal pipeline | Partially coupled | `multimodal/processor.py` requires `draft_id`, `asset_id`, `asset_model` and returns `EvidenceBundle`; `providers.py` requires `asset_model` and prompts for an industrial asset. | OCR, QR, video decomposition, boxes, transcripts and candidate findings are portable; the service contract is asset-evidence oriented. |
| Agent graph loop | Partially coupled | `agent/graph.py` has bounded LangGraph control flow but imports `DIAGNOSIS_GRAPH_VERSION` and `budget_report`, with fixed diagnosis actions/nodes. | Mechanics reusable; public contract and terminal semantics are diagnosis-owned. |
| Agent runtime | Strongly industrial-specific | `agent/diagnosis_runtime.py` imports `DiagnosisWorkflowInput`, retrieval, tool gateway and diagnosis contracts; state is `diagnosis-state/v2`. | It is an Industrial Diagnosis runtime, not a generic runtime plus plug-in. |
| Agent contracts/prompts | Strongly industrial-specific | `agent/contracts.py` defines `DIAGNOSIS_*`, industrial read-only tools, diagnosis report and fallback text. | Reusable ideas, not reusable contracts. |
| Checkpoints/events | Mostly reusable | `agent/checkpoints.py` and `agent/events.py` work with run ID, sequence, graph version and JSON state/event. | Code is reusable, but `AgentRunRecord` is currently diagnosis-owned. |
| Tool registry/governance | Mostly reusable | `ToolDefinition` carries version, risk, schema, permission, approval, idempotency, timeout/retry/rate limit; `ToolGateway.invoke` validates, authorizes, rate-limits and audits. | Valuable reusable primitives. |
| Tool catalog/implementations | Strongly industrial-specific | Default schemas use asset, incident, parts, work-order, quotation and equipment-control objects; gateway requires `PartsAdapter` and implements repair/procurement/refund/FSM flows. | Industrial business logic surrounds the generic entry point. |
| Model Gateway transport/audit | Mostly reusable | `GatewayRequest`, `ModelTransport`, quota, inference audit, replay and context manifest are generic serving mechanisms. | Transport and audit are portable. |
| Model Gateway route policy | Partially coupled | Aliases are `industrial-diagnosis[-staging]`; allowed classes are `DIAGNOSIS`/ `VLM`; resolved model exposes `diagnosis_binding`. | No direct Incident import, but release policy is application-specific. |
| Knowledge ingestion/embedding | Mostly reusable | Documents, chunks, ACLs, checksums, parser/chunker versions, embeddings and releases are document-centric. | Runbooks/deployment docs fit this lifecycle. |
| Retrieval/RAG | Partially coupled | `RetrievalQuery` requires `device_model`; SQL prefilters, guard trace, fusion and citations use device family/model; knowledge versions persist both arrays. | Hybrid retrieval is reusable, applicability is equipment-specific. |
| Memory/context | Partially coupled | `select_for_diagnosis()` reads `IncidentRecord`, filters `purpose == "DIAGNOSIS"`, and scopes session notes to incident plus asset. | Governance/truncation/hashes reusable; selection policy is diagnosis-specific. |
| Evaluation | Partially coupled | `evaluation/metrics.py` has generic cost/latency/JSON/retrieval/VLM/ASR/tool metrics; datasets also import industrial training, telemetry and RUL contracts. | Measurement substrate reusable; suites/contracts are partly industrial. |
| Temporal orchestration | Partially coupled | Temporal owns durability/retry; `DiagnosisActivity` and `DiagnosisWorkflow` take diagnosis input and publish diagnosis records. | Infrastructure reusable; shipped agent workflow is a diagnosis application. |
| Application services | Strongly industrial-specific | `application/diagnoses.py` validates Incident, Asset, EvidenceBundle, knowledge release, production model binding and DiagnosisRun lifecycle. | This is the industrial reference application boundary. |
| Persistence | Partially coupled | Database/tenant/inference/tool/event/checkpoint mechanisms are reusable; same model package contains industrial records and `AgentRunRecord.diagnosis_run_id`. | Storage mechanics reusable; schema boundary is not clean. |
| Frontend | Strongly industrial-specific | Routes/client expose incident, asset, work-order, recognition, diagnosis, field/offline and industrial-AI flows. | Generic web shell/proxy exists beneath an industrial product UI. |

## 2. Dependency direction

Intended direction:

```text
Reusable Core ──► Domain Application ──► Industrial Diagnosis reference application
```

The tree also contains reverse dependencies from substrate-facing modules into
Industrial Diagnosis:

| Reverse dependency | Evidence | Consequence |
| --- | --- | --- |
| Agent graph → diagnosis contracts | `graph.py` imports `DIAGNOSIS_GRAPH_VERSION` and `budget_report`. | A second agent must inherit or change diagnosis semantics. |
| Agent runtime → incident/asset/evidence/tools | `diagnosis_runtime.py` state and calls contain incident, asset ID/model, device context and industrial tools. | Domain application runtime, not reusable core. |
| Agent persistence → diagnosis run | `AgentRunRecord.diagnosis_run_id` is required and foreign-keyed to `diagnosis_runs`. | Events/checkpoints cannot have an independent domain owner. |
| Tools → industrial entities | Default registry and gateway use incident, asset, parts, work orders, quotation and equipment control. | A triage catalog cannot be supplied as an entirely independent domain module. |
| Multimodal → industrial asset | VLM protocol requires `asset_model`; prompts name an industrial asset. | Screenshot understanding is not a supported domain-neutral input contract. |
| Retrieval → equipment applicability | Query, SQL filters, index record, fusion and citation all carry device family/model. | General technical knowledge needs applicability extraction. |
| Memory → incident/asset | `select_for_diagnosis` queries `IncidentRecord`. | Technical context selection cannot reuse this policy unchanged. |
| Model route → industrial release | Fixed aliases, request classes, diagnosis binding and trace name in `model_gateway/service.py`. | A second governed agent release needs policy extension. |

The direction is therefore **mixed**: a real reusable substrate exists, while
several core-facing contracts point back to Industrial Diagnosis.

## 3. Agent Runtime

### Reusable runtime

- Bounded LangGraph execution, deadline and tool budget enforcement.
- Node-level commit hooks, checkpoints, event sequencing and JSON state.
- Structured model responses, evidence/context manifest, tool-call audit and replay.

### Industrial Diagnosis runtime

- `DiagnosisGraphRuntime`, `DiagnosisGraph`, graph version, action enum and
  budget-exhausted final output are diagnosis-specific.
- `DiagnosisRuntime` loads diagnosis memory, device retrieval context,
  industrial tool facts and `diagnosis-state/v2`.
- `agent/contracts.py` maps output into `DiagnosisReport`.
- Workflow load/publish code commits industrial business records.

Natural boundary:

```text
Reusable mechanics:
  graph execution, time/budget guard, checkpoints/events, model envelope

Per-domain agent:
  state schema, prompt, action/result schema, retrieval profile, allowed tools,
  memory selector, final mapper, business-run persistence and publishing
```

This is a small, concrete extraction—not a request to turn the project into a
generic framework.

## 4. Multimodal isolation

Portable primitives already exist: `BoundingBox`, `OcrBlock`,
`VisualFinding`, ASR segments, QR candidates, video keyframes and temporal
events. `multimodal/video.py` is a bounded decomposer/provider boundary that
does not intrinsically require a machine asset.

Current coupling:

- `ProcessingRequest` requires draft, asset and asset-model identity.
- `MultimodalProcessor` returns `EvidenceBundle` and records
  `industrial-entity-rules-v2`.
- `VlmProvider.inspect(..., asset_model=...)` requires an asset model.
- Both VLM paths explicitly instruct the model to inspect an industrial asset
  and avoid a final fault diagnosis.
- Entity extraction is oriented to industrial evidence, not service, log,
  dashboard, deployment or runbook contexts.

**Can current core process software/log/dashboard screenshots without change?**
No. A screenshot can pass generic image validation, OCR and bounded transport,
but the processor-level input contract, VLM prompt and evidence ownership require
industrial asset context. Text logs are also not represented by this image/video
processor. Low-level OCR/ASR/video parsing is reusable; the current processor
service is only partially isolated.

## 5. Tool boundary

Reusable governance is present in `ToolDefinition` and the entry path of
`ToolGateway.invoke()`: version/schema validation, authorization, rate limit,
approval state, idempotent audit and execution record. `tools/mcp.py` is a
potentially reusable authenticated, schema-pinned read-only adapter.

Industrial implementation is co-located with it:

- asset, warranty, parts, schedule and work-order history;
- parts reservation/issue/consumption and compatibility;
- entitlement, repair work order, quotation, procurement, notification, refund
  and FSM assignment;
- equipment-control handoff policy.

Further, `ToolGateway.__init__()` has a required `PartsAdapter`, even if a
second domain wants only read-only tools. Current state is therefore:

```text
generic governance entry point + industrial catalog + industrial transactional implementations
```

It is not yet a clean generic runtime with independently supplied domain tools.

## 6. RAG / knowledge

Documents, chunks, checksums, releases, embeddings, reranking, citations, ACLs,
tenant filtering and hybrid recall can serve runbooks, API docs, deployment notes
and postmortems.

The boundary problem is applicability:

- `RetrievalQuery` makes `device_model` mandatory and includes
  `device_family`.
- Sparse and vector SQL paths prefilter `device_families` and
  `device_models`.
- Returned evidence, fusion, evaluation and guard traces retain device-model
  semantics.
- `KnowledgeDocumentVersionRecord` and ingestion-job records persist those
  arrays.

Technical Incident Triage would fit the document lifecycle, but must express
applicability as service/repository/environment/component/version/time context
rather than universal equipment context. Incident history additionally needs a
governed document/event projection instead of assuming the industrial Incident
record.

## 7. Workflow / backend

Temporal itself is reusable durable orchestration. The shipped
`DiagnosisActivity`/`DiagnosisWorkflow` is not: it takes diagnosis input,
loads and publishes diagnosis/incident state, owns diagnosis-specific
reanalysis, and is assembled with industrial adapters in
`orchestration/runner.py`.

| Layer | Status |
| --- | --- |
| Temporal client/worker/retry capability | Reusable infrastructure |
| Workflow invocation conventions | Mostly reusable |
| Diagnosis activity/workflow | Industrial Diagnosis application code |
| Runner composition | Industrial application composition using reusable dependencies |

## 8. Static stress test: Technical Incident Triage

Scenario only; no implementation is made:

```text
Screenshot / Logs / Runbook / Deployment History / Service Status
  → Technical Incident Triage Agent
  → retrieval + read-only tools
  → root-cause hypothesis / recommended action
```

### Files to add

These are static-impact recommendations, not files created by this audit.

| Proposed file | Responsibility |
| --- | --- |
| `src/industrial_ops_agent/application/technical_triage.py` | Triage command validation and domain-run lifecycle. |
| `src/industrial_ops_agent/agent/triage_runtime.py` | Triage state, prompt assembly, retrieval/tool calls and result mapping. |
| `src/industrial_ops_agent/agent/triage_contracts.py` | Triage step/final schemas, allowed tools, root-cause/recommended-action output. |
| `src/industrial_ops_agent/api/routes/technical_triage.py` | Screenshot/log/runbook/service-context API. |
| `src/industrial_ops_agent/tools/technical_triage.py` | Read-only tools for runbooks, deployment history, service status and permitted log queries. |
| `src/industrial_ops_agent/evaluation/technical_triage.py` | Triage evaluator/adapter and test interpretation. |
| `web/app/.../technical-triage/...` plus components | A new reference-application UI, not reuse of industrial incident screens. |
| `alembic/versions/<new_revision>.py` | Persist triage/agent-owner schema changes. |

### Existing files to modify

| Existing file | Required reason |
| --- | --- |
| `agent/graph.py` | Supply graph version/fallback/actions through domain configuration, or duplicate it. Small extraction is preferable. |
| `agent/checkpoints.py` and/or agent-run creation paths | The code is run-oriented, but durable ownership must no longer assume diagnosis. |
| `persistence/models.py` | `AgentRunRecord.diagnosis_run_id` is mandatory; add neutral ownership or a triage relation, plus triage run records as needed. |
| `alembic/versions/<new_revision>.py` | Apply the preceding persistence change. |
| `knowledge/models.py` | Replace mandatory equipment applicability with extensible filter data. |
| `knowledge/retrieval.py` | Filter/verify triage applicability in sparse and vector paths; remove device-only fusion/output assumptions. |
| `persistence/models.py` knowledge record definitions | Extend `device_families`/`device_models` applicability storage consistently. |
| Knowledge ingestion service and API/schema files | Accept service/repository/environment/component metadata for runbooks/deployments. |
| `memory_governance/service.py` | Generalize or add selector; current selector reads Industrial Incident and asset. |
| `tools/gateway.py` | Permit read-only governance without required `PartsAdapter`; isolate equipment T3 policy. |
| `tools/registry.py` or registry assembly | Keep industrial default catalog separate from triage catalog. |
| `tools/contracts.py` and `tools/authority.py` | Add triage fact authority/schema validation rather than applying industrial facts. |
| `model_gateway/service.py` | Generalize aliases, request classes, diagnosis binding and trace naming for a triage release. |
| `orchestration/workflows.py` | Add triage activity/workflow or extract shared agent-workflow mechanics. |
| `orchestration/runner.py` | Compose/register triage workflow, runtime and tools. |
| `api/app.py` | Include triage router. |
| Generated OpenAPI frontend client and relevant `web` routes/navigation | Expose the new API and reference application. |

### Current core modules needing no source change

| Module | Why |
| --- | --- |
| `persistence/database.py`, `persistence/tenant.py` | Tenant-bound transactions are domain-neutral. |
| `model_gateway/context_manifest.py` | Context references, truncation and hashing are generic. |
| `model_gateway/openai.py` | HTTP transport remains valid; policy changes belong above it. |
| `tools/mcp.py` | Can serve a new read-only schema catalog unchanged. |
| Low-level media validation/storage modules | A screenshot is ordinary media. |
| `multimodal/video.py` | Bounded decomposition is generic if future triage needs video. |
| Generic parts of `evaluation/metrics.py` | Cost, latency, schema, citation, tool-use and basic retrieval metrics can be reused. |
| Next backend proxy route | It forwards backend paths without industrial fields. |

“No source change” does not mean “no integration work”: checkpoint/event source
can remain as-is only after its persistence owner is no longer diagnosis-only.

## 9. Isolation scorecard

Scale: `0` fully industrial-bound; `1` highly coupled; `2` partially
reusable; `3` mostly isolated; `4` fully domain-independent.

| Capability | Score | Reason |
| --- | ---: | --- |
| Multimodal pipeline | 2 | Portable primitives, but asset-model request, industrial prompt and EvidenceBundle ownership. |
| Agent loop | 2 | Bounded graph exists; imports/version/actions/fallback are diagnosis-bound. |
| Agent state | 1 | `diagnosis-state/v2` and incident/asset/evidence/tool/report fields dominate. |
| Agent contracts | 1 | Explicitly named and shaped for diagnosis. |
| Tool runtime | 2 | Generic governance path, but construction and T3 policy mix domain concerns. |
| Tool implementations | 0 | Industrial operations/business workflows. |
| RAG infrastructure | 2 | Document/ACL/hybrid substrate reusable; applicability equipment-specific end to end. |
| Model Gateway | 2 | Transport/audit reusable; route/release contract industrial diagnosis-specific. |
| Evaluation | 2 | Generic metrics coexist with industrial training/telemetry/RUL contracts. |
| Temporal orchestration | 2 | Durable engine reusable; shipped workflow semantics diagnosis-owned. |
| Persistence | 2 | Generic mechanics coexist with industrial schema and diagnosis-owned AgentRun. |
| Frontend | 1 | Generic shell exists under a strongly industrial UI. |

## 10. Positioning decision

**B — Mostly Isolated, Small Extraction Needed.**

Evidence:

- The repository has substantial reusable mechanisms: media primitives, tenant
  and authorization infrastructure, structured model gateway, hybrid retrieval,
  tool governance, checkpoint/event mechanics and durable orchestration.
- Industrial Diagnosis is concentrated in identifiable contracts/modules rather
  than duplicated across every low-level component.
- A second read-only, evidence-based agent can reuse significant mechanics.

It is not A because core-facing contracts still directly encode `DIAGNOSIS_*`,
asset/incident ownership, device applicability, industrial aliases and required
industrial tool adapters. It is not C or D because the reusable substrate is
real and the necessary work is bounded extraction/parameterization, not a
replacement platform.

## 11. Boundary finding

The defensible portfolio positioning is **Multimodal Operations Agent / Applied
AI System with Industrial Diagnosis as its current reference application**.
That is a target positioning, not proof that the repository is already fully
domain-neutral. A second reference application is credible after small,
targeted boundary extraction.

# Executive Decision

1. **How isolated are multimodal / Agent / Tool / RAG today?** They are partially isolated: low-level media, governance, transport, hybrid-search and orchestration mechanisms are reusable, while operational contracts retain asset, incident, diagnosis, device-model and industrial-tool assumptions.
2. **How much core-code modification is required to add Technical Incident Triage?** More than adapter-only work but less than a rewrite: small targeted changes are needed in graph/config binding, agent-run ownership, retrieval applicability, memory selection, tool construction/policy and model-release policy; runtime/tools/workflow/API/UI/corpus/evaluation are new domain code.
3. **Is an architecture refactor required before repositioning?** No large refactor. State that Industrial Diagnosis is the current reference application, then complete a small boundary extraction before claiming a second domain is supported.

**Recommended action: Small extraction.**

