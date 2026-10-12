# Project Direction Audit

审计日期：2026-09-29。范围：仓库根目录说明、`docs/` 下全部 31 份 Markdown（含 plans、specs、reports、follow-ups）及与定位有关的生产代码入口；`docs/m5-release/` 的 3 个 JSON 和 2 个 JSONL 仅作为历史评测样例识别。本审计是静态阅读，未重新运行产品部署或验收脚本。除本报告外未修改任何文件。

## 1. Executive Summary

**文档定位与当前阶段不一致。** 根目录 `README.md` 仍以“企业级多模态工业设备智能运维与售后 Agent 平台”为项目定义，描述了 Phase 1 已删除的履约、预测维护、GraphRAG、现场实时会话和事件管线。`pyproject.toml:8` 的项目描述也保留旧称谓。这些是当前入口残留，不应由历史报告中的旧描述来判断现状。

**代码状态需要准确限定。** Phase 1 的最终验收在 `deindustrialization_phase1_final_acceptance.md` 第 15–16 节记录为 PASS；保留 Industrial Diagnosis 和 Maintenance Planning 作为领域侧能力。`agent/trajectory.py` 已有只读 `TrajectoryProjector`，可按 `AgentRun` 汇集事件、检查点、模型推理及工具审计，形成第一版 `Trajectory`。但生产 Agent 决策仍在 `DiagnosisRuntime`，仓库未显示该 Trajectory 接入验证、AgentRun 评测、领域 reward 或 RL 优化的闭环。现有 `evaluation/` 和 `training/` 的评测、PPO/GRPO/reward 实现不能直接算作该闭环。

**定位结论：**“通用 Agent Harness / Agent Learning Infrastructure”是正在推进的项目方向；当前可证实的是通用能力边界、一个工业诊断 reference application，以及 Trajectory Projection MVP。不能写成已有第二个 reference application、通用 Agent 训练环境或已完成 Agentic RL readiness。

## 2. Current Project Position

| 阶段 | 证据支持的表述 | 边界 |
|---|---|---|
| 原始工业应用 | `README.md:1-3`、`project_positioning_inventory.md:72-107` 记录工业运维/售后定位。 | 这是历史来源，不能继续当作当下完整产品清单。 |
| Phase 1 后 | `deindustrialization_phase1_final_acceptance.md:315-395` 记录 Closure 后 PASS；`multimodal/processor.py`、`knowledge/retrieval.py`、`tools/gateway.py` 与 Diagnosis adapter 并存。 | 核心能力逐步中性化；保留的工业诊断与维护规划仍是领域应用，不能宣称整仓无工业代码。 |
| 当前 Phase 2A.1 | `agent/trajectory.py:82-144` 的只读 projector 将同一 AgentRun 的持久化记录投影为步骤与终态，缺失信息标为 `gaps`。 | MVP 是投影能力，不是经过验证的训练样本格式，也未产生 reward。 |
| 后续方向 | 拟建立 Trajectory Validation → AgentRun Evaluation → Reward Assessment → Future RL Optimization。 | 这些是计划；已有模型评测/训练代码与 AgentRun Trajectory 尚未形成已证实连接。 |

### 主要入口文档分类

分类：A = 符合当前定位；B = 历史记录，保留原文；C = 现行入口定位过旧，后续更新；D = 缺失，应新增。

| 文件 | 当前项目定位 | 分类 / 是否符合当前阶段 | 建议 |
|---|---|---|---|
| `README.md` | 工业设备智能运维与售后全栈平台。 | C / 否 | 将现行简介、能力清单、架构图、阅读导航和状态改为当前可证实的能力；工业诊断放在 reference application。 |
| `pyproject.toml` 的 `description` | 同一旧产品描述。 | C / 否 | 后续与 README 统一元数据；本次不改配置。 |
| `docs/deindustrialization_phase1_final_acceptance.md` | Phase 1 结构验收。 | B / 作为历史验收符合用途 | 保留原貌；新入口明确“第 1–14 节是 Closure 前快照，第 15–16 节是最终 PASS”，不能摘引早期 FAIL 作为现状。 |
| `docs/project_positioning_inventory.md` | 基于早期 ZIP 的工业应用盘点。 | B / 不适合作为现行总览 | 保留原时间与证据边界；它列出的 GraphRAG、预测维护和“无 tests”均是当时快照。 |
| `docs/project_readiness_report.md` | Batch 3C 时期求职/演示就绪评估。 | B / 不适合作为现行状态 | 保留历史结论，不直接改写其中当时的未验证项；新总览另给当前状态。 |
| `docs/domain_isolation_audit.md`、`docs/deindustrialization_manifest.md` | Phase 1 执行前依赖与去工业化方案。 | B / 作为决策来源符合用途 | 保留原候选、UNKNOWN 与删除顺序，不当作今日运行架构。 |
| `docs/agentic_rl_readiness_audit.md`、`docs/agentic_rl_trajectory_readiness_audit.md` | 2026-09-25/27 的只读 readiness 快照。 | B / 当时结论有价值 | 保留“尚无 trajectory”之类当时判断；新架构文档须注明 Phase 2A.1 的 MVP 后续变化。 |
| 当前项目方向与现行架构入口 | 无独立现行文档。 | D / 否 | 见第 6 节。 |

## 3. Documentation Classification

### 架构覆盖与概念问题

| 能力 | 代码证据 | 现行文档覆盖 | 判断 |
|---|---|---|---|
| Agent Runtime、AgentRun、AgentEvent、Checkpoint | `agent/graph.py`、`agent/diagnosis_runtime.py`、`agent/events.py`、`agent/checkpoints.py`、`persistence/models.py:1968-2010`。 | README 侧重诊断流程；两份 RL 审计记录生命周期和限制。 | 有分散说明，缺当前架构入口。 |
| Multimodal perception 与 Evidence provenance | `multimodal/models.py:192`、`multimodal/processor.py`、`industrial_recognition/evidence.py:489`；Batch 2A/2A.2 报告。 | 历史迁移/验收写得较详细。 | 需在当前架构总览中区分通用 perception 与工业 EvidenceBundle ownership。 |
| Retrieval、Tool execution | `knowledge/retrieval.py:87`、`tools/gateway.py:68`；Batch 2B/2C 报告。 | README 仍列 GraphRAG、履约工具与旧副作用链。 | 当前说明须按保留的检索、只读工具及 domain catalog 重写。 |
| Model tracking | `persistence/models.py:3609` 的 `ModelInferenceRecord`；RL readiness audit。 | 审计中有模型 release/hash 证据，README 未与 AgentRun 轨迹关联。 | 补现行引用关系和已知缺口。 |
| Trajectory Projection | `agent/trajectory.py:24-144` 的 `Trajectory`、`TrajectoryStep`、`TrajectoryProjector`。 | README 与已有 RL 审计均早于 MVP，没有当前用法/限制说明。 | 当前文档缺失；不能把 checkpoint 快照误称稳定训练数据契约。 |
| Evaluation / Reward | `evaluation/runner.py`、`evaluation/backend.py`、`training/reward_contracts.py` 是已有评测/训练组件。 | README 用“训练 / 评测 / 发布”描述模型生命周期。 | 需明确尚未接入 AgentRun Trajectory 的验证、评测、reward 闭环。 |

| 当前描述 | 问题 | 推荐方向 |
|---|---|---|
| README “报障 → 维修履约 → 售后反馈”作为整体项目闭环（`README.md:1-3,120-126`）。 | Phase 1 删除了多项履约域；这些流程不再代表默认产品。 | 以现存 generic capabilities、工业诊断 reference application 和学习基础设施进度组织总览。 |
| README 架构图写“报障、工单、知识、审批、发布”（`README.md:54-101`）。 | 遗漏事件/检查点 → Trajectory 投影；混入已删除的工单履约。 | 画出 AgentRun、AgentEvent、Checkpoint、ModelInference、ToolCall 到只读 projector 的关系；领域侧独立标示。 |
| README 能力和目录表包含 GraphRAG、predictive、portal、supplier、`realtime_media/` 等（`README.md:29-40,181-198,202-218`）。 | 与 Batch 3A–3E 删除报告和 Phase 1 最终验收冲突。 | 按当前源码/API 清点后修订；保留 Maintenance Planning、Device Family 等实际仍存在的领域能力。 |
| README 实时/扩展描述 `compose.realtime.yaml`、GraphRAG 与 Kafka/RUL（`README.md:555-587`）。 | 与当前仓库文件清单和 Batch 3D/3E 状态不符。 | 后续逐项核对当前部署入口；已删除能力只在历史报告中保留。 |
| 旧 RL 审计表述“没有 trajectory contract”。 | 在审计当时成立，但 Phase 2A.1 已新增 projector。 | 新文档写“已有投影 MVP；独立验证、可训练样本、reward 与优化尚未建立”，并链接原审计作为历史。 |
| `project_readiness_report.md` 称预测维护/GraphRAG 尚在，并称无当前 RL 能力。 | 前者是 Batch 3C 快照；后者需与投影 MVP 现状区分。 | 不回改历史报告；在现行状态页注明日期和适用范围。 |

## 4. Documents To Keep

| 文档 | 类型 | 处理建议 |
|---|---|---|
| `docs/deindustrialization_batch1_report.md`、`docs/deindustrialization_batch2_report.md`、`docs/deindustrialization_batch3a_report.md` 至 `batch3e_report.md` | Batch 1/2/3 迁移、smoke、schema 与验收记录 | 原文保留；其分批 PASS/FAIL 只对应当批时间点，当前入口应指向 Phase 1 Closure 最终判定。 |
| `docs/deindustrialization_phase1_final_acceptance.md` | Phase 1 验收与 Closure 重验 | 原文保留；第 1–14 节为旧失败快照，第 15–16 节为最终状态。 |
| `docs/deindustrialization_batch1_followups.md`、`batch2_followups.md`、`batch3d_followups.md` | 当时的 follow-up 列表 | 原文保留；其中“Batch 3E remains unopened”等是历史状态，不作当前待办。 |
| `docs/deindustrialization_batch2a_recognition_migration_audit.md`、`batch2a2_evidence_provenance_audit.md`、`batch3a_inventory.md`、`deindustrialization_unknown_resolution.md` | 执行前审计、决策与库存 | 原文保留；只作为演进证据。 |
| `docs/domain_isolation_audit.md`、`deindustrialization_manifest.md`、`docs/project_positioning_inventory.md`、`docs/project_readiness_report.md` | 早期盘点/定位/准备度快照 | 原文保留；不可当作现行架构规范。 |
| `docs/agentic_rl_readiness_audit.md`、`agentic_rl_trajectory_readiness_audit.md` | Phase 2A.1 前只读 RL 审计 | 原文保留；引用时标明它们早于 Trajectory Projection MVP。 |
| `docs/plans/`、`docs/superpowers/plans/`、`docs/superpowers/specs/` 下的 8 份 plan 与 2 份 spec | Phase 1 设计与实施计划 | 原文保留；计划中的未来式/停止条件不是今日状态。 |
| `docs/m5-release/` 下 3 个 JSON 和 2 个 JSONL | 模型/评测历史样例 | 保留；不将样例视为 AgentRun trajectory 或 reward 证据。 |

以上文档均不建议删除或整体重写。历史 migration 也应作为数据库演进证据保留。

## 5. Documents To Update

### README 专项审计

| 部分 | 当前内容 | 问题 | 后续修改方向 |
|---|---|---|---|
| 项目简介 `:1-3` | 工业设备售后全栈平台。 | 将历史产品与当前项目方向混为一体。 | 明确当前已实现的通用能力和保留的 Industrial Diagnosis reference application；“Agent Learning Infrastructure”标为建设方向。 |
| Architecture overview `:46-133` | 业务后端、Temporal、模型服务、工单/数据反馈闭环。 | 遗漏 Trajectory Projector、事件/检查点关联；含已删除业务链。 | 展示目前 AgentRun → event/checkpoint/inference/tool → Trajectory 的读侧架构，以及 domain adapter 边界。 |
| Features / code map `:25-43,177-255` | GraphRAG、预测维护、客户门户、供应商、工单履约及旧路径。 | 大量入口不再 active；当前能力清单不可依赖。 | 对照源码和生成 OpenAPI 重做能力/路径库存；把现有维护规划明确归为领域侧保留能力。 |
| Roadmap / learning direction | 无独立当前路线；训练章节主要是模型制品生命周期。 | 读者容易将已有 PPO/GRPO/评测误读成 AgentRun 强化学习闭环。 | 加极简状态表：投影 MVP 已实现；Trajectory Validation、AgentRun Evaluation、Reward Interface/Assessment、RL optimization 计划中。 |
| Current status / verification | 以旧部署和业务操作说明为主。 | 缺 Phase 1 Closure PASS 与 Phase 2A.1 MVP 的证据边界。 | 引用最终验收与 Trajectory 测试，同时区分 synthetic/service smoke 与完整产品部署验证。 |

根目录没有第二份可作为现行项目说明的 Markdown；`pyproject.toml` 的旧 `description` 需在后续文档/元数据同步阶段处理。本次均未修改。

## 6. Missing Documents

| 建议新增的文档 | 应说明的事实与边界 | 当前缺口 |
|---|---|---|
| `docs/project_direction.md` | Industrial Agent → 去工业化后的通用能力平台 → Agent Harness / Agent Learning Infrastructure 方向；一张“已实现 / 进行中 / 计划”状态表。 | 没有现行、可引用的项目定位来源。 |
| `docs/current_architecture.md` | Agent Runtime、AgentRun/Event/Checkpoint、Multimodal perception、Evidence provenance、Retrieval、ToolGateway、ModelInference、Trajectory Projector 的真实依赖与数据流；Industrial Diagnosis 为 reference application。 | README 架构图过旧，Batch 报告分散。 |
| `docs/agentic_rl_architecture.md` | 目标链：Agent Runtime → Trajectory Projection → Trajectory Validation → Evaluation → Reward Assessment → Future RL Optimization；逐项标注状态、证据、尚缺信息。 | 当前只有 readiness audit；尚无 Phase 2A.1 之后的方向说明。不得写成已有 Agentic RL 训练闭环。 |
| `docs/architecture_boundary.md` | Generic Core 可持有 AgentRun、Trajectory、未来 evaluation interface/reward contract；Domain Adapter 负责 Diagnosis evaluator、domain reward、人类反馈解释，且不得把 Diagnosis/Maintenance/EvidenceBundle 语义移回 core。 | Phase 1 文档涉及边界，但缺当前 Learning Layer 的明确 ownership。未来接口不得描述为已实现。 |
| `docs/trajectory_projection_mvp.md`（可合并到现行架构文档） | 只读投影的输入、步骤类型、记录引用、`gaps`、已知不可恢复项、测试范围和调用方式。 | 新代码已存在，现行说明仍停在投影前审计。 |

这些是文档缺口清单，不是本次新增文档或功能承诺。

## 7. Recommended Documentation Update Order

1. 先写 `project_direction.md`，固定当前事实、目标和状态用语，避免 README 再次把计划写成实现。
2. 写 `current_architecture.md` 并纳入 Trajectory Projection MVP；核实当前路由/进程/模型依赖后再描述部署能力。
3. 写 `architecture_boundary.md`；明确通用记录与工业 reference application 的 ownership。
4. 写 `agentic_rl_architecture.md`，把 validation、evaluation、reward 和优化标为尚待设计/实施的阶段。
5. 最后更新 README 与项目元数据，并链接现行文档和 Phase 1 历史验收；保持历史审计与迁移报告原文。

## 8. Risks If Documentation Is Not Updated

1. **误导使用者：** README 把已删除的路由、服务和数据管线当作当前能力，造成无效部署和错误集成判断。
2. **架构误判：** 读者从旧总览看不到 AgentRun → Trajectory 投影，也可能误以为 Industrial Diagnosis/EvidenceBundle 已完全通用化。
3. **RL 能力夸大：** 将现有 PPO/GRPO 或模型评测与 AgentRun 轨迹闭环混同，会把尚无验证、reward 和优化接线的方向表述为已完成。
4. **历史结论误用：** Phase 1 最终验收文档前半部保留 Closure 前 FAIL；不标注章节范围会与最后 PASS 冲突。旧 follow-up/审计中的“未开始”“不存在 trajectory”也会被当作实时状态。
5. **设计边界漂移：** 若缺现行 ownership 文档，后续 Evaluation/Reward 接口容易直接引用 Diagnosis、Maintenance 或 EvidenceBundle，重新引入领域反向依赖。
