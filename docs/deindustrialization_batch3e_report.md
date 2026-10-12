# Batch 3E — Graph / Field Realtime / Runtime Surface Cleanup

## Scope

Batch 3E 只做已确认的删除与收口，不进入 Batch 2B，不改变 Multimodal 的
`MultimodalProcessor → PerceptionResult → Industrial Recognition → EvidenceBundle`
contract，也不新增业务能力。

## GraphRAG / Neo4j

已从 active surface 移除：

- GraphRAG runtime construction、Temporal extraction workflow/activity、API route、依赖注入和 readiness/close path；
- Neo4j configuration、secret、Compose volume、OPA action、Docker lock dependency；
- GraphRAG ORM records、前端知识图谱页面、导航、API client surface 和 OpenAPI paths/schemas。

新增前向迁移 `alembic/versions/0092_remove_graphrag_neo4j.py`，按 child-first 顺序删除
graph tables，并移除 `knowledge_index_activations.revoked_graph_release_ids`。

保留：`HybridRetriever`、citation、ACL/tenant boundary，以及默认关闭的 OpenSearch
optional profile。`LangGraph` 作为通用 Agent 编排依赖保留，不是 GraphRAG。

## Field Realtime split

保留的 generic capability：

- bounded audio transcription；
- transcript persistence、idempotency 和 validation；
- human confirmation；
- `agent.user_input.confirmed` event append；
- Diagnosis-bound transcript confirmation and Agent resume path。

删除的 field-specific shell：

- WebRTC session/signaling/reconnect/heartbeat/consume/delete API；
- STUN/TURN、coturn/media-server、field session persistence、field audio panel；
- diagnosis TTS route/runtime gateway and field voice-guidance UI；
- industrial hotword/entity extraction behavior from the generic transcript path。

新增前向迁移 `alembic/versions/0093_remove_field_realtime_shell.py`，保留
`realtime_transcript_segments`，移除 session FK 和 `realtime_media_sessions`，并以
`diagnosis_run_id` 建立 generic transcript 到 Diagnosis 的关联。

审计发现 video decomposition 仍复用通用 VAD。为避免删除 shared mechanism 导致
Batch 2A regression，VAD 最小归位到 `src/industrial_ops_agent/multimodal/vad.py`；它不包含
WebRTC、现场会话、工业实体或售后语义。

## Runtime / API / frontend cleanup

- production runtime 不再构造 GraphRAG、Neo4j、WebRTC session、diagnosis TTS、portal 或 service-performance surface；
- portal/customer update API、service-entitlement API 和 service-performance API/前端入口已移除；历史 ORM/migration compatibility data 未在本批删除；
- Parts 的 read-only Diagnosis tool/API 保留，Parts mutation 不恢复；独立 Parts UI 已移除；
- supplier/A2A lock/runtime residue、旧 speech/realtime client paths、对应 OpenAPI surface 已清除；
- 当前 frontend brand/工作台文案改为 Multimodal Operations Agent / Reference Application 定位；
- OpenSearch 仍为 optional，`knowledge_search_profiles_enabled` 默认 `False`。

## Dependency / dead-reference audit

Active source、web、infra、Docker lock、Compose、OPA、OpenAPI 扫描结果：

- GraphRAG/Neo4j：无 active reference；
- WebRTC/session/STUN/TURN/coturn/media-server：无 active reference；
- portal/service-entitlement/service-performance/diagnosis speech：无 production route 或 frontend entry；
- 历史 Alembic migrations、历史 reports、兼容 ORM records 保留并归类为 historical/compatibility data；
- Grafana 的 `graphTooltip` 和通用 Agent graph-node event 不是 GraphRAG，保留。

## Verification evidence

通过：

- `deindustrialization_batch3e_surface_smoke.py`；
- `deindustrialization_batch3e_sqlite_migration_smoke.py`；
- `deindustrialization_batch1_golden_path_smoke.py`；
- Batch 1 boundary、Batch 1.5 review boundary；
- Batch 2 multimodal/retrieval/tools；
- Batch 2A recognition/manifest/provenance；
- Batch 2B generic applicability/retrieval parity；
- Batch 2C runtime isolation；
- Batch 3A、3B、3C、3D deletion smoke；
- Alembic head：`0093_remove_field_realtime_shell`；
- changed-file Ruff；
- `python -m compileall -q src scripts`；
- OpenAPI JSON parse and regenerated TypeScript schema。

Focused mypy 仍报告既有 SQLAlchemy typing baseline：
`src/industrial_ops_agent/incident_operations/service.py:824 — Result[Any] has no attribute rowcount`。
本批未修改该无关 baseline。

Full FastAPI import:

`NOT RUN — existing local PIL dependency unavailable. Non-blocking for Batch 3E structural verification.`

PostgreSQL rehearsal:

`NOT RUN — no disposable PostgreSQL environment available`

## Result

Batch 3E deletion goals: PASS
