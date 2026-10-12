# Deindustrialization Batch 2A Recognition Workflow Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `multimodal` return domain-neutral perception while retaining the existing Industrial Diagnosis `EvidenceBundle` contract.

**Architecture:** Generic multimodal types retain OCR, VLM, QR, ASR and temporal observations in `PerceptionResult`.  `industrial_recognition` owns the industrial instruction, entity/security interpretation and maps that result to the unchanged `EvidenceBundle`; `RecognitionService` remains the composition boundary and persists the same object.

**Tech Stack:** Python 3.11+, dataclasses, asyncio, existing provider protocols and smoke scripts.

**Spec:** `docs/deindustrialization_batch2a_recognition_migration_audit.md`

## Global Constraints

- No database migration, API contract, frontend contract, Temporal payload, or Diagnosis downstream contract change.
- No retrieval applicability, dual gateway composition, fulfillment deletion, realtime work, or Model Gateway redesign.
- `multimodal` must not own assets, incidents, drafts, industrial entity rules, EvidenceBundle/review semantics, or industrial prompt constants.
- Preserve resulting EvidenceBundle fields, review/confirmation state, automation eligibility, persistence mapping and diagnosis manifest semantics.

---

### Task 1: Perception contracts and behavioral RED smoke

**Files:**
- Modify: `scripts/deindustrialization_batch2_multimodal_smoke.py`
- Create: `scripts/deindustrialization_batch2a_recognition_smoke.py`
- Modify: `src/industrial_ops_agent/multimodal/models.py`

- [ ] Write a runnable smoke that constructs a `PerceptionResult` with OCR/VLM/QR/ASR/video observations and asserts it has no industrial identity or review state.
- [ ] Run the smoke and confirm it fails because `PerceptionResult` does not yet exist.
- [ ] Add only the domain-neutral request/context/result dataclasses needed by the processor.
- [ ] Re-run the smoke and confirm it passes.

### Task 2: Move industrial evidence ownership and map perception parity

**Files:**
- Create: `src/industrial_ops_agent/industrial_recognition/__init__.py`
- Create: `src/industrial_ops_agent/industrial_recognition/evidence.py`
- Create: `src/industrial_ops_agent/industrial_recognition/adapter.py`
- Modify: all existing non-multimodal EvidenceBundle import sites

- [ ] Write a parity smoke with literal OCR/VLM/QR/ASR/video perception data and assert the adapter preserves findings, confidence, regions, provenance, industrial identifiers, initial review state and automation eligibility.
- [ ] Run it and confirm it fails because the adapter does not exist.
- [ ] Move industrial evidence/review/entity/security ownership without changing its validation rules; add the adapter mapping.
- [ ] Re-run the parity smoke and confirm it passes.

### Task 3: Make the generic processor return perception

**Files:**
- Modify: `src/industrial_ops_agent/multimodal/processor.py`
- Modify: `src/industrial_ops_agent/application/incidents.py`
- Modify: `src/industrial_ops_agent/orchestration/activities.py` only if its internal call needs adaptation

- [ ] Write an image-path smoke using deterministic providers; assert processing returns `PerceptionResult` and RecognitionService maps it to an equivalent EvidenceBundle.
- [ ] Run it and confirm it fails against the old processor return contract.
- [ ] Change processor inputs/return ownership and have RecognitionService construct the final EvidenceBundle before existing persistence and workflow steps.
- [ ] Re-run the image and video parity smokes; preserve IDs, retry/idempotency and activity return object.

### Task 4: Move industrial provider context out of multimodal

**Files:**
- Modify: `src/industrial_ops_agent/multimodal/providers.py`
- Modify: `src/industrial_ops_agent/multimodal/video.py`
- Modify: `src/industrial_ops_agent/multimodal/processor.py`
- Modify: `src/industrial_ops_agent/industrial_recognition/adapter.py`
- Modify: composition sites that build the processor

- [ ] Write a smoke asserting generic VLM/ASR/temporal protocols accept caller-provided instruction/context without `asset_model`.
- [ ] Run it and confirm it fails on the current asset-model parameters.
- [ ] Replace the parameters with the smallest caller-provided instruction/context values; have Industrial Recognition build the exact existing industrial instructions/hotwords.
- [ ] Re-run provider and recognition parity smokes.

### Task 5: Regression and boundary verification

**Files:**
- Modify: `docs/deindustrialization_batch2_report.md`

- [ ] Run Batch 1 Golden Path, Batch 1 boundary, Batch 1.5, Batch 2 tool catalog, Batch 2A behavioral and dependency smokes.
- [ ] Run ruff, `py_compile`, and focused mypy on changed code.
- [ ] Run an import/dependency scan proving generic multimodal has no industrial EvidenceBundle/review/prompt/asset ownership.
- [ ] Record all command results and the environment-limited FastAPI status in the Batch 2 report; declare PASS only if every required result is green.
