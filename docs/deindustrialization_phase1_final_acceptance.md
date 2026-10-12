# Phase 1 — Deindustrialization Final Acceptance

## Verdict

```text
Phase 1 deindustrialization:
PASS
```

本文第 1–14 节保留 Closure Batch 前的 audit snapshot。第 15 节是本次
Closure Batch 的重新验证结果，并取代其中所有旧的 FAIL 结论。

失败不是由历史 migration、历史报告、兼容性 ORM 记录或本地第三方依赖单独造成，而是由以下当前可执行/可消费表面造成：

1. `infra/opa/policy.rego` 仍授予已删除的 `work_order.execute`、`predictive_outcome.record`、`alert_candidate.*` 和 `agent_collaboration.*` 动作；该文件由 `compose.lite.yaml` 挂载到运行中的 OPA。
2. `src/industrial_ops_agent/auth/policy.py` 仍声明并绑定 `work_order.execute` 及 `agent_collaboration.*` 授权动作。
3. `contracts/openapi.json` 和 `web/generated/api/schema.d.ts` 仍暴露：
   - `/api/v1/incidents/{incident_id}/repair-work-order-options`
   - `/api/v1/incidents/{incident_id}/repair-work-order-proposals`
4. `src/industrial_ops_agent/model_gateway/governance.py`、`orchestration/runner.py` 和 `orchestration/workflows.py` 仍 active-import Maintenance Planning；这违反 Reusable Capability Layer 不依赖 Maintenance Planning Domain 的边界。

这些项目不属于单纯的文档或历史 migration 残留，因此 `D = 0` 不成立。

## 1. Final Product Boundary

运行时和前端品牌已呈现为：

```text
Multimodal Operations Agent
```

工作台中以 Incident 诊断作为 Reference Application 入口，Diagnosis Result 是诊断闭环的终点。当前 active runtime 不再构造 Supplier/A2A、Refund、Procurement、Quotation、Customer Notification、WorkOrder fulfillment、Dispatch、Field Service、Predictive Maintenance、Telemetry/RUL、Kafka/Debezium、GraphRAG/Neo4j 或 field WebRTC session。

保留的 Maintenance Planning / Device Family 页面和 API 属于尚未删除的工业策略/治理能力，不等同于恢复完整售后履约平台；但其被 reusable core 直接引用的问题仍是本次 dependency blocker。

## 2. Final Golden Path

service/application-level synthetic path 已通过：

```text
Incident / Case
→ Media Upload
→ Generic Multimodal Perception
→ Industrial Recognition
→ Human Evidence Confirmation
→ Persisted EvidenceBundle
→ Diagnosis Manifest
→ Evidence Resolver
→ Agent Context
→ Hybrid Retrieval parity
→ Diagnosis read-only tools
→ final DiagnosisReport
→ traceable citation
```

证据：

- `deindustrialization_batch1_golden_path_smoke.py`：真实 production Agent graph、checkpoint/event store、ToolGateway 和 synthetic read-only adapter；PASS。
- `deindustrialization_batch2a1_manifest_parity_smoke.py`：RecognitionService 持久化后 reload，构造真实 Diagnosis manifest，Evidence Resolver 读取 OCR 与 visual finding，并验证 final report citation 能回到 `finding-indicator`；PASS。
- `deindustrialization_batch2a2_evidence_provenance_smoke.py`：确认 citation 含 `source_id` 和 `evidence_bundle_id`，拒绝 rejected finding；PASS。
- `deindustrialization_batch2b_retrieval_parity_smoke.py`：相同 corpus/query 下过滤结果、排序结果和 knowledge citation IDs 保持 parity；PASS。

因此：

```text
Final Golden Path: PASS — service-level synthetic verification
```

完整 FastAPI import 未完成，见环境限制；这不否定已通过的 service-level path，但不能把它描述为完整部署环境验收。

## 3. Core Dependency Direction

通过的部分：

- `governance/review_boundary.py` 保持 domain-neutral，不包含 Maintenance Planning records、policy version、assignment/council/evaluation 语义。
- Multimodal → PerceptionResult → Industrial Recognition → EvidenceBundle contract smoke 通过。
- Knowledge retriever 只读取 generic applicability；retrieval parity 通过。
- ToolGateway/governance 为 Diagnosis catalog 提供共享实现，未恢复第二套 tool runtime。

未通过的部分：

| Active file | Evidence | Classification |
|---|---|---|
| `src/industrial_ops_agent/model_gateway/governance.py` | active import `maintenance_planning.review_isolation` 并读取 Maintenance Planning records | Reusable core boundary violation |
| `src/industrial_ops_agent/orchestration/runner.py` | active import/assembly of Maintenance Planning activity | Orchestration core boundary violation |
| `src/industrial_ops_agent/orchestration/workflows.py` | active Maintenance Planning workflow/activity registration | Orchestration core boundary violation |

这三个问题不是历史文本，不能归入 compatibility-only。

## 4. Final Tool Inventory

默认 Diagnosis registry 实际包含且仅包含以下五个 read-only tools：

```text
asset.get
warranty.get
parts.availability
schedule.availability
work_orders.history
```

通过证据：

- Diagnosis tool catalog smoke：PASS。
- Batch 3A / 3B / 3C deletion smoke：PASS。
- mutation tools 不在默认 registry；Parts mutation 不在 Diagnosis gateway。

```text
Final tool inventory: PASS
```

## 5. Final Runtime Inventory

当前 `runtime.py` 实际构造的主要 capability 包括：

- Database、tenant cache、object store、OIDC/OPA authorization；
- generic ToolGateway + one read-only adapter；
- Recognition、Diagnosis、Knowledge ingestion/deletion/index evaluation/search rebuild；
- 保留的 Maintenance Planning dispatcher/binding；
- bounded realtime transcription-to-Agent input；
- dataset/training/evaluation、Model Gateway、MLflow、recovery、assurance、operations；
- optional OpenSearch（默认关闭）。

未发现默认 runtime 构造以下已删除 surface：

- Supplier / A2A、Refund、Procurement、Quotation、Customer Notification；
- WorkOrder fulfillment、Dispatch、Field Service、fulfillment FSM、Equipment Control；
- Parts mutation、Predictive Maintenance、Telemetry/RUL；
- Kafka/Debezium pipeline、GraphRAG/Neo4j、field WebRTC shell。

```text
Final runtime surface: PASS
```

说明：Maintenance Planning dispatcher 是明确保留的 domain-specific capability，不属于本次已删除清单；它不能被 reusable core 直接依赖，故另计入 dependency failure。

## 6. API Surface

当前 OpenAPI JSON 共 192 个 path；已删除的 GraphRAG、predictive、realtime session、portal、service entitlement、service performance 等路径未出现，Parts mutation 路径也未出现。

但是合约仍包含两个 active-looking repair-work-order 路径：

```text
/api/v1/incidents/{incident_id}/repair-work-order-options
/api/v1/incidents/{incident_id}/repair-work-order-proposals
```

相同残留也出现在 `web/generated/api/schema.d.ts`。当前 Python route source 已没有对应实现，因此这是 stale generated API surface，而不是已运行的 route；但它仍是可被客户端消费的 active contract，不能按历史文档忽略。

```text
Final API surface: FAIL — stale repair-work-order paths remain in OpenAPI and generated TypeScript contract.
```

## 7. Frontend Surface

active navigation 主要包含：

- Workspace；
- Incident Diagnosis；
- Knowledge / search / external reference；
- training / evaluation / model release / enterprise assets / prompt / memory governance；
- retained Maintenance Planning / Device Family governance；
- operations、GPU、cost、trace、tool、security、tenant governance。

以下页面目录没有 active `page.tsx` 或已被移除：

- WorkOrder management；
- Dispatch / Field Service；
- Parts mutation；
- Supplier / Procurement / Quotation / Refund；
- Predictive Maintenance；
- GraphRAG administration；
- field realtime UI。

本次未做 UI redesign。

## 8. Persistence / Alembic

当前 migration chain 连续：

```text
0086_maintenance_review_exposure
→ 0087_agent_run_independent_ownership
→ 0088_knowledge_generic_applicability
→ 0089_remove_peripheral_fulfillment
→ 0090_remove_workorder_field_fulfillment
→ 0091_remove_predictive_maintenance
→ 0092_remove_graphrag_neo4j
→ 0093_remove_field_realtime_shell
```

验证结果：

- `python -m alembic heads`：PASS；head 为 `0093_remove_field_realtime_shell`。
- Batch 3E SQLite migration rehearsal：PASS。
- 所有既有 SQLite deletion rehearsals：包含在 regression matrix，PASS。
- PostgreSQL：`NOT RUN — no disposable PostgreSQL environment available`。

未修改历史 migration，也未连接生产数据库。

## 9. Retained AI Capabilities

已由现有 smoke、静态 surface 检查或文件/route inventory 证明仍保留：

- OCR / VLM / ASR / video perception；
- bounded Agent execution、events、checkpoints、resume；
- Recognition evidence context、Evidence Resolver、citation provenance；
- Hybrid Retrieval、ACL/tenant filtering、generic applicability；
- generic ToolGateway、Model Gateway、inference audit；
- evaluation、SFT、DPO、PPO、GRPO、generic dataset pipeline、MLflow、model promotion；
- Temporal core、observability、security；
- optional OpenSearch profile，默认关闭；
- generic reviewed transcription-to-Agent input capability。

## 10. Historical Data vs Active Capability

当前仍保留 WorkOrder / Parts 相关 persistence 与数据反馈字段，用于历史/read compatibility 和数据血缘；Batch 3C 的 `parts.availability` 仍是 read-only capability。

已删除的是 active mutation workflow：

```text
historical/read facts = retained
active mutation workflow = deleted
```

`src/industrial_ops_agent/workorders/service.py` 仍是可导入的历史/read projection，包含旧领域类型和旧 read transaction；它没有被默认 API runtime 装配。该部分归入 C（retained historical/read compatibility），但不应被误写成完整 WorkOrder fulfillment 已保留。

## 11. Dead Reference Audit

| Category | Findings | Result |
|---|---|---|
| A. Historical Alembic migration | 早期 migrations 仍记录已删除表/字段 | Allowed |
| B. Historical/project documentation | README、旧报告、验收材料仍出现旧产品域名 | Allowed for structural scan; 文档定位仍不完全更新 |
| C. Retained historical/read compatibility | ORM historical records、WorkOrder/Parts read projection、training/evaluation compatibility markers、`__pycache__` | Allowed; 不作为 active runtime |
| D. Stale active production reference | OPA deleted-action grants；Python authorization action declarations；OpenAPI repair-work-order paths | Not allowed |
| Boundary violation | Reusable `model_gateway` / `orchestration` active-import Maintenance Planning | Not allowed |

因此：

```text
Final dependency scan: FAIL
```

## 12. Regression Matrix

本次使用仓库已有 `.venv`（Python 3.12.10）并设置 `PYTHONPATH=src`，18 个 smoke 全部重新执行并通过：

| Batch | Result |
|---|---|
| 1 | PASS |
| 1.5 | PASS |
| 2A | PASS |
| 2B | PASS |
| 2C | PASS |
| 3A | PASS |
| 3B | PASS |
| 3C | PASS |
| 3D | PASS |
| 3E | PASS |

其中包含：Golden Path、boundary、review boundary、Multimodal、retrieval、tool catalog、Recognition、manifest/provenance、generic applicability、retrieval parity、runtime isolation、各 deletion smoke 和 SQLite migration smoke。

## 13. Static Verification and Environment Debt

### Structural/static results

- Targeted Ruff（review boundary、tool boundary、Multimodal processor、retrieval）：PASS。
- `python -m compileall -q src scripts`：PASS。
- explicit changed-boundary `py_compile`：PASS。
- OpenAPI JSON parse：PASS，192 paths / 478 schemas。
- Alembic head：PASS，0093。
- Tool inventory：PASS。
- Route/deletion surface smoke：PASS for deleted source/runtime routes, but final contract scan FAIL due stale generated repair-work-order paths。

### Existing baseline / environment debt

- Full FastAPI import：
  `NOT RUN — existing local PIL dependency unavailable. Non-blocking for service-level structural verification.`
- OpenAPI generator shell check：未完成；仓库脚本在当前 Windows shell 中调用 `.venv/bin/python`，而本地环境是 `.venv\Scripts\python.exe`，且直接 app import 同样在 `PIL` 缺失处停止。
- Frontend typecheck：
  `NOT RUN — web/node_modules unavailable`。
- Full repository Ruff：存在 89 个既有错误，包含 scripts、model gateway runtime、sandbox、training 等 baseline；未扩大修复范围。
- Focused mypy：存在 5 个既有错误，主要为 `model_gateway/governance.py` 的模型 view 类型和 `orchestration/runner.py` 的 resolver 类型；未扩大修复范围。
- PostgreSQL rehearsal：
  `NOT RUN — no disposable PostgreSQL environment available`。
- `.git` 缺失是既定工作副本状态；未执行 `git init`。

上述环境/仓库 baseline debt 不单独构成 architecture failure；本次 FAIL 来自前述 active stale surfaces 和 reusable-core dependency violation。

## 14. Final Acceptance Summary

### Before

```text
Industrial after-sales platform
+ AI/Agent capabilities
```

### Current observed state

```text
Multimodal Operations Agent
+ Industrial Diagnosis Reference Application
+ retained AI/model/evaluation/governance capabilities
+ retained Maintenance Planning policy/application surface
```

已完成的去工业化删除面足以证明默认 runtime 不再是完整售后履约平台；但 Phase 1 还不能宣布完成，因为 active API/authz 残留和 reusable-core 反向依赖尚未达到验收要求。

```text
Phase 1 deindustrialization:
FAIL — stale active authorization/API references and reusable-core → Maintenance Planning dependency remain.
```

## 15. Phase 1 Closure Batch — Re-run Final Acceptance

### A. Active API / authorization residuals

| Former residual | Closure action | Re-run evidence | Result |
|---|---|---|---|
| Repair Work Order generated API | Removed the two stale paths and four unreferenced schemas from `contracts/openapi.json` and `web/generated/api/schema.d.ts`; no production route was restored. | Parsed OpenAPI: 190 paths / 474 schemas; Repair Work Order paths: 0; schemas: 0. | PASS |
| `work_order.execute` | The two remaining historical read projections now require `work_order.read`; removed enum, role grant and OPA enforcement. | Active source/infra/contract scan: 0 occurrences. | PASS |
| `agent_collaboration.*` | Removed enum, role grants and OPA entries. | Active source/infra/contract scan: 0 occurrences. | PASS |
| `alert_candidate.*`, `predictive_outcome.record` | Removed stale OPA grants. | Active source/infra/contract scan: 0 occurrences. | PASS |

There is no FastAPI route source, router include, handwritten web client, or
active request/response source corresponding to the removed Repair Work Order
paths. They were generated-contract residuals only.

```text
Active stale API references: 0
Active stale authorization references: 0
```

### B. Reusable core dependency direction

The retained Maintenance Planning domain remains active: its API routers,
runtime dispatcher/binding, and Temporal council registration are still used.
It was not deleted or generalized.

| Former core edge | Type | Closure ownership | Result |
|---|---|---|---|
| `model_gateway/governance.py` → Maintenance Review records/disclosure | Type 2 | `maintenance_planning/model_inference_reader.py` now owns Diagnosis/council lineage and disclosure. Generic Model Gateway owns only authorization and tenant-scoped inference selection, including a caller-owned transaction seam. The API application composes the domain reader through a one-method neutral reader contract. | PASS |
| `orchestration/workflows.py` → Maintenance Planning Temporal types | Type 2 | Council payload, activity, workflow and lazy dispatcher now belong to `maintenance_planning/temporal.py`; generic orchestration is dependency-free. | PASS |
| `orchestration/runner.py` → Maintenance Planning registration | Type 2 | Generic runner accepts a generic registration value. `orchestration/entrypoint.py` is the explicit Industrial composition root and imports the Maintenance Planning registration factory. Docker, Compose and Helm invoke that entrypoint. | PASS |

The only `maintenance_planning` text found beneath the scanned orchestration
area is in `orchestration/entrypoint.py`, the permitted composition root.
AST import scan confirms no such import from:

```text
model_gateway/governance.py
orchestration/runner.py
orchestration/workflows.py
```

```text
Reusable core → Maintenance Planning active dependency: 0
```

### C. Closure verification

| Verification | Result |
|---|---|
| New `deindustrialization_phase1_closure_smoke.py` | RED on stale OpenAPI residual; GREEN after all closure changes. |
| Batch 1–3E smoke suite | PASS — 25 scripts, including Golden Path, Batch 1 boundary, Batch 1.5 boundary, 2A/2B/2C parity and isolation, 3A–3E deletion and SQLite rehearsals. |
| Final Golden Path | PASS — service-level synthetic execution. |
| Focused imports for generic governance, Maintenance inference reader, Maintenance Temporal transport, generic runner and composition entrypoint | PASS. |
| OpenAPI JSON parse and generated-contract residual inventory | PASS. The repository shell generator check remains unavailable on Windows because it invokes `.venv/bin/python`; direct application generation is also blocked by the existing missing `PIL` dependency. |
| Authorization inventory | PASS. |
| Tool inventory and runtime isolation | PASS through the existing Batch 2 tools and Batch 2C runtime smokes. |
| Changed-file Ruff | PASS. |
| `py_compile` and `compileall` | PASS. |
| Focused mypy | Existing 7 baseline errors remain in pre-existing `model_gateway/governance.py`, `orchestration/runner.py`, and `runtime.py` provider/view typing; no error is reported in either new domain module or composition module. |
| Alembic | PASS — head `0093_remove_field_realtime_shell`; the `0086` → `0093` chain is continuous. |
| PostgreSQL rehearsal | `NOT RUN — no disposable PostgreSQL environment available`. |

No schema migration was created. No production database was contacted. `.git`
remains absent by design; no repository was initialized.

## 16. Final Verdict

All Phase 1 structural acceptance conditions now hold:

```text
Active stale API references: 0
Active stale authorization references: 0
Reusable core → Maintenance Planning active dependency: 0
Golden Path: PASS
Batch 1–3E regression: PASS
Tool/runtime inventory: PASS

Phase 1 deindustrialization:
PASS
```
