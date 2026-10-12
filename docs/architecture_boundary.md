# Architecture Boundary

更新日期：2026-10-04。本文冻结新增 Learning Layer 能力的通用层/领域层 ownership 规则，延续 Phase 1 deindustrialization 的依赖方向。它是架构约束，不能代替当前代码说明或宣称所有历史模块已经完成物理拆包。

当前实现依据见 [Current Architecture](current_architecture.md)。新接口只有落地并得到验证后，才能从 Planned 改为 Implemented。

## Generic Core

通用层可以包含执行记录、稳定引用、投影机制以及后续评价接口。下表的“允许”不代表对应接口均已实现。

| 允许的能力 | 状态 | Ownership |
|---|---|---|
| AgentRun、AgentEvent | Implemented | 运行身份、状态记录、顺序事件与原始 payload。 |
| Checkpoint reference | Implemented | 记录 ID、sequence、checksum 与图版本绑定；不在通用层推导领域状态。 |
| Trajectory、TrajectoryProjector | Implemented | 汇集已有执行记录，关联 observation/action/result 和已有引用。 |
| Trajectory Validation | Implemented | 纯内存、只读地检查 Trajectory 结构、引用和记录绑定；不调用 runtime、不修改数据、不代表 Evaluation/Reward/训练资格。 |
| Evaluation interface | Planned | 未来接受通用轨迹/引用并返回评价结果的接口；具体领域正确性由 adapter 判断。 |
| Reward contract | Planned | 未来表达 reward 来源与评价绑定的通用契约；不内置工业评分规则。 |

通用层禁止依赖或解释：

- `DiagnosisReport` 及 Diagnosis 的结论、诊断状态和领域评分规则。
- `EvidenceBundle`、工业 finding 类型、确认规则和自动化资格。
- Maintenance Planning 的 policy、records、assignment、council、evaluation。
- Asset model、设备族/型号以及工业实体规则。
- 作为通用接口字段、校验分支或优化目标的工业术语。

通用层可以保留调用者提供的 opaque payload 或 source reference。payload 中含领域内容，不授予通用层解释该内容的权限；例如 Projector 保留已有 response JSON，不能据其中的诊断报告判定业务成功或 reward。

## Domain Adapter

adapter 拥有领域输入/输出解释，将领域数据转换为通用层可接收的引用或 payload。具体职责如下。

| 职责 | 状态 | 说明 |
|---|---|---|
| Recognition / Diagnosis evidence adapter | Implemented | [DiagnosisEvidenceResolver](../src/industrial_ops_agent/industrial_recognition/diagnosis_evidence.py)读取持久化 EvidenceBundle/finding，检查确认与版本，并提供 Agent evidence context。 |
| Diagnosis runtime / tool catalog | Implemented | [DiagnosisRuntime](../src/industrial_ops_agent/agent/diagnosis_runtime.py)及 Diagnosis catalog 拥有领域决策契约、工业上下文和可用工具集。 |
| Diagnosis evaluator | Planned | 判断诊断结论、证据支持、引用与缺失信息的领域含义；尚未接入新 Trajectory 评价链路。 |
| Domain reward | Planned | 根据领域评价与外部结果定义评分，不能通过 generic core 硬编码诊断分数。 |
| Human feedback interpretation | Planned（Trajectory 链路） | 当前已有业务人工确认/反馈；将其映射为 trajectory evaluation/reward 的解释尚未实现。 |

领域语义的解释必须留在 adapter；只能向通用层提供约定的引用或数据，不能重新成为 generic core 的业务判断逻辑。

## Dependency Direction and Composition

```text
Domain application / adapter
        ↓
Generic execution and trajectory capability

Composition root
        → generic interface
        → domain implementation
```

dependency 允许 domain → generic；禁止 generic → Diagnosis/Maintenance 业务实现。未来 evaluator/reward 的领域实现通过显式 composition root 接入通用接口，不由通用层解析具体领域报告。

composition root 可以知道 domain。当前例子包括 [runtime.py](../src/industrial_ops_agent/runtime.py)、[tools/diagnosis_composition.py](../src/industrial_ops_agent/tools/diagnosis_composition.py)、[orchestration/runner.py](../src/industrial_ops_agent/orchestration/runner.py)和 [orchestration/entrypoint.py](../src/industrial_ops_agent/orchestration/entrypoint.py)。`orchestration/runner.py`组装当前 Reference Application 的 Recognition、Diagnosis 与 Knowledge worker activities；`orchestration/workflows.py`声明这些应用 workflow/activity contracts。它们是应用编排/装配，不是可复用的 generic orchestration engine。不得用 re-export、alias 或 facade 把 domain 依赖伪装成通用机制。

## Current Layout and Known Limits

当前 ownership 是按能力定义的，不是按目录整体认定。`agent/graph.py` 的图机制可复用，但同目录中的 `diagnosis_runtime.py` 和 `models.py` 的 DiagnosisManifest/DiagnosisReport 属于 reference application。

现有 SQLAlchemy 模型集中定义通用与领域 records，`ModelInferenceRecord` 仍有可选 Diagnosis 关联字段。本文不要求本批修改这些存储结构；generic projection 不据该字段解释工业语义，也不因此获得依赖 EvidenceBundle 或 Maintenance 规则的许可。

Trajectory Projection 与 Validation 均已实现为显式调用的 read-side library；没有自动生产生成/验证 pipeline。Projector 仍依赖当前节点/事件约定，并传递已有 JSON。该现状不等于已经完成任意应用适配或完整训练契约；第二个应用的适配尚未实现。

Knowledge 的通用检索 core（`knowledge/retrieval.py`、`knowledge/applicability.py` 与 `knowledge/ingestion.py`）不导入 Industrial Recognition。`knowledge/files.py`承载现有 Industrial 文件摄取字段（device family/model）并调用 `industrial_recognition.knowledge_applicability` 转换 legacy 输入；`knowledge/seed.py`是 Industrial synthetic fixture。它们是当前 Reference Application 的摄取/fixture 边界，不作为 generic retrieval core；文件位置共用 `knowledge/` 包并不改变其领域语义，也不表示第二应用复用已验证。

Maintenance Planning 是 optional retained reference-domain capability；其默认开关 `multi_agent_planning_enabled` 为 `false`。API 与 workflow 仍存在，但 council E2E 不属于本次 generic-core 验收。

## Relationship to Phase 1

[Phase 1 Final Acceptance](deindustrialization_phase1_final_acceptance.md)第 15–16 节记录 Maintenance Planning reverse dependency 的 Closure 结果。Learning Layer 延续同一原则：保留领域行为，把领域策略留在 adapter，通过通用机制与显式装配复用能力。

结构引用验证与领域正确性必须分开：前者由当前通用 Trajectory Validation library 执行；后者仍属于未来 domain evaluator/reward。Validation 已实现不等同于领域质量评测或 reward 已交付。
