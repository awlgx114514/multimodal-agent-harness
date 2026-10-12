# Batch 2B Knowledge Applicability Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move reusable Knowledge/RAG filtering from industrial device fields to a minimal generic key/value applicability contract while preserving Industrial Diagnosis retrieval behavior.

**Architecture:** `Knowledge` owns only opaque applicability filters and generic matching. Industrial Diagnosis converts its device family/model context into those filters at the boundary. Existing `device_families` and `device_models` persistence columns remain as compatibility fields and are backfilled into the new applicability JSON column; runtime retrieval reads only the new column.

**Tech Stack:** Python 3.11+, SQLAlchemy 2, Alembic, SQLite test fallback, PostgreSQL SQL path, deterministic sparse/vector ranking, OpenSearch optional search profile, Ruff, py_compile, focused mypy.

**Spec:** `docs/deindustrialization_batch2_report.md` Batch 2B task specification supplied by the user.

## Global Constraints

- Do not modify Multimodal, Recognition, or the Batch 2A Evidence bridge.
- Do not delete legacy database columns or fulfillment, and do not enter Batch 2B follow-on work.
- Do not introduce ontology, schema registry, DSL, nested expression language, or broad Knowledge redesign.
- Generic retrieval consumes only `ApplicabilityFilter(key, values)` key/value matching.
- Generic applicability is the only runtime filtering source of truth.
- Existing ACL, release/version, validity, ranking, reranking, citation, and wildcard semantics must remain equivalent.
- PostgreSQL rehearsal is `NOT RUN — no disposable PostgreSQL environment available`; SQLite migration must run.

---

### Task 1: Freeze Industrial Diagnosis retrieval baseline

**Files:**
- Create: `scripts/deindustrialization_batch2b_retrieval_baseline.py`
- Test data: in-memory SQLite production Knowledge records only

**Interfaces:**
- Consumes: current `RetrievalQuery` and `HybridRetriever`.
- Produces: deterministic JSON-like baseline containing candidate counts, eligible IDs, final IDs, citation IDs, ACL/release cases, and family/model mismatch cases.

- [ ] **Step 1: Write the baseline fixture and cases**

Create production-record fixture rows covering matching family, matching model, family match/model mismatch, tenant isolation, ACL, release/version eligibility, global applicability, and citation anchors. Use deterministic embeddings/content and run each case through `HybridRetriever.search_with_trace()`.

- [ ] **Step 2: Run the baseline before contract changes**

Run:

```powershell
$env:PYTHONPATH="D:\Microsoft\Large-Model-Application-main-batch1\src"
& "D:\Microsoft\Large-Model-Application-main-batch1\.venv\Scripts\python.exe" "D:\Microsoft\Large-Model-Application-main-batch1\scripts\deindustrialization_batch2b_retrieval_baseline.py"
```

Expected: PASS and a printed baseline for every case; no production source changes are allowed before this result is captured.

---

### Task 2: Add the minimal generic applicability contract (RED → GREEN)

**Files:**
- Create: `src/industrial_ops_agent/knowledge/applicability.py`
- Modify: `src/industrial_ops_agent/knowledge/models.py`
- Test: `scripts/deindustrialization_batch2b_generic_applicability_smoke.py`

**Interfaces:**
- Produces `ApplicabilityFilter(key: str, values: frozenset[str])` with exact key/value matching and empty filters meaning no restriction.
- `RetrievalQuery` consumes `applicability: tuple[ApplicabilityFilter, ...]` and no mandatory device fields.
- `RetrievedEvidence` exposes generic applicability in citations; any temporary legacy deserialization support must not be used by filtering.

- [ ] **Step 1: Write a failing domain-neutral contract smoke**

The smoke must instantiate `ApplicabilityFilter(key="product.version", values=frozenset({"v2"}))`, build a `RetrievalQuery` without `device_family/device_model`, assert exact serialization, and scan `knowledge/applicability.py` and the query declaration for forbidden industrial terms.

- [ ] **Step 2: Run the smoke and confirm the expected RED**

Expected: failure because `knowledge/applicability.py` and the new query shape do not yet exist.

- [ ] **Step 3: Implement only the minimal contract**

Use an immutable dataclass, validate non-empty key/values, and add only tuple-based key/value filters. Do not add operators, nested expressions, registries, or ontology concepts.

- [ ] **Step 4: Run the smoke GREEN**

Expected: PASS with no industrial term in the reusable contract.

---

### Task 3: Add persistence and forward migration

**Files:**
- Modify: `src/industrial_ops_agent/persistence/models.py`
- Create: `alembic/versions/0088_knowledge_generic_applicability.py`
- Test: `scripts/deindustrialization_batch2b_sqlite_migration_smoke.py`

**Interfaces:**
- `KnowledgeDocumentVersionRecord.applicability` stores JSON mapping opaque keys to string arrays.
- Migration `0088_knowledge_generic_applicability` adds the nullable-compatible JSON column, backfills old rows from `device_families/device_models`, and preserves both legacy columns.
- Existing rows map to the Industrial adapter keys without dropping or rewriting legacy values.

- [ ] **Step 1: Write the SQLite migration test**

The test must create the pre-0088 schema using Alembic, seed global, family-only, model-specific, and empty legacy applicability rows, upgrade to 0088, and assert the new JSON values plus unchanged legacy columns.

- [ ] **Step 2: Run the migration test and confirm RED**

Expected: failure because revision 0088 and the new column are absent.

- [ ] **Step 3: Implement the forward migration and ORM field**

Backfill `device_families` to the adapter family key and `device_models` to the adapter model key. Empty old arrays become `{}`. Do not modify revisions 0001–0087.

- [ ] **Step 4: Run SQLite migration GREEN**

Expected: PASS, with no dropped columns and Alembic head at 0088.

---

### Task 4: Industrial adapter and ingestion source-of-truth write path

**Files:**
- Create: `src/industrial_ops_agent/industrial_recognition/knowledge_applicability.py`
- Modify: `src/industrial_ops_agent/knowledge/ingestion.py`
- Modify: `src/industrial_ops_agent/knowledge/files.py`
- Test: `scripts/deindustrialization_batch2b_ingestion_applicability_smoke.py`

**Interfaces:**
- `industrial_applicability(device_family: str | None, device_model: str | None) -> tuple[ApplicabilityFilter, ...]` owns equipment-to-key conversion.
- New and extracted Industrial Knowledge ingestion writes `applicability` and temporarily mirrors the old columns for compatibility.
- Generic Knowledge code receives generic filters and never interprets the industrial keys.

- [ ] **Step 1: Write failing adapter and ingestion assertions**

Assert family-only, model-only, family-plus-model, and missing-value conversions; assert new ingestion records persist both applicability and compatibility values.

- [ ] **Step 2: Run RED**

Expected: missing adapter/column/write-path failure.

- [ ] **Step 3: Implement the smallest adapter and write-path changes**

Keep the existing public ingestion inputs for compatibility, convert immediately at the Industrial boundary, and write one generic applicability object as runtime source of truth.

- [ ] **Step 4: Run GREEN**

Expected: PASS, with one applicability representation and mirrored legacy fields only for compatibility.

---

### Task 5: Migrate RetrievalQuery, HybridRetriever, and optional SearchProfile filters

**Files:**
- Modify: `src/industrial_ops_agent/knowledge/retrieval.py`
- Modify: `src/industrial_ops_agent/agent/diagnosis_runtime.py` only at the RetrievalQuery construction site
- Modify: `src/industrial_ops_agent/knowledge/index_evaluation.py`
- Modify: `src/industrial_ops_agent/search_profiles/service.py`
- Modify: `src/industrial_ops_agent/search_profiles/store.py`
- Test: `scripts/deindustrialization_batch2b_retrieval_parity_smoke.py`

**Interfaces:**
- `HybridRetriever` receives only `query.applicability` for applicability filtering.
- SQLite and PostgreSQL use generic JSON key/value matching with the same empty/global semantics.
- Ranking and citation constructors use no equipment semantics; reranking receives only the generic retrieval result/query data required for ordering.
- SearchProfile receives a serialized generic applicability filter and remains optional; no OpenSearch startup or deployment changes.

- [ ] **Step 1: Extend the parity smoke with before/after expected IDs**

Use the frozen baseline fixture and assert eligible document IDs, sparse/vector/fused/final counts, final rank order, citation IDs, ACL, release, validity, family-only, model-only, combined, and global cases.

- [ ] **Step 2: Run RED against the new query shape and generic-only retriever scan**

Expected: failure because the current retriever reads `query.device_family/device_model` and legacy JSON columns.

- [ ] **Step 3: Implement generic filtering in both SQL paths**

Use `json_each/jsonb` over `applicability` with exact key/value existence checks. Preserve ACL, classification, release, validity, sparse/vector candidate limits, RRF, and citation identity. Keep old columns out of runtime filtering.

- [ ] **Step 4: Convert Industrial Diagnosis context at the boundary**

Construct `applicability=industrial_applicability(device_family, device_model)` before creating `RetrievalQuery`; do not add industrial compatibility logic to `HybridRetriever`.

- [ ] **Step 5: Update index evaluation and SearchProfile optional projection**

Pass generic applicability through evaluation and use generic applicability keys/values in optional SearchProfile query construction and authorization checks. Do not connect to OpenSearch.

- [ ] **Step 6: Run the parity smoke GREEN**

Expected: exact eligible/final IDs and citations match the frozen baseline for all deterministic cases.

---

### Task 6: Domain-neutral smoke, dependency scan, and regression verification

**Files:**
- Create: `scripts/deindustrialization_batch2b_domain_neutral_smoke.py`
- Modify: `scripts/deindustrialization_batch2_retrieval_smoke.py` if needed to reflect the final contract
- Modify: `docs/deindustrialization_batch2_report.md`

- [ ] **Step 1: Add the domain-neutral retrieval smoke**

Seed applicability `product.version=v2` and query it without any industrial identifier. Assert exact matching, nonmatching, missing applicability/global visibility, ACL, and citation behavior.

- [ ] **Step 2: Run the mechanical dependency scan**

Scan reusable `knowledge`, `search_profiles`, and retrieval evaluation code for `device_model`, `device_family`, `Asset`, `Equipment`, and Industrial Diagnosis imports. Legacy persistence columns may remain only with an explicit report note that they are not consumed by runtime retrieval.

- [ ] **Step 3: Run required regression checks**

Run Batch 1 Golden Path, Batch 1 boundary, Batch 1.5, Batch 2 tool catalog, Batch 2A Recognition/Multimodal, Batch 2A evidence provenance, generic applicability smoke, SQLite migration smoke, parity smoke, domain-neutral smoke, Ruff, `py_compile`, and focused mypy.

- [ ] **Step 4: Record PostgreSQL and FastAPI environment status**

Record exactly:

```text
PostgreSQL migration rehearsal:
NOT RUN — no disposable PostgreSQL environment available
```

Do not repair `spacy.tokens` or install dependencies.

- [ ] **Step 5: Update Batch 2B report and verify final status**

Document Before/After, source of truth, migration 0088/backfill/SQLite result/PostgreSQL status, baseline-vs-after parity, remaining legacy references, commands/results, and scope exclusions. Declare PASS only if every required deterministic check passes.

---

## Self-review

- The plan covers baseline capture, RED/GREEN contract work, persistence/backfill, Industrial adapter, both primary SQL paths, optional SearchProfile projection, ingestion, parity, domain-neutral behavior, dependency scan, and every required regression command.
- No task changes Multimodal, Recognition, Agent evidence/citation semantics, fulfillment, GraphRAG, realtime, or gateway composition.
- No database migration is destructive; legacy columns remain and 0088 is the only new revision.
- Generic Knowledge code compares opaque key/value data only; all equipment meaning stays in the Industrial adapter and migration backfill mapping.
