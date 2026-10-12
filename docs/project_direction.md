# Project Evolution

更新日期：2026-10-10。当前方向是建设中的通用 Agent Harness / Agent Learning Infrastructure。现有实现以 Industrial Diagnosis 作为 reference application，并具备可复用的执行、记录、上下文、工具和模型追踪能力。Plant Disease Diagnosis 正在作为第二个 reference application 接入。

本文定义项目方向与阶段状态。当前代码结构见 [Current Architecture](current_architecture.md)，通用层与领域层规则见 [Architecture Boundary](architecture_boundary.md)，学习基础设施方向见 [Agentic RL Architecture](agentic_rl_architecture.md)。

## Phase 0 — Industrial Agent Application

早期项目围绕工业设备报障、媒体识别、诊断、维修履约和售后数据反馈组织。Agent、工具、知识和模型治理服务于这条领域流程。

[早期项目盘点](project_positioning_inventory.md)记录该阶段的源码快照；其中的能力清单、依赖和缺口属于当时状态，不作为当前产品架构。

## Phase 1 — Deindustrialization

Phase 1 清理工业履约流程耦合，将通用图执行、perception、检索 applicability、工具治理等机制与工业业务语义分开。保留 Industrial Diagnosis reference application 及其必要的领域 adapter；Maintenance Planning 作为活跃领域能力保留。

Phase 1 的结果不是所有工业代码消失，而是领域应用依赖可复用能力，通用能力不应反向依赖维护规划等领域规则。[Phase 1 Final Acceptance](deindustrialization_phase1_final_acceptance.md)第 15–16 节记录 Closure 后的结构验收 PASS；其第 1–14 节保留 Closure 前历史快照。

## Phase 2 — Agent Learning Infrastructure

Phase 2 的目标是让 Agent execution 可观察、可记录、可评价、可优化。

| 目标 | 当前能力与剩余工作 |
|---|---|
| 可观察 | 已有 AgentEvent、模型推理审计和工具调用审计。 |
| 可记录 | 已有 AgentRun、Checkpoint，以及汇集已有记录的 Trajectory Projection MVP。 |
| 可评价 | Trajectory Validation 已实现为只读结构验证 library；消费 Trajectory 的 AgentRun Evaluation 尚待实现。 |
| 可优化 | Reward Assessment 与 RL Optimization 属于后续计划。 |

### Status Definitions

- **Implemented**：存在可定位的实现。该状态不自动表示所有部署环境、任意应用或训练用途均已验收。
- **In Progress**：按当前阶段安排推进的工作项；是否存在代码需单独说明。
- **Planned**：后续方向，尚未交付对应的 AgentRun trajectory 链路。

### Current Stage

| 能力 | 状态 | 当前证据 / 边界 |
|---|---|---|
| Agent Runtime、AgentRun / AgentEvent、Checkpoint | Implemented | `agent/graph.py`、`agent/events.py`、`agent/checkpoints.py`；生产领域实现为 `DiagnosisRuntime`。 |
| Multimodal perception、Evidence provenance | Implemented | 通用 perception 与工业 Recognition/Evidence adapter 分开；provenance 保留到诊断引用链。 |
| Retrieval、Tool execution、Model tracking | Implemented | HybridRetriever、ToolGateway、ModelInferenceRecord；复用范围仍受当前 adapter 和事件约定限制。 |
| Trajectory Projection MVP — Phase 2A.1 | Implemented | [trajectory.py](../src/industrial_ops_agent/agent/trajectory.py)实现 AgentRun → read-side projector → Trajectory。 |
| Trajectory Validation — Phase 2A.2 | Implemented | [trajectory_validation.py](../src/industrial_ops_agent/agent/trajectory_validation.py)在内存中只读检查 Trajectory；不写数据库、不自动运行，也不代表 AgentRun Evaluation、Reward 或训练资格。 |
| AgentRun Evaluation | Planned | 尚无消费新 Trajectory 的通用运行评测链路；已有模型/组件评测不能替代该能力。 |
| Reward Assessment | Planned | 尚无绑定该 Trajectory 的领域 reward 评估链路。 |
| RL Optimization | Planned | 尚无从 AgentRun trajectory 数据到策略改进的已证实闭环。 |
| Maintenance Planning | Optional retained reference-domain capability | API、workflow 与 domain implementation 保留；默认 feature flag 关闭。它不是 generic core capability，council E2E 未纳入本次验收。 |
| Plant Disease Diagnosis | In Progress | PlantDoc 导入器与候选清单检查已实现，600 张图片、2,130 个原始标注框、29 个原始类别；suite/policy 独立审核合同已实现。公开来源尚未提交，通用来源快照、发布前候选 VLM 评测、Plant Disease runtime 和页面尚未实现。Model Gateway 的 `none` / `bearer` 认证配置已经实现，尚无真实 Ollama Gateway release。状态与边界见 [Portfolio Demo 记录](plant_disease_portfolio_demo.md)。 |

目前可声明 Trajectory Projection MVP 与 Trajectory Validation 已实现。Validation 是显式调用的 read-only library，不是自动 production pipeline。完整 Agentic RL readiness 仍需后续 Evaluation 和 Reward 工作提供证据；Agentic RL 训练闭环尚未实现。

本 milestone 的代码/结构验收见 [Project Final Acceptance](project_final_acceptance.md)。部署及外部服务验收状态单独列明，不由离线测试推定。

## Scope of the Direction

通用层负责执行机制、记录与未来学习接口。领域应用负责业务输入、证据授权语义、结果契约和领域评价。未来新增应用应通过 adapter 和显式 composition root 使用通用层。

本方向不将现有 Diagnosis 契约提升为通用训练契约，也不将已有模型训练模块视为 AgentRun 学习闭环的证明。历史 audit、batch report、spec 和 plan 保留其原始事实与阶段结论。
