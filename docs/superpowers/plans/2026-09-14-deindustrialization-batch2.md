# Deindustrialization Batch 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove Industrial Diagnosis assumptions from reusable multimodal,
retrieval, and tool-governance contracts without changing the current diagnosis flow.

**Architecture:** Generic capability modules expose only neutral data and protocols.
Industrial Recognition, equipment applicability, and the diagnosis catalog adapt
those contracts in composition/application code.  Existing persistence fields and
fulfillment paths remain compatible.

**Tech Stack:** Python 3.12, SQLAlchemy/Alembic, FastAPI, LangGraph, JSON Schema.

**Spec:** `docs/superpowers/specs/2026-09-14-deindustrialization-batch2-design.md`

## Global Constraints

- Preserve Incident → Recognition → Evidence review → Diagnosis → Agent → RAG/tools.
- Do not delete fulfillment, realtime, predictive, Kafka, GraphRAG, or supplier code.
- Add no prompt framework, ontology, schema registry, second reference app, or tool runtime.
- No Git checkpoint is possible; do not initialize a repository.

---

### Task 1: Establish Batch 2 acceptance checks

**Files:**
- Create: `scripts/deindustrialization_batch2_multimodal_smoke.py`
- Create: `scripts/deindustrialization_batch2_retrieval_smoke.py`
- Create: `scripts/deindustrialization_batch2_tools_smoke.py`

- [ ] Write each smoke against the desired public contracts and run it before
  production changes.  Expect failure because generic processing/result,
  applicability, and diagnosis-only catalog do not yet exist.
- [ ] Keep each smoke independent of external OCR/VLM/PostgreSQL services by using
  existing deterministic readonly/provider fixtures and SQLite records.

### Task 2: Make multimodal perception domain-neutral

**Files:**
- Modify: `src/industrial_ops_agent/multimodal/models.py`
- Modify: `src/industrial_ops_agent/multimodal/processor.py`
- Modify: `src/industrial_ops_agent/multimodal/providers.py`
- Modify: `src/industrial_ops_agent/multimodal/video.py`
- Create: `src/industrial_ops_agent/application/industrial_evidence.py`
- Modify: `src/industrial_ops_agent/application/incidents.py`
- Modify: `src/industrial_ops_agent/orchestration/activities.py`
- Modify: `src/industrial_ops_agent/orchestration/runner.py`

- [ ] Define neutral `ProcessingRequest`, `ProcessingResult`,
  `InspectionContext`, and `TranscriptionContext`; no field mentions an asset,
  draft, incident, diagnosis, work order, or EvidenceBundle.
- [ ] Make provider and video contracts accept those contexts, and move hard-coded
  industrial prompts/model values into an Industrial Recognition context builder.
- [ ] Change the processor to return neutral findings/provenance only.
- [ ] Move EvidenceBundle creation, review semantics, and industrial entity
  validation to `application/industrial_evidence.py`; have RecognitionService adapt
  the generic result before existing persistence calls.
- [ ] Run the multimodal smoke, then Batch 1 Golden Path; confirm the persisted
  bundle fields and existing result behaviour remain unchanged.

### Task 3: Replace retrieval device semantics with applicability

**Files:**
- Create: `src/industrial_ops_agent/knowledge/applicability.py`
- Modify: `src/industrial_ops_agent/knowledge/models.py`
- Modify: `src/industrial_ops_agent/knowledge/retrieval.py`
- Modify: `src/industrial_ops_agent/knowledge/ingestion.py`
- Modify: `src/industrial_ops_agent/search_profiles/store.py`
- Modify: `src/industrial_ops_agent/search_profiles/service.py`
- Modify: `src/industrial_ops_agent/persistence/models.py`
- Create: `alembic/versions/0088_generic_knowledge_applicability.py`
- Modify: `src/industrial_ops_agent/agent/diagnosis_runtime.py`
- Create: `src/industrial_ops_agent/agent/applicability.py`

- [ ] Define deterministic generic applicability values/tags and a filter whose
  matching semantics are identical to current model/family filtering.
- [ ] Add nullable-safe JSON applicability storage and migration backfill from
  existing device columns; retain legacy values as write-compatible mirrors.
- [ ] Replace SQLite, PostgreSQL, in-memory/OpenSearch, ranking, guard-trace and
  Search Profile reads with generic applicability filtering; do not reference
  device terms in `HybridRetriever`.
- [ ] Map diagnosis device values in `agent/applicability.py` before constructing
  `RetrievalQuery`.
- [ ] Run migration and retrieval parity smoke with equivalent industrial corpus,
  ranks, citations, ACL, tenant and generic metadata cases.

### Task 4: Create an Industrial Diagnosis read-only catalog

**Files:**
- Modify: `src/industrial_ops_agent/tools/registry.py`
- Create: `src/industrial_ops_agent/agent/tool_catalog.py`
- Modify: `src/industrial_ops_agent/tools/factory.py`
- Modify: `src/industrial_ops_agent/orchestration/runner.py`
- Modify: `src/industrial_ops_agent/runtime.py`

- [ ] Extract the existing five unchanged ToolDefinition values into a neutral
  registry selector without importing agent contracts into `tools`.
- [ ] Implement `diagnosis_tool_registry()` in the agent package; assert exactly
  the five existing ids/versions and preserve all schemas.
- [ ] Build a readonly-only gateway for the diagnosis worker and retain the
  existing full gateway/catalog for fulfillment composition.
- [ ] Run the catalog smoke using representative readonly calls and verify it
  constructs without Parts/mutation adapters while existing full construction stays
  available.

### Task 5: Final verification and report

**Files:**
- Create: `docs/deindustrialization_batch2_report.md`
- Create: `docs/deindustrialization_batch2_followups.md` only if a stop condition occurs

- [ ] Run Batch 1, Batch 1.5, and all Batch 2 smoke scripts; run lint, py_compile,
  focused mypy, Alembic head, and import scans.
- [ ] Record exact migration state, parity evidence, remaining later-batch
  dependencies, and scope discipline.  State `Batch 2 structural goals: PASS` only
  if every required check succeeds; otherwise state the exact blocker.
