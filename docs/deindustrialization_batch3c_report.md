# Batch 3C — Parts Read / Mutation Split

## Result

`Batch 3C deletion goals: PASS`

本批只处理 Parts 边界：保留 `parts.availability` 及其库存事实读取，删除
Parts 的 active reserve/issue/consume/return mutation capability；未进入 Batch 3D，
未删除 fulfillment 的历史 accounting 数据。

## Boundary decision

### Before

Diagnosis 和 Fulfillment 通过混合的 Parts service / adapter / ToolGateway 同时
访问 availability 和 mutation。

### After

Diagnosis → read-only Parts availability boundary → inventory facts。

默认 registry 只包含以下五个 Diagnosis T0 read-only tools：

- `asset.get`
- `warranty.get`
- `parts.availability`
- `schedule.availability`
- `work_orders.history`

`parts.reserve`、`parts.issue`、`parts.consume`、`parts.return` 不再注册，调用会被
`tool_not_registered` 拒绝。ToolGateway 只接收并执行 `ReadonlyToolAdapter`，共享既有
governance、authorization、rate limiting、attestation 和 audit mechanism；没有新增
第二套 Tool runtime。

## KEEP / SPLIT / DELETE

### KEEP — availability and historical facts

- `parts.availability` 的 part number、requested/available quantity、availability
  decision、source record、authority 和 freshness metadata；
- `PartReservationRecord`、`PartIssueRecord`、`PartMaterialMovementRecord` 等历史
  persistence records；
- `WorkOrderService` 对上述记录的历史读取和 Parts accounting 查询。

这些记录仍被 WorkOrder closure/accounting 读取，因此本批删除 active capability，
不删除历史事实表，也不破坏既有读取。

### SPLIT — read boundary

- generic `ReadonlyToolAdapter` contract；
- read-only `ToolGateway`；
- `SyntheticPartsAvailabilityReader` 作为无 mutation state 的 Parts availability
  read boundary；
- `EnterpriseHttpAdapter` 的 Parts availability GET path；
- Diagnosis composition root 的 read-only adapter/gateway 装配。

Industrial Diagnosis 的五个 tool schema、authorization 和实际 read behavior 保持不变。

### DELETE — active Parts mutation surface

- Parts reserve/issue/consume/return tool definitions 和 gateway execution branches；
- Parts mutation adapter contract/state（包括旧 `PartsAdapter` / synthetic mutation
  adapter / external WMS mutation routes）；
- reservation proposal、approval、execution reconciliation API routes；
- `/parts` 页面中的 reservation mutation UI；
- approvals/reconciliations 页面、导航入口、对应 client API 和 OpenAPI paths/schema
  surface；
- 相关 runtime/factory/release/config 的 active mutation 装配和 required tool marker。

没有为了清除兼容性或历史材料中的文本标记而改动训练/evaluation 非生产面。

## Persistence and migration

Batch 3C 没有 persistence schema 变更，因此不新增 0091 migration，也没有需要执行的
Batch 3C SQLite migration。历史 Parts records 和 WorkOrder accounting columns 保持不变。

SQLite migration rehearsal：

`NOT APPLICABLE — no Batch 3C schema migration; retained historical tables unchanged.`

当前 Alembic head 仍为：

`0090_remove_workorder_field_fulfillment (head)`

PostgreSQL rehearsal：

`NOT RUN — no disposable PostgreSQL environment available`

未连接生产数据库，未为本批搭建新的基础设施。

## Availability parity

使用既有 synthetic fixture 对同一 availability contract 验证：

- `part_number=FILTER-X100` 保持不变；
- `available_quantity=8` 保持不变；
- request quantity 与 availability decision 保持不变；
- source record、authority、as-of/freshness metadata 仍由 read adapter 提供；
- gateway 仍执行 schema validation、authorization、attestation、audit 和 rate limit。

因此，availability read behavior 与迁移前 contract 等价；active reservation 不再作为
availability read path 的隐式 mutation state。

## Dependency and ownership audit

生产依赖方向已收敛为：

`composition root → read-only adapter → generic ToolGateway/governance`

generic tool contracts、gateway 和 factory 不 import Parts mutation domain，也不构造
Parts mutation adapter。Parts historical ORM records 仅保留在 persistence/work-order
历史 accounting 读取侧。

扫描中仍可见的 Parts mutation 文本属于以下非 active production surface：

- Batch smoke/dependency tests 对“工具不存在”行为的断言；
- `m3_integration_probe.py` 对历史 `ActionProposalRecord` / `PartReservationRecord`
  fixture 的记录；
- evaluation/training 兼容 marker；
- 早期 migration 中的历史表定义。

这些项目不是当前可执行的 Parts mutation runtime，未扩大本批范围。

## Verification evidence

以下 20 个既有/本批 smoke 全部 PASS：

- Batch 1 boundary、Golden Path；
- Batch 1.5 review boundary；
- Batch 2 Multimodal、Retrieval、Tools；
- Batch 2A Recognition、manifest/persistence、evidence resolver、provenance；
- Batch 2B dependency、generic applicability、retrieval parity、SQLite migration；
- Batch 2C dependency、runtime isolation；
- Batch 3A deletion、SQLite migration；
- Batch 3B deletion、SQLite migration；
- Batch 3C Parts read/mutation smoke。

其他门禁：

- `ruff check` on changed Python files：PASS；
- `python -m compileall -q src scripts`：PASS；
- production tool/persistence imports：PASS，metadata 共 144 张表；
- `contracts/openapi.json` parse 和 Parts mutation route/schema scan：PASS；
- Alembic heads：PASS，head 为 0090。

环境限制记录：

- Full FastAPI import：`NOT RUN — existing local dependency chain is unavailable.`
  当前 import chain 首先缺少 `PIL`；既有 `spacy.tokens` 限制也未修复。该限制不影响
  已完成的 service-level、tool-level 和结构 smoke；
- evaluation runtime focused import 同样受既有 `PIL` 缺失影响，未安装依赖；
- web typecheck：`NOT RUN — web/node_modules unavailable`；
- focused mypy：未 clean，报告 36 个错误，主要集中在既有缺失/未类型化依赖和
  pydantic/SQLAlchemy stubs；未借本批扩大修复；
- `.git` 不存在；未执行 `git init`。

## Scope disposition

Batch 3D 未开始。未删除 fulfillment、未修改 Multimodal architecture，未处理
predictive/Kafka/GraphRAG、realtime split 或其他后续删除项。

`Batch 3C deletion goals: PASS`
