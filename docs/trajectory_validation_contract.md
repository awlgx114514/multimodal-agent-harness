# Trajectory Validation Contract v1

日期：2026-10-01。适用现有 Trajectory Projection MVP，不修改其 contract。

## Purpose

Validate trajectory structural/data integrity, not agent performance evaluation.
Execution success != Trajectory quality：完整记录的 FAILED run 可以为 PASS。

## Input

`TrajectoryValidator().validate(trajectory)` 消费 Projector 已生成的内存
`Trajectory`，不查询数据库、不解析完整 prompt，不重新运行 Agent、model、
retrieval、tool 或 Diagnosis。领域 JSON 为 opaque payload。

## Output

冻结的 `TrajectoryValidationReport` 包含 `agent_run_id`、`quality`、五类
`checks`、`issues`、`evaluation_eligible` 和 `contract_version`。
Issue 使用稳定 code、WARNING/ERROR、check、message、可选 step index/event ID
及 source reference；`blocks_evaluation` 明确 WARNING 是否阻塞。

## Quality Levels

| Quality | 规则 | Evaluation eligible |
|---|---|---|
| PASS | 无 ERROR，无阻塞 WARNING；允许不影响 attribution 的限制 | true |
| PARTIAL | 无 ERROR，但有阻塞 WARNING；可分析，绑定不完整 | false |
| FAIL | 至少一项 ERROR；结构或关键身份不可可信解释 | false |

## Five Checks

| Check | ERROR / FAIL | Blocking WARNING / PARTIAL |
|---|---|---|
| STRUCTURE | 空 run/event identity；非正数或非递增 sequence；重复 event/inference/call identity；未知 step kind；checkpoint 类型、顺序或同 ID 绑定冲突 | checkpoint checksum 缺失 |
| OBSERVATION_BINDING | MODEL_DECISION/RETRIEVAL/TOOL 同时无非空 observation 和有效 checkpoint reference；显式 request inference ID 与 step 冲突 | — |
| ACTION_BINDING | action token 无法识别；tool identity 缺失或 result identity 与 action 冲突 | inference ID/response hash 或持久化 inference record 缺失；retrieval query 缺失；已执行 tool 缺少 call ID |
| RESULT_BINDING | tool audit 与明确 failure 同时声称成功等矛盾结果 | model response/checkpoint 无可解释结果；retrieval result 缺失；tool 无 fact/failure/明确 audit outcome；被 Projector 标记缺失的 tool audit record |
| TERMINAL | 缺失终态；run/terminal status 不一致；终态 event label 无法解释 status；terminal identity/sequence 与 steps 冲突 | — |

v1 仅验证 Projector 支持的 MODEL_DECISION、RETRIEVAL、TOOL；模型 action
tokens 为 RETRIEVE/CALL_TOOL/FINAL/NEEDS_INFORMATION。空 retrieval evidence
列表是有效结果，不能把 Projector 因缺失记录而合成的空列表误认为真实空结果。
tool 的 SUCCEEDED/FAILED/REJECTED/CANCELLED audit outcome 或明确 fact/failure
均可解释结果；失败不是质量错误。无 call ID 的明确前置拒绝/failure 不要求
伪造 call ID，但成功 fact/audit 不能用此豁免。
tool fact 需包含已有 `values` 容器；仅有 tool/call identity 不是执行结果。
无绑定 failure 本身不能证明是否发生过未记录的执行，v1 只认可已投影的失败尝试，
不据此宣称所有 runtime attempt 均有审计。

终态验证不读取业务报告。v1 根据 event 最后一个 namespace segment 的通用
生命周期标签 completed/failed/cancelled/needs_information 与 status 核对。
现有 ESCALATED/WAITING_EXPERT 等人类干预业务事件不能仅凭 status 自动通过；
其应用特有 label 不在本批泛化，返回 TERMINAL_EVENT_UNSUPPORTED / FAIL。
这不是新增运行状态，也不表示相应业务执行失败。

## Exact Gap Mapping and Limits

现有 gaps 是字符串，不做 substring 匹配。下面列出全部当前 Projector gap。
结构化字段优先决定直接绑定；gap 提供不能从投影值恢复的缺失来源。

| Exact gap | 固定处理 |
|---|---|
| run_start_event_missing, model_started_event_missing | 非阻塞 WARNING；关键输入/终态仍独立验证 |
| decision_observation_checkpoint_missing, decision_request_missing, retrieval_observation_checkpoint_missing, tool_observation_checkpoint_missing | 有可用输入或 reference 时非阻塞；否则 observation ERROR |
| model_inference_record_missing | 阻塞 WARNING：不能确认持久化模型记录 |
| decision_action_missing | 阻塞 WARNING，即使有 event token fallback，也无法恢复完整 decision |
| retrieval_query_missing, tool_id_missing | 按实际 action 字段验证；可用等价字段时非阻塞 |
| retrieval_result_checkpoint_missing, retrieval_evidence_missing | 阻塞 WARNING：合成空 evidence 不能证明真实结果 |
| tool_call_record_missing | 明确无 call ID 的前置 failure 时非阻塞；否则阻塞 WARNING |
| tool_result_checkpoint_missing | 有明确 audit/fact/failure 时非阻塞，否则阻塞 WARNING |
| tool_result_missing | 有明确 audit outcome 时非阻塞，否则阻塞 WARNING |
| terminal_event_missing | 按实际 terminal 独立验证；不能掩盖缺失终态 |
| retrieval_candidate_ranking_unavailable, historical_metadata_unavailable | 明确允许的非阻塞 WARNING；不要求完整历史 ranking |
| 其他未知 gap | 阻塞 WARNING / PARTIAL，不能静默宣布完整 |

Validator 检查引用形状/一致性，不重新 resolve 或重算 checksum/hash，不能证明
数据库引用存在、原始值未被篡改或完整 runtime 事件覆盖。当前初始 retrieval
query 可能没有被 Projector 从 runtime state 提取，此时 PARTIAL，不改 Projector。

## Explicit Non-goals

不计算 reward，不评价 Diagnosis，不解释 EvidenceBundle，不调用 Maintenance
Planning，不修改 AgentRun/Trajectory，不创建数据库记录，不判断 training
eligibility。PASS 是 v1 后续 Evaluation 的结构门槛，不是已交付 Evaluation、
Reward 或 RL training 的证明。

## Implementation and Verification Order

1. 写 contract 和纯内存测试，确认 Validator 缺失导致 RED。
2. 新增只读 Validator，实现五类固定规则，不修改 Projector/Runtime。
3. 测试完整 success/failure、缺口、绑定冲突、终态、纯度和 generic boundary。
4. 使用生产 SQLite records 跑 Projector → Validator，再跑现有投影回归。
5. Ruff、py_compile、focused mypy、相关离线 smoke，最后记录真实结果。
