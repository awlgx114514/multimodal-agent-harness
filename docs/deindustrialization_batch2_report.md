# Deindustrialization Phase 1 — Implementation Batch 2 Report

## Status

Batch 2 stopped at the Multimodal boundary Stop Condition 2.  No fulfillment domain
was deleted and no retrieval schema migration was started.

## Locate evidence

- `multimodal/models.py` owns both generic findings and the industrial
  `EvidenceBundle`, including confirmation/review state, automation eligibility,
  and security-review validation.
- `multimodal/processor.py` accepts `bundle_id`, `draft_id`, `asset_id`, and
  `asset_model`, and directly calls `EvidenceBundle.create` in both its image and
  video paths.
- `application/incidents.py` invokes that processor and directly persists/maps the
  resulting bundle and its review records.

Therefore extracting generic processing would require simultaneously replacing the
processor's public return type, image/video construction, RecognitionService
workflow, persistence mapping, and review transitions.  That is a recognition
workflow rewrite, which Batch 2 explicitly forbids as a way to bypass the stop
condition.  A wrapper or a copied protocol would only conceal the ownership.

## Changes Made

- Added the three Batch 2 RED acceptance scripts for Multimodal, retrieval, and
  tool-catalog boundaries.
- Added `agent/tool_catalog.py` and
  `tools.registry.diagnosis_readonly_tool_definitions()`.  The explicit Industrial
  Diagnosis catalog contains only the five existing read-only tool definitions and
  does not change fulfillment definitions.

## Verification

| Check | Result |
| --- | --- |
| Multimodal generic contract smoke | RED — generic contracts and separation absent |
| Retrieval generic applicability smoke | RED — generic applicability absent |
| Diagnosis-only catalog smoke | PASS |
| Batch 2 scope | STOPPED before fulfillment deletion, migration, or runtime split |

## Remaining Reverse Dependencies

The Multimodal `EvidenceBundle` ownership remains the blocking dependency.  It must
be addressed only in a dedicated recognition-workflow refactor batch with its own
compatibility and persistence plan.

## Scope Discipline

This batch did not delete fulfillment, enter realtime split, modify predictive,
Kafka, GraphRAG, supplier, or frontend domains, and did not create a second reference
application.

## Final Success Statement

```text
Batch 2 structural goals:
FAIL — Stop Condition 2: EvidenceBundle cannot be separated from multimodal processing without rewriting the recognition workflow and persistence mapping.
```

## Batch 2A Recognition Migration

### Changes Made

- Added `multimodal.models.PerceptionRequest` and `PerceptionResult`; their fields
  describe only media, caller-provided context, perception observations and runtime
  metadata.
- Changed `MultimodalProcessor` image and video paths to return `PerceptionResult`.
  It no longer creates an EvidenceBundle, applies industrial entity rules, evaluates
  evidence security/review policy, or accepts an `asset_model`.
- Moved the existing EvidenceBundle, review/confirmation state, entity models and
  security validation into `industrial_recognition/evidence.py` without changing
  their validation logic.
- Added `industrial_recognition/adapter.py`. `IndustrialEvidenceMapper` converts
  perception primitives into the existing industrial evidence types, applies the
  original entity/security rules, and constructs the unchanged EvidenceBundle.
- `RecognitionService.process` now supplies industrial instruction/hotword context,
  calls the generic processor, then maps the result to EvidenceBundle before the
  existing keyframe persistence, run completion and API-visible lifecycle.
- VLM, ASR and temporal provider protocols now accept caller-provided
  instruction/context rather than `asset_model`; industrial prompt construction is
  owned by Industrial Recognition.

### Before

```text
MultimodalProcessor → EvidenceBundle
```

### After

```text
MultimodalProcessor → PerceptionResult → Industrial Recognition → EvidenceBundle
```

### EvidenceBundle Parity

The Batch 2A behavioral smoke verifies literal OCR, visual and QR data preserve
identifiers, text, normalized regions, confidence, processor provenance and
industrial ownership identifiers after mapping. It also verifies the initial review
state/blocker and the existing confirmation transition to automation eligibility.

### Provider Boundary

`multimodal/providers.py` and `multimodal/video.py` no longer contain an
`asset_model` parameter or industrial instruction text. `RecognitionService` obtains
the prior Industrial Diagnosis VLM, temporal and ASR context from
`industrial_perception_instructions()` and passes it as opaque caller context.

### Persistence/API/Workflow Compatibility

No database migration, persistence schema, API response/request model or Temporal
payload was changed. `RecognitionActivity` still returns EvidenceBundle and the
workflow continues to use its existing run and bundle identifiers.

### Verification

| Check | Result |
| --- | --- |
| Perception contract, image processing, mapping, confirmation and automation smoke | PASS |
| Multimodal dependency scan | PASS — target core files contain no asset_model, EvidenceBundle, review state or industrial prompt text |
| Batch 1 Golden Path / boundary / Batch 1.5 / Batch 2 tools | PASS |
| ruff on changed files | PASS |
| py_compile on changed Python files | PASS |
| focused mypy: models, processor, Industrial Recognition adapter/evidence | PASS |
| focused mypy including providers | NOT CLEAN — local optional PIL typing dependency is missing |
| Full FastAPI import | NOT RUN — existing local environment lacks `spacy.tokens` |
| persistence-to-Diagnosis-manifest-to-final-report parity | NOT YET VERIFIED |

### Remaining Reverse Dependencies

Batch 2A does not alter realtime modules, retrieval applicability, dual gateway
composition, fulfillment, predictive maintenance, Kafka or GraphRAG. Those remain
outside this recognition migration scope.

### Batch 2A Final Result

```text
Batch 2A structural goals:
FAIL — persistence-to-Diagnosis-manifest-to-final-report parity has not yet been independently verified; full FastAPI import is also blocked by the pre-existing missing spacy.tokens environment dependency.
```

## Batch 2A.1 End-to-End Parity

### Verification architecture

This verification deliberately did not construct the FastAPI application.  The new
`scripts/deindustrialization_batch2a1_manifest_parity_smoke.py` uses production
SQLAlchemy records and services with a disposable, thread-safe SQLite database,
the production `RecognitionService`, `MultimodalProcessor`, Industrial Recognition
mapper, `DiagnosisService`, production persistence repositories, authorization,
and deterministic OCR/VLM and model-resolution fixtures.  It invokes the actual
write and subsequent read paths rather than comparing only in-memory objects.

### Persistence parity

PASS up to the persisted EvidenceBundle boundary.

- Production recognition consumed clean media through `MediaService` and generated
  a `PerceptionResult`, then Industrial Recognition produced the EvidenceBundle.
- `RecognitionService` persisted the bundle and its recognition results.  A fresh
  `RecognitionService.get_evidence()` read retained the bundle/draft/asset/media
  ownership, source hash, processor provenance, one OCR result (`ALARM-42`), one
  visual finding, its region and confidence, and the initial review state.
- Production `RecognitionService.confirm()` then persisted the accepted finding;
  a second read retained `CONFIRMED`, versioned review state, and automation
  eligibility.

### Diagnosis manifest parity — structural blocker

The production `DiagnosisService.start()` accepted that reloaded confirmed bundle,
created an AgentRun and DiagnosisRun, wrote the normal queued event, and dispatched
the normal `DiagnosisWorkflowInput`.  Its manifest correctly preserves
`evidence_bundle_id`, `evidence_version`, the active index release, graph version,
prompt bundle and tool versions.

However, it preserves only the opaque EvidenceBundle ID and version.  It contains
no persisted OCR/finding IDs, finding payload, review/confirmation references, or
provenance binding that reaches an original perception finding.  This is not a
serialization loss: the same smoke proved those records exist after reload.

The direct production call-chain scan confirms the consequence: `DiagnosisRuntime`
initializes `state["evidence"]` empty and populates it only from `HybridRetriever`;
it does not read `EvidenceBundleRecord` or `RecognitionResultRecord`.  Consequently
the Agent has no authorized Diagnosis context from which it can consume the
confirmed perception evidence.

### Agent execution and final DiagnosisReport

NOT RUN after the manifest stop condition.  Running a synthetic Agent after this
point could exercise retrieval and tools, but it cannot satisfy the required chain
from a final citation through Diagnosis context to a persisted EvidenceBundle and
its original perception finding.  It would therefore be a false parity result.

The missing binding also prevents verification of the required final
`DiagnosisReport` evidence/citation trace.  No production change was made: this
is an application-contract gap to be resolved before attempting that execution.

### Commands and results

| Check | Result |
| --- | --- |
| Batch 2A.1 persistence + reload + confirmation + Diagnosis manifest smoke | FAIL as required by the verification: persistence and manifest ID/version pass; persisted finding-to-manifest context/citation binding is absent |
| Batch 1 Golden Path smoke | PASS |
| Batch 1 boundary smoke | PASS |
| Batch 1.5 review-boundary smoke | PASS |
| Diagnosis tool catalog smoke | PASS |
| Batch 2A recognition smoke | PASS |
| Batch 2A generic Multimodal contract smoke | PASS |
| Dependency scan | PASS for the Batch 2A generic Multimodal core; the existing Batch 1.5 classified direct Maintenance-policy imports remain outside this Batch 2A.1 scope |
| Ruff on changed files | PASS |
| `py_compile` on changed Python files | PASS |
| Focused mypy (Multimodal core, Industrial Recognition adapter/evidence, Batch 2A.1 smoke) | PASS — 5 source files checked |

### FastAPI environment limitation

```text
Full FastAPI import:
NOT RUN — existing local spacy.tokens dependency unavailable.
Non-blocking for Batch 2A structural verification.
```

Direct import was attempted only to classify the limitation and stopped at
`presidio_analyzer -> spacy.tokens`.  No dependency, FastAPI startup, NLP module,
or requirements file was modified.

### Batch 2A.1 Final Result

```text
Batch 2A structural goals:
FAIL — Diagnosis manifest/runtime carries only EvidenceBundle ID/version and does not load confirmed persisted findings; therefore a final DiagnosisReport citation cannot be traced to the original perception finding.
```

## Batch 2A.2 Evidence Provenance Bridge

### Implementation

按已确认的 Option B 最小方案补齐了：

```text
persisted EvidenceBundle
  → Diagnosis Manifest.evidence_refs[]
  → DiagnosisEvidenceResolver
  → AgentEvidenceContext
       ├ Recognition evidence
       └ Knowledge evidence
  → final DiagnosisReport.citations
```

- `agent/evidence.py` 只包含 domain-neutral 的 Agent evidence item、context 和 resolver protocol。
- `industrial_recognition/diagnosis_evidence.py` 负责 Industrial Diagnosis 的 persisted result 解析、确认状态过滤、版本/租户/媒体源哈希/结果哈希校验，以及 recognition citation provenance。
- `DiagnosisManifest` 增加兼容性的 `evidence_refs[]` 与整组引用 hash；没有新增数据库表或 migration。
- `DiagnosisRuntime` 同时消费 Recognition 与 Knowledge evidence；旧 Knowledge checkpoint 仍可恢复。
- worker composition root 显式装配 `DiagnosisEvidenceResolver`；没有把 Industrial 依赖塞回 reusable Agent layer。
- 被拒绝的 finding、被拒绝的 OCR/ASR/QR 结果和未确认 entity 不进入 Agent context；修正后的文本使用确认后的值，原始结果 hash 保留为 provenance 锚点。

### Verification

| Check | Result |
| --- | --- |
| Batch 2A.1 persist → reload → confirm → manifest → resolver → final citation | PASS |
| Recognition citation 回溯到 bundle/result/media/source finding | PASS |
| rejected evidence filtering / tamper rejection | PASS |
| Batch 1 Golden Path / boundary / Batch 1.5 | PASS |
| Diagnosis tool catalog / Batch 2A recognition / Multimodal contract | PASS |
| changed-file Ruff | PASS |
| changed-file `py_compile` | PASS |
| focused mypy（5 个生产文件） | PASS |
| reusable evidence boundary scan | PASS — 无 maintenance planning 业务语义或 import |
| PostgreSQL migration rehearsal | NOT RUN — no disposable PostgreSQL environment available |
| Full FastAPI import | NOT RUN — existing local `spacy.tokens` dependency unavailable; non-blocking |

### Scope result

本次没有修改 Multimodal architecture，没有进入 Batch 2B，没有删除 fulfillment 或其他业务域，也没有修改数据库 schema。

```text
Batch 2A structural goals:
PASS
```

# Batch 2B — Generic Knowledge Applicability

## Scope and ownership

Batch 2A remains frozen and passed.  This batch changes only Knowledge/RAG
applicability representation and its retrieval consumers.  It does not modify
Multimodal, Recognition, the Evidence provenance bridge, fulfillment, realtime,
predictive maintenance, Kafka, GraphRAG, frontend, or gateway runtime composition.

The reusable layer now owns only a minimal opaque key/value contract:

```text
ApplicabilityFilter(key, values)
  → exact intersection match
  → missing or empty document key is open
  → multiple filters are ANDed
```

Industrial Diagnosis owns the mapping from its existing family/model context to
`equipment.family` and `equipment.model` filters through
`industrial_recognition/knowledge_applicability.py`.  The reusable Knowledge
retriever, models, and SearchStore do not import Industrial Recognition or
Maintenance Planning and do not contain industrial field names.

## Before / after

Before, runtime filtering was coupled directly to the legacy fields:

```text
RetrievalQuery.device_family/device_model
        ↓
device_families/device_models persistence fields
        ↓
HybridRetriever and optional SearchStore filtering
```

After, the runtime source of truth is generic applicability:

```text
Industrial Diagnosis adapter
        ↓
RetrievalQuery.applicability[]
        ↓
HybridRetriever / SearchStore generic filtering
        ↓
RetrievedEvidence.applicability → citation payload
```

The legacy `device_families` and `device_models` columns remain for compatibility
serialization and existing callers.  They are not read by the reusable retrieval
or SearchStore authorization filters.  Industrial ingestion paths populate the
generic object and continue mirroring the legacy values during this compatibility
period.  This establishes one runtime source of truth rather than two independent
filtering implementations.

## Migration 0088

`alembic/versions/0088_knowledge_generic_applicability.py` adds the non-null
`applicability` JSON object to `knowledge_document_versions` and backfills existing
rows as follows:

```text
device_families → equipment.family
device_models   → equipment.model
empty legacy scope → {}
```

The migration preserves both legacy columns and their values.  `alembic heads`
reports `0088_knowledge_generic_applicability (head)`.

SQLite rehearsal passed with global, family-only, and family-plus-model fixtures:

```text
DEINDUSTRIALIZATION_BATCH2B_SQLITE_MIGRATION_PASS
```

PostgreSQL rehearsal:

```text
NOT RUN — no disposable PostgreSQL environment available
```

No production database was contacted and no infrastructure was created.

## Retrieval parity

The frozen baseline was seeded with the same global, family-only, model-specific,
ACL, mismatch, validity, release, and tenant-isolation cases.  Generic retrieval
preserved the baseline result sets:

| Case | Sparse/vector/fused/returned | Final chunk IDs |
| --- | ---: | --- |
| matching family and model | 5 / 5 / 5 / 5 | family, global, model, role-acl, subject-acl |
| family match, model mismatch | 4 / 4 / 4 / 4 | family, global, role-acl, subject-acl |
| unspecified family, model match | 3 / 3 / 3 / 3 | global, role-acl, subject-acl |

Citation IDs remained aligned with the same chunks.  Citation payloads now expose
generic applicability instead of the query's legacy model field; source checksum,
content checksum, document/version identity, page and fused ranking semantics are
preserved.

## Verification

| Check | Result |
| --- | --- |
| Generic applicability contract smoke | PASS |
| Retrieval parity smoke | PASS |
| Existing retrieval boundary smoke | PASS |
| SQLite 0088 migration rehearsal | PASS |
| Diagnosis read-only tool catalog smoke | PASS |
| Batch 2A recognition and Multimodal contract smoke | PASS |
| Batch 2A persistence/manifest/provenance smoke | PASS |
| Batch 1 Golden Path smoke | PASS |
| Batch 1 boundary and Batch 1.5 smoke | PASS |
| Reusable capability dependency scan | PASS |
| Changed-file Ruff | PASS |
| Changed-file `py_compile` | PASS |
| Focused mypy | PASS |
| Full FastAPI import | NOT RUN — existing local `spacy.tokens` dependency unavailable; non-blocking |

The mechanical dependency check confirms that `knowledge/applicability.py`,
`knowledge/models.py`, `knowledge/retrieval.py`, and `search_profiles/store.py`
contain no Maintenance Planning/Industrial Recognition imports or legacy device
filter tokens.  Remaining legacy field references are limited to compatibility
storage, industrial adapters/ingestion boundaries, parser compatibility, and
existing citation/governance views.

## Batch 2B structural result

```text
Batch 2B structural goals:
PASS
```

# Batch 2C — Runtime Composition

## Scope and ownership

Batch 2A and Batch 2B remain frozen and passed.  This batch changes only the
Diagnosis runtime composition and tool catalog boundary.  It does not modify
Multimodal/Recognition, the Agent evidence bridge, Knowledge applicability,
database migrations, fulfillment deletion, or any later deindustrialization
scope.

## Before / after

Before, the Temporal worker composition root built the full enterprise adapter
set and the mixed default registry before injecting a `ToolGateway` into
`DiagnosisActivity`:

```text
DiagnosisActivity
  → default mixed ToolRegistry
  → ToolGateway + parts + all enterprise adapter construction
```

After, the worker composition root explicitly builds a Diagnosis-only adapter
and catalog:

```text
Diagnosis composition root
  → Diagnosis read-only catalog (five existing tools)
  → shared ToolGateway implementation
  → DiagnosisActivity / DiagnosisRuntime
```

The API runtime continues to own the existing mixed gateway for Fulfillment
routes.  Diagnosis and Fulfillment therefore use separate gateway instances
with the same `ToolGateway` implementation; no second governance/runtime
implementation was introduced.

## Runtime isolation

`tools/diagnosis_composition.py` contains only the Diagnosis read-only catalog
composition and lazy read-adapter selection.  It does not construct or import
mutation adapter types for parts, work-order dispatch, quotation, procurement,
refund, FSM assignment, or equipment control.  The Diagnosis gateway receives
no mutation adapter fields.  The existing `ToolGateway` remains the shared
governance implementation and its mutation capabilities remain available to
the legacy Fulfillment composition.

The five Diagnosis tool definitions are reused unchanged through
`diagnosis_tool_registry()`: names, version `1.0.0`, T0 risk, `asset.read`
authorization, no approval requirement, schema, idempotency, and rate/timeout
semantics remain intact.

## Verification

| Check | Result |
| --- | --- |
| Batch 2C RED: missing Diagnosis composition | PASS — expected module absence observed |
| Batch 2C GREEN: production `DiagnosisRuntime.tool()` read-only path | PASS |
| Diagnosis mutation tool rejection | PASS |
| Separate Diagnosis/Fulfillment gateway instances using same implementation | PASS |
| Batch 1 Golden Path smoke | PASS |
| Batch 1 boundary and Batch 1.5 smoke | PASS |
| Diagnosis catalog, Multimodal, and Batch 2A recognition smokes | PASS |
| Batch 2A persistence/manifest/provenance smokes | PASS |
| Generic applicability, retrieval parity, and 0088 SQLite rehearsal | PASS |
| Batch 2C mechanical dependency scan | PASS |
| Changed-file Ruff | PASS |
| Changed-file `py_compile` | PASS |
| Focused mypy for new composition module | PASS |
| Full `runner.py` mypy | NOT CLEAN — existing Temporal stubs and two pre-existing resolver type errors |
| Full FastAPI import | NOT RUN — existing local `spacy.tokens` dependency unavailable; non-blocking |
| Temporal worker import | NOT RUN — existing local `temporalio.bridge` dependency unavailable; non-blocking |
| MCP adapter import | NOT RUN — existing local `pywintypes` dependency unavailable; non-blocking |
| PostgreSQL migration rehearsal | NOT RUN — no disposable PostgreSQL environment available |

No unrelated dependency was installed or repaired.  No production database was
contacted and no infrastructure was created.

## Remaining coupling

The shared `ToolGateway` source still contains the legacy mutation operations,
and the API runtime still composes the mixed Fulfillment gateway.  Those are
intentional compatibility boundaries for this batch; Fulfillment deletion and
further gateway decomposition remain out of scope.

```text
Batch 2C structural goals:
PASS

Batch 2 structural goals:
PASS
```
