# Batch 3B — WorkOrder Fulfillment / Dispatch / Field / FSM / Equipment Control Deletion

## Result

`Batch 3B deletion goals: PASS`

Batch 3B 删除了生产应用中的 WorkOrder 履约生命周期、派工、现场执行、FSM
交付、现场专家协作和设备控制能力，同时保留 Diagnosis Golden Path、五个
Diagnosis 只读工具、Parts 变更路径、Diagnosis 人工接管/恢复，以及必要的
历史读取和 Parts accounting 兼容能力。

Batch 3C 未开始。

## Deletion boundary

### WorkOrder split

保留：

- `work_orders` 主表及 `WorkOrderRecord`；
- `work_order_events`、`work_order_controls`；
- `work_order_completions`、`work_order_verifications`、`work_order_reworks`；
- `work_order_field_entries`，仅用于保留 Parts accounting 所需的历史事实；
- `WorkOrderService` 的历史读取、控制记录读取、维修历史/关闭报告读取，以及
  Parts allocation/accounting 所需的最小查询。

删除：

- WorkOrder 创建、派工、接单、现场记录上传、离线包、边缘诊断、专家现场协作、
  完工履约和设备控制 mutation 生命周期；
- 对应 API routes、tool registry entries、gateway branches、adapter/factory
  装配、权限 action、配置/secret 和前端页面/组件。

因此，`WorkOrderRecord` 的保留不代表履约服务仍然存在；它只承载仍被历史读取
和 Parts accounting 使用的事实。

### Schedule boundary

`schedule.availability` 仍是 Diagnosis 可使用的只读事实来源，
`work_orders.history` 仍是 Diagnosis 可使用的历史查询工具。派工 API、assignment
delivery/receipt 和调度执行路径已移除。

### Human-in-the-loop boundary

保留 Diagnosis 的 expert takeover、revision 和 Agent resume。删除现场专家协作、
现场音频协作和 field guidance；这两类能力没有合并为同一套运行时。

### FSM and equipment boundary

删除 fulfillment FSM、FSM assignment delivery/receipt、现场离线/边缘执行状态机。
Agent state machine、Temporal orchestration、model release/promotion 等仍属平台
运行机制，未被本批删除。

设备资产事实和 Diagnosis 的资产只读查询保留；`equipment.control.*` 的生产工具、
路由、gateway 分支、配置、secret 和 handoff adapter 已删除。

## Persistence migration

新增前向 Alembic revision：

`alembic/versions/0090_remove_workorder_field_fulfillment.py`

该 migration 先解除 Recognition/Evidence/Realtime/WorkOrder 上的已删除字段、索引、
约束和外键，再按 child-first 顺序删除以下表：

- `equipment_control_handoffs`
- `fsm_assignment_deliveries`
- `fsm_assignment_receipts`
- `work_order_field_evidence_uploads`
- `work_order_assignments`
- `work_order_offline_packs`
- `work_order_edge_diagnosis_packs`
- `work_order_edge_diagnosis_candidates`
- `work_order_expert_collaborations`
- `work_order_expert_collaboration_events`
- `work_order_expert_collaboration_recommendations`

未修改历史 migration；0090 为不可逆前向删除 revision。SQLite rehearsal 已验证：
删除表不存在、旧列不存在、保留的 WorkOrder/Recognition/Evidence 表仍可用。

PostgreSQL rehearsal：

`NOT RUN — no disposable PostgreSQL environment available`

未连接生产数据库，也未搭建新的基础设施。

## Runtime, route and tool inventory

生产 runtime/factory/gateway 不再装配或执行 WorkOrder 履约、FSM assignment、现场
offline/edge、现场专家协作或 equipment control。相关 FastAPI route 和前端入口已删除；
前端 manifest 已恢复为平台根范围，不再以 `/field` 作为 PWA 入口。

保留的 Diagnosis T0 只读工具集合为：

- `asset.get`
- `warranty.get`
- `parts.availability`
- `schedule.availability`
- `work_orders.history`

Parts mutation 仍复用既有 generic ToolGateway/governance，不重新引入履约 runtime。

## Dependency scan classification

生产 surface 的删除 smoke 已确认：

- 已删除模块、页面和组件不存在；
- 删除的 mutation tool IDs 未注册；
- 五个 Diagnosis T0 工具仍注册；
- app、runtime、factory、gateway、config、secret、client 和 generated schema
  不含本批删除能力的生产 markers；
- ORM metadata 不再映射已删除表，也不再包含已删除的 binding columns。

扫描中仍可见的标识均不属于本批生产能力：

- 早期 Alembic revisions 中的旧表定义是不可修改的历史迁移；
- `work_order.closed` event contract、event worker 和 `closure_report` 是保留的历史事实读取；
- evaluation/training fixtures 中的 `t3_control_execution` 和旧 equipment tool 名称只属于
  后续评测兼容面，当前不被 registry、生产 route 或 runtime factory 暴露；
- `work_orders/history` 是明确保留的只读 sandbox/enterprise adapter 路径。

没有为了清理这些历史或后续评测标识而扩大 Batch 3B 范围。

## Verification evidence

最终 working copy 的 smoke 结果：

- Batch 1 Golden Path：PASS
- Batch 1 boundary：PASS
- Batch 1.5 review boundary：PASS
- Batch 2 Multimodal、Retrieval、Tools：PASS
- Batch 2A Recognition、manifest/persistence、evidence resolver、provenance：PASS
- Batch 2B dependency、generic applicability、retrieval parity、SQLite migration：PASS
- Batch 2C dependency、runtime isolation：PASS
- Batch 3A deletion、SQLite migration：PASS
- Batch 3B deletion：PASS
- Batch 3B SQLite migration rehearsal：PASS
- `src` 与 `scripts` Python compilation：PASS
- 本批实际改动 Python 文件 Ruff：PASS
- production model/key imports：PASS；当前 metadata 共 144 张表，保留表存在
- `contracts/openapi.json` JSON parse：PASS
- Alembic heads：`0090_remove_workorder_field_fulfillment (head)`

额外环境记录：

- 全仓 Ruff 仍有既有基线问题，集中在未涉及本批的旧脚本、模型网关、训练和 sandbox 文件；
  未借本批修复。
- focused mypy 仍有既有基线错误，主要来自 SQLAlchemy/pydantic stubs、旧 gateway 调用和
  realtime 等未涉及面；未借本批扩大修复。
- web typecheck：`NOT RUN — web/node_modules unavailable`。
- Full FastAPI create_app：`NOT RUN — existing local dependency chain is unavailable`
  （当前首先缺少 `PIL`；既有 `spacy.tokens` 限制也未修复）。service-level 和 structural
  verification 不依赖完整 FastAPI 构造，因此不阻塞本批结构验收。
- `.git` 不存在；未执行 `git init`。

## Final disposition

Batch 3B 的生产删除边界、数据库前向迁移、Diagnosis/Parts 保留边界和回归证据均已
完成。未删除 WorkOrder 历史事实，不再提供履约 mutation；未修改 Multimodal 架构，
未进入 Batch 3C。

`Batch 3B deletion goals: PASS`
