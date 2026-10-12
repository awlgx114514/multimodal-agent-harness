# Deindustrialization Manifest — Phase 1

## Scope and evidence

This is execution-preparation analysis only. No code, schema, configuration,
prompt, migration, route, document, or runtime service has been changed or
deleted.

The target is a portfolio-grade Multimodal Operations Agent / Applied AI System,
not a general Agent Framework. Industrial Diagnosis remains the single Reference
Application, and Diagnosis Result is its final business output.

Evidence is static: imports, symbols, constructors, route/workflow registration,
ORM foreign keys, migrations, frontend paths, configuration and scripts.
Production traffic, data retention rules, external contracts, applied migration
state, and generated-client provenance are unavailable. Decisions needing that
evidence are UNKNOWN.

Allowed labels:

| Label | Meaning |
| --- | --- |
| KEEP | Retain without a deindustrialization change now. |
| MOVE | Retain as Industrial Diagnosis reference-app code, not reusable layer. |
| GENERALIZE | Retain mechanism but extract specific industrial contract/dependency. |
| DELETE | Deletion target after stated blockers are removed. |
| UNKNOWN | Static analysis cannot establish a safe action. |

## 1. Golden Path: the one preserved chain

    web incident pages
      → incident draft API/application
      → upload/media
      → recognition workflow/activity
      → human evidence confirmation / evidence bundle
      → start diagnosis
      → Temporal diagnosis workflow/activity
      → DiagnosisGraph / DiagnosisRuntime
      → retrieval + diagnosis read-only tools + Model Gateway
      → DiagnosisReport
      → diagnosis record + agent events/checkpoints + feedback/evaluation

| Stage | Real file / symbol | Action |
| --- | --- | --- |
| Frontend case entry/list/detail | web/app/incidents/page.tsx; new/page.tsx; [incidentId]/page.tsx | MOVE |
| Draft/evidence review | web/app/incidents/drafts/[draftId]/page.tsx; recognition/page.tsx; timeline/page.tsx | MOVE |
| Shared frontend API/navigation | web/lib/api/client.ts; web/components/AppShell.tsx | GENERALIZE — mixed Golden Path and after-sales links |
| Incident API | api/routes/incidents.py: create_draft, get_draft, update_draft, get_timeline | MOVE |
| Upload API | api/routes/uploads.py: upload_media, media_status | KEEP; GENERALIZE only if it remains Incident-only |
| Recognition API | api/routes/recognition.py: start_recognition, get_recognition_run, get_evidence, confirm_recognition | MOVE |
| Diagnosis API | api/routes/diagnoses.py: start_diagnosis, get_diagnosis, cancel_agent_run, resume_agent_run | MOVE |
| Agent trace API | api/routes/agent_events.py: stream_agent_events, stream_ag_ui_events | GENERALIZE; run_diagnosis_agent is MOVE |
| Incident application | application/incidents.py | MOVE |
| Diagnosis application | application/diagnoses.py: DiagnosisWorkflowInput and DiagnosisService | MOVE |
| Media store/validation | media/service.py; media/validation.py | KEEP / GENERALIZE; service imports industrial review-isolation |
| Multimodal | multimodal/processor.py; providers.py; video.py | GENERALIZE |
| Recognition worker | orchestration/activities.py: RecognitionActivity; workflows.py: RecognitionWorkflow | MOVE |
| Diagnosis worker | orchestration/workflows.py: DiagnosisActivity, DiagnosisWorkflow | MOVE |
| Worker assembly | orchestration/runner.py registration lists | GENERALIZE |
| Agent mechanics | agent/graph.py; checkpoints.py; events.py | GENERALIZE |
| Diagnosis runtime/contracts | agent/diagnosis_runtime.py; agent/contracts.py | MOVE |
| Retrieval | knowledge/retrieval.py: HybridRetriever; knowledge/models.py: RetrievalQuery | GENERALIZE |
| Model serving | model_gateway/service.py; context_manifest.py; openai.py | GENERALIZE; transport/audit is KEEP |
| Persistence | persistence/models.py: Incident, Asset, Evidence, Recognition, Diagnosis, AgentRun records | Split MOVE / GENERALIZE |
| Evaluation | evaluation/metrics.py; dataset.py; runner.py | GENERALIZE |
| Application composition | api/app.py:create_app; runtime.py:create_runtime_app | GENERALIZE |
| Settings/deployment | config.py:Settings; .env.example; Compose/Helm | GENERALIZE |

Golden Path stop condition: no candidate deletion may proceed until a local path
successfully proves draft → upload → recognition → human confirmation →
diagnosis → final report → events/checkpoints/citations. A candidate imported
by this path is not directly deletable.

## 2. Minimal Industrial Diagnosis Surface

| Entity / concept | Classification | Evidence |
| --- | --- | --- |
| Case / Incident | Required for Diagnosis | DiagnosisRun links to incident; evidence authorization and UI use it. MOVE. |
| Asset / Equipment context | Required for Diagnosis | Diagnosis state, VLM asset model, retrieval applicability and tools use it. MOVE. |
| Device family/model | Required for current Diagnosis, not core | Knowledge/VLM use it. MOVE as app metadata; GENERALIZE retrieval. |
| Evidence / recognition review | Required for Diagnosis | Confirmed EvidenceBundle is a diagnosis precondition. MOVE ownership; GENERALIZE primitives. |
| Diagnosis run/result | Required for Diagnosis | Temporal publishes final report. MOVE. |
| Industrial knowledge | Required for Diagnosis | Release-bound, device-filtered retrieval. MOVE content/policy; KEEP substrate. |
| Maintenance history | Required for Diagnosis | work_orders.history is in agent/contracts.py allowlist. Retain read-only fact boundary. |
| Sensor data | Mixed / UNKNOWN | Desired surface permits it, but current diagnosis tool list has no sensor tool; predictive code is not proven required. |
| Warranty | Required for current Diagnosis | warranty.get is allowed. Retain read-only fact. |
| Parts | Mixed | parts.availability is allowed; reservation, issue and consumption are fulfillment. Split. |
| Work order | Mixed | work_orders.history is allowed; creation, field execution, close/rework are post-diagnosis. Split. |
| Quotation | Post-Diagnosis Business Only | Not in diagnosis tool allowlist; used by repair path. |
| Entitlement | Post-Diagnosis Business Only | Repair/quotation eligibility, not diagnosis allowlist. |
| Procurement | Post-Diagnosis Business Only | Purchase and fulfillment path. |
| Dispatch / FSM | Post-Diagnosis Business Only | Work-order assignment and delivery. |
| Customer portal / notifications | Post-Diagnosis Business Only | Customer update and service communication. |
| Refund | Post-Diagnosis Business Only | Customer-service/work-order refund path. |
| Equipment control | Post-Diagnosis Business Only | T3 safety handoff is not a diagnosis-agent tool. |

## 3. Main file-level classification

| Path / Symbol | Action | Reason | Blocking dependency | Required preceding change |
| --- | --- | --- | --- | --- |
| agent/graph.py: DiagnosisGraph, DiagnosisGraphRuntime | GENERALIZE | Bounded graph imports diagnosis version/fallback and fixed action semantics. | agent/contracts.py | Parameterize metadata, terminal factory and action routing. |
| agent/diagnosis_runtime.py: DiagnosisRuntime | MOVE | Incident/asset/evidence/retrieval/tool/memory/report composition. | reusable modules | Establish reference-app boundary. |
| agent/contracts.py: DIAGNOSIS constants and schemas | MOVE | Prompt, allowed tools, action/final contract. | graph.py, runtime | Remove graph reverse import. |
| agent/checkpoints.py; agent/events.py | GENERALIZE | Mechanics are generic by run and sequence. | AgentRunRecord.diagnosis_run_id | Generalize run ownership. |
| agent/ag_ui.py | GENERALIZE | Event projection recognizes diagnosis naming. | event vocabulary | Domain-neutral projection vocabulary. |
| multimodal/models.py primitives | KEEP | BoundingBox, OCR/VLM/ASR/video primitives are perception data. | None | None. |
| multimodal/models.py: EvidenceBundle | MOVE / GENERALIZE | Asset/draft evidence ownership is industrial. | processor/persistence | Separate Industrial Evidence adapter. |
| multimodal/processor.py: ProcessingRequest and MultimodalProcessor | GENERALIZE | Requires asset, draft and model; returns EvidenceBundle. | recognition flow | Split generic findings processor from adapter. |
| multimodal/providers.py VLM providers | GENERALIZE | Public asset_model and industrial-asset prompt. | processor/runtime | Prompt/context supplied by app adapter. |
| multimodal/video.py | KEEP | Decomposer/ASR/temporal mechanics are not asset-owned. | None | None. |
| media/validation.py and object-store primitives | KEEP | Generic media validation/storage. | None | None. |
| media/service.py | GENERALIZE | Imports maintenance_planning review-isolation helper. | helper import | Move generic disclosure transaction helper out. |
| knowledge/models.py RetrievalQuery/RetrievedEvidence | GENERALIZE | Mandatory device_model and device-centric citation. | retriever and diagnosis runtime | Small metadata/applicability filter. |
| knowledge/retrieval.py HybridRetriever | GENERALIZE | SQL prefilter, trace and fusion embed device family/model. | knowledge schema | Generic filters in sparse and vector paths. |
| knowledge ingestion/parser/embedding/rerank/release | KEEP / GENERALIZE | Document/ACL/release mechanics reusable; metadata handling needs extraction. | knowledge records | Generalize applicability only. |
| graph_rag and search_profiles | KEEP | Document-search infrastructure, no fulfillment evidence. | optional deployment | None. |
| tools/registry.py ToolDefinition/ToolRegistry | KEEP | Generic version/schema/risk governance. | None | Remove equipment wildcard from generic path. |
| tools/registry.py default_tool_registry | GENERALIZE / SPLIT | Mixes diagnosis reads and fulfillment mutations. | runner/gateway | Separate diagnosis catalog. |
| tools/gateway.py generic invoke path | KEEP / GENERALIZE | Schema/auth/rate/approval/audit is reusable. | required PartsAdapter and industrial helpers | Optional/injected adapters; isolate T3 policy. |
| tools/gateway.py repair/quote/procurement/refund/FSM methods | DELETE after decoupling | Pure post-diagnosis operations. | same file, ORM, adapters | Split gateway first. |
| tools/mcp.py | KEEP | Generic authenticated read-only transport. | registry schema | None. |
| tools/authority.py and tools/contracts.py | GENERALIZE | Attested facts embed industrial tool assumptions. | gateway/tools | Split fact attestations. |
| tools/synthetic_parts.py | GENERALIZE BEFORE DELETE | Factory/evaluation use it; parts availability remains diagnosis-required. | factory/evaluation/gateway | Retain read-only substitute or remove deps. |
| tools procurement/quotations/refunds/fsm_assignments/customer_notifications | DELETE after decoupling | Fulfillment delivery adapters. | factory, sandbox, dev_lite, gateway | Remove constructor/factory paths. |
| application incidents/assets/diagnoses/expert_diagnoses/diagnosis_feedback/agent_runs | MOVE | Industrial Diagnosis reference application. | routes/workflows/persistence | Clean reusable imports first. |
| API incidents/assets/uploads/recognition/diagnoses/diagnosis_feedback/agent_events | MOVE / GENERALIZE | Reference endpoints; upload/event mechanisms are reusable. | app/frontend | Extract only if independently exposed. |
| API parts/procurement/refunds/fsm/portal/customer_notifications/entitlements/equipment control | DELETE after decoupling | Post-diagnosis routes. | app/frontend/services | Remove backend dependency first. |
| workorders directory | GENERALIZE / SPLIT | History required; lifecycle/field/offline is fulfillment. | diagnosis app, realtime/speech, gateway, many FKs | Extract history query. |
| parts/service.py | GENERALIZE / SPLIT | Availability required; mutation flows are not. | route/gateway/ORM | Retain read-only fact. |
| service_entitlements, customer_portal, cost_operations, service_performance | DELETE after decoupling | No diagnosis allowlist/Golden Path use found. | routes; review-isolation import | Extract helper first. |
| maintenance_planning | GENERALIZE / SPLIT | review-isolation helper is imported by core media/memory/diagnosis; planning business is outside Golden Path. | many imports/runner/workflows | Extract helper then delete planning behavior. |
| predictive_maintenance | UNKNOWN | Industrial and outside Golden Path, but could become sensor-read-only capability. | training/release/routes/datasets/Docker/Airflow | Product decision plus runtime evidence. |
| collaboration / supplier A2A | UNKNOWN | May be diagnosis review, but supplier semantics are industrial. | API/config/Compose supplier agent | Decide whether expert collaboration stays. |
| api/app.py:create_app, runtime.py, orchestration/runner.py | GENERALIZE | Root composition registers mixed domains. | all routes/services/workflows | Isolate modules before registrations. |
| persistence/database.py and tenant.py | KEEP | Infrastructure-only. | None | None. |
| persistence/models.py AgentRunRecord | GENERALIZE | Required diagnosis foreign key reverses direction. | events/checkpoints | Neutral owner or app association. |
| persistence Incident/Asset/Evidence/Recognition/Diagnosis records | MOVE | Industrial reference persistence. | Golden Path | Retain until move. |
| persistence fulfillment records | DELETE after decoupling | Detailed below. | FK graph | Child-first forward migration. |
| evaluation/metrics.py | KEEP | Generic metrics. | None | None. |
| evaluation/dataset.py, runner.py, runtime_backend.py | GENERALIZE | Mix generic evaluation with industrial/predictive contracts and synthetic parts. | training/predictive/tool stubs | Move industrial suites. |
| workflows Diagnosis Activity/Workflow | MOVE | Reference-app execution. | runner/Temporal | None prior to move. |
| workflows MaintenancePlanning Activity/Workflow | DELETE after helper extraction | Not Golden Path. | runner/routes/planning | Extract helper. |
| web/app/incidents | MOVE | Reference UI. | APIs | None prior to move. |
| web/app parts/dispatch/entitlements/field/portal/work-orders | DELETE after backend split | Post-sales UI; work-order history must survive. | AppShell/client/panels | Remove read dependencies first. |
| web/app maintenance-planning | DELETE after helper extraction | Not Golden Path. | planning backend | Extract helper. |
| web/app predictive-maintenance | UNKNOWN | Depends on product decision. | predictive backend | Decide scope. |
| AppShell/API client/generated types | GENERALIZE | Mixed navigation and operations. | route set | Regenerate after route removal. |
| Compose/Helm fulfillment settings | DELETE after code deletion | Providers and secrets are fulfillment-only. | runtime factory | Remove all env reads. |
| Airflow predictive DAGs | UNKNOWN | Product decision pending. | predictive package/datasets | Separate review. |
| Alembic fulfillment revisions | UNKNOWN / retain history | Deleting applied migration files is unsafe. | migration chain | New forward migration only. |

## 4. Tool cleanup manifest

The current Diagnosis Agent allowlist in agent/contracts.py is:

| Tool | Action |
| --- | --- |
| asset.get | KEEP FOR DIAGNOSIS; MOVE definition/adapter to reference app. |
| warranty.get | KEEP FOR DIAGNOSIS; read-only fact. |
| parts.availability | KEEP FOR DIAGNOSIS; split from reservation/issue/consumption. |
| schedule.availability | KEEP FOR DIAGNOSIS; read-only fact. |
| work_orders.history | KEEP FOR DIAGNOSIS; split from fulfillment. |
| work_order draft/read/create/assign/close | DELETE after decoupling; not agent-allowed diagnosis tools. |
| parts reserve/issue/consume/return | DELETE after decoupling. |
| refund.request | DELETE after decoupling. |
| equipment.control wildcard | DELETE after decoupling. |
| quotation/procurement/notification/FSM paths | DELETE after decoupling. |

ToolGateway is GENERALIZE BEFORE DELETE: its constructor requires PartsAdapter,
and its implementation co-locates generic invocation with repair, entitlement,
quotation, procurement, refund, FSM and equipment-control policy.

## 5. Agent, multimodal, RAG and persistence isolation

### Agent layer

| Item | Action | Reverse dependency preventing isolated import |
| --- | --- | --- |
| agent/graph.py | GENERALIZE | diagnosis version and budget report import. |
| agent/checkpoints.py | GENERALIZE | AgentRunRecord requires diagnosis run owner. |
| agent/events.py | GENERALIZE | same AgentRun relation; diagnosis event projection. |
| model_gateway/context_manifest.py | KEEP | no Industrial Diagnosis ORM import found. |
| diagnosis_runtime.py | MOVE | DiagnosisWorkflowInput, incident/asset/evidence, industrial retrieval/tools/memory. |
| agent/contracts.py | MOVE | diagnosis prompt, actions, report and allowlist. |
| memory_governance/service.py select_for_diagnosis | GENERALIZE | reads IncidentRecord and asset-scoped memory. |

If the reference app were removed today, reusable Agent code could not
independently import because graph.py imports diagnosis contracts, AgentRun
persistence requires DiagnosisRun, model routing binds diagnosis releases, and
memory/retrieval/tools contain incident/device/parts assumptions.

### Multimodal boundary

| Category | Paths / symbols | Action |
| --- | --- | --- |
| Generic perception | BoundingBox, OcrBlock, VisualFinding, ASR/video structures, video.py, media validation | KEEP |
| Industrial interpretation | ProcessingRequest asset/draft/model, EvidenceBundle, industrial entity rules, VLM prompt | GENERALIZE / MOVE |
| Recognition workflow | recognition routes/application/activity and evidence persistence | MOVE |

Desired boundary:

    Generic Media / OCR / VLM / ASR → Generic Findings
                                         ↓
                       Industrial Diagnosis Adapter → Industrial Evidence

### Knowledge boundary

| Area | Action | Specific pollution |
| --- | --- | --- |
| documents/chunks/embedding/reranking/ACL/release | KEEP | Generic infrastructure. |
| knowledge/models.py | GENERALIZE | device_model mandatory. |
| knowledge/retrieval.py | GENERALIZE | device filter in SQL, trace and fusion. |
| knowledge persistence applicability columns | GENERALIZE | device_families/device_models are universal fields. |
| industrial document metadata/corpus | MOVE | Reference-app policy. |

### Persistence sets

| Set | Records |
| --- | --- |
| Reusable Persistence | tenant transaction, inference audit, tool audit, idempotency, event/checkpoint mechanics, media storage mechanics. |
| Reference App Persistence | Asset, Incident, IncidentDraft/timeline, EvidenceBundle, RecognitionRun, DiagnosisRun, diagnosis feedback, industrial knowledge policy. |
| Delete Candidates | equipment-control handoff; customer updates/notifications; part reservation/issue/material movement; purchase/fulfillment; quotation; refund; FSM; work-order lifecycle/field/offline/rework/expert collaboration. |

AgentRunRecord.diagnosis_run_id is a non-null foreign key to diagnosis_runs.
It blocks standalone reusable Agent persistence.

## 6. DELETE impact matrix

Every candidate below is Requires decoupling first. Static direct-import lists
cover repository source/scripts found by search; runtime plug-ins/external
consumers remain UNKNOWN.

| Candidate domain | Direct import / registration evidence | Indirect/runtime impact | Database impact | API/frontend impact | Infrastructure/evaluation impact | Decision |
| --- | --- | --- | --- | --- | --- | --- |
| Customer portal | portal route imports customer_portal.service; app registers portal/staff routers. | Customer updates feed notification/refund. | customer_service_updates; referenced by notification/refund. | web/app/portal; AppShell/client. | Docs/external consumers UNKNOWN. | Requires decoupling first. |
| Customer notification | app registers router; tools/customer_notifications; gateway methods. | Portal/customer-update flow, audit/approval. | customer_notification_deliveries and receipts; receipt FK to delivery. | notification/approval/client surfaces. | dev_lite, sandbox/factory, notification env. | Requires decoupling first. |
| Refund | app route, tools factory, sandbox, dev_lite import adapter. | Gateway refund methods; work-order/customer-update links. | refund_requests and receipts; receipt FK and work-order/customer FK. | refunds/approvals/client. | refund mode/provider secret. | Requires decoupling first. |
| Procurement | app route, tools factory, sandbox, dev_lite. | Gateway and parts/quotation flows. | purchase_requests, receipts, fulfillments and receipts; quotation links. | procurement panels/client. | provider URL/token, sandbox. | Requires decoupling first. |
| Service quotation | tools gateway plus factory/sandbox/dev adapter import. | Repair-work-order and entitlement eligibility. | service_quotations and decisions; work-order/purchase links. | quotation panels/approvals/client. | catalog URL/token/sandbox. | Requires decoupling first. |
| FSM / dispatch | app route and FSM adapter factory/sandbox/dev. | Gateway, work-order assignment, field/offline records. | fsm_assignment_deliveries and receipts; assignment FK. | web/app/dispatch, field/work-order UI. | FSM webhook/mode/provider. | Requires decoupling first. |
| Equipment control | app handoff route; registry wildcard; gateway handoff. | Gateway T3 policy/audit. | equipment_control_handoffs; incident/asset/tool-call relations. | handoff routes/client. | policy/config/acceptance must be searched again. | Requires decoupling first. |
| Work-order fulfillment | app route; incidents, speech, realtime and gateway import workorders. | Voice/field/re-diagnosis/history tool. | work_orders plus events/control/field/assignment/offline/edge/completion/verification/rework/expert children; many FKs. | work-orders, field, dispatch, PWA, AppShell/client. | workers/scripts/migrations. | Requires decoupling first; extract history first. |
| Parts fulfillment | app route/service; synthetic adapter used by factory/evaluation. | Gateway mandatory PartsAdapter; diagnosis keeps availability. | reservation, issue, material movement; work-order FKs. | parts and field UI. | enterprise tool/MCP scopes; synthetic evaluator. | Requires decoupling first. |
| Entitlement | app route/service; lazy ToolGateway imports. | Repair/quotation eligibility only. | No dedicated table proven statically; may be remote facts. | entitlements page/client. | external service settings need inventory. | Requires decoupling first. |
| Cost/service performance | app routes/services. | review-isolation helper import; no Golden Path tool use. | service_performance_baselines observed; cost table needs migration review. | operations pages/client. | dashboards/docs UNKNOWN. | Requires decoupling first. |
| Maintenance planning | routes/app/dependencies/runner/workflows; review-isolation used by core media/memory/diagnosis. | Shared disclosure transaction helper. | planning migrations 0075/0080/0081/0086; full FK set needs review. | maintenance-planning page/client. | runner/workflow registrations. | Requires decoupling first; not direct DELETE. |

Database rule: delete children before parents only through a new forward
migration after retention/backfill decisions. Do not remove historical Alembic
revision files from an applied migration chain. Existing evidence already shows
many work-order child FKs, receipt-to-parent FKs, quotation links to purchase
and work order, and refund links to work order/customer update.

## 7. Temporal, frontend, infrastructure and CI

| Area | Action | Evidence / condition |
| --- | --- | --- |
| Temporal client/worker/retry conventions | KEEP | Infrastructure. |
| Recognition workflow/activity | MOVE | Reference-app adapter. |
| Diagnosis workflow/activity | MOVE | Reference-app execution. |
| MaintenancePlanning workflow/activity | DELETE after helper extraction | runner registers it conditionally; outside Golden Path. |
| runner task queue/registration | GENERALIZE | default registry/ToolGateway and mixed workflows. |
| web/app/incidents | MOVE | Reference UI. |
| web/app/ai knowledge/memories/prompts/releases/experiments/datasets | KEEP / MOVE | Portfolio value; not an automatic deletion. |
| web/app parts/dispatch/entitlements/field/portal/work-orders | DELETE after backend split | Preserve work-order history only. |
| web/app maintenance-planning | DELETE after helper extraction | Not Golden Path. |
| web/app predictive-maintenance | UNKNOWN | Product decision. |
| Compose core: PostgreSQL, Redis, MinIO, ClamAV, OPA, Temporal, API/worker/web, models/gateway | KEEP | Golden Path dependencies. |
| Compose fulfillment variables/services | DELETE after code removal | notification/procurement/refund/FSM/quotation/sandbox settings. |
| OpenSearch, Neo4j, MLflow, training workers, Kafka/Debezium, realtime | UNKNOWN | Optional feature dependency; prove use before deletion. |
| Airflow telemetry/RUL DAGs and RUL Dockerfiles | UNKNOWN | Predictive scope decision. |
| Generated frontend client and OpenAPI | GENERALIZE | Regenerate after routes change. |
| scripts dev_lite and sandbox acceptance adapters | DELETE after decoupling | Instantiate fulfillment adapters. |
| CI/docs/datasets/acceptance | GENERALIZE / DELETE | Remove only candidate-specific paths after final route/runtime list. |

## 8. Desired dependency direction and acceptance criteria

Target:

    Industrial Diagnosis Reference App → Reusable Capability Layer

Forbidden:

    Reusable Capability Layer → Industrial Diagnosis

Current violations:

1. agent/graph.py imports diagnosis contracts/version/fallback.
2. AgentRunRecord requires diagnosis_run_id.
3. multimodal processor and VLM contracts require asset/draft/asset_model.
4. retrieval contracts, SQL and persistence require device applicability.
5. memory selector reads Incident and asset.
6. ToolGateway requires PartsAdapter and embeds equipment/repair policy.
7. Model Gateway fixes industrial diagnosis aliases/request classes/manifest/trace.
8. media service and other core-ish services import maintenance review helper.
9. app/runtime/runner compose all domains together.

Mechanical acceptance criteria:

1. Removing reference_apps/industrial_diagnosis in a verification branch leaves
   multimodal core, Agent mechanics, tool governance, model transport/audit,
   knowledge, evaluation and orchestration substrate importable/buildable.
2. Reusable modules import none of Incident, Asset, DiagnosisRun, WorkOrder,
   Parts, Quotation, Procurement or industrial contracts.
3. AgentRun/Event/Checkpoint persistence has no mandatory diagnosis ownership.
4. Generic multimodal requests/findings require no asset_model, asset_id,
   draft_id or Industrial EvidenceBundle.
5. Retrieval has a small generic metadata/applicability filter and no mandatory
   device_model field.
6. ToolGateway constructs and runs a registered read-only tool without
   PartsAdapter, work-order, equipment-control or fulfillment adapters.
7. Diagnosis Result is the Industrial Diagnosis terminal business transition.
8. Main runtime registers no fulfillment API, workflow, worker or adapter.
9. Main navigation/client has no after-sales management functions.
10. New forward migrations preserve FKs and historic migration chain.
11. Golden Path smoke test and focused import/build checks pass after every batch.

## 9. Delete order

| Batch | Scope | Stop condition | Independent verification |
| --- | --- | --- | --- |
| 1 | Freeze Golden Path regression, route list, tables/FKs and worker registrations. | Any core dependency is unaccounted for. | Golden Path smoke and route/import/worker inventory. |
| 2 | Extract shared review/disclosure helper, AgentRun ownership, graph contract binding, ToolGateway construction. | Reusable layer still imports industrial entity/contract. | Import-boundary check and migration test. |
| 3 | Split diagnosis required read-only tools; separate Industrial Evidence and retrieval applicability. | Tool/retrieval/citation behavior changes. | Diagnosis tool/retrieval contract and Golden Path smoke. |
| 4 | Delete fulfillment tool paths/adapters: quotations, procurement, refunds, notifications, FSM, equipment control and mutable parts/work orders. | Gateway/factory/runtime still requires an adapter. | Registry diff, gateway construction, route/config scan. |
| 5 | Delete fulfillment API/services/UI: portal, entitlement, parts fulfillment, work orders/field/dispatch. | Maintenance-history read or Golden Path UI breaks. | OpenAPI regeneration, frontend build, Golden Path UI. |
| 6 | Forward-migrate persistence child-first. | FK, retention or external consumer unresolved. | Disposable DB upgrade and FK inventory. |
| 7 | Delete maintenance-planning workflows/routes/UI after helper extraction. | Core import points to planning package. | Worker registration/import check and smoke. |
| 8 | Clean config, Compose, Helm, secrets, sandbox, scripts, CI, sample data and docs. | Retained runtime still references removed setting. | Config lint, build and repository reference scan. |
| 9 | Decide predictive, Airflow, realtime and supplier collaboration separately. | Product decision or deployment evidence missing. | Separate scope review. |

# Executive Decision

1. 第一阶段可以直接删除哪些工业业务域？没有带持久化或运行时注册的域能在没有前置解耦时安全直接删除。客户门户、通知、退款、采购、报价、FSM/派工、设备控制、工单履约和零件履约是明确 DELETE 目标；独立页面/路由最接近删除，但仍先要移除 API、客户端和配置引用。
2. 哪些工业代码必须继续保留作为 Industrial Diagnosis reference application？Incident/Case、Asset/Equipment context、Recognition/Evidence review、EvidenceBundle、DiagnosisRun/Result、工业知识、诊断提示/契约、Temporal Diagnosis workflow，以及 asset、warranty、parts availability、schedule availability、work-order history 五个只读工具。
3. 哪些 reusable modules 在删除前必须先做 boundary extraction？Agent graph/checkpoint/event ownership、ToolGateway/registry/authority、多模态 processor/VLM contract/EvidenceBundle、retrieval filter/persistence、memory selector、Model Gateway release policy、maintenance review helper，以及根运行时组装。
4. 第一阶段预计属于：Large restructuring。删除面跨 ORM FK、运行时构造器、API、Temporal、前端、配置、脚本和迁移，但能按小批次实施，不需要重写为通用 Agent Framework。
5. 是否存在会迫使项目大规模重写的依赖？没有此类代码证据。核心风险是共享模块的反向工业依赖，可经小范围 extraction/split 解除。生产数据保留、外部接口和预测性维护范围仍是 UNKNOWN，可能增加工作量但不必然要求重写。

# Recommended Execution Order

1. 冻结 Golden Path 回归验证和 route/FK/worker 清单；停止条件是任一主链环节没有证据。
2. 解耦 AgentRun ownership、Agent graph diagnosis import、ToolGateway PartsAdapter 和 maintenance review helper；停止条件是 reusable 层仍反向 import 工业实体。
3. 抽出诊断只读工具与工业 Evidence/knowledge adapter；停止条件是工具、检索或引用结果改变。
4. 删除履约工具与外部适配器；停止条件是 ToolGateway、factory 或 runtime 仍要求它们。
5. 删除履约 API、服务和前端；停止条件是 history read-only 工具或 Golden Path 前端破坏。
6. 采用前向迁移处理履约持久化；停止条件是 FK、保留策略或外部消费者无法证明安全。
7. 删除 maintenance-planning 业务 workflow/routes/UI；停止条件是核心模块仍依赖其 helper。
8. 清理 Compose、Helm、env/secrets、sandbox、脚本、CI、数据和文档；停止条件是 retained runtime 仍有引用。
9. 单独决定 predictive maintenance、Airflow、realtime media 和 supplier collaboration；停止条件是缺少产品选择或部署证据。

