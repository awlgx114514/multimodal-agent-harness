# Plant Disease Portfolio Demo

更新日期：2026-10-10。

## 当前状态

```text
MIGRATION_REHEARSAL=PASS
LOCAL_RUNTIME_CONFIG=PASS
COMPOSE_CONFIG=PASS
SOURCE_READINESS=PASS
SOURCE_CANDIDATE_STATUS=NOT_APPROVED
SOURCE_SUBMISSION=NOT_CREATED
SOURCE_REVIEW_RECORD=NOT_CREATED
SOURCE_REVIEW_INSPECTION=IMPLEMENTED
OBJECT_STORAGE=PASS
MEDIA_SERVICE_E2E=NOT_RUN
GOLD_EVALUATION=NOT_RUN
MODEL_GATEWAY_AUTH_MODE=PASS
OLLAMA_MODEL_GATEWAY=NOT_CONFIGURED
PLANT_DISEASE_RELEASE=NOT_CREATED
FRONTEND_BUILD=PASS
FRONTEND_CONTAINER_BUILD=PASS
FULL_REGRESSION=PASS
PORTFOLIO_DEMO=NOT_RUN
```

PlantDoc 候选清单包含 600 张真实图片、2,130 个原始边界框和 29 个原始类别，保留了来源标注、图片身份、许可信息及 SHA-256。清单通过现有 evaluator 的区域校验，候选数据仍处于审核状态。

本地 disposable PostgreSQL 已从空库完整迁移至 Alembic head `0096_evaluation_suite_policy_approval`。完整 Python regression 通过：80 tests、61 subtests，其中包含使用独立 `ioap_demo` 数据库的真实 migration regression。测试脚本创建并删除临时数据库角色，执行后已清理。迁移回归已核对新增 suite/policy 审批记录与租户隔离。

前端容器镜像使用官方 Node.js `v22.23.1` Linux x64 发布包，构建前按 Node 官方 SHA-256 清单核验。Next.js 容器构建与 production build 通过。Model Gateway 认证模式新增 5 项专门测试；相关配置、传输和转写模块的 Ruff、编译和 focused mypy 检查通过。`none` 模式不读取模型 API 密钥且不发送 Authorization，`bearer` 模式缺少密钥会立即失败。

本地 S3 endpoint 的正式 bucket bootstrap 已通过，并确认媒体 bucket 和数据集 bucket 可用。`scripts/demo/plant_disease/object_storage_connection_smoke.py` 使用候选清单中的真实 PlantDoc 图片验证 bucket 查询、S3 上传/下载/删除、对象大小和摘要，以及签名 GET/PUT；下载内容的 SHA-256 与来源图片一致。该检查验证了 S3 接口，尚未验证数据库媒体记录与 API 上传流程。

前端 TypeScript 检查、Next.js production build 与前端容器镜像构建通过。当前应用路由没有 Plant Disease 页面。

`scripts/dev_lite.sh init` 已按仓库正式流程校验并补齐本地运行配置，Compose 配置解析通过。`compose.lite.yaml` 的正式 seed 关闭合成知识文档写入。完整本地 seed 尚未执行：现有 seed 还会创建合成制造租户、资产和演示身份，没有 Plant Disease 专用的真实租户、身份与资产建立流程；这些记录不能作为 Plant Disease 数据或人工审核身份使用。完整仓库 Ruff 当前有 33 项告警；本次变更涉及的 Python 文件通过 Ruff，focused mypy 与 Python 编译通过。

本地安装并运行 `qwen3-vl:4b-instruct-q4_K_M` 与 `qwen3-vl:8b-instruct-q4_K_M`。使用同一张候选图片分别调用 Ollama 原生视觉接口、OpenAI-compatible 接口及项目 transport。两种模型都能接收图片；4B 的部分结构化调用可以运行，但识别类别与区域不符合来源标注。8B 的完整 Recognition schema 与移除 `allOf` 的 schema 均无法由 Ollama grammar 编译；最小 schema 调用没有产生 findings，JSON 模式结果也未满足正式输出与定位要求。两种模型都未进入正式 Gateway evaluation 或 release 决策。

`scripts/demo/plant_disease/vision_transport_probe.py` 保存了逐层调用证据，不输出图片 base64。当前模型能力与 Ollama 结构化输出边界尚未满足正式 Recognition evaluation 条件。

## 来源审核合同

`POST /api/v1/public-evaluation-sources` 保存不可变来源 manifest，并创建 `PENDING_REVIEW` 记录。审核接口为 `POST /api/v1/public-evaluation-sources/{source_id}/decision`，要求 `public_evaluation_source.review` 权限。当前授权角色为 `MODEL_RELEASE_APPROVER`。

审核人可通过 `GET /api/v1/public-evaluation-sources` 查看待审核记录，再通过 `GET /api/v1/public-evaluation-sources/{source_id}/manifest` 读取服务保存的完整 manifest。服务会重新计算 SHA-256 并校验来源合同、版本和样本数量。列表和 manifest 查询使用与决定相同的 reviewer 权限。

审核服务在 `public_source.py` 中比较 `submitted_by_subject_id` 和当前审核人的 `identity.subject_id`。两个身份相同会拒绝审核，错误码为 `evaluation_source_submitter_cannot_review`。本地运行环境没有可代表独立授权审核人的已认证人员身份；不得通过更换 subject、创建服务账号或修改数据库记录代替真实审核。来源提交也须通过真实 OIDC submitter 会话；当前未取得可用于正式提交的已认证 submitter 会话。

服务合同能验证 OIDC 授权结果、reviewer 权限、submitter/reviewer subject 分离、决定理由和摘要一致性；它无法从 subject 声明证明账号背后的操作者属于现实中的授权人员。该身份归属由本地身份系统与组织授权人确认，自动化流程不能代替该人员提交审核决定。

PlantDoc 候选来源尚未提交到本地审批服务。正式审核需要由具有 `MODEL_RELEASE_APPROVER` 权限、且身份独立于提交人的人员完成。该步骤需要真实授权人员操作，自动化流程不能代替该人员判断来源许可、归属、标注来源及清单内容。

隔离数据库可独立启动和迁移。Suite 与 Policy 注册时处于 `DRAFT`，提交后进入 `SUBMITTED`；决定会绑定提交摘要，并校验提交人与审核人身份分离。公开来源审核、Suite 审核和 Policy 审核都要求真实的独立授权审核身份。本地服务种子和 PlantDoc 来源提交尚未验收。

## 尚需实现的正式流程

- Evaluation Suite 与 Evaluation Policy 已有独立审核记录及审核路由。PlantDoc 来源还没有进入正式服务，GOLD Suite 与 Policy 尚未创建。
- 当前模型评测流程依赖训练 experiment；仓库没有只服务指定 suite/policy 的发布前 VLM evaluation execution path。
- `EnvironmentAwareModelResolver` 只解析已发布的 production release。显式认证模式已支持本地无认证端点与 bearer 密钥端点；现有 Model Gateway 尚未连接本地 Ollama endpoint，也没有候选模型 release lifecycle。
- Evaluation snapshot loader 仍依赖现有 curation dataset snapshot，且该来源由工业数据整理流程创建；尚无可直接消费公开数据源的领域无关 snapshot。Plant Disease 目前包含数据导入和来源检查能力。尚无完整 diagnosis runtime、Evaluation application 流程、release/deployment/production alias/quota 配置、两次端到端演示或前端页面验收。

正式 GOLD evaluation、发布和 Portfolio Demo 必须在来源审核通过、suite/policy 进入审批治理、候选 VLM 评测经 Model Gateway 执行并满足发布门槛后进行。真实 citation、Trajectory Projection 和 Trajectory Validation 也须使用这些正式运行结果逐项确认。

## 数据准备检查

```powershell
.venv\Scripts\python.exe scripts\demo\plant_disease\dataset_readiness.py readiness
```

此命令只验证现有公开来源候选清单及其图像、标注和摘要，不会改变来源审批状态，也不会创建 GOLD suite。
