# Multimodal Agent Platform — Project Readiness Audit

审计日期：2026-09-20  
结论等级：**C — Not ready as a primary application project today**

本报告评估的是实习求职中的可解释、可展示、可复现程度，不是系统架构规模或企业功能数量。代码和当前 Smoke 是事实来源；Batch 报告只在源码/Smoke 能对应时采纳。

## Executive judgment

仓库具备很强的系统库存：FastAPI API、Next.js web、SQLite-capable persistence、Alembic、Agent graph/checkpoint/event、knowledge retrieval、evidence/provenance/citation、multimodal processor/provider、tool gateway 和多批 deindustrialization smoke。Batch 1 Golden Path、Batch 2 multimodal/retrieval/provenance、Batch 3C parts-read smoke 本轮均通过。

但当前可证明的是**合成/结构化 vertical slice**，不是今天可稳定演示的真实模型 + API + 前端多模态产品：本地 `.venv` 运行时缺少 `PIL`，FastAPI 生产 import 未通过；README 描述的主链仍是工业设备报障/诊断/售后平台，而不是已经收敛的通用非工业 AI 产品；真实模型服务、Temporal、Postgres/MinIO/Redis、认证和前端联调本轮未启动。因此架构很多不等于 Golden Path 已对求职者开放。

## Evidence and current status

| Dimension | Status | Evidence-backed assessment |
|---|---|---|
| Golden Path | **合成路径通过，真实产品路径未证实** | `scripts/deindustrialization_batch1_golden_path_smoke.py` 本轮输出 `DEINDUSTRIALIZATION_BATCH1_GOLDEN_PATH_PASS`，覆盖合成 runtime、SQLite in-memory persistence、readonly tool、event/checkpoint 和 citation report；这不是真实模型/API/frontend smoke。 |
| Positioning | **当前叙事过宽且仍工业化** | README 一句话是企业级多模态工业设备运维与售后 Agent；README 同时列出诊断、知识、GraphRAG、工单、审批、训练、部署、预测维护和运维。对简历需要收敛为一个“证据驱动的多模态诊断 Agent vertical slice”，不能把全仓能力都当成已交付产品。 |
| Technical depth | **强，但过宽** | multimodal evidence contracts、OCR/VLM candidates、retrieval/evidence provenance、authorized citation、readonly ToolGateway、Agent checkpoints/events、SQLite migrations、web/API boundaries。深度足够，风险是面试无法在 20 分钟内讲清主链。 |
| Reality | **合成/代码真实；外部运行未验证** | 多模态 processor/provider 与模型 gateway 代码存在；当前 smoke 使用 synthetic adapter/runtime。未验证真实 VLM/LLM inference、媒体上传到页面、Temporal worker、真实 database/object store 的整链。 |
| Validation | **定向结构/服务 smoke 强；integration 未完成** | 本轮 5 个定向 smoke 全部 PASS。Batch 3C 报告还记录 compileall/ruff 等历史门禁，但同时明确 Full FastAPI import 未运行/受 `PIL` 缺失影响、web typecheck 未运行、PostgreSQL rehearsal 未运行。 |
| Demo readiness | **今天不能宣称 3–5 分钟 coherent product demo** | 可运行的最短路径是 synthetic Batch 1 script；它没有浏览器、真实媒体、真实模型或可见 citations UI。README 的 `/incidents/new` → upload → recognition review → diagnosis 页面链路需要完整依赖、身份和服务配置，本轮未复现。 |
| Interview depth | **高，但需砍范围** | 最适合深挖：① candidate evidence 与 authorized evidence 的边界；② citation/provenance/checksum 链；③ Agent graph budget/checkpoint/event stream；④ readonly tool governance 和工业 mutation 删除；⑤ SQLite/Alembic migration 与运行依赖隔离。 |

## Requested multimodal-platform checks

### Batch 1–3C architecture

- Batch 2 smoke confirms generic `PerceptionResult`/processor boundary，不再由 multimodal models 持有 `EvidenceBundle` 或强制 `asset_model`。
- Batch 2 retrieval smoke confirms `ApplicabilityFilter` 和 domain-neutral retrieval boundary。
- Batch 2A2 smoke confirms persisted recognition evidence can become Agent evidence with citation/provenance and rejected recognition results are not authorized.
- Batch 3C report and smoke confirm Parts active reserve/issue/consume/return mutation surface was removed from the active registry; availability remains readonly and historical records remain for accounting.
- These are boundary proofs, not proof that a real user can complete the whole web journey.

### Multimodal/perception → evidence → Agent

Code evidence shows media validation, OCR/VLM provider paths, `PerceptionResult`/visual findings, evidence context, retrieval, provenance and `_report_from_model` citation conversion. Batch 2A2 smoke verifies the citation bridge. Real VLM calls and real media bytes were not run in this audit; current environment missing `PIL` blocks the normal import path.

### Diagnosis tools / Agent consumption

The formal diagnosis runtime loads evidence, uses `HybridRetriever`, `ToolGateway` and a model gateway, and emits structured diagnosis events/citations. Batch 1 synthetic graph verifies `prepare → retrieve → decide → tool → decide → finish` and a cited report. The smoke's model decision is a stub, so it proves orchestration contract, not model quality or real tool selection.

### API/backend/frontend Golden Path

README maps the intended path to `web/lib/api/client.ts:startDiagnosis` → Next proxy → `api/routes/diagnoses.py` → `DiagnosisService` → Temporal `DiagnosisWorkflow`/`DiagnosisActivity` → model gateway → event/checkpoint/report UI. `api/app.py` exposes a very broad service graph. This is a credible architecture, but this audit did not start the full stack; `PIL` is missing and the required external services/auth/model runtime were not available. Therefore API/backend/frontend end-to-end status is **unverified**.

### SQLite/Alembic

SQLite in-memory schema creation is exercised by Batch 1 smoke. Batch 3C explicitly says no new schema migration was needed and retains head `0090_remove_workorder_field_fulfillment`; PostgreSQL rehearsal was not run. Alembic history contains substantial prior enterprise migrations, so “SQLite-capable” is verified for the smoke path, not production parity.

### Removed vs still active industrial workflows

Removed/contractually deactivated in the current batch evidence: active Parts reserve/issue/consume/return mutations and related mutation UI/routes; Batch 3C keeps readonly availability and historical accounting. Still active in source/README: industrial incidents, assets, warranty, work orders, knowledge, diagnosis, approvals/portal, maintenance planning, predictive maintenance, GraphRAG/search, enterprise tools, model release/training/deployment and operations pages. The project has not become a generic non-industrial AI product.

### Future Agentic RL

There is natural room for future Agentic RL through the existing experiment/training/evaluation/release surfaces and explicit Agent trajectories/evidence. That is only architectural room. RL is **not current capability** and must not appear as a resume claim or be used to inflate readiness.

## Completion state

### Implemented and verified

- Synthetic diagnosis graph with event/checkpoint/persistence behavior.
- Domain-neutral multimodal contracts and processor/provider boundaries.
- Retrieval boundary, evidence context, provenance/citation conversion.
- Readonly diagnosis tool registry/gateway boundary and Batch 3C Parts mutation removal.
- Alembic/SQLite-compatible persistence path in targeted smoke.
- Frontend/API source surfaces and deployment definitions exist.

### Implemented but unverified in a real product run

- Real image/media upload → OCR/VLM → review → evidence → model diagnosis → frontend result.
- Real LLM/VLM calls through model gateway and model-serving services.
- Full API + Temporal + database/object-store + auth + web integration.
- Real citation rendering and user-visible evidence inspection.
- PostgreSQL migration parity and web typecheck in the current environment.

### Planned, future, or not a current capability

- Agentic RL improvement or measurable RL gain.
- A generic non-industrial product abstraction.
- Full enterprise workflows as a single demonstrated demo; their source presence is not proof of runnability.

## Demo path today

The exact reproducible path is a developer-facing synthetic smoke:

```text
python scripts/deindustrialization_batch1_golden_path_smoke.py
→ synthetic graph: prepare → retrieve → decide → tool → decide → finish
→ SQLite in-memory events/checkpoint
→ readonly parts.availability tool
→ cited diagnosis report
```

This is useful interview evidence for orchestration and governance, but it is not a 3–5 minute user-facing multimodal product demo. Do not demonstrate it as a real VLM diagnosis.

## Truthful resume material if kept secondary

- Built a multimodal evidence pipeline that separates perception candidates from authorized Agent evidence and preserves citation/provenance metadata into structured diagnosis reports.
- Implemented a bounded diagnosis orchestration path with retrieval, readonly enterprise tools, event/checkpoint persistence and structured report citations; verified with a synthetic SQLite Golden Path.
- Designed deindustrialized boundaries that remove active Parts mutation tools while retaining readonly availability facts and historical accounting reads.
- Added domain-neutral multimodal contracts and retrieval/evidence smoke tests; real model-serving and full-stack integration remain environment-dependent.

## Minimal 7-day gap closure if this project must become presentable

Do not add more domains, agents, RAG variants, MCP or RL. Instead:

1. Pick one generic scenario and one media type; remove industrial nouns from the demo surface only, without redesigning the repository.
2. Make the smallest local fixture path: media input → perception result → evidence/provenance → one retrieval/tool call → Agent report with citation.
3. Provide a dependency-light local runner that does not require Postgres/Temporal/MinIO/auth; clearly label model stub versus real model.
4. If real model access is available, run one real image/text inference and record latency, model id, input hash, output and citation validity; otherwise keep the stub honest.
5. Add one negative case: untrusted visual instruction, rejected recognition result, or invalid citation must not enter final diagnosis.
6. Add a short screen/demo script and one architecture diagram focused on this slice.
7. Only then decide whether it can be a secondary resume project; do not claim the full enterprise surface.

**Milestone definition:** a clean local command or screen-recordable path accepts a real or explicitly labeled fixture media input, produces a perception result, persists/threads evidence with provenance, lets the Agent consume that evidence, emits a cited structured report, and demonstrates one rejection case. Without this, keep it as an architecture/research project rather than a primary application project.

