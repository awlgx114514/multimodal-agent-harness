# Batch 3E GraphRAG / Realtime / Repository Surface Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remove active GraphRAG/Neo4j and field-oriented WebRTC surfaces while preserving governed knowledge retrieval, generic transcription confirmation, Agent events, and the Diagnosis Golden Path.

**Architecture:** Graph retrieval is removed at the application boundary; governed document retrieval remains the only knowledge retrieval path. Realtime is reduced to the existing persisted transcript/confirmation-to-Agent-event capability, while WebRTC session/signaling and field-specific orchestration are removed from default runtime and API composition.

**Tech Stack:** Python, FastAPI, SQLAlchemy/Alembic, Temporal, OpenAPI, Next.js/TypeScript, Docker/Helm, existing repository smoke scripts.

**Spec:** Batch 3E user-provided specification in the current task attachment.

## Global Constraints

- Preserve `Recognition → Evidence → Diagnosis → Agent → RAG → Read-only Tools → DiagnosisReport`.
- Preserve governed Knowledge ingestion, HybridRetriever, embeddings/reranking, citations, ACL, release/version, generic applicability, and optional OpenSearch.
- Preserve generic transcription, bounded validation, human confirmation, generic Agent input events, and Agent resume.
- Do not modify historical Alembic migrations or historical audit/deindustrialization reports.
- Do not fix missing local dependencies, PostgreSQL availability, or repository-wide mypy/stub baseline.
- Do not start new product features or redesign the frontend.

## Review Focus

- Default runtime must not import or construct GraphRAG/Neo4j or field WebRTC services.
- Graph table deletion must be child-first and preserve generic knowledge/index tables.
- Confirmed transcript-to-Agent-event behavior must remain available without a media session.
- OpenSearch remains optional and disabled by default.
- Active route, frontend, deployment, and dependency scans must distinguish historical references from stale production references.

### Task 1: Remove GraphRAG / Neo4j Active Surface

**Files:** `src/industrial_ops_agent/graph_rag/`, graph API route, runtime/orchestration/app/dependencies/config/auth/secrets/knowledge deletion/models, graph frontend page, graph deployment/config/dependencies, and one forward migration after `0091` if required.

- [ ] Remove graph runtime construction, workflow registration, route inclusion, settings/secrets, authorization actions, and graph-specific prompt registration.
- [ ] Remove graph models and active knowledge deletion coupling while keeping document/index/citation deletion.
- [ ] Add a forward-only child-first migration for graph tables only if the current schema contains them.
- [ ] Remove GraphRAG frontend/API generated references without changing retained knowledge retrieval.

### Task 2: Reduce Realtime to Generic Transcript Capability

**Files:** `src/industrial_ops_agent/realtime_media/`, `src/industrial_ops_agent/multimodal/realtime.py`, realtime API/app/runtime/config/dependencies, realtime persistence models and forward migration if needed, `docker/media-server.Dockerfile`, `compose.realtime.yaml`, `web/components/m3/RealtimeAudioPanel.tsx`, generated OpenAPI/client output.

- [ ] Remove WebRTC session/token/signaling/STUN/TURN and field session construction.
- [ ] Retain or minimally adapt transcript persistence, bounded segment validation, confirmation, and generic Agent input event append.
- [ ] Remove only field realtime routes/UI/deployment; do not remove generic ASR or transcript review contracts used by Diagnosis.

### Task 3: Final Runtime/API/Frontend/Deployment Inventory

**Files:** current route registrations, runtime worker registration, compose/Helm/Vault/env/config/docs/readme, generated OpenAPI/client artifacts.

- [ ] Verify deleted domains are not constructed by default runtime and remove stale active references.
- [ ] Update current-facing technical documentation only; preserve historical reports and migrations.
- [ ] Keep PostgreSQL, Redis where used, MinIO, Temporal, Model Gateway, generic training, MLflow, Airflow, and optional OpenSearch.

### Task 4: Batch 3E Smoke and Verification

**Files:** `scripts/deindustrialization_batch3e_surface_smoke.py`, `docs/deindustrialization_batch3e_report.md`, optional follow-ups.

- [ ] Add smoke assertions for graph absence, HybridRetriever presence, generic transcript confirmation/event path, runtime/API/frontend/deployment absence, and OpenSearch default-off behavior.
- [ ] Run Batch 1, 1.5, 2A, 2B, 2C, 3A, 3B, 3C, 3D regressions plus Batch 3E smoke, compile, targeted Ruff, API/dependency scans, and Alembic head.
- [ ] Record PostgreSQL as `NOT RUN — no disposable PostgreSQL environment available` and report PASS/PARTIAL/FAIL from evidence.
