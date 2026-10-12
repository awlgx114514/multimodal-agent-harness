# Agentic RL Architecture

更新日期：2026-10-04。本文描述 Agent Learning Infrastructure 的现有基础与后续方向。**Current** 表示已有实现，**In Progress** 表示当前推进工作项且注明代码状态，**Planned** 表示尚未交付的方向。

项目处于通用 Agent Harness 建设阶段。完整 Agentic RL readiness 尚未完成，当前没有从 AgentRun Trajectory 到策略优化的已证实 RL loop。

## Current State

状态：**Implemented — Agent Runtime + Trajectory Projection MVP + Trajectory Validation library**。

```text
Agent Runtime
        ↓
Persisted AgentRun / Events / Checkpoints / Records
        ↓
Trajectory Projection MVP
        ↓
Trajectory
        ↓
Trajectory Validation (explicit, read-only call)
```

执行层产生运行、事件、检查点、模型推理和工具审计记录。[TrajectoryProjector](../src/industrial_ops_agent/agent/trajectory.py)在读侧关联这些记录，投影出 model decision、retrieval、tool 步骤与已有终态。Projector 不参与 runtime execution，不执行训练、不计算 reward，也不写入新 trajectory 表。

observation、action 与 result 只能从已有持久化内容恢复。当前可关联 checkpoint ID/sequence/checksum、inference ID/response hash、模型 release/manifest、tool call ID与元数据。完整工具参数/输出、完整检索候选、所有失败尝试或任意 graph 的投影并无完整性保证；`gaps` 是数据缺口提示，尚不是独立 Validation 结果。

现有生产应用仍是 Industrial Diagnosis；通用边界与领域 ownership 见 [Architecture Boundary](architecture_boundary.md)。Trajectory Validation 是纯内存 read-only library，不自动运行、不改变 Agent runtime，也不生成可训练数据。现有模型评测和训练模块并未证明它们已经消费该 Trajectory。

## Next Steps

```text
Trajectory                 [Implemented: projection MVP output]
        ↓
Trajectory Validation      [Implemented: explicit read-only library]
        ↓
AgentRun Evaluation        [Planned]
        ↓
Reward Assessment          [Planned]
```

| 工作项 | 状态 | 预期职责与验收关注点 |
|---|---|---|
| Trajectory Validation | Implemented | 纯内存验证 STRUCTURE、OBSERVATION_BINDING、ACTION_BINDING、RESULT_BINDING、TERMINAL 五类；输出结构质量与 `evaluation_eligible`，不评价 Agent/Diagnosis 质量，不计算 reward 或 training eligibility。 |
| AgentRun Evaluation | Planned | 消费轨迹及允许的证据，形成可追溯的运行评价；业务正确性由 domain evaluator 解释。 |
| Reward Assessment | Planned | 将评价、领域结果和人类反馈按领域规则解释为 reward，保留来源与适用范围。 |

以上职责是方向约束，不是新 schema、存储迁移或接口签名设计。现有报告和人工确认状态不能直接等同于学习 reward；generic core 不读取 DiagnosisReport 或 Maintenance policy 来硬编码评分。

AgentRun Evaluation 与 Reward Assessment 尚未交付，因此不能把 projection/validation 输出声明为已评价的 trajectory dataset 或可直接使用的 RL 训练样本。Validation PASS 只表示其 v1 结构检查规则通过。

## Future

状态：**Planned**。

```text
Trajectory Dataset
        ↓
Policy Optimization
        ↓
Agent Improvement
```

Future sections are planned directions, not implemented capabilities。

未来 Trajectory Dataset 应以已验证的轨迹与可追溯评价为基础；当前没有该数据集交付。Policy Optimization 只有在输入、评价和 reward 边界得到验证后，才可能使用这些记录改善策略。Agent Improvement 应由运行评价证据证明，不能由训练入口存在、模型版本变化或完成一次投影推定。

本文不选择训练算法或引入 trainer 实现。后续工作需继续遵守 [项目方向](project_direction.md)与通用层/领域层边界，并区分现有能力、进行中工作项和未来计划。
