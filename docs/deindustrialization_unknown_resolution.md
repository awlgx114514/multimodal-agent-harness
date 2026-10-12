# Deindustrialization Unknown Resolution Audit

## Scope and decision rule

This audit resolves only the UNKNOWN items that affect Phase 1 product scope in
the prior Domain Isolation Audit and Deindustrialization Manifest. It does not
repeat already-established KEEP, MOVE or fulfillment-delete analysis, and makes
no source, configuration, deployment or data change.

Product boundary used for every decision:

    Case / Incident
    → Multimodal Evidence
    → Human Review
    → Agent
    → RAG / Read-only Tools
    → Structured Diagnosis
    → Trace / Eval

Industrial Diagnosis is the sole Reference Application and Diagnosis Result is
the business endpoint. A capability is retained only if it is Golden Path
required, a reusable AI capability, directly reusable by Technical Incident
Triage, or offers an explainable portfolio signal at reasonable complexity.

## 1. Final decision table

Portfolio and complexity use 0–4. Net Value equals Portfolio Value minus
Complexity Cost.

| Capability | Current role | Golden Path dependency | Direct future reuse | Portfolio value | Complexity | Final action |
| --- | --- | --- | --- | ---: | ---: | --- |
| Predictive maintenance: telemetry/anomaly/RUL | Industrial time-series prediction and maintenance referral product | No | No current Agent integration | 2 | 4 | DELETE |
| Sensor/telemetry facts | Predictive-maintenance API/service data, not an Agent tool | No | None without new tool work | 1 | 3 | DELETE with predictive domain |
| Realtime ASR and transcript-to-Agent-event | Optional live audio transcription with human confirmation | No; optional profile | Live spoken clarification can become Agent input | 3 | 3 | SPLIT |
| WebRTC/signaling/field realtime sessions | Incident/diagnosis/work-order/expert session control plane | No; flag default false | No direct reuse without extracting generic session model | 1 | 4 | DELETE after transcript split |
| Diagnosis Agent resume and expert takeover | AG-UI resume and diagnosis expert takeover | Yes, when clarification/human intervention is used | Human-in-the-loop agent execution | 3 | 1 | KEEP / MOVE with reference app |
| Work-order expert collaboration | Field expert session/recommendation workflow | No | No direct Agent resume path | 1 | 3 | DELETE with work-order fulfillment |
| Supplier A2A | Supplier-agent request, polling, human acceptance on diagnosis run | No; flag default false | No planned triage path | 1 | 3 | DELETE |
| Kafka event worker / feedback pipeline | Consumes closed work-order feedback candidates | No | None | 1 | 3 | DELETE |
| Kafka telemetry consumer | Consumes telemetry topic for predictive maintenance | No | None | 1 | 3 | DELETE |
| Debezium / CDC integration profile | Supports operational/event data pipeline | No | None after work-order/telemetry removal | 0 | 3 | DELETE |
| Generic dataset snapshot DAG | Governed Parquet snapshot for training/eval | No | Training/evaluation data preparation | 3 | 2 | KEEP |
| Knowledge retention DAG | Expired knowledge sweep and durable deletion dispatch | No | Runbook/document governance | 3 | 1 | KEEP |
| Telemetry dataset DAG | Predictive Transformer telemetry snapshots | No | None | 1 | 3 | DELETE |
| RUL dataset DAG | Industrial failure-lead-time training snapshots | No | None | 1 | 3 | DELETE |
| OpenSearch search profile | Optional governed document sparse/vector profile | No; disabled by default | Runbook corpus search for Technical Incident Triage through SearchProfileService and OpenSearchStore | 3 | 3 | OPTIONAL PROFILE |
| Neo4j / GraphRAG | Optional knowledge graph projection/extraction | No; graph flag default false | No current Agent retrieval route | 2 | 4 | DELETE |
| MLflow | Training experiment tracking and finished-run proof for promotion | No | Model lifecycle, SFT/DPO/PPO/GRPO evaluation and artifact traceability | 3 | 2 | KEEP |
| Generic training workers | SFT, DPO, PPO, GRPO, multimodal training, evaluation, model promotion | No | Agentic RL and model lifecycle | 4 | 3 | KEEP / SPLIT |
| Predictive/RUL training workers and runtimes | Industrial telemetry/RUL model training/inference | No | None | 1 | 4 | DELETE |
| Model Gateway, release, deployment, eval and observability | Governed model serving/lifecycle | Indirectly yes | Same model/eval/trace substrate for triage | 4 | 2 | KEEP |

No product-boundary UNKNOWN remains. The remaining uncertainties are operational
only: external data retention, deployed migration history and third-party
contracts. They determine deletion rollout safety, not which capabilities belong
in the Phase 1 product.

## 2. Predictive maintenance, telemetry and RUL

### What it actually does

The source implements an industrial time-series maintenance product, not a
generic sensor capability:

    TelemetryEventInput
    → PredictiveMaintenanceService.ingest telemetry event
    → telemetry window and feature snapshot
    → TimeseriesDetector anomaly detection
    → AlertCandidate review
    → maintenance referral to IncidentDraft
    → optional RUL forecast/calibration
    → WorkOrder and PredictiveOutcome feedback

Evidence:

- predictive_maintenance/service.py imports AssetRecord, IncidentDraftRecord,
  IncidentRecord and WorkOrderRecord, as well as TelemetryEvent, window, alert,
  RUL and predictive-outcome records.
- Its only built-in schema is rotating-equipment.telemetry.v1 with vibration,
  bearing temperature, motor current and RPM.
- api/routes/predictive_maintenance.py exposes telemetry ingestion, window
  construction, detection, alert/review, RUL forecast and dataset snapshot
  endpoints.
- runtime.py unconditionally constructs the service and detector/forecaster
  when model resolver is available, then injects it into the broad API factory.

### Golden Path determination

No predictive maintenance reference was found in:

- agent/diagnosis_runtime.py, other than generic OpenTelemetry tracing;
- agent/contracts.py and its five diagnosis read-only tools;
- DiagnosisRuntime state or prompt assembly;
- multimodal EvidenceBundle;
- DiagnosisReport contract.

Therefore:

**Sensor data is not currently part of the Diagnosis Agent tool surface.**

There is no current sensor reader, telemetry query, time-series query, anomaly
fact tool or RUL fact tool exposed to the Diagnosis Agent. The predictive API is
a separate application API, not an agent tool.

### Portfolio assessment and decision

This is a separate industrial ML application, not a multimodal/temporal Agent
capability in the retained product. It may be technically substantial, but it
does not meet the narrowed product criterion and adds Kafka, Airflow,
time-series/RUL runtimes, model-release fields, datasets and deployment cost.

Final action: **DELETE** predictive_maintenance, its predictive API/frontend,
telemetry/RUL consumer and worker/runtimes, predictive datasets/DAGs and
predictive-only model-release/evaluation branches. This is contingent on the
existing Phase 1 migration and external-retention checks; it does not mean
removing a source file in this audit.

## 3. Realtime media

### Actual capability

multimodal/realtime.py is a tenant-bound WebRTC control plane. It creates
one-time media tokens, renewable leases, signaling and STUN/TURN configuration.
Its session record carries Incident, DiagnosisRun, optional WorkOrder and expert
collaboration identifiers.

multimodal/realtime_transcripts.py accepts audio segments, sends them through
the transcription gateway, applies injection checks and entity review, and
persists ASR segments without retaining raw audio. On accepted confirmation for
a diagnosis-linked session, it appends:

    AgentEventRecord
    event_type = agent.user_input.confirmed
    source_type = realtime_transcript

The normal Agent resume path remains the diagnosis API and AG-UI resume input.
Realtime writes a confirmed input event; it is not an automatic
live-media-to-Agent-observation loop.

### Golden Path and future use

- Realtime media is not required: realtime_media_enabled defaults to false and
  runtime creates the session service only when enabled.
- It is not a generic live video/VLM pipeline. The code is WebRTC session and
  streaming ASR control, with industrial entity patterns and strong
  WorkOrder/field/expert dependencies.
- The confirmed-transcript append is a genuine reusable idea for Technical
  Incident Triage: live operator speech can become a reviewed Agent input.
  The concrete reusable path is TranscriptionGateway → transcript confirmation
  → generic Agent event append. It requires the prior AgentRun ownership and
  event vocabulary extraction.

Final action: **SPLIT**. Retain only the generic transcription transport,
bounded segment validation, confirmation gate and generic event-append
mechanism. Delete the current WebRTC session, field voice guidance, work-order
binding, industrial hotwords/entity patterns and field/expert realtime UI unless
a later explicitly-scoped live-operations feature is approved.

## 4. Collaboration, expert review and supplier A2A

These are three different things.

| Capability | Actual behavior | Agent resume relationship | Decision |
| --- | --- | --- | --- |
| Diagnosis expert takeover | application/expert_diagnoses.py and diagnoses route allow a human expert to take over or submit a diagnosis revision. | It is human intervention in the reference application; not supplier flow. | KEEP / MOVE with Industrial Diagnosis. |
| AG-UI resume | agent_events route accepts an approved resume clarification and invokes AgentRunControlService.resume. | Direct Agent → human input → resume capability. | KEEP as Agent mechanic, GENERALIZE in prior manifest. |
| Work-order expert collaboration | workorders/expert_collaboration.py plus expert_collaborations route organize field-expert sessions/recommendations. | No source evidence that recommendation automatically resumes the Diagnosis Agent. | DELETE with work-order fulfillment. |
| Supplier collaboration | collaboration/service.py and collaborations route create, dispatch, poll, cancel and human-review a supplier request tied to diagnosis_run_id. | No Agent graph/runtime call submits or consumes it. | DELETE. |
| Supplier A2A client | collaboration/a2a.py OfficialA2ASupplierAgentClient exchanges a task with a named remote supplier agent using OAuth credentials, skill ID and polling. | Agent-to-agent protocol transport exists, but it is invoked by supplier collaboration service/API, not Agent Runtime. | DELETE with supplier flow. |

Supplier A2A is technically agent-to-agent transport, not merely a supplier REST
API. Its message/state has supplier task identity, remote tenant, diagnosis run,
dispatch/refresh/cancel and human acceptance gates. That specificity, its
default-disabled configuration, and absence from Agent Runtime make it a poor
Phase 1 retention target. Do not preserve it as a generic A2A framework.

## 5. Kafka, Debezium and event pipeline

### Actual consumers and events

| Component | Topic/event | Consumer | Classification |
| --- | --- | --- | --- |
| event_worker/consumer.py | settings.kafka_work_order_topic, default ops.work-order.v1 | FeedbackEventProcessor | Post-diagnosis work-order feedback candidate creation |
| event_worker/handlers.py | work_order.closed | Feedback candidate and aggregate-version/inbox handling | Post-diagnosis fulfillment/training feedback |
| predictive_maintenance/consumer.py | settings.kafka_telemetry_topic, default ops.telemetry.v1 | ReplaySafeTelemetryConsumer | Predictive maintenance telemetry ingestion |
| eventing/envelope.py | Event envelope carrying work_order_id and trace metadata | Kafka-compatible work-order event producer path | Fulfillment support |
| Debezium in compose.integration.yaml | CDC/connector integration profile | Integration pipeline, not Diagnosis Runtime | Operational/event pipeline |

The current Golden Path uses database persistence, Temporal workflows, model
gateway audit records and SSE/AG-UI event streaming. No DiagnosisRuntime,
RecognitionActivity, DiagnosisWorkflow, Agent event stream or inference path was
found to publish to or consume from Kafka.

Final action: **DELETE** Kafka event worker, telemetry consumer, Kafka/Debezium
integration profile, Kafka settings/topics and work-order feedback event schema
after removing work-order and predictive domains. Preserve the non-Kafka
AgentEventRecord and SSE paths.

## 6. Airflow decisions

| DAG | Input | Output | Consumer | Golden Path? | Future AI value | Decision |
| --- | --- | --- | --- | --- | --- | --- |
| build_dataset_snapshot | Governed source data over daily window | Immutable Parquet dataset snapshot and OpenLineage confirmation | Generic training/evaluation pipeline | No | Direct generic training/eval value | KEEP |
| retention_and_deletion | Expired knowledge records | Durable deletion dispatch | Knowledge governance | No | Direct runbook/document lifecycle value | KEEP |
| build_telemetry_dataset_snapshot | Telemetry windows | Transformer telemetry training snapshot | Predictive maintenance | No | No retained use | DELETE |
| build_rul_dataset_snapshot | Observed failure lead times | RUL Transformer snapshot | Predictive maintenance | No | No retained use | DELETE |

Airflow is therefore **SPLIT**, not wholly kept or deleted. The two retained DAGs
support governed dataset/evaluation and knowledge-retention capabilities. The
telemetry and RUL DAGs are deleted with predictive maintenance.

## 7. OpenSearch, Neo4j and GraphRAG

### OpenSearch

HybridRetriever in knowledge/retrieval.py operates on the governed relational
knowledge/chunk store and can execute the current diagnosis retrieval path
without OpenSearch. DiagnosisRuntime imports HybridRetriever, not
SearchProfileService or OpenSearchStore.

OpenSearch is used by search_profiles as a governed projection/profile:
SearchProfileService uses OpenSearchStore and returns backend equal to
opensearch. Runtime creates it only when knowledge_search_profiles_enabled,
which defaults to false.

Concrete triage reuse path:

    Triage runbook documents
    → existing governed knowledge ingestion/release
    → SearchProfileService
    → OpenSearchStore sparse/vector profile
    → triage-specific retrieval adapter

It is document/runbook search, not an implemented log-search service. Logs
would still need a separate ingestion/query contract.

Final action: **OPTIONAL PROFILE**. It must remain disabled outside a
search-profile deployment and leave default Golden Path Compose/readiness
independent of OpenSearch.

### Neo4j / GraphRAG

GraphRAG has a governed knowledge projection and extraction workflow, with
Neo4jGraphStore created only when graph_rag_enabled is true. That flag defaults
to false. DiagnosisRuntime does not import GraphRAG and no primary/fallback
diagnosis retrieval path was found to call Neo4j.

Removing GraphRAG leaves HybridRetriever sufficient for the current Industrial
Diagnosis reference app.

Final action: **DELETE** GraphRAG and Neo4j from Phase 1 scope. The capability
does not justify its separate graph extraction, store, worker and operational
complexity for the retained path. It can be reconsidered only with a concrete
retrieval requirement, not as future optional complexity.

## 8. MLflow and training workers

### MLflow

MLflow is not interchangeable with the project Model Gateway:

- Model Gateway resolves governed serving routes and records inference.
- Release/deployment records govern rollout and serving.
- MLflow tracks experiment runs and metrics/artifacts, and training/promotion
  code verifies a finished MLflow run.
- api/routes/experiments.py exposes experiment tracking via ExperimentTracker
  and returns a dependency-unavailable response if MLflow is unavailable.
- runtime.py constructs MlflowRestTracker and injects it into the application.

What breaks if MLflow is removed: experiment API tracking, reproducible
training-sandbox reports, quantization/training CLI tracking and GPU promotion
finished-run evidence. Diagnosis inference itself does not require MLflow.

Final action: **KEEP** as the experiment-tracking side of a reusable model
lifecycle. It provides a clear Applied AI portfolio signal at moderate cost.

### Training split

| Training scope | Decision | Reason |
| --- | --- | --- |
| training/backend.py, runner.py, model contract, artifacts, checkpoints, distributed execution, generic dataset/reward contracts | KEEP / SPLIT | SFT, DPO, PPO, GRPO, multimodal training, evaluation and governed promotion support model lifecycle and future Agentic RL. |
| MLflow tracker and generic training CLI/quantization/promotion mechanics | KEEP | Direct model lifecycle/reproducibility value. |
| predictive_maintenance timeseries/RUL training datasets, models, transformer backends, inference/runtimes | DELETE | Tied to rotating-equipment telemetry and RUL product. |
| training files that import predictive training datasets | SPLIT | Retain generic SFT/DPO/PPO/GRPO paths; remove predictive imports and modes. |
| gpu_promotion_kserve_fsm.py | KEEP pending normal review | This FSM is model-promotion state machinery, not field-service FSM; no evidence it is after-sales dispatch. |

## 9. Second Reference Application stress test

| Kept or optional capability | Concrete Technical Incident Triage reuse path |
| --- | --- |
| Multimodal core after split | Screenshot → OCR/VLM generic findings → triage domain adapter. |
| Agent events/resume | Operator confirms an agent clarification → generic Agent event append → resume triage run. |
| Generic transcription after realtime split | Live operator audio → TranscriptionGateway → human confirmation → Agent input event. |
| Hybrid retrieval | Runbook/deployment documents → governed knowledge corpus → triage retrieval adapter with generic applicability metadata. |
| OpenSearch optional profile | Runbook corpus → SearchProfileService → OpenSearchStore → triage retrieval adapter; not log search without new work. |
| Model Gateway / release / eval / MLflow | Structured triage inference, context trace, experiment tracking and model promotion. |
| Generic training/RL | Triage prompt/action examples → SFT/DPO/PPO/GRPO or evaluation pipeline. |
| Observability / Temporal | Triage workflow trace, retry, model/tool event audit. |

No retained capability is justified solely by a vague future possibility.

## 10. Updated Phase 1 product boundary

    CORE CAPABILITIES
    ├── generic media storage and validation
    ├── generic perception primitives: OCR, VLM findings, ASR, video decomposition
    ├── Agent mechanics: bounded execution, events, checkpoints, resume
    ├── governed read-only tool governance and MCP/HTTP transport
    ├── knowledge ingestion, hybrid retrieval, ACL, release and retention
    ├── Model Gateway, serving release, inference audit and observability
    ├── evaluation substrate, generic training and MLflow experiment tracking
    ├── Temporal orchestration and tenant/security infrastructure
    └── optional OpenSearch document-search profile

    INDUSTRIAL DIAGNOSIS REFERENCE APP
    ├── Incident / Asset / Equipment context
    ├── Industrial Evidence review and EvidenceBundle
    ├── Industrial knowledge applicability/content
    ├── Diagnosis contracts, prompt, runtime and workflow
    ├── Diagnosis result, feedback and expert takeover
    └── read-only asset, warranty, parts availability, schedule and maintenance-history tools

    OPTIONAL CAPABILITIES
    ├── OpenSearch search profile, disabled by default
    └── generic live-transcription input after realtime session/work-order split

    DELETE
    ├── predictive maintenance, telemetry, anomaly and RUL products
    ├── telemetry/RUL data pipelines, runtimes, Airflow DAGs and model paths
    ├── work-order fulfillment, field/dispatch, parts mutation and customer service domains
    ├── supplier collaboration and supplier A2A
    ├── Kafka event worker, telemetry consumer and Debezium integration profile
    ├── GraphRAG and Neo4j
    ├── current WebRTC session/field realtime implementation after generic ASR split
    └── all associated frontend, API, persistence, config, worker, Docker, CI, dataset and documentation surfaces

## 11. Phase 1 boundary changes to the prior manifest

The following earlier UNKNOWNs are resolved:

| Earlier unknown | Resolution | Phase 1 consequence |
| --- | --- | --- |
| predictive maintenance / sensor / telemetry / RUL | DELETE | Not part of Diagnosis Agent surface; remove as separate industrial ML product. |
| realtime media | SPLIT | Retain generic reviewed transcription-to-Agent-event idea only; remove field/WebRTC implementation. |
| collaboration | SPLIT / DELETE | Keep diagnosis takeover and generic Agent resume; delete work-order expert and supplier flows. |
| supplier A2A | DELETE | Protocol exists but has no runtime path into Agent and is supplier-specific. |
| Airflow | SPLIT | Keep generic dataset and knowledge retention DAGs; delete telemetry/RUL DAGs. |
| Kafka / Debezium | DELETE | Used for work-order feedback and telemetry, not Golden Path. |
| OpenSearch | OPTIONAL PROFILE | Existing concrete document-search reuse; disabled by default. |
| Neo4j / GraphRAG | DELETE | Optional, not used by Diagnosis Runtime, high cost. |
| MLflow | KEEP | Required by experiment/training/promotion lifecycle, distinct from serving gateway. |
| training workers | SPLIT | Keep generic model/RL lifecycle; remove predictive/RUL paths. |

# Final Answer

NO

