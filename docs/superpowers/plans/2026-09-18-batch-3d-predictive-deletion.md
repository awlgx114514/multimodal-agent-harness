# Batch 3D Predictive Maintenance Deletion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the predictive maintenance, telemetry, anomaly, RUL, and orphaned fulfillment-feedback product surfaces while retaining the Diagnosis Golden Path and generic AI lifecycle.

**Architecture:** The default runtime will construct only Recognition, Diagnosis, Agent, RAG, read-only tools, generic training/evaluation, and model lifecycle capabilities. Predictive-specific persistence is removed through a forward child-first migration; historical migrations remain unchanged. Generic dataset snapshots, retention/deletion, MLflow, model gateway, promotion, and the remaining event/data primitives are kept only where current code proves they are used.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, Alembic, Pydantic, Airflow DAG files, Docker Compose/Helm, Next.js/TypeScript, Ruff, mypy, SQLite rehearsal.

**Spec:** `C:/Users/32313/.codex/attachments/1f72d9da-c288-4fb5-b8ac-088c8bb85bbf/pasted-text.txt`

## Global Constraints

- Preserve `Recognition → Evidence → Diagnosis → Agent → RAG → Read-only Tools → DiagnosisReport`.
- Do not add sensor tools to Diagnosis and do not reconnect telemetry.
- Keep generic SFT/DPO/PPO/GRPO, multimodal training, evaluation, dataset snapshots, MLflow, Model Gateway, promotion, quantization, and generic workers.
- Do not modify historical Alembic migrations.
- Do not process GraphRAG, realtime, OpenSearch optional profile, generic MLflow/training redesign, Technical Incident Triage, RL trajectory integration, or repository rename.
- Do not repair `spacy.tokens`, `temporalio.bridge`, `pywintypes`, PostgreSQL availability, or existing mypy dependency/stub debt.
- Do not enter Batch 3E.

---

### Task 1: Add the Batch 3D RED contract smoke

**Files:**
- Create: `scripts/deindustrialization_batch3d_deletion_smoke.py`
- Test: `scripts/deindustrialization_batch3d_deletion_smoke.py`

**Interfaces:**
- Consumes current source tree, default runtime imports, generic training registries, model lifecycle modules, and Airflow DAG files.
- Produces one executable smoke proving predictive absence and generic lifecycle retention.

- [ ] **Step 1: Write the failing smoke first**

Assert all of the following before deleting production code:

```python
assert not (SRC / "predictive_maintenance").exists()
assert not (SRC / "api/routes/predictive_maintenance.py").exists()
assert not (WEB / "app/predictive-maintenance").exists()
assert "PredictiveMaintenanceService" not in runtime_source
assert "TelemetryDatasetPipelineService" not in runtime_source
assert "RulDatasetPipelineService" not in runtime_source
assert {"build_dataset_snapshot", "retention_and_deletion"} <= airflow_dag_ids()
assert "build_telemetry_dataset_snapshot" not in airflow_dag_ids()
assert "build_rul_dataset_snapshot" not in airflow_dag_ids()
assert {"SFT", "DPO", "PPO", "GRPO"} <= registered_training_methods()
assert mlflow_tracker_importable()
assert promotion_importable()
```

Also inspect the default source/deployment inventory and fail if it still contains an active telemetry consumer, RUL runtime, predictive route, predictive worker, Kafka work-order consumer, or Debezium connector.

- [ ] **Step 2: Run the smoke and verify the expected RED**

Run:

```powershell
$env:PYTHONPATH = "src"
.venv/Scripts/python.exe scripts/deindustrialization_batch3d_deletion_smoke.py
```

Expected: FAIL because the predictive package, route, page, runtime wiring, predictive DAGs, and predictive training branches still exist.

- [ ] **Step 3: Keep the smoke deterministic**

Use file existence/source inspection and import checks only; do not start FastAPI, Kafka, Airflow, GPU training, or external services.

### Task 2: Remove the predictive API, UI, service, runtime, and worker surface

**Files:**
- Delete: `src/industrial_ops_agent/predictive_maintenance/*.py`
- Delete: `src/industrial_ops_agent/api/routes/predictive_maintenance.py`
- Delete: `web/app/predictive-maintenance/page.tsx`
- Modify: `src/industrial_ops_agent/api/app.py`
- Modify: `src/industrial_ops_agent/api/dependencies.py`
- Modify: `src/industrial_ops_agent/runtime.py`
- Modify: `src/industrial_ops_agent/runtime_metrics.py`
- Modify: `src/industrial_ops_agent/config.py`, `src/industrial_ops_agent/secrets.py`
- Modify: `src/industrial_ops_agent/api/authorization.py` and the relevant action enum/policy files
- Modify: `web/components/AppShell.tsx`, `web/lib/api/client.ts`
- Delete or modify only predictive-specific scripts, tests, Dockerfiles, and lock/profile entries found by the audit.

**Interfaces:**
- Consumes the existing generic diagnosis runtime and generic application factory.
- Produces a runtime that has no predictive service, detector, forecaster, telemetry dataset service, RUL dataset service, or predictive route dependency.

- [ ] **Step 1: Remove the route/factory wiring and run the RED smoke again**

Remove the route import/include and the optional factory/dependency parameters. Remove only predictive API response models, actions, client functions, navigation, and page code. Keep Diagnosis routes and UI unchanged.

- [ ] **Step 2: Remove predictive runtime construction**

Delete imports, resolver construction, metrics construction, service construction, app-state injection, and close hooks for predictive detectors/forecasters and predictive dataset services. Keep generic `configure_telemetry`, Temporal, Model Gateway, RAG, and Diagnosis construction.

- [ ] **Step 3: Remove the predictive worker and deployable images**

Delete the predictive Kafka consumer and RUL/timeseries runtime entrypoints, then remove only their Docker/Compose/Helm/script references. Do not remove unrelated OpenTelemetry or application telemetry.

- [ ] **Step 4: Run the smoke and verify GREEN**

Run the Batch 3D smoke. Expected: the predictive absence assertions pass while the training and model-lifecycle assertions remain pending until Tasks 3–5 are complete.

### Task 3: Remove predictive persistence with a forward migration

**Files:**
- Modify: `src/industrial_ops_agent/persistence/models.py`
- Create: `alembic/versions/0091_remove_predictive_maintenance.py`
- Create: `scripts/deindustrialization_batch3d_sqlite_migration_smoke.py`

**Interfaces:**
- Consumes current Alembic head `0090_remove_workorder_field_fulfillment`.
- Produces head `0091_remove_predictive_maintenance` and metadata without predictive-only tables.

- [ ] **Step 1: Define the exact table set from live metadata**

Remove only these predictive-only tables after confirming no retained generic model/training table has a foreign key to them:

```text
telemetry_events
telemetry_stream_states
telemetry_windows
alert_candidates
alert_candidate_decisions
predictive_maintenance_referrals
predictive_outcomes
rul_forecast_candidates
rul_forecast_calibrations
```

Keep `DatasetSnapshotRecord`, `DatasetArtifactRecord`, `TrainingExperimentRecord`, evaluation records, model release/deployment records, MLflow integration, and knowledge retention records.

- [ ] **Step 2: Write the SQLite migration rehearsal first**

Construct a temporary SQLite schema containing the predictive tables and their actual foreign-key relationships, apply the migration, and assert the predictive tables are absent while `assets`, `incidents`, `dataset_snapshots`, `training_experiments`, `model_releases`, and knowledge tables remain.

- [ ] **Step 3: Run the migration smoke and verify the expected RED**

Run:

```powershell
$env:PYTHONPATH = "src"
.venv/Scripts/python.exe scripts/deindustrialization_batch3d_sqlite_migration_smoke.py
```

Expected: FAIL because revision 0091 and its table drops do not yet exist.

- [ ] **Step 4: Implement child-first migration and remove ORM classes**

Use `down_revision = "0090_remove_workorder_field_fulfillment"`. Drop calibration, RUL, outcome/referral, alert decision/candidate, window, stream-state, and telemetry-event tables in dependency order. Do not edit revisions 0001–0090.

- [ ] **Step 5: Run the migration smoke and verify GREEN**

Run the SQLite rehearsal and `alembic heads`; expect migration PASS and `0091_remove_predictive_maintenance (head)`.

### Task 4: Split training and experiment registration to generic methods only

**Files:**
- Modify: `src/industrial_ops_agent/training/runner.py`
- Modify: `src/industrial_ops_agent/training/config.py`, `src/industrial_ops_agent/training/backend.py` only where predictive branches are explicit
- Modify: `src/industrial_ops_agent/experiments/service.py`
- Modify: `src/industrial_ops_agent/persistence/models.py` for predictive-only experiment/model fields if present
- Modify: `src/industrial_ops_agent/model_gateway/*` and `src/industrial_ops_agent/releases/*` only for explicit predictive branches

**Interfaces:**
- Consumes generic dataset loader, training config compiler, backend, experiment registry, MLflow tracker, release, and promotion machinery.
- Produces generic registration for SFT/DPO/PPO/GRPO plus existing generic multimodal/embedding/reranker/ASR/TTS methods, with no telemetry/RUL dataset or inference branch.

- [ ] **Step 1: Add RED assertions to the Batch 3D smoke**

Assert predictive methods and classes are absent from the generic runner/configuration, while generic method registration and MLflow/promotion imports remain available.

- [ ] **Step 2: Remove telemetry/RUL dataset loaders and method branches**

Delete imports and constructor fields for `GovernedTelemetryDatasetLoader` and `GovernedRulDatasetLoader`; route all remaining methods through the generic dataset loader. Remove only `TIMESERIES_TRANSFORMER`, `TIMESERIES_RULE_BASELINE`, `RUL_TRANSFORMER`, and `RUL_EMPIRICAL_BASELINE` branches and artifact profiles.

- [ ] **Step 3: Remove predictive experiment gates and release fields**

Remove explicit predictive method/component constants, metrics, revisions, and model release manifest fields. Preserve generic release transport, aliases, inference audit, promotion evidence, MLflow tracking, and Diagnosis model aliases.

- [ ] **Step 4: Run generic lifecycle smoke and verify GREEN**

Run the Batch 3D smoke plus the repository’s existing generic training/evaluation and promotion contract smokes. Do not launch GPU training or external MLflow.

### Task 5: Delete predictive Airflow DAGs and orphaned Kafka/Debezium deployment

**Files:**
- Delete: `airflow/dags/build_telemetry_dataset_snapshot.py`
- Delete: `airflow/dags/build_rul_dataset_snapshot.py`
- Keep: `airflow/dags/build_dataset_snapshot.py`, `airflow/dags/retention_and_deletion.py`
- Delete: `src/industrial_ops_agent/event_worker/` if its only consumer remains `work_order.closed` feedback after Batch 3B
- Delete/modify: `docker/event-worker.Dockerfile`, `compose.observability.yaml`, `compose.integration.yaml`, `infra/debezium/**`, related Helm values/templates and Prometheus targets
- Modify: `pyproject.toml`, lock/profile/config files only when the dependency is exclusively the deleted consumer

**Interfaces:**
- Consumes generic dataset and knowledge governance DAGs, retained event envelope primitives only if still imported.
- Produces an Airflow inventory with exactly the two retained DAGs and a default deployment that does not require Kafka/Debezium.

- [ ] **Step 1: Add RED inventory assertions**

Assert telemetry/RUL DAG files, event worker deployment, work-order Kafka topic, and Debezium connector are absent; assert retained DAG files exist.

- [ ] **Step 2: Prove event-worker orphan status**

Search imports and call sites. If no KEEP capability consumes the worker, delete the worker and its deployment wiring. Preserve `EventEnvelope`, `EventOutboxRecord`, SSE, AG-UI, Temporal, and inference audit only when a retained module imports or uses them.

- [ ] **Step 3: Delete predictive DAG and Kafka/Debezium references**

Remove only predictive/work-order feedback deployment configuration. Classify generic Kafka library references and OpenTelemetry “telemetry” wording separately; do not delete unrelated observability.

- [ ] **Step 4: Verify retained DAG loading without Airflow infrastructure**

Use the existing repository DAG contract/import mechanism if available; otherwise inspect DAG IDs and imports without starting a scheduler. The retained files must remain syntactically importable in the available environment.

### Task 6: Final regression, dependency scan, and report

**Files:**
- Modify: `scripts/deindustrialization_batch3d_deletion_smoke.py`
- Modify: `docs/deindustrialization_batch3d_report.md`
- Create if needed: `docs/deindustrialization_batch3d_followups.md`

**Interfaces:**
- Consumes all retained smoke scripts and source/deployment inventories.
- Produces the final evidence report and exact status line.

- [ ] **Step 1: Run the complete required regression**

Run all existing Batch 1, 1.5, 2A, 2B, 2C, 3A, 3B, and 3C smokes, then Batch 3D absence/training/Airflow/migration smoke. Run changed-file Ruff, `python -m compileall -q src scripts`, focused meaningful mypy, route/worker/config dependency scans, `alembic heads`, and SQLite rehearsal.

- [ ] **Step 2: Record environment limitations exactly**

Record:

```text
PostgreSQL:
NOT RUN — no disposable PostgreSQL environment available
```

Do not fix existing `PIL`, `spacy.tokens`, `temporalio.bridge`, `pywintypes`, or mypy dependency/stub debt.

- [ ] **Step 3: Verify the final report before claiming completion**

The report must include Deleted Predictive Product, Training Split, Airflow Split, Kafka/Debezium, Model Lifecycle, Database, and Golden Path sections. Only claim PASS if all structural and Golden Path checks pass; otherwise use the required PARTIAL/FAIL status and name the concrete blocker.

