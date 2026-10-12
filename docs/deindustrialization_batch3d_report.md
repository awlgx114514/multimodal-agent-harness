# Deindustrialization Batch 3D — Predictive Maintenance / Telemetry / RUL Deletion

## Scope

Batch 3D removed the predictive-maintenance product surface, telemetry/anomaly/RUL
runtime paths, predictive-only model lifecycle branches, and the orphaned
fulfillment-feedback Kafka/Debezium deployment surface. Batch 3E was not started.

The retained product path remains:

```text
Recognition → Evidence → Diagnosis → Agent → RAG → Read-only Tools → DiagnosisReport
```

The generic SFT/DPO/PPO/GRPO training paths, multimodal training/evaluation,
MLflow tracking, Model Gateway, dataset snapshots, retention/deletion DAGs,
knowledge retention, and generic release/promotion machinery remain present.

## Deleted predictive product surfaces

- Deleted `src/industrial_ops_agent/predictive_maintenance/` source modules and
  the predictive API route.
- Deleted the predictive-maintenance frontend page and navigation/API client
  surface.
- Deleted telemetry consumers, RUL/timeseries runtimes, predictive Dockerfiles,
  predictive promotion script, and the event-worker deployment entrypoints.
- Removed predictive training/evaluation methods, release fields, deployment
  metrics, authorization actions, and enterprise-asset RUL component handling.
- Removed predictive API paths and schemas from `contracts/openapi.json` and
  regenerated `web/generated/api/schema.d.ts`.
- Removed the obsolete `telemetry.v1` event contract and the M3 integration
  probe that depended on the removed feedback event pipeline.

## Training and model lifecycle split

Retained:

- Generic SFT, DPO, PPO and GRPO registration/configuration/execution.
- Generic multimodal, ASR, TTS, embedding and reranker evaluation paths.
- MLflow tracking, reproducible training sandbox, Model Gateway, release
  promotion, deployment observation, and generic model evidence.

Deleted:

- Telemetry dataset, timeseries-transformer, anomaly, RUL dataset and RUL
  inference branches.
- Predictive-only experiment gates, model-release fields, serving metrics and
  KServe deployment blocks.

## Airflow and eventing

Retained Airflow DAGs are the generic `build_dataset_snapshot` and
`retention_and_deletion` DAGs. Telemetry/RUL snapshot DAGs were deleted.

Kafka/Debezium is no longer required by the default Compose, Helm, observability,
or application deployment. The retained event envelope/outbox code is a generic
domain-event primitive used by current data-governance code; it does not start a
Kafka broker, consumer, Debezium connector, telemetry topic, or work-order event
worker in the default product.

## Database migration

Created forward-only migration:

`alembic/versions/0091_remove_predictive_maintenance.py`

It drops the nine predictive-only tables in child-first order:

```text
rul_forecast_calibrations
rul_forecast_candidates
predictive_outcomes
predictive_maintenance_referrals
alert_candidate_decisions
alert_candidates
telemetry_windows
telemetry_stream_states
telemetry_events
```

Historical migrations were not modified. The SQLite rehearsal passed and retained
generic parent/domain tables. Alembic verification reported:

```text
0091_remove_predictive_maintenance (head)
```

PostgreSQL rehearsal:

```text
NOT RUN — no disposable PostgreSQL environment available
```

No production database was contacted and no infrastructure was added.

## Verification evidence

Passed:

- `DEINDUSTRIALIZATION_BATCH3D_DELETION_PASS`
- `DEINDUSTRIALIZATION_BATCH3D_SQLITE_MIGRATION_PASS`
- Batch 1, Batch 1.5, Batch 2A, Batch 2B, Batch 2C, Batch 3A, Batch 3B and
  Batch 3C regression smokes.
- `python -m compileall -q src scripts`
- Ruff on all changed Python implementation/smoke files.
- OpenAPI JSON validation and OpenAPI TypeScript regeneration.
- Dependency scan proving predictive paths, tables, routes, workers, DAGs and
  active deployment surfaces are absent while generic lifecycle surfaces remain.

Known environment limitations, not Batch 3D structural blockers:

- Full FastAPI import was not run to completion because the local environment
  lacks `PIL`; the previously known `spacy.tokens`, Temporal and Windows
  dependency issues remain untouched.
- Frontend TypeScript check was not run because this copy has no installed
  frontend `node_modules` binary.
- Focused mypy remains at the repository's existing untyped/stub baseline,
  including the missing `PIL` dependency; no unrelated baseline was repaired.
- `.git` is absent by design; no repository was initialized.

## Scope guard

Batch 3E was not started. No realtime split, fulfillment deletion, predictive
replacement, Technical Incident Triage, GraphRAG cleanup, or unrelated
environment repair was performed.

Batch 3D deletion goals: PASS
