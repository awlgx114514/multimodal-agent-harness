# Agentic RL Readiness Audit

审计日期：2026-09-25  
范围：生产 Diagnosis Agent 的运行时、持久化、工具网关、模型网关与诊断反馈链路。未修改生产代码。

## 结论摘要

当前系统具备可追溯的 Diagnosis Agent 执行基础：运行实例、顺序事件、原子检查点、结构化模型决策、受治理的工具调用、最终报告和人工质量反馈均有持久化记录。

但这些记录尚未构成一个版本化、逐步关联、可复现并可标注回报的 **trajectory contract**。因此结论不是“没有 RL 数据”，而是：

| 能力 | 结论 | 说明 |
| --- | --- | --- |
| AgentRun 生命周期 | 部分就绪 | 已有稳定的 `agent_run_id` 和诊断运行一对一绑定，但运行记录本身只保存状态、预算和序列号。 |
| AgentEvent 动作覆盖 | 部分就绪 | 图节点和终态有事件；完整 action、observation 与 transition 并非每步显式、规范化记录。 |
| Tool call 结构化 | 部分就绪 | 调用具有 ID、版本、schema 校验、授权和摘要审计；原始参数、完整结果及决策步骤关联不足。 |
| Observation 完整性 | 部分就绪 | 检查点保留大量运行状态；缺少稳定的逐步 observation contract 和可重放的输入/输出引用集合。 |
| Final outcome → reward | 未就绪 | 有报告、专家修订和人工 verdict，但没有版本化 reward 定义、聚合规则、延迟结果或每条轨迹绑定。 |
| Model version | 已就绪 | 每次推理绑定 resolved release、manifest hash、prompt/context 证据。 |

**总体判断：** 当前可用于审计、人工标注和离线轨迹抽取的候选数据源；尚不适合直接作为在线 RL 或可复现离线 RL 训练数据集。首要缺口是 trajectory/reward 合约，不是模型版本或基础事件存储。

## 1. 当前 `AgentRun` 在哪里产生？

`AgentRunRecord` 是 `agent_runs` 表的持久化根，字段为 `agent_run_id`、`status`、`budget`、`last_sequence`、`version`（`src/industrial_ops_agent/persistence/models.py:1968`）。它由 Diagnosis 应用服务在创建诊断工作流之前写入：

| 入口 | 产生方式 | 关联 |
| --- | --- | --- |
| 首次启动诊断 | `DiagnosisService.start()` 创建 `AgentRunRecord`，随后创建带相同 `agent_run_id` 的 `DiagnosisRunRecord`。 | `DiagnosisRunRecord.agent_run_id` 为外键，且同租户唯一。`src/industrial_ops_agent/application/diagnoses.py:187`、`:311`、`src/industrial_ops_agent/persistence/models.py:1299`。 |
| 已确认转录后的重新分析 | `DiagnosisService.reanalyze_with_confirmed_transcript()` 创建新的 AgentRun/DiagnosisRun。 | 新运行保留输入上下文的来源标识。`src/industrial_ops_agent/application/diagnoses.py:402`、`:537`。 |
| 补充信息后恢复 | `AgentRunControlService.resume()` 生成 successor AgentRun/DiagnosisRun，并把已确认人工输入事件写入新 manifest。 | 父运行与确认输入事件在 `input_context` 中相连。`src/industrial_ops_agent/application/agent_runs.py:196`、`:326`、`:338`。 |

Temporal 的 `DiagnosisWorkflow` 和 `DiagnosisActivity` 负责执行既有运行，并不创建 AgentRun（`src/industrial_ops_agent/orchestration/workflows.py:370`、`:698`）。这意味着 AgentRun 的正确 ownership 在应用服务/持久化边界，而不在图运行时。

## 2. 当前 `AgentEvent` 是否覆盖所有 action？

**结论：否。** 它覆盖了运行生命周期和图节点的关键里程碑，但不是“每一个可训练 action 的规范化事件流”。

已有覆盖：

| 类别 | 已记录的例子 | 证据 |
| --- | --- | --- |
| 排队与人工输入 | `diagnosis.queued`、`diagnosis.reanalysis_queued`、`diagnosis.resume_queued`、`agent.user_input.confirmed` | `src/industrial_ops_agent/application/diagnoses.py:346`、`:365`、`:572`；`src/industrial_ops_agent/application/agent_runs.py:302`、`:359`。 |
| 图执行 | `diagnosis.graph_started`、`diagnosis.graph_node_started`、`diagnosis.graph_node_completed` | `src/industrial_ops_agent/agent/diagnosis_runtime.py:107`、`:197`、`:224`。 |
| 模型尝试 | `diagnosis.model_started`、`diagnosis.model_attempt_failed`；发布时另有 `diagnosis.model_completed` | `src/industrial_ops_agent/agent/diagnosis_runtime.py:373`、`:478`；`src/industrial_ops_agent/orchestration/workflows.py:636`。 |
| 最终/中断状态 | completed、needs-information、failed、cancelled、expert takeover/revision 等 | `src/industrial_ops_agent/orchestration/workflows.py:427`、`:647`、`:669`；`src/industrial_ops_agent/application/agent_runs.py:133`、`:182`；`src/industrial_ops_agent/application/expert_diagnoses.py:177`。 |

缺失或不完整的部分：

- `decide` 的完成事件只保存最终 `action` 和 `inference_request_id`，未形成含 action 参数、候选集合、策略概率/采样参数和前后状态引用的统一 action record。
- `retrieve` 事件仅有 `evidence_count` 与 `retrieval_guard`；检索 query、排序结果、入选/淘汰项及它们的版本化引用主要散落在检查点或检索层，而非该事件。
- `tool` 事件只带 `tool_id` 与可找到时的 `tool_call_id`；完整输入、完整受限输出、失败细节及 action-to-observation transition 不在事件中。
- 事件 payload 是开放 JSON，而不是版本化的 trajectory step schema。事件存储虽能保证同一运行的顺序与原子追加（`src/industrial_ops_agent/agent/events.py:27`、`src/industrial_ops_agent/agent/checkpoints.py:102`），但不能仅靠 event stream 重建每个训练步骤。

因此，`AgentEvent` 是可靠的审计时间线，不是完整的 RL trajectory。

## 3. Tool call 是否已经结构化？

**结论：已结构化且受治理，但对 RL 轨迹而言仍不完整。**

`ToolGateway.invoke()` 接收明确的 `tool_id`、`version`、`parameters` 与 `agent_run_id`；它执行 registry/schema 校验、授权、限流、只读适配器调用和工具事实校验（`src/industrial_ops_agent/tools/gateway.py:91`）。成功和失败都会写 `ToolCallRecord`，包含工具 ID/版本、风险等级、状态、输入摘要和输出元数据（`src/industrial_ops_agent/persistence/models.py:2012`；`src/industrial_ops_agent/tools/gateway.py:136`、`:223`）。

但它不是完整 replay/action 数据：

- 只保存 `input_digest`，不保存可访问控制下的规范化参数快照或参数引用；
- 成功输出只审计 `source`、`source_record_id`、`as_of`、`authority` 和传输元数据，非完整工具 observation；
- `agent_run_id` 可为空，且没有 `agent_event_id`、事件 sequence、决策 inference ID 或 checkpoint 前后版本的外键；
- Diagnosis runtime 只将被限制后的 tool facts 放进 state（`src/industrial_ops_agent/agent/diagnosis_runtime.py:330`），这适合提示上下文，不等同于完整的工具结果记录。

现有结构足以支持安全审计；要支持训练，应增加对“本步选择的工具动作 → 输入版本 → 输出 observation → 后继状态”的显式关联，而不是复制一个第二工具运行时。

## 4. Observation 是否完整？

**结论：对运行恢复较完整，对可重放训练 observation 不完整。**

有利基础：

- 每个图转换与事件在同一事务内写入 `AgentCheckpointRecord`；检查点保存完整 JSON state 与 checksum（`src/industrial_ops_agent/agent/checkpoints.py:49`、`:102`）。
- `diagnosis-state/v2` 已包含 evidence、tool facts/failures、记忆及截断、inference IDs、模型执行记录、decision、report、retrieval query 和预算等（`src/industrial_ops_agent/agent/diagnosis_runtime.py:107`）。
- `AgentEvidenceItem` 包含 citation ID、内容、content/source checksum 和 citation payload；它区分 Recognition 与 Knowledge evidence（`src/industrial_ops_agent/agent/evidence.py:12`）。
- `ModelInferenceRecord` 保存 context manifest/hash、prompt hash、完整模型响应和 token/guardrail 结果（`src/industrial_ops_agent/persistence/models.py:3609`）。

关键缺口：

1. 没有每一步统一且版本化的 `observation` 定义：什么是策略可见输入、哪些字段被截断、哪些只能作为审计内容，当前由多处 state/prompt builder 隐式决定。
2. 没有 `observation_id`/hash 与 action step 的显式关联。可从 checkpoint、inference 与工具记录事后拼接，但拼接规则本身未被持久化为合约。
3. 检索的完整候选/排序、工具完整结果、模型实际 prompt 组成和过滤后的 visibility 没有统一的可重放 observation reference。
4. checkpoint 是恢复状态快照，而不是不可变的训练样本；其 schema `diagnosis-state/v2` 也不是面向长期数据集兼容性承诺的 trajectory schema。

## 5. Final outcome 是否可计算 reward？

**结论：可以采集 reward 的候选信号，但当前不能计算受治理、可比较的生产 Agent reward。**

可用信号已经存在：

- `DiagnosisReport` 有状态、结论、引用、矛盾、缺失信息、后续检查、置信度和停止原因（`src/industrial_ops_agent/agent/models.py:63`）。发布后进入 `DiagnosisRunRecord.report`，并有终态事件（`src/industrial_ops_agent/orchestration/workflows.py:574`）。
- `DiagnosisQualityFeedbackRecord` 保存与 `agent_run_id` 绑定的人工 verdict（HELPFUL、PARTIALLY_HELPFUL、NOT_HELPFUL、UNSAFE）、问题码、报告/manifest 摘要及模型、提示词、索引和 context 绑定（`src/industrial_ops_agent/persistence/models.py:1320`；`src/industrial_ops_agent/application/diagnosis_feedback.py:66`）。
- 专家接管与修订保留 AI 报告快照/摘要、专家 outcome 和修订原因（`src/industrial_ops_agent/persistence/models.py:1910`、`:1939`；`src/industrial_ops_agent/application/expert_diagnoses.py:83`）。

但缺少：

- 版本化 `reward_spec`：各 verdict、citation correctness、工具失败、超时、人工接管、专家修订、事故后续状态分别如何转换为 reward；
- reward 的计算时间、观察窗口、缺失反馈/延迟反馈的 censoring 规则；
- 按 trajectory/step 保存的 reward component、总 reward、来源和证据引用；
- 防止把 model confidence 或“完成”状态错误当作真实性 reward 的校准与审计策略。

仓库中的 PPO reward-model 逻辑位于 evaluation/training 评测链，不与生产 `AgentRun` 关联；它不能证明生产诊断 Agent 已具有 reward 链路。

## 6. Model Gateway 是否记录 model version？

**结论：是，且绑定强度足以作为 trajectory 的 policy-version 基础。**

每个 `ModelInferenceRecord` 保存：

- `model_alias`；
- `resolved_release_id`（指向模型 release）；
- `manifest_hash`；
- `agent_run_id`、`diagnosis_run_id`、trace ID；
- prompt bundle、index release、context manifest/hash、prompt hash；
- response JSON/hash、token 用量、finish reason、安全/guardrail 和失败信息。

证据见 `src/industrial_ops_agent/persistence/models.py:3609` 与 `src/industrial_ops_agent/model_gateway/service.py:628`。Diagnosis runtime 会以 expected alias、release、manifest、主体、trace 和运行 ID 复核成功模型执行（`src/industrial_ops_agent/agent/diagnosis_runtime.py:444`）。

需要补的不是 model version 字段，而是将该 inference 明确链接为某个 trajectory step 的 policy action，并冻结该步所见 observation 的引用。

## 7. 哪些地方需要新增 trajectory contract？

建议以 Diagnosis Agent 为第一个 consumer，新增一个小的、领域中立的“执行轨迹”持久化合约；不替换现有 AgentEvent、Checkpoint、ToolGateway 或 ModelGateway。

### 最小合约与落点

| 合约 | 最小字段/语义 | 写入/关联位置 |
| --- | --- | --- |
| `AgentTrajectory` | `trajectory_id`、`agent_run_id`、`diagnosis_run_id`、schema version、graph/prompt/model/index/tool-catalog binding、开始/结束时间、terminal disposition | 在 `DiagnosisService.start()`、重新分析与 resume 创建 AgentRun 后初始化；只保存稳定绑定，不把领域报告复制进去。 |
| `TrajectoryStep` | step sequence、node、`observation_ref`、规范化 action、`policy_inference_request_id`、`tool_call_id`、transition/terminal reason、前后 checkpoint sequence | 在 `DiagnosisRuntime` 的 node commit 点产生。应复用现有原子 checkpoint/event sequence，而非另起图执行循环。 |
| `TrajectoryObservationRef` | observation schema version/hash；evidence refs、检索 query/候选/排序 refs、memory/truncation refs、tool-result ref、visibility/redaction 描述 | 在 evidence resolver、retrieve、tool 与 model request 构建边界生成。大对象保留在现有 evidence/tool/inference 存储中，轨迹只存不可变引用和摘要。 |
| `TrajectoryOutcome` | final report digest/ref、citation refs、终态、取消/超时/专家接管、人工反馈/专家修订 refs、可用性与 censoring 状态 | 在 `_publish_report()`、失败/取消、专家修订和反馈写入后追加或更新。 |
| `RewardAssessment` | `reward_spec_version`、计算时间、观察窗口、components、total、证据 refs、missing/censored reason | 由独立 reward projector 根据 `TrajectoryOutcome` 和延迟人工结果计算；不得在图运行时把未验证的 confidence 当 reward。 |

### 必须补齐的关联边

```text
AgentRun
  └─ AgentTrajectory
       └─ TrajectoryStep (event/checkpoint sequence)
            ├─ ModelInferenceRecord (policy binding + response)
            ├─ ToolCallRecord (structured execution)
            └─ TrajectoryObservationRef (evidence/retrieval/tool facts)
       └─ TrajectoryOutcome
            ├─ DiagnosisReport / citations
            ├─ DiagnosisQualityFeedbackRecord
            └─ DiagnosisExpertRevisionRecord
                 └─ RewardAssessment (versioned)
```

### 实施优先级

1. **P0 — 可重建性：** 建立 `AgentTrajectory`、`TrajectoryStep`，补 event/checkpoint/inference/tool 的显式引用；冻结 observation/action schema version 与 hash。
2. **P1 — Observation 完整性：** 为检索候选、工具受限输出和 prompt-visible context 追加可访问控制下的不可变引用，定义保留期与脱敏规则。
3. **P2 — Reward：** 将现有质量反馈和专家修订投影为 versioned `RewardAssessment`；明确延迟窗口、censoring、人工分歧处理和不可训练样本的排除规则。

## 边界与下一步判断

- 不应把开放 JSON `AgentEvent.payload` 直接宣布为 trajectory contract；这会把 UI/审计事件和训练数据语义永久耦合。
- 不应复制 ToolGateway 或 ModelGateway；轨迹层应引用它们现有的受治理记录。
- 不应将最终报告文本、模型置信度或“已完成”直接等同 reward；这些最多是 reward 计算的输入信号。
- 在完成 P0 前，不建议开始基于生产 AgentRun 的 RL rollout、RLHF/RLAIF 或策略比较训练。完成 P0 后可先进行受控的离线 trajectory extraction；P2 完成并通过数据治理审查后，才具备可比较的 reward 数据集基础。
