# Agentic RL Trajectory Readiness Audit

审计日期：2026-09-27  
范围：当前生产运行中与 `AgentRun` 关联的 Industrial Diagnosis Agent。审计同时做了有界扫描，以区分 Maintenance Planning council、评测和多模态推理等其他模型调用；它们不被误记为 `AgentRun` 轨迹的一部分。  
变更：无生产代码变更。

## 结论

一次 `AgentRun` **可以作为第一版 trajectory 的容器/根引用**：它拥有稳定 ID、顺序事件、原子检查点、与 `DiagnosisRun` 的一对一关联，并可通过 `ModelInferenceRecord` 和 `ToolCallRecord` 找到主要执行证据。

但 `AgentRun` **尚不是自包含的完整 trajectory**。一次训练步骤的完整 observation、动作结果与 transition 仍需跨 manifest、checkpoint、inference、tool 与检索结果拼接；特别是 AgentRun 本身没有明确的 `RUNNING` 写入点，工具持久化只保存输入摘要和有限输出元数据，检索候选/排序也未作为独立结果快照持久化。

## 1. AgentRun 生命周期

### 创建

`AgentRunRecord` 是 `agent_runs` 表的根记录，字段仅含 `agent_run_id`、`status`、`budget`、`last_sequence`、`version`（`src/industrial_ops_agent/persistence/models.py:1968`）。每个 `DiagnosisRunRecord.agent_run_id` 都外键关联此记录，且同租户唯一（`src/industrial_ops_agent/persistence/models.py:1299`）。

| 创建入口 | 文件 / 函数 | 初始状态 | 同时建立的关联 |
| --- | --- | --- | --- |
| 首次诊断 | `src/industrial_ops_agent/application/diagnoses.py:187`，`DiagnosisService.start()` | `QUEUED` | 新建 `DiagnosisRunRecord`、manifest、`diagnosis.queued` 事件。 |
| 已确认转录后的重新分析 | `src/industrial_ops_agent/application/diagnoses.py:402`，`reanalyze_with_confirmed_transcript()` | `QUEUED` | 新建 run，manifest 绑定已确认转录事件；写 `diagnosis.reanalysis_queued`。 |
| 补充信息后恢复 | `src/industrial_ops_agent/application/agent_runs.py:196`，`AgentRunControlService.resume()` | `QUEUED` | 新建 successor run，manifest 绑定父 run 与已确认人工输入；写 `diagnosis.resume_queued`。 |

### 开始

Temporal `DiagnosisWorkflow` 调用 `DiagnosisActivity.execute()`，再构造 `AgentGraph` 与 `DiagnosisRuntime`（`src/industrial_ops_agent/orchestration/workflows.py:370`、`:698`）。在 `DiagnosisActivity._load_context()` 中，**`DiagnosisRunRecord.status`** 从 `QUEUED` 变为 `RUNNING`（`src/industrial_ops_agent/orchestration/workflows.py:488`、`:535`）。随后 `DiagnosisRuntime.load()` 创建或重载图状态，并以 `diagnosis.graph_started` 事件和同序号 checkpoint 开始执行（`src/industrial_ops_agent/agent/diagnosis_runtime.py:107`；`src/industrial_ops_agent/agent/checkpoints.py:102`）。

审计发现：在 AgentRun 相关代码中未找到把 **`AgentRunRecord.status`** 写为 `RUNNING` 的路径。它从 `QUEUED` 直接在终态事件写入终态值。这不阻止用事件序列确定开始时间，但 AgentRun 状态字段本身不能准确表示“当前正在执行”。

### 结束与状态

| 类别 | `AgentRun.status` | 结束位置 | 证据 |
| --- | --- | --- | --- |
| 成功 | `COMPLETED` | `_publish_report()` 写 `DiagnosisRun.report`、发 `diagnosis.completed`，并以该状态更新 AgentRun。 | `src/industrial_ops_agent/orchestration/workflows.py:569`、`:669`。 |
| 可恢复的非成功终态 | `NEEDS_INFORMATION` | 同一发布路径产生 `diagnosis.needs_information`。 | `src/industrial_ops_agent/orchestration/workflows.py:673`。 |
| 工作流最终失败 | `FAILED` | 最后一次 Activity 失败时 `_record_terminal_failure()` 写失败报告与 `diagnosis.failed`。 | `src/industrial_ops_agent/orchestration/workflows.py:427`、`:460`。 |
| 用户取消 | `CANCEL_REQUESTED` → `CANCELLED` | `AgentRunControlService.cancel()` 先请求取消，再在 dispatcher 返回后写 `diagnosis.cancelled`。 | `src/industrial_ops_agent/application/agent_runs.py:83`、`:133`、`:182`。 |
| 人工接管 / 升级 | `WAITING_EXPERT` / `ESCALATED` | 专家接管或专家修订路径更新。 | `src/industrial_ops_agent/application/expert_diagnoses.py:177`、`:340`。 |

`COMPLETED` 是当前唯一明确的成功状态。`NEEDS_INFORMATION`、`WAITING_EXPERT` 和 `ESCALATED` 是业务终态/交接状态，不应在现状审计中视为 success 或 failure reward。

## 2. Agent decision points

### AgentRun 关联的生产决策点

当前只有一个 AgentRun-backed 的模型决策函数：

| 文件 / 函数 | 决策输入 | 模型输出 | 后续路由 |
| --- | --- | --- | --- |
| `src/industrial_ops_agent/agent/diagnosis_runtime.py:373`，`DiagnosisRuntime.decide()` | 由 `build_step_request()` 构造：incident/query、最多 4 条授权 evidence、既有 tool facts、工具失败、已确认 memory、可用只读工具、剩余预算，以及受版本绑定的 prompt/schema。 | `DIAGNOSIS_STEP_SCHEMA` 的 `{action, query, tool_id, report}`，经 `validate_step()` 校验。 | `AgentGraph._node()` 按 `RETRIEVE`、`CALL_TOOL`、`FINAL`、`NEEDS_INFORMATION` 路由。`src/industrial_ops_agent/agent/contracts.py:82`、`:122`；`src/industrial_ops_agent/agent/graph.py:56`。 |

该决策的模型请求和结果落在 `ModelInferenceRecord`：其中有 model alias/release/manifest、prompt/context hash、response JSON、token 用量及 guardrail 结果（`src/industrial_ops_agent/persistence/models.py:3609`）。`DiagnosisRuntime.decide()` 还按 AgentRun、DiagnosisRun、trace、release 与 manifest 复核执行结果（`src/industrial_ops_agent/agent/diagnosis_runtime.py:444`）。

### 其他模型调用的边界

仓库还存在 Maintenance Planning council 的 `_complete_role()`（`src/industrial_ops_agent/maintenance_planning/service.py:417`）：它为 specialist/coordinator 生成建议并保存 contribution。它没有创建或使用 `AgentRunRecord`、`AgentEventRecord` 或 `AgentCheckpointRecord`，故不属于当前 AgentRun trajectory 容器。Prompt 评测与多模态推理同样是模型调用，不是本审计的 AgentRun-backed action loop。

## 3. Observation sources

下表列出模型在 `DiagnosisRuntime.decide()` 时实际可见、或可用于重建其可见状态的来源。

| 来源 | 现有实现 | 模型是否直接可见 | 轨迹可用性 |
| --- | --- | --- | --- |
| 静态运行绑定 | `DiagnosisRunRecord.manifest`：incident/evidence 版本、模型、prompt、索引、工具版本、预算。 | 间接；`build_step_request()` 从 state/manifest 取值。 | 可引用；manifest 已持久化。 |
| Checkpoint | `AgentCheckpointRecord.state` 保存 `diagnosis-state/v2`、node、pending request、evidence、tool facts/failures、memory、decision、report、预算等，并有 checksum。 | state 是构造 prompt 的工作来源。 | 高；每次图转换与 event 原子写入。 |
| Recognition evidence | `DiagnosisEvidenceResolver` 从确认的 EvidenceBundle/RecognitionResult 依 manifest refs 解析为 `AgentEvidenceItem`。 | 是；最多 4 条被写入 `authorized_evidence`。 | 高；带 bundle/version/result/media/source/result hash。 |
| Knowledge retrieval | `HybridRetriever.search_with_trace()` 返回 Knowledge evidence；与 recognition evidence 合并，最多保留 12 条 state evidence。 | 是；模型请求最多带其中 4 条。 | 部分；入选 evidence 与 guard 写入 state，但完整候选与排序没有独立持久化快照。 |
| Tool result | `ToolGateway.invoke()` 返回 data；runtime 将受限的 source、record、as-of、authority、values 存为 `tool_facts`。 | 是；作为 `authorized_enterprise_facts`。 | 部分；ToolCallRecord 持久化输入 digest 与元数据，不保留完整 data。 |
| Tool failure | runtime 将工具失败原因存为 `tool_failures`。 | 是；作为 `enterprise_tool_failures`。 | 高于成功输出；失败原因在 checkpoint 中。 |
| Memory | `select_for_diagnosis()` 写入 `memories` 与 `memory_truncations`。 | 是；作为 `untrusted_human_confirmed_memories`。 | 高；Gateway context manifest 还记录 memory reference 和截断。 |
| 输入文本 | incident description，或经确认的 reanalysis/resume 输入。 | 是；裁剪至 1800 字符。 | 部分；原文来源在 Incident/AgentEvent/输入 context，模型可见文本由 state 重建。 |
| Prompt-visible context manifest | `ContextManifest` 记录 evidence/memory/tool result references、token budget、截断、rendered context hash 与 context hash。 | 这是模型调用的版本化描述。 | 高；存入 `ModelInferenceRecord.context_manifest_json`。 |

核心证据位置：`src/industrial_ops_agent/agent/diagnosis_runtime.py:107`、`:289`、`:513`；`src/industrial_ops_agent/industrial_recognition/diagnosis_evidence.py:37`；`src/industrial_ops_agent/model_gateway/context_manifest.py:73`。

## 4. Action sources

| Action | 来源 | 执行位置 | 是否为模型决策 |
| --- | --- | --- | --- |
| 初始检索 | 图的固定路由 `prepare → retrieve`。 | `AgentGraph._node()` / `DiagnosisRuntime.retrieve()`。 | 否；query 初始为 incident description。 |
| 继续检索 | 模型输出 `action=RETRIEVE` 与 `query`；`_apply_diagnosis_action()` 更新 retrieval query。 | `src/industrial_ops_agent/agent/contracts.py:30`；`:82`。 | 是。 |
| 只读工具调用 | 模型输出 `action=CALL_TOOL` 与 `tool_id`。 | `DiagnosisRuntime.tool()` → `ToolGateway.invoke()`。 | 工具选择是；参数当前固定为 `{asset_id}`。 |
| 形成最终报告 | 模型输出 `FINAL` 或 `NEEDS_INFORMATION`，含符合 schema 的 report。 | `DiagnosisRuntime.finish()` 将 citation IDs 解析为 `DiagnosisReport`。 | 是。 |
| 预算耗尽报告 | timeout/token/tool budget 触发 `budget_report()`。 | graph/runtime guard。 | 否；系统控制流。 |
| 取消、补充信息、专家接管 | 用户或专家应用服务。 | AgentRunControlService / ExpertDiagnosisService。 | 否；外部环境/人工事件。 |

动作 contract 已明确约束为四类：`RETRIEVE`、`CALL_TOOL`、`FINAL`、`NEEDS_INFORMATION`（`src/industrial_ops_agent/agent/contracts.py:96`）。

## 5. Environment results

| action 后的结果 | 来源 | 记录在哪里 | 当前限制 |
| --- | --- | --- | --- |
| 检索结果 | `HybridRetriever.search_with_trace()` 的 evidence 与 guard。 | 合并后的 evidence / `retrieval_guard` 进入 checkpoint；node-completed event 记录 count/guard。 | 完整候选、得分、排序与淘汰理由没有单独持久化。 |
| 工具成功 | `ReadonlyToolAdapter` → `ToolGateway` 返回已校验 fact data。 | checkpoint `tool_facts`；`ToolCallRecord` 保存状态、输入摘要、有限 output metadata。 | 原始参数和完整输出不在 ToolCallRecord 中。 |
| 工具失败 | adapter/限流异常或不可用结果。 | checkpoint `tool_failures`；适用时 ToolCallRecord `FAILED`。 | 失败与选择它的模型 inference 没有直接外键。 |
| 模型结果 | Model Gateway response，经 release/manifest/context 验证和 schema 校验。 | ModelInferenceRecord；checkpoint `decision`、`inference_ids`、`model_execution`。 | AgentEvent 只记录 inference ID/action 摘要。 |
| 终态结果 | `DiagnosisReport`、citation、stop reason。 | `DiagnosisRunRecord.report`、终态 AgentEvent、最终 checkpoint。 | 没有统一的 outcome/reward 记录。 |
| 人工后续结果 | 质量反馈、专家接管/修订。 | 独立 diagnosis feedback/intervention/revision 记录。 | 不是运行时 transition 的一部分；需要按 DiagnosisRun/AgentRun 事后关联。 |

## 6. RL mapping table

| RL Concept | Existing Implementation | Location | Missing |
| --- | --- | --- | --- |
| Episode / trajectory container | `AgentRunRecord`，与 `DiagnosisRunRecord` 一对一。 | `persistence/models.py:1299`、`:1968`。 | 无明确 trajectory schema/version；AgentRun 缺少 domain/task binding字段，需通过 DiagnosisRun join。 |
| Episode start | 创建 `QUEUED` run、初始 event；图 load 写首个 checkpoint。 | `application/diagnoses.py:187`；`agent/diagnosis_runtime.py:107`。 | AgentRun 没有 `RUNNING` transition 或明确 start timestamp。 |
| State / checkpoint | `AgentCheckpointRecord`，含完整运行 state 与 checksum。 | `agent/checkpoints.py:25`；`persistence/models.py:1993`。 | checkpoint schema 是恢复状态，不是稳定的 trajectory observation schema。 |
| Observation | manifest + state + evidence + retrieval + tool facts + memory；模型调用有 ContextManifest。 | `agent/diagnosis_runtime.py:513`；`model_gateway/context_manifest.py:73`。 | 需跨表重建；检索完整排序与工具完整结果不完整。 |
| Policy / model binding | `ModelInferenceRecord` 记录 release、manifest、prompt/context hash、response。 | `persistence/models.py:3609`；`model_gateway/service.py:628`。 | 没有直接 step ID；通过 AgentRun、inference ID 和 checkpoint sequence 间接关联。 |
| Action | 校验后的 `{action, query, tool_id, report}`。 | `agent/contracts.py:82`、`:122`；`agent/diagnosis_runtime.py:373`。 | action 的完整参数、执行结果与 transition 没有一个统一不可变 record。 |
| Environment transition | AgentGraph 路由；event 与 checkpoint 原子追加。 | `agent/graph.py:56`；`agent/checkpoints.py:102`。 | Event payload 面向 UI/审计，不能单独重放完整 transition。 |
| Tool action/result | ToolGateway 与 ToolCallRecord；runtime tool facts。 | `tools/gateway.py:91`；`persistence/models.py:2012`。 | ToolCallRecord 只保存 digest/metadata，agent_run_id 也可为空。 |
| Terminal / done | completed、needs-information、failed、cancelled、expert states。 | `orchestration/workflows.py:427`、`:569`；`application/agent_runs.py:83`。 | 业务状态与训练终态分类未定义；不能把 NEEDS_INFORMATION 自动视为失败。 |
| Reward | 报告、人工 quality verdict、专家修订提供候选信号。 | `agent/models.py:63`；`persistence/models.py:1320`、`:1939`。 | 无 reward 值、版本、计算窗口、censoring 规则或每 run/step 绑定。 |

## 最终判断

**第一版容器：可以。** 把 `AgentRun` 作为 trajectory 的稳定根引用是符合现有实现的：可按 `agent_run_id` 获取顺序事件、检查点、模型推理和工具审计，并通过一对一 `DiagnosisRun` 获得 manifest 和最终报告。

**完整 trajectory：尚不可以直接宣称。** 当前数据足以做受约束的离线拼接和人工审计；但要将每个 AgentRun 直接导出为完整的 observation → action → environment result → terminal trajectory，仍缺少明确的逐步 contract，尤其是 AgentRun 的运行中状态、检索完整结果快照、工具完整 observation 及统一 outcome/reward 绑定。
