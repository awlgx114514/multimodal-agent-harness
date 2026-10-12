# Phase 2A.2 Trajectory Validation Report

日期：2026-10-01。工作副本：`D:\Microsoft\Large-Model-Application-main-batch1`。

## 1. Scope

在现有 Trajectory Projection MVP 后新增纯内存、只读 Validation Layer：

```text
AgentRun → TrajectoryProjector → Trajectory
                               → TrajectoryValidator → TrajectoryValidationReport
```

只新增以下四个文件，没有修改现有 Projector、Trajectory model、Runtime、graph、
retrieval、ToolGateway、Multimodal、数据库模型/迁移、README 或既有阶段文档。

- `src/industrial_ops_agent/agent/trajectory_validation.py`
- `tests/agent/test_trajectory_validation.py`
- `docs/trajectory_validation_contract.md`
- `docs/trajectory_validation_phase2a2_report.md`

## 2. Contract

先交付 [Trajectory Validation Contract v1](trajectory_validation_contract.md)，再写测试
和实现。输入是现有 `Trajectory`；接口为
`TrajectoryValidator().validate(trajectory)`。不需要 database、tenant context、
model provider、tool adapter 或应用服务。

输出包含 agent_run_id、固定五类 checks、稳定 issue code、severity、是否阻塞
Evaluation、step index/event ID、可用 source reference、quality 和 evaluation_eligible。
`contract_version = trajectory-validation/v1`；不提供 training_eligible。

Trajectory Validation != Agent Evaluation。

Trajectory Validation != Reward。

Trajectory Validation != Training Eligibility。

## 3. Implementation

沿用 frozen/slots dataclass 风格，定义 TrajectoryQuality、ValidationSeverity、
ValidationIssue、ValidationCheckResult、TrajectoryValidationReport。
Validator 无持久化成员和外部调用，每次验证只分配本地 issue accumulator。

五类检查分别核对结构、输入绑定、action、result、terminal。所有 JSON 仅检查
通用 action token、identity 和记录容器，不解释 report、evidence、工具 values
里的领域含义。保留原始输入，不补写 call ID、query、result 或 terminal。

gaps 使用精确映射，覆盖当前 Projector 的全部 16 个 gap，以及两个明确允许的
非关键限制标签。未知 gap 为阻塞 WARNING；不根据 substring 或 gaps 非空与否
统一判 FAIL。测试通过 AST 核对 Projector 当前 gap 清单与预期规则清单相等。

## 4. Quality Rules

| 判定 | v1 规则 | Evaluation eligible |
|---|---|---|
| PASS | 无 ERROR、无阻塞 WARNING；允许不影响 attribution 的限制 | true |
| PARTIAL | 无 ERROR，但 attribution/记录来源缺失 | false |
| FAIL | 身份、顺序、关键输入或终态不可解释/矛盾 | false |

完整记录的失败 tool + FAILED run 为 PASS。工具缺少任何结果为 PARTIAL，不把
failure 本身当质量错误。缺少 observation 且无可用 reference 固定为 FAIL。
真实空 retrieval evidence 有效；因 Projector 缺失记录而合成的空列表不等价，
缺失 gap 导致 PARTIAL。

终态不能仅相信 Projector 复制的 AgentRun status。v1 核对已存在的通用生命周期
event label completed/failed/cancelled/needs_information。没有终态、矛盾终态、
将 graph_node_completed 当作终态均 FAIL。应用特有的人类干预事件不读取领域报告
来猜测，返回明确 TERMINAL_EVENT_UNSUPPORTED；边界见第 7 节。

## 5. Test Matrix

新增 27 个 unittest test methods（包含参数化 subtests），现有投影测试 3 个保留。

| 覆盖项 | 结果 / 固定期望 |
|---|---|
| 完整 success | PASS、eligible=true |
| 完整 failed execution | PASS、eligible=true；failure != bad trajectory |
| 排名/历史 metadata 非关键限制 | 非阻塞 WARNING、PASS |
| 三种 step 均缺少 observation 和 reference | FAIL |
| checkpoint-only observation | PASS |
| 有 call 但没有 tool result | PARTIAL |
| 无 call ID 的明确 failure attempt | PASS，不伪造 call ID |
| 成功 fact 无 call identity | PARTIAL |
| 仅有身份的 tool fact | PARTIAL，不算 execution result |
| SUCCEEDED/FAILED/REJECTED/CANCELLED audit outcome | 明确 outcome 可作为有效结果 |
| 缺少 model/retrieval result | PARTIAL |
| terminal 缺失/状态矛盾/错误 label/序号冲突 | FAIL |
| CANCELLED/NEEDS_INFORMATION | 与对应 event 相符时 PASS |
| 非法序号、重复 event/inference/call identity、未知 kind/action | FAIL |
| request/tool identity 或 checkpoint ID/sequence/checksum 冲突 | FAIL |
| inference ID/hash、query、checkpoint checksum 缺失 | PARTIAL |
| 当前全部 16 个 Projector gap | 精确规则验证；无未知映射 |
| 未知 gap 与伪造 substring 相似 gap | PARTIAL，不能借关键词降级为可接受限制 |
| start metadata 缺失、核心绑定完整 | 非阻塞 WARNING、PASS |
| 应用特有 human intervention label | 明确 FAIL / unsupported，不从 status 猜测 |
| 领域 JSON、输入不变、重复验证、无 training_eligible | PASS |
| direct import boundary | 仅依赖现有 trajectory 与标准库 |
| persisted records → Projector → Validator | 生产 SQLite models；PASS，run version/sequence 与 event/checkpoint 数量不变 |

TDD 证据：实现前新测试 import 因 Validator 模块不存在失败（exit 1）；实现后
转 GREEN。补充的“身份-only fact”“同 sequence 不同 checkpoint”和 terminal
issue source reference 测试先出现 2 FAIL + 1 ERROR，再最小修复，全部 GREEN。
既有 Projection 测试未修改。

## 6. Boundary Verification

Validator 直接 project import 只有 `industrial_ops_agent.agent.trajectory`。
不 import DiagnosisReport、EvidenceBundle、Maintenance Planning、asset business
rules；不使用领域 status/report 内容决定 trajectory 质量。学习层输入中已有的
领域 JSON 保持 opaque。

只读性同时由实现检查、输入 deep-copy equality、重复验证结果 equality 和生产
SQLite records 集成测试验证。不调用数据库 resolver、模型、检索、工具或 graph。

原 trajectory 模块导入集中 persistence models 的布局是既有事实；本批未进行
物理拆包，也不把该既有依赖误称为完全独立于 persistence 的模块 import。

## 7. Known Limitations

1. v1 验证的是现有投影对象，不证明所有事件、重试和失败尝试均被 Projector 覆盖。
2. Reference/hash 只验证存在性形状与内部一致性，不重新 resolve 数据库记录或重算
   hash；PASS 不是完整回放、数据真实性证明或 training eligibility。
3. 现有初始 retrieval 可能在 runtime state.retrieval_query 中保存 query，而
   Projector 只提取 decision.query；投影缺少 query 时 PARTIAL。本批不改 Projector。
4. 完整候选历史 ranking、完整工具输入/输出、完整 prompt 不是 v1 要求。
5. WAITING_EXPERT/ESCALATED 及 expert_revision_completed 等应用特有终态 label
   无通用状态绑定可供本批可靠解释，返回 unsupported / FAIL；不是说这些业务执行
   不合法，也未在 generic validator 内加入 Diagnosis 特例或 facade。
6. 无 call ID 的 failure attempt 无法证明其前后边界是否发生过未投影的 execution；
   只接受当前已记录的 observation/action/failure，不虚构 execution record。
7. 输入限定为现有 typed Trajectory dataclasses，不提供任意 JSON schema 校验。
8. 四份方向/架构文档的既有状态快照本批未改；新增报告记录本批交付状态。

## 8. Verification Results

在仓库已有 `.venv` 中执行，不安装依赖。测试沿用现有 unittest 风格。

| Command | 实际结果 |
|---|---|
| `.venv\Scripts\python.exe -m unittest discover -s tests/agent -p test_trajectory_validation.py -v` | 27 validation tests PASS |
| `.venv\Scripts\python.exe -m unittest discover -s tests/agent -p test_trajectory_projection.py -v` | 3 existing projection tests PASS |
| `.venv\Scripts\python.exe -m unittest discover -s tests/agent -v` | 30 focused agent tests PASS |
| `.venv\Scripts\python.exe -m ruff check src/industrial_ops_agent/agent/trajectory_validation.py tests/agent/test_trajectory_validation.py` | PASS |
| `.venv\Scripts\python.exe -m py_compile src/industrial_ops_agent/agent/trajectory_validation.py tests/agent/test_trajectory_validation.py` | PASS |
| `.venv\Scripts\python.exe -m mypy --follow-imports=silent src/industrial_ops_agent/agent/trajectory.py src/industrial_ops_agent/agent/trajectory_validation.py` | PASS — 2 source files；不宣称全仓 mypy 已通过 |

以下 8 个离线脚本均以 `.venv\Scripts\python.exe scripts/<name>.py` 重新运行，
exit code 均为 0：

- deindustrialization_batch1_golden_path_smoke
- deindustrialization_batch1_boundary_smoke
- deindustrialization_batch15_review_boundary_smoke
- deindustrialization_batch2_tools_smoke
- deindustrialization_batch2a1_manifest_parity_smoke
- deindustrialization_batch2a2_evidence_provenance_smoke
- deindustrialization_batch2c_runtime_isolation_smoke
- deindustrialization_phase1_closure_smoke

这是本批相关回归覆盖，不宣称执行了全仓所有测试或重新验收部署环境。
不需要 schema change，无新 migration；不执行 PostgreSQL rehearsal 或完整
FastAPI startup；未修复既有外部环境依赖。

## 9. Final Status

Contract 已新增；Validator 已实现；27 新测试 + 3 既有 Projection 测试通过；
generic/domain 边界未回退；相关 Golden Path、provenance、tool/runtime 与 Closure
离线 smoke 通过。

`PHASE_2A2_TRAJECTORY_VALIDATION=PASS`

到此停止。AgentRun Evaluation、Reward Assessment、DiagnosisEvaluator、dataset
export 与 RL training/optimization 均未在本批实现。
