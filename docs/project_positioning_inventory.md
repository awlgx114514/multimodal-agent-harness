# 项目现状盘点：Large-Model-Application

> 盘点对象：`D:/Microsoft/Large-Model-Application-main-inspect/Large-Model-Application-main`
>
> 盘点方式：基于当前 ZIP 快照中的源码、配置、文档、数据样例和 CI/验证脚本进行静态盘点。没有把 README 中的能力描述直接当作实现证据；没有运行完整 Compose、GPU 模型、外部企业系统或 Kubernetes 环境。
>
> 重要边界：当前 ZIP 不包含 `.git` 历史、模型权重、运行时 `artifacts/` 目录，也没有标准 `tests/` 目录。因此“代码路径存在”不等于“本次已验证在真实环境跑通”。

## 1. Repository Map

### 1.1 主要目录

```text
Large-Model-Application-main/
├── src/industrial_ops_agent/       # Python 后端、Agent、Worker、模型、训练与业务域
│   ├── main.py                     # API 进程入口
│   ├── runtime.py                  # 生产运行时依赖组装
│   ├── config.py                   # Settings、环境和安全约束
│   ├── api/                        # FastAPI 应用、依赖和路由
│   ├── application/                # 业务用例：incident、diagnosis、agent run
│   ├── agent/                      # LangGraph 诊断 Agent、状态、事件、checkpoint、PPO/GRPO/DPO runtime
│   ├── orchestration/              # Temporal Workflow 和 Activity
│   ├── tools/                      # Tool Registry、Tool Gateway、HTTP/MCP/企业适配器
│   ├── multimodal/                 # OCR、VLM、ASR、TTS、视频帧、实时转写
│   ├── media/                      # 上传对象、隔离扫描、媒体证据
│   ├── model_gateway/              # Release/Deployment/Quota/Inference 审计和模型传输
│   ├── knowledge/、graph_rag/      # 知识入库、检索、GraphRAG
│   ├── memory_governance/          # 人工确认记忆和诊断上下文选择
│   ├── training/、evaluation/      # 训练、奖励、模型评测和评测 Runner
│   ├── simulation/                 # 业务验收、模型推广和 GPU/Serving 实验
│   ├── persistence/、alembic/      # 数据库模型、事务、租户和迁移
│   ├── auth/、security/            # OIDC、OPA、授权、安全审计
│   └── observability.py            # 日志、请求关联、OTel 和 HTTP metrics
├── web/                            # Next.js App Router 前端和后端代理
│   ├── app/                        # 登录、工作台、报障、工单、AI/模型、运维页面
│   ├── components/                 # 业务组件和 Agent 事件展示
│   └── lib/api/client.ts           # 类型化 API 客户端和事件流
├── contracts/                      # OpenAPI、事件 Schema、证据资料
├── datasets/、docs/                # 数据样例、评测输入和发布资料
├── airflow/dags/                   # 数据快照和保留策略调度定义
├── docker/                         # API、Web、Worker、模型和训练镜像
├── infra/                          # Helm、Terraform、KServe、Vault、OPA 等部署配置
├── scripts/                        # 本地启动、验证、模型训练/发布和验收脚本
├── alembic/                        # 数据库迁移
├── acceptance/                     # 项目业务闭环验收输入
└── .github/workflows/              # CI、供应链和镜像证据流程
```

### 1.2 入口和边界索引

| 能力 | 真实入口 / 关键位置 | 当前判断 |
|---|---|---|
| API | `src/industrial_ops_agent/main.py`、`api/app.py` | FastAPI 应用工厂；路由集中注册 |
| Backend | `src/industrial_ops_agent/application/`、`domain/`、`persistence/` | 业务服务、领域模型和持久化分开 |
| Frontend | `web/app/`、`web/components/`、`web/lib/api/client.ts` | Next.js App Router，多业务页面 |
| LLM / Model | `model_gateway/service.py`、`model_gateway/openai.py`、`model_gateway/router_runtime.py` | 有治理的模型解析和 OpenAI-compatible transport |
| Agent | `agent/graph.py`、`agent/diagnosis_runtime.py` | 一个明确的、受预算约束的诊断 Agent |
| Tool | `tools/registry.py`、`tools/gateway.py`、`tools/contracts.py` | 有 schema、版本、授权、审批、幂等和限流 |
| Multimodal | `multimodal/processor.py`、`multimodal/providers.py`、`multimodal/video.py` | 图片、视频帧、OCR、VLM、ASR、时间分析 |
| Image / screenshot | `media/`、`multimodal/providers.py` | 支持上传图片和从视频产生帧；没有浏览器/桌面截图采集 |
| Browser / Computer-use | 全仓库未发现浏览器控制依赖或执行器 | Absent |
| Memory / Context | `memory_governance/service.py`、`model_gateway/context_manifest.py` | 有治理记忆、上下文哈希和截断记录 |
| Database | `persistence/`、`alembic/versions/` | PostgreSQL/SQLAlchemy/租户事务/RLS 相关代码 |
| Workflow / State | `orchestration/workflows.py`、`agent/graph.py`、业务状态模型 | Temporal + LangGraph + 业务状态机 |
| Eval / Benchmark | `evaluation/`、`model_gateway/benchmark.py`、`docs/m5-release/` | 有模型/组件/发布评测，不等于线上 Agent 回归套件 |
| Training / RL | `training/`、`agent/ppo_runtime.py`、`agent/grpo_runtime.py` | 有 SFT、DPO、GRPO、PPO 训练/运行时路径 |
| Tests | 未发现标准 `tests/`、`test_*.py` 或测试 Runner | Absent as a conventional test suite；CI 有静态和 Compose 验证脚本 |
| Deployment | `compose.*.yaml`、`docker/`、`infra/helm/`、`infra/terraform/` | Compose、Helm、Terraform、KServe 和供应链流程均有代码 |

## 2. 项目到底是什么

### 2.1 原始目标

当前 ZIP 没有 `.git` 历史，无法从提交历史独立确认最初的产品决策。现有 README、路由、业务域和运行时代码共同指向的目标是：

> 将工业设备报障、媒体证据、企业知识、企业系统事实和模型推理连接起来，形成带人工复核、审批、工单履约和数据反馈的企业售后运维闭环。

代码证据包括：

- `application/incidents.py`：报障、媒体、识别、证据确认和 Incident 生命周期。
- `application/diagnoses.py`：诊断启动、版本、幂等、模型绑定和工作流派发。
- `workorders/`、`parts/`、`service_entitlements/`、`customer_portal/`：售后履约域。
- `multimodal/`、`knowledge/`、`model_gateway/`：媒体、知识和模型链路。
- `training/`、`evaluation/`、`releases/`、`deployment/`：模型迭代和发布治理。

### 2.2 当前真实形态

主定位是：

> **面向工业运维/售后的 Multimodal Agent Application，同时带有较重的 Model Platform / Workflow Platform / AI Backend 基础设施。**

不是以下定位：

| 候选定位 | 判断 | 原因 |
|---|---|---|
| LLM Platform | 次级定位 | 有 Model Gateway、Release、Deployment、Quota、Inference audit，但模型平台服务于垂直业务 |
| Chat Platform | 不是主定位 | 没有通用聊天产品；诊断输入、证据和业务状态是核心 |
| Multimodal LLM Platform | 次级定位 | 有 OCR/VLM/ASR/TTS 和模型绑定，但入口是工业业务 |
| Agent Platform | 部分成立 | 有 Agent runtime、工具治理、事件、checkpoint，但不是通用 SDK/框架 |
| Agent Framework | 不是主定位 | Agent 逻辑绑定诊断、企业事实和工业报告，不是可独立复用的通用框架 |
| Agent Application | **主定位** | 用户实际面对的是报障、诊断、工单、售后和维护业务 |
| Computer-use Agent | Absent | 没有浏览器、DOM、截图控制或 click/type/scroll 执行器 |
| Workflow Platform | 次级定位 | Temporal 和大量业务状态机很重，但工作流围绕工业业务闭环 |
| Model Playground | 不是主定位 | 有实验和评测页面，但不是任意模型试验台 |
| AI SaaS | 代码形态接近，但运行前提未验证 | 有多租户、角色和业务页面；依赖大量外部服务和模型制品 |

因此，代码量虽然很大，但不能把它直接描述为“通用 Agent 框架”或“Computer-use 平台”。它更接近一个企业级垂直 AI 产品与其运行基础设施的合体。

## 3. 当前用户可以完成什么完整任务

### 3.1 代码层面最完整的主流程：工业故障诊断

```text
用户登录
  → 选择租户和设备
  → 创建 Incident / 故障草稿
  → 上传 JPG/PNG 或视频
  → 媒体进入对象存储并经过隔离扫描
  → 启动 Recognition Workflow
  → OCR + VLM + QR；视频还会解码关键帧、音频和时间窗口
  → 用户逐项接受、修正或拒绝识别候选
  → 确认 Evidence Bundle
  → 发起 Diagnosis
  → DiagnosisService 校验权限、设备、证据、索引 Release 和模型 Release
  → Temporal DiagnosisWorkflow
  → DiagnosisActivity 加载持久化 Agent state
  → LangGraph: prepare → retrieve → decide
       ├─ RETRIEVE → 再检索
       ├─ CALL_TOOL → 读取企业事实 → 回到 decide
       ├─ FINAL → finish
       └─ NEEDS_INFORMATION → finish
  → 结构化报告：结论、引用、矛盾、缺失信息、后续检查、置信度
  → 持久化 Agent events / checkpoint / inference audit
  → 前端通过查询或 SSE/AG-UI 事件流展示进度和结果
```

这条链路在源码中形成了相对完整的调用链：`web/lib/api/client.ts` → `api/routes/diagnoses.py` → `application/diagnoses.py` → `orchestration/workflows.py` → `agent/graph.py` / `agent/diagnosis_runtime.py` → `model_gateway/service.py` 和 `tools/gateway.py`。

**状态判断：代码闭环成立；真实环境跑通状态 Unknown。** 原因是模型权重、模型镜像、数据库、Temporal、身份服务、对象存储、企业接口和有效 Release/Deployment 绑定不在 ZIP 中，本次没有启动整套环境。

### 3.2 其他代码中存在的流程

| 流程 | 代码状态 | 是否能据当前仓库证明真实闭环 |
|---|---|---|
| 图片识别和人工确认 | `MultimodalProcessor._process_image`、`recognition.py`、前端 recognition 页面 | 代码链路完整；运行时 Unknown |
| 视频 → 关键帧/音频 → OCR/VLM/ASR/时间事件 → 复核 | `multimodal/video.py`、`processor.py`、`recognition.py` | 条件式实现；依赖 `multimodal-video`、视频解码器和对应模型绑定 |
| 知识文档 → 解析/OCR → 审核 → 索引发布 → 检索 | `knowledge/`、`graph_rag/`、`search_profiles/` | 模块和 API 存在；GraphRAG/OpenSearch 由配置决定，运行闭环 Unknown |
| 诊断 → 报价/派工/工单/现场证据/验收/关闭 | `workorders/`、`parts/`、`service_entitlements/`、相关 API 和页面 | 业务代码覆盖广；完整跨服务实际执行 Unknown |
| 工单关闭 → Outbox/Kafka/Debezium → 数据快照 | `eventing/`、`event_worker/`、`airflow/dags/`、`data_pipeline/` | 代码和部署定义存在；外部集群和实际事件消费 Unknown |
| 数据集 → SFT/DPO/GRPO/PPO/专用模型训练 → 评测 → Release/Deployment | `training/`、`evaluation/`、`releases/`、`deployment/` | 训练/评测/发布代码存在；当前 ZIP 无模型权重和 runtime artifacts，实际执行 Unknown |
| 实时媒体 / 语音协作 | `realtime_media/`、`multimodal/realtime.py`、`compose.realtime.yaml` | Optional；默认配置关闭或依赖额外服务 |

## 4. Agent 能力盘点

| 能力 | 状态 | 证据与判断 |
|---|---|---|
| Agent loop | **Implemented** | `agent/graph.py:DiagnosisGraph` 建立 `prepare/retrieve/decide/tool/finish` 循环 |
| 谁决定下一步 action | **Implemented** | `agent/diagnosis_runtime.py:decide` 调 ModelGateway；`graph.py:_node` 根据结构化 `action` 路由 |
| Tool calling | **Implemented** | 模型输出 `CALL_TOOL` + `tool_id`，不是自由文本；`agent/contracts.py:step_schema/validate_step` 校验 |
| Tool schema | **Implemented** | `tools/registry.py:ToolDefinition` 保存 input schema、版本、风险、审批、幂等、超时和限流 |
| Observation 回到模型 | **Implemented** | `DiagnosisRuntime.tool` 将结果写入 `tool_facts/tool_failures`，下一次 `build_step_request` 放回上下文 |
| 显式 state | **Implemented** | `diagnosis-state/v2` 字典 state，包含 evidence、tool facts、memory、budget、pending request、decision、trace |
| State machine / graph | **Implemented** | LangGraph 诊断图；业务侧另有 Incident/Work Order 状态和 Temporal Workflow |
| 多步执行 | **Implemented** | 默认 `max_steps=8`、`max_tool_calls=5`，实际值从 Manifest 受上限约束 |
| Termination condition | **Implemented** | `FINAL`、`NEEDS_INFORMATION`、时间/步数/Token/Tool budget exhausted、模型失败 |
| Retry | **Implemented** | Temporal Activity retry；`DiagnosisRuntime._retry_later` 对可重试模型错误做固定请求重试 |
| Error recovery | **Partial** | checkpoint CAS、resume/cancel、幂等和重试存在；没有一个通用跨任务 repair/recovery Agent |
| Human approval | **Implemented** | Tool Gateway 对 T2 工具要求独立 proposal/approval；诊断本身主要使用只读工具，专家接管/修订也存在 |
| Memory | **Partial** | `GovernedMemoryService` 和 `MemoryContextReader` 支持人工确认的 session note/user preference；不是自动长期记忆学习 |
| Context management | **Implemented** | `ContextManifest`、上下文哈希、Token budget、截断记录和证据/工具/记忆来源绑定 |
| Planning | **Partial** | 诊断 Agent 是检索/工具/结束决策，不是长程计划器；另有 `maintenance_planning/` 专项规划模块 |
| Subagent / multi-agent | **Partial** | 有维护规划多 Agent、供应商 A2A、专家协作路径；主诊断 loop 本身是单 Agent |
| Execution trace | **Implemented** | `agent/events.py` append-only event store、`agent/checkpoints.py`、OTel、SSE/AG-UI 投影 |

### 4.1 Agent 的准确定位

这不是普通的“一次 Prompt → 一次回答”：它有模型驱动的 action 选择、受版本约束的工具、工具观察回填、持久化 state、有限循环、重试和事件流。

但它也不是一个通用 Agent Harness：Agent 的 state、prompt、tool registry、报告 schema、预算和检索都是围绕“工业诊断”固定的。它更像一个生产化倾向的垂直诊断 Agent runtime。

## 5. Multimodal 能力盘点

| 能力 | 状态 | 真实实现 |
|---|---|---|
| Image 输入 | **Implemented** | `uploads.py` 接收媒体 bytes；`providers.py` 校验 PNG/JPEG；VLM 以 data URL/base64 发送 |
| Screenshot 输入 | **Partial** | 普通截图可以作为图片上传；没有 screenshot capture 或 GUI 语义 |
| 多张图片 | **Partial** | 同一识别任务可产生多个媒体/证据；当前 `GatewayVlmProvider.inspect` 是逐个媒体调用，未看到一个通用多图 Agent 请求接口 |
| 图片直接进入 VLM | **Implemented** | `GatewayVlmProvider` / `OpenAiCompatibleVlmProvider` 将图片作为 `image_url` 发给 VLM |
| Resize / compression / encoding | **Partial** | 有 MIME、尺寸、字节数、像素和 base64/JPEG 限制；没有通用的输入压缩策略。视频关键帧会编码为 JPEG |
| Vision model | **Implemented conditionally** | `GatewayVlmProvider`、`vlm_runtime.py`；配置/文档绑定 SmolVLM-500M 和受管 VLM endpoint |
| Vision output | **Implemented** | 结构化 JSON finding，包含 label、confidence、normalized region/bounding box、evidence 等 |
| OCR | **Implemented** | `PaddleOcrProvider` + `ReleaseBoundOcrProvider`，并将 OCR block 纳入证据复核 |
| Object detection | **Partial** | 有视觉 finding 和区域框，但不是独立 object detector 训练/推理接口 |
| Grounding / bounding box | **Partial** | `BoundingBox` / normalized region 存在并可评测；不是 GUI element grounding |
| GUI understanding | **Absent** | 没有 DOM、accessibility tree、网页元素语义或桌面控件模型 |
| Screenshot → action | **Absent** | VLM 输出被定义为候选观察，明确不能声称执行物理动作 |
| 连续 screenshot observation | **Absent** | 没有浏览器/桌面连续观察；视频关键帧时间分析不等价于 GUI observation loop |
| Visual history | **Partial** | 视频有 frame_id、时间戳、窗口和融合事件；诊断 Agent 使用的是确认后的结构化证据，不是原始视觉记忆流 |
| Video / frame | **Implemented conditionally** | `PyAvVideoDecomposer` 解码关键帧和音频，`MultimodalProcessor._process_video` 执行逐帧 OCR/VLM、ASR 和 temporal VLM |
| Browser screenshot | **Absent** | 全仓库未发现浏览器截图采集器 |
| Multimodal tool call | **Absent in the Agent contract** | 工具调用由诊断 JSON action 触发；VLM 本身没有输出可执行多模态 tool call |

### 5.1 当前多模态的真实形态

当前已经超过简单的 `图片 → 模型 → 文本`：

```text
图片/视频
  → 隔离、校验、OCR/VLM/ASR/帧时间处理
  → 结构化视觉/音频候选
  → 人工复核和 Evidence Bundle
  → 文本/结构化证据进入诊断 Agent
  → 检索、企业事实工具和结构化诊断报告
```

但是它还没有形成用户所说的：

```text
视觉 Observation → Agent Reasoning → GUI/设备 Action → 新视觉 Observation
```

现有闭环是“视觉证据 → 人工确认 → 诊断/业务流程”，不是“视觉 Agent 自主操作环境”。

## 6. Computer-use / GUI Agent 能力

当前判断：**Absent**。

在源码、前端依赖和脚本中，没有发现可证明以下能力的实现：

| 能力 | 状态 |
|---|---|
| Screenshot capture | Absent |
| DOM 读取 | Absent |
| Accessibility tree | Absent |
| Browser control | Absent |
| Desktop control | Absent |
| click / type / scroll / keyboard | Absent |
| Coordinate grounding | Absent |
| Element grounding | Absent |
| Action validation | Absent；现有 action validation 是诊断 JSON/tool contract，不是 GUI action validation |
| GUI environment state | Absent |
| GUI action history | Absent |
| GUI task success detection | Absent |

因此不存在可画出的 Computer-use loop。现有前端页面是被用户操作的产品界面，不是被 Agent 控制的环境；`web/lib/field-offline-*` 的 IndexedDB 离线包也不是浏览器自动化。

## 7. Backend / Systems 能力

| 能力 | 状态 | 证据 |
|---|---|---|
| API framework | **Implemented** | FastAPI，`api/app.py` 统一注册大量业务路由 |
| Async | **Implemented** | async route、Temporal Activity、异步 HTTP/Redis/媒体处理；CPU/DB 工作适当转线程 |
| Streaming | **Implemented** | `api/routes/agent_events.py` 使用 SSE；AG-UI 投影持久化事件。模型 transport 本身不是 token streaming |
| WebSocket / realtime | **Partial** | `realtime_media/` 和 `compose.realtime.yaml` 支持可选实时媒体/信令；默认关闭且依赖额外服务 |
| Queue / worker | **Implemented** | Temporal、workflow-worker、media worker、event/telemetry worker、Airflow 等 |
| Task execution | **Implemented** | 诊断、识别、知识、评测、训练等均有异步任务入口 |
| Concurrency | **Partial** | async、Temporal 并发、图片 OCR/VLM `gather` 存在；没有统一并发调度抽象 |
| Session | **Implemented** | NextAuth/Keycloak/OIDC、AgentRun、DiagnosisRun、媒体/证据和租户上下文 |
| Authentication | **Implemented** | OIDC/JWKS、Keycloak、服务端 session 和 API token 验证 |
| Authorization | **Implemented** | Authorizer + OPA + 租户/RLS/资源上下文 |
| Database | **Implemented** | SQLAlchemy、PostgreSQL/pgvector、迁移、事务租户上下文 |
| Cache | **Implemented** | Redis tenant cache；有命名空间和边界校验 |
| Object storage | **Implemented** | MinIO tenant object store，媒体和数据集分开使用 |
| Logging | **Implemented** | structlog、请求/租户 hash、可选日志文件镜像 |
| Tracing | **Implemented** | OpenTelemetry、traceparent、Agent/Inference span、Langfuse 属性 |
| Retry / timeout | **Implemented** | Temporal retry、模型 retry、HTTP/工具/媒体超时和预算 |
| Rate limit | **Implemented** | Tool rate limiter、Model Gateway quota、媒体限制 |
| Model routing | **Implemented** | Release/Deployment/Alias/endpoint/runtime profile 校验，OpenAI-compatible transport 和模型 router |
| Configuration | **Implemented** | Pydantic Settings，环境和生产安全规则；拒绝旧模型开关 |
| Secrets | **Implemented** | Vault/SecretProvider、受限 token 文件、模型 API key 注入 |
| Container | **Implemented** | 多进程 Dockerfile 和 Compose profile |
| Deployment | **Implemented conditionally** | Helm/Terraform/KServe/Compose/供应链脚本存在，但所需集群、镜像和制品不在 ZIP |
| Observability | **Implemented** | Prometheus metrics、OTel、Grafana/Tempo/Loki 配置和运维页面 |

这些系统能力不是简单 demo 级别的单文件示例；但“production-like 代码”与“当前快照已经在生产运行”是两件事，后者无法由静态仓库证明。

## 8. Model Layer

| 能力 | 状态 | 证据 / 说明 |
|---|---|---|
| OpenAI-compatible provider | **Implemented** | `model_gateway/openai.py:OpenAiCompatibleTransport` 调用 `/v1/chat/completions` |
| 诊断模型 | **Implemented conditionally** | Model Gateway 的 `DIAGNOSIS` 类；文档和配置指向 Qwen3-0.6B + Adapter |
| VLM | **Implemented conditionally** | `GatewayVlmProvider`、SmolVLM 运行时和 VLM route |
| OCR | **Implemented conditionally** | PaddleOCR，受 Release component 绑定 |
| ASR | **Implemented conditionally** | `TranscriptionGateway`、视频 ASR、实时 ASR |
| TTS | **Implemented conditionally** | `multimodal/tts_runtime.py`、Speech gateway 和专用训练/评测 |
| Embeddings | **Implemented conditionally** | `search_profiles/embedding.py`、Embedding runtime/KServe 路径 |
| Reranker | **Implemented conditionally** | `search_profiles/reranker.py`、Reranker runtime/KServe 路径 |
| Local model | **Implemented conditionally** | Transformers、Llama.cpp、GPU runtime；模型文件不在 ZIP |
| Structured output | **Implemented** | JSON Schema、Pydantic/JSON 校验、VLM/诊断/训练输出契约 |
| Function calling | **Partial** | Agent 使用 `action + tool_id` 自定义 JSON contract；未发现 OpenAI native `tools/function` 调用协议 |
| Model streaming | **Absent** | OpenAI transport 一次性 POST 并解析完整响应；外部 SSE 是 Agent event stream |
| Model router | **Implemented** | `model_gateway/router_runtime.py` 根据已绑定 diagnosis/VLM model id 转发 |
| Fallback | **Absent / Unknown** | 有 retry 和失败分类，但未发现通用模型 fallback 或自动切换 provider |
| Retry | **Implemented at Agent/Gateway boundary** | `DiagnosisRuntime` 对可重试 transport 状态重试；Gateway 维护幂等 inference audit |
| Prompt management | **Implemented** | `prompting/registry.py`、Prompt Bundle hash、Release Manifest 绑定 |

模型层和 Agent 层总体有清晰分层：`ModelGateway` 负责模型解析、配额、审计和 transport，`DiagnosisGraph/DiagnosisRuntime` 负责 state、action、工具和报告。但这是一种“垂直业务内的清晰分层”，不是已抽象成可供任意 Agent 使用的通用框架层。

## 9. Agentic RL / Training 现状

### 9.1 仓库确实有 RL/后训练代码，但需要区分层次

不能把整个项目直接称为 Agentic RL 项目，也不能说它完全没有 RL。更准确的判断是：

> **仓库存在真实的 SFT、DPO、GRPO、PPO 训练和模型发布/评测路径；但线上工业诊断 Agent 没有接入一个由环境、轨迹、奖励和成功信号驱动的在线 Agentic RL 闭环。**

代码证据：

- `training/backend.py`：实际调用 Transformers/TRL 的 `DPOTrainer`、`GRPOTrainer` 和 `trl.experimental.ppo.PPOTrainer`；也有 SFT、VLM、ASR、TTS、Embedding、Reranker 等专用训练。
- `training/config.py`：`CompiledDpoConfig`、`CompiledGrpoConfig`、`CompiledPpoConfig` 和奖励/模型 revision 约束。
- `training/grpo_reward_profile.py`、`training/reward_contracts.py`：版本化、确定性的 JSON reward contract。
- `agent/ppo_runtime.py`、`agent/grpo_runtime.py`、`agent/dpo_runtime.py`：加载不可变基础模型和 Adapter 的 GPU runtime，并执行结构化输出检查。
- `evaluation/backend.py`、`evaluation/metrics.py`：PPO safety、GRPO、DPO 和模型组件的 baseline/candidate 对比及 replay/安全门禁。

### 9.2 能力逐项判断

| 能力 | 状态 | 判断 |
|---|---|---|
| Trajectory | **Partial** | Agent checkpoint/event 能保存逐节点 state，但没有统一 `observation → action → result → reward` trajectory contract |
| Rollout | **Implemented in training/research paths** | PPO/GRPO Trainer 和 `simulation/*rollout*` 存在；不是线上诊断 Agent rollout |
| Environment | **Partial** | 有业务系统沙箱、KServe/部署 rollout、项目验收模拟；没有一个供线上 Agent 交互的通用 RL environment API |
| Action | **Implemented in diagnosis** | Agent action 是 RETRIEVE/CALL_TOOL/FINAL/NEEDS_INFORMATION；训练数据中的 action 也有结构化 JSON |
| Observation | **Implemented but fragmented** | evidence、tool facts、memory、事件和 model output 存在；未统一为 RL observation interface |
| Reward | **Implemented for GRPO/PPO experiments** | 确定性 GRPO reward、PPO reward model；不是每个线上诊断任务的业务结果 reward |
| Reward function | **Implemented for training profiles** | `score_reward`、`score_grpo_reward`、PPO reward scorer |
| Success signal | **Partial** | 评测有 success/gate/attack rate/replay 等；线上 Agent 没有统一任务成功判定 |
| Verifier | **Implemented in release/eval** | 结构化输出、引用、攻击成功率、部署/供应链和确定性 verifier 较多 |
| Policy | **Implemented** | PPO policy adapter、模型发布绑定、工具授权 policy；业务 Agent 不是独立可替换策略对象 |
| Logprob | **Partial** | DPO runtime 明确计算 safe/rejected log probability；PPO/GRPO 主要委托 TRL |
| KL | **Unknown in project code** | 可能由 TRL trainer 参数/实现承担，但当前仓库未形成独立 KL 观测契约 |
| Advantage | **Unknown in project code** | 未发现项目自有 advantage 计算；若存在主要由 TRL 负责 |
| PPO | **Implemented** | `training/backend.py:_train_ppo`、`agent/ppo_runtime.py`、PPO eval/release scripts |
| GRPO | **Implemented** | `_train_grpo`、版本化 reward profile、GRPO runtime 和 rollout scripts |
| REINFORCE | **Absent** | 未发现实现 |
| SFT | **Implemented** | `HuggingFaceSftBackend`、SFT config/trainer |
| Preference data | **Implemented conditionally** | DPO dataset/config 和 preference runtime 存在；当前 ZIP 只带有限样例/草稿资料 |
| Training scripts | **Implemented** | `training/cli.py`、`scripts/model_training_sandbox.sh` 等 |
| Evaluation environment | **Partial** | 有组件/模型/发布实验和项目沙箱；没有线上 Agent 任务环境的统一接口 |

### 9.3 当前 Agent 是否产生可用于 RL 的 trajectory

当前只能说**有可利用的片段**，不能说已经有标准 RL trajectory：

```text
已有：Agent state → node event → model decision → tool fact/checkpoint → report
缺少：统一 observation schema → action schema → tool/environment result → reward → success/termination
```

`agent/events.py` 和 `agent/checkpoints.py` 证明了执行记录和 state 持久化；`training/reward_contracts.py` 证明了训练 reward contract；但两者没有在当前代码中连接成“线上业务 Agent 自动产出、可回放、可评分、可用于 PPO/GRPO 的轨迹数据管道”。

所以：

- 如果“Agentic RL”指模型训练算法和受控实验：**已存在**。
- 如果指产品 Agent 在真实环境中执行并根据任务结果学习：**当前不存在**。

## 10. Evaluation

### 10.1 已实现的评测范围

- `evaluation/runner.py`：加载 job、candidate、baseline、suite、policy，执行成对评测。
- `evaluation/metrics.py`：有结构化输出、引用、延迟、Token、成本、replay、检索 Recall/MRR/NDCG、VLM region IoU/幻觉率、ASR WER/CER、TTS intelligibility、RUL/时序指标和 PPO safety 指标。
- `evaluation/backend.py`：有 Transformers、Llama.cpp、量化、Retrieval、VLM、ASR、TTS、PPO 等 backend。
- `model_gateway/benchmark.py`：模型推理 benchmark。
- `docs/m5-release/`、`datasets/`：诊断、模型推广、训练/验证和评测输入样例。
- 多处 `simulation/*`：VLM、ASR、DPO、GRPO、PPO、Reranker、部署 rollout 和项目闭环证据验证。

### 10.2 逐项判断

| 能力 | 状态 | 说明 |
|---|---|---|
| Unit tests | **Absent** | 当前快照未发现标准测试目录/测试文件 |
| Integration tests | **Partial** | CI 的 Compose cold-start、MCP/Vault/Helm/Terraform/供应链脚本是集成/契约验证，但不是常规测试套件 |
| Agent eval | **Partial** | 有 Agent JSON/PPO safety/reward 评估；没有覆盖线上诊断 Agent 全部决策轨迹的专用 regression suite |
| Multimodal eval | **Implemented** | VLM region、ASR、TTS、视频/多模态实验路径存在 |
| Task benchmark | **Implemented** | inference benchmark、项目验收和多种 model promotion lab |
| Success rate | **Implemented in eval profiles** | 有 structured success、safe response、attack success、quality gate 等 |
| Latency | **Implemented** | observation 和 metrics 保存延迟/p95 |
| Token usage | **Implemented** | ModelGateway/Agent state/evaluation observation 记录 input/output/token budget |
| Cost | **Implemented in evaluation** | evaluation observation 和成本计算存在；线上成本归因也有模块 |
| Trajectory replay | **Partial** | checkpoint/event 和部分评测 replay 存在；没有任意线上 Agent run 的通用重放器 |
| Regression tests | **Partial** | 版本化 verifier/contract/CI 存在；缺少传统自动化回归测试集 |
| LLM-as-judge | **Absent / not configured** | `evaluation/runner.py` 多处明确 `"judge": "NOT_CONFIGURED"` |
| Deterministic verifier | **Implemented** | JSON schema、reward contract、manifest、release、引用、部署和供应链验证较多 |

### 10.3 能否回答“修改 Agent 后，它真的变好了吗？”

对**模型/组件/发布候选**：部分可以。仓库有 baseline/candidate、冻结数据、确定性指标、延迟/成本和发布门禁。

对**核心线上诊断 Agent 的任意改动**：目前不能稳定回答。主要原因是没有标准 Agent test suite、统一 trajectory replay、线上业务 success signal 和完整的 Agent-level regression benchmark。

## 11. 项目成熟度

评分标准：`0 = 不存在`，`1 = demo`，`2 = 初步可用`，`3 = 比较完整`，`4 = production-like`。分数评价的是当前仓库证据，不是代码行数，也不是未提供的运行环境。

| 模块 | 分数 | 依据 |
|---|---:|---|
| Product | **2** | 页面和业务域广，主流程代码存在；完整外部环境和真实用户验收未在本次确认 |
| Frontend | **2** | Next.js 页面覆盖广、类型化 API 和事件展示存在；未实际执行 build/交互验收 |
| Backend | **3** | FastAPI、事务、租户、Temporal、Worker、错误处理和业务状态较完整 |
| LLM integration | **3** | Model Gateway、OpenAI-compatible transport、结构化输出、Release/Quota/Audit 完整度较高 |
| Agent | **2** | 有真正的受限多步诊断 Agent，但领域绑定、只有一个核心 Agent loop，缺少通用评测闭环 |
| Tools | **3** | Registry、schema、版本、权限、审批、幂等、限流和多种 transport 都有 |
| Multimodal | **2** | 图片 OCR/VLM 和视频帧/ASR/temporal 代码较丰富，但依赖可选运行环境，未证实端到端实际运行 |
| Computer-use | **0** | 没有 GUI/browser 控制能力 |
| Context / Memory | **2** | 有人工确认记忆、上下文 Manifest、Token budget 和截断审计；不是通用记忆系统 |
| Reliability | **3** | 幂等、CAS checkpoint、Temporal retry、timeout、quota、审计和 fail-closed 约束较完整 |
| Evals | **2** | 组件和发布评测丰富，但缺少标准测试套件和线上 Agent regression/replay |
| Observability | **3** | OTel、structured log、Prometheus、SSE/AG-UI、Agent event store 存在 |
| Deployment | **3** | Compose/Helm/Terraform/KServe/供应链验证代码存在；模型和实际基础设施不在 ZIP |
| Agentic RL readiness | **2** | 有 PPO/GRPO/reward/eval scaffolding；缺少线上 Agent environment、trajectory、reward 和 success 连接 |

## 12. 技术债与架构问题

以下只记录已有证据，不在本次修复。

### 12.1 Production、simulation 和 research 路径混在同一个 Python 包

**Evidence**：`src/industrial_ops_agent/simulation/` 包含大量 `*_value_lab.py`、`*_rollout.py`、`*_acceptance.py`；同一仓库同时有 `agent/ppo_runtime.py`、生产 `model_gateway`、业务 `application` 和 deployment controller。

**Consequence**：阅读者容易把模拟/验收证据当成生产业务事实；产品能力、研究实验和发布验证的边界需要依赖命名和调用者判断。

### 12.2 缺少标准测试套件

**Evidence**：当前快照没有标准 `tests/` 或 `test_*.py`；CI 主要运行 ruff/mypy/OpenAPI/client build、Compose 和多个契约脚本。

**Consequence**：对核心 Agent、业务状态、媒体处理和权限组合的回归覆盖难以直接量化；“CI 通过”不等于业务流程回归充分。

### 12.3 线上 Agent 执行日志和 RL trajectory 没有统一连接

**Evidence**：`agent/checkpoints.py` 持久化 graph state，`agent/events.py` 持久化事件；训练侧使用 `training/reward_contracts.py`、PPO/GRPO trainer 和独立 simulation/evaluation 数据。

**Consequence**：当前不能直接从真实诊断 run 构造标准 observation/action/result/reward trajectory，也不能直接 replay 一次线上诊断并进行 RL 训练闭环。

### 12.4 Agent runtime 与诊断业务强耦合

**Evidence**：`DiagnosisRuntime` 固定 `DIAGNOSIS_GRAPH_VERSION`、诊断 prompt、工业工具列表、诊断报告和 `DiagnosisWorkflowInput`；`DiagnosisActivity` 直接组装 `DiagnosisGraph`。

**Consequence**：它适合当前工业诊断，但不能不改造就成为 ChangeGuard 那种通用 Agent Harness 或多个产品共用的 runtime。

### 12.5 两层持久化/重试责任并存

**Evidence**：`orchestration/workflows.py` 让 Temporal 拥有 durable orchestration 和 retry；`agent/graph.py` 明确不使用第二个 checkpointer/retry policy，但 `agent/checkpoints.py` 又独立持久化图状态并执行 CAS；`DiagnosisRuntime` 还有自己的 model retry。

**Consequence**：恢复、重试、事件顺序和幂等的责任分布在 Temporal、Agent checkpoint 和 ModelGateway 三处，维护者需要同时理解多个状态源。

### 12.6 Multimodal provider 存在并行实现路径

**Evidence**：`multimodal/providers.py` 同时有 `OpenAiCompatibleVlmProvider` 和 `GatewayVlmProvider`；`video.py` 有 development ASR 和 Gateway ASR；`orchestration/runner.py` 根据运行配置组装不同 provider。

**Consequence**：同一能力可能走不同的治理、审计和依赖边界；静态阅读时不能只看到 provider 类就断言生产路径使用了它。

### 12.7 没有 GUI environment abstraction

**Evidence**：没有 browser/desktop environment、DOM/accessibility/action executor/success detector；现有 `web/` 是被用户访问的应用页面。

**Consequence**：无法自然地扩展为 screenshot → action → new screenshot 的 Computer-use Agent，也没有现成的 GUI trajectory 采集点。

### 12.8 模型 fallback 没有形成清晰的通用策略

**Evidence**：`model_gateway/openai.py` 只有单一 OpenAI-compatible transport；`DiagnosisRuntime` 对部分错误重试固定请求；`router_runtime.py` 按绑定 model id 路由，没有看到通用 fallback provider。

**Consequence**：模型服务不可用时主要是失败/重试/预算终止，不是自动降级到备用模型的高可用策略。

### 12.9 Compose profile 和历史兼容层增加配置判断成本

**Evidence**：仓库同时有 `compose.lite.yaml`、`compose.real-model.yaml`、`compose.integration.yaml`、`compose.realtime.yaml`、`compose.observability.yaml` 和历史 `compose.ai.yaml`；README 明确提示旧模型开关会被当前 `Settings` 拒绝。

**Consequence**：部署成功依赖正确的文件组合、顺序、环境变量和绑定，不能把“某个 Compose 文件存在”理解为对应能力已经可用。

### 12.10 Prompt 本身集中，但业务契约仍分布在多个层

**Evidence**：prompt 有 `prompting/registry.py` 和 Manifest hash；但输出契约还分布在 `agent/contracts.py`、VLM schema、Tool Registry、评测 dataset 和各 runtime。

**Consequence**：Prompt 版本是集中治理的，但修改 Agent 行为时仍需同步检查模型输出、工具、报告、评测和发布契约，变更影响面较宽。

## 13. 与 ChangeGuard 的能力重合

以下关于 ChangeGuard 只使用用户提供的定位，不把未提供的内容当作事实。

### 13.1 当前项目已经重合的能力

| ChangeGuard 能力 | 当前项目对应实现 | 重合程度 |
|---|---|---|
| Agent runtime / harness | `agent/graph.py`、`diagnosis_runtime.py`、`orchestration/workflows.py` | 中等；当前项目是诊断专用 |
| 多步 Agent loop | LangGraph 五节点 bounded loop | 高 |
| Tool calling | `action + tool_id`、Tool Registry、Tool Gateway | 高 |
| State / validation | `diagnosis-state/v2`、JSON Schema、Pydantic、checkpoint binding | 高 |
| Policy / approval | OPA、Authorizer、T2 proposal/approval、Tool Gateway | 高 |
| Trace | Agent event store、OTel、SSE/AG-UI、Inference audit | 高 |
| Retry / recovery | Temporal retry、model retry、checkpoint resume/cancel、幂等 | 中高 |
| Benchmark / evals | Evaluation Runner、paired metrics、replay gate、release gates | 中等；主要偏模型/发布 |
| Agent reliability | budget、timeout、CAS、审计、fail-closed、工具权限 | 中高 |
| Workspace isolation 的相近部分 | tenant context、RLS、对象存储命名空间、证据隔离 | 部分重合，但不是同一语义的 workspace isolation |

### 13.2 当前项目拥有而 ChangeGuard 不强调的能力

基于用户提供的 ChangeGuard 定位，当前项目的差异主要在：

- 工业售后产品工作流：Incident、诊断、报价、派工、工单、现场证据、验收、客户门户和关闭。
- 多模态媒体链路：隔离上传、OCR、VLM、QR、视频关键帧、ASR、时间事件和人工识别复核。
- 企业事实和模型治理：Model Release、Deployment、Alias、Manifest、Quota、Inference audit、供应链和审批。
- 知识和检索产品：文档入库、授权检索、GraphRAG、Search Profile、Embedding、Reranker。
- 前端与人机交互：Next.js 工作台、现场 PWA/离线包、识别复核和业务审批页面。
- 训练/评测/发布闭环：SFT、DPO、GRPO、PPO、VLM/ASR/TTS/Embedding/Reranker 训练和候选发布。
- 实时媒体和企业接入：实时语音/媒体、MCP、HTTP、A2A、Kafka/Debezium、Airflow 等。
- **没有** ChangeGuard 之外可推断的 Browser/GUI Agent；当前项目的多模态不是 Computer-use。

当前最大的重合点是：**受约束的 Agent 执行、工具治理、状态、审批、追踪、重试和评测。**

当前最大的差异点是：**本项目把 Agent 嵌入工业多模态业务和模型生命周期；ChangeGuard 的核心是通用 Agent harness/reliability，而本项目的主价值在垂直应用、媒体证据、企业工作流和模型运营。**

## 14. 求职信号

评分只基于当前仓库内容，不把未来可能加入的 Browser、GUI 或在线 RL 计入。

### Applied AI Engineer

- **当前 signal**：能够把模型、检索、媒体、人工复核和企业业务流程组合成可追踪的应用，而不是只调用一个 LLM API。
- **证据**：`application/incidents.py`、`application/diagnoses.py`、`knowledge/`、`multimodal/`、`model_gateway/`、`workorders/`。
- **缺失**：真实生产运行证据、用户质量数据和稳定的产品级回归测试。
- **signal strength**：**Strong**。

### AI Engineer

- **当前 signal**：理解多种模型组件、OpenAI-compatible serving、结构化输出、Embedding/Reranker/VLM/ASR/TTS 和模型评测。
- **证据**：`model_gateway/`、`multimodal/`、`search_profiles/`、`training/`、`evaluation/`。
- **缺失**：仓库内没有模型权重和可复现运行产物；训练结果不能仅凭快照复核。
- **signal strength**：**Medium**。

### Agent Engineer

- **当前 signal**：实现过真实的模型驱动多步 Agent：有 action contract、只读工具、观察回填、预算、checkpoint、事件和结构化报告。
- **证据**：`agent/graph.py`、`agent/diagnosis_runtime.py`、`agent/contracts.py`、`tools/gateway.py`。
- **缺失**：Agent 主要是单一工业诊断 loop，缺少通用 Agent benchmark、环境交互和可复用 SDK。
- **signal strength**：**Medium**。

### Agent Systems Engineer

- **当前 signal**：能处理 Durable workflow、租户隔离、授权、幂等、审计、模型路由、异步 Worker、可观测性和发布治理。
- **证据**：`orchestration/`、`persistence/`、`auth/`、`security/`、`model_gateway/`、`.github/workflows/`。
- **缺失**：没有足够的真实运行/容量/故障演练结果，且部分系统能力是垂直业务绑定的。
- **signal strength**：**Strong**。

### Agent Harness Engineer

- **当前 signal**：具备 state、tool contract、checkpoint、retry、approval、trace、budget 和 recovery 的实际经验。
- **证据**：`agent/`、`tools/`、`orchestration/`、`agent_events.py`。
- **缺失**：不是通用 harness；没有 ChangeGuard 所强调的通用 workspace isolation、可插拔环境和跨任务抽象，也没有 Computer-use。
- **signal strength**：**Medium**，且与 ChangeGuard 的信号高度重合。

### AI Backend Engineer

- **当前 signal**：后端工程面很强：FastAPI、SQLAlchemy/PostgreSQL、Redis、MinIO、Temporal、OIDC/OPA、Vault、Docker、Helm、OTel 和 CI。
- **证据**：`api/`、`persistence/`、`cache/`、`object_store/`、`orchestration/`、`infra/`、`docker/`。
- **缺失**：没有在本次盘点中验证实际部署、性能和高可用指标。
- **signal strength**：**Strong**。

### Multimodal Agent Engineer

- **当前 signal**：能把图片/视频/音频处理、OCR/VLM/ASR、证据复核、结构化输出和诊断业务连接起来。
- **证据**：`multimodal/processor.py`、`multimodal/providers.py`、`multimodal/video.py`、`api/routes/recognition.py`。
- **缺失**：不是 perception-action GUI Agent；没有 screenshot loop、element grounding 或连续 Computer-use。
- **signal strength**：**Medium**。

### Agentic RL Engineer

- **当前 signal**：有真实的 SFT/DPO/GRPO/PPO Trainer 接入、reward contract、PPO/GRPO runtime、GPU 运行和 candidate/baseline 评测。
- **证据**：`training/backend.py`、`training/config.py`、`training/grpo_reward_profile.py`、`agent/ppo_runtime.py`、`evaluation/backend.py`。
- **缺失**：线上诊断 Agent 没有标准 RL environment、trajectory、任务 reward 和 success signal；PPO/GRPO 主要是独立的模型后训练/研究发布路径。
- **signal strength**：**Medium**；对于“应用型模型后训练”是中等，对于“交互式 Agentic RL”不是 Strong。

# Executive Summary

1. **用一句话描述这个项目当前实际上是什么。**

   它是一个面向工业设备运维和售后的企业级多模态 Agent 应用，外围配有模型网关、工作流、工具治理、训练评测和部署治理平台能力。

2. **当前最核心的完整 workflow 是什么。**

   用户创建工业故障、上传图片/视频、经过扫描和 OCR/VLM/ASR 识别并人工确认后，系统通过 Temporal + LangGraph 诊断 Agent 结合授权知识和企业只读工具生成带引用和缺失信息的结构化诊断报告。

3. **当前最有价值的三项技术能力是什么。**

   - 诊断场景中的真实 bounded Agent loop：模型决定检索、工具调用或结束，并有持久化 state 和事件。
   - 企业级工具/模型治理：schema、版本、权限、审批、幂等、配额、Release/Deployment/Inference audit。
   - 多模态证据链：图片 OCR/VLM、视频帧/音频/时间事件、人工复核和证据溯源连接到业务流程。

4. **当前最薄弱的三项能力是什么。**

   - 没有 Browser/Computer-use/GUI action 能力。
   - 没有标准测试套件、通用 Agent replay 和覆盖核心诊断的 Agent regression benchmark。
   - 线上 Agent state/event 尚未形成带 reward/success 的标准 RL trajectory；PPO/GRPO 与产品 Agent 仍是分离的训练/研究路径。

5. **Multimodal 当前到底做到什么程度。**

   已经做到图片 OCR/VLM、结构化视觉 finding、区域框、视频关键帧、ASR 和 temporal VLM 的条件式处理，并通过人工复核进入诊断；没有做到 screenshot → GUI action → 新 screenshot 的多模态 Agent 闭环。

6. **Agent 当前到底做到什么程度。**

   已经有一个真实的、受预算约束的单诊断 Agent loop，支持结构化 action、只读工具、观察回填、显式 state、checkpoint、retry、终止条件、人类审批边界和持久化 trace；但它是工业诊断专用 Agent，不是通用 Harness。

7. **Agentic RL 当前是否已经存在，以及离可引入 RL 还缺什么。**

   PPO/GRPO/DPO/SFT 的训练、reward 和评测代码已经存在；但线上工业诊断 Agent 还没有统一 environment、observation/action/result/reward/success trajectory 和通用 replay，因此当前不存在产品级在线 Agentic RL 闭环。

8. **它与 ChangeGuard 当前最大的重合点和最大的差异点分别是什么。**

   最大重合点是受约束 Agent runtime 的基础能力：loop、tool、state、approval、retry、trace、eval 和 reliability。最大差异点是本项目把这些能力用于工业多模态售后产品、企业事实、媒体证据、工单和模型生命周期；它没有 ChangeGuard 所代表的通用 harness 和 Computer-use 方向。

# Evidence Index

以下是支撑主要判断的关键文件；路径均相对于当前项目根目录。

## 项目结构、入口和系统组装

- `src/industrial_ops_agent/main.py`：API 进程入口。
- `src/industrial_ops_agent/runtime.py`：数据库、模型、工具、识别、Temporal、实时媒体等运行时组装。
- `src/industrial_ops_agent/config.py`：环境、模型 alias、VLM/OCR、实时媒体和安全校验。
- `src/industrial_ops_agent/api/app.py`：FastAPI 应用工厂、健康检查、路由注册。
- `pyproject.toml`：Python 依赖、可选训练/评测/多模态依赖和 CLI 入口。
- `web/package.json`：Next.js/React/pnpm 前端依赖和构建脚本。
- `Makefile`、`compose.lite.yaml`、`compose.real-model.yaml`：开发、基础服务和真实模型部署边界。

## 核心诊断 Agent 和工作流

- `src/industrial_ops_agent/application/diagnoses.py`：诊断前置条件、幂等、模型 binding、Manifest 和 Temporal 派发。
- `src/industrial_ops_agent/orchestration/workflows.py`：`DiagnosisActivity`、`DiagnosisWorkflow`、Temporal retry 和报告发布。
- `src/industrial_ops_agent/agent/graph.py`：LangGraph bounded loop、节点和 action 路由。
- `src/industrial_ops_agent/agent/diagnosis_runtime.py`：state、预算、记忆、检索、工具调用、模型请求、retry 和报告。
- `src/industrial_ops_agent/agent/contracts.py`：诊断 action/output schema 和校验。
- `src/industrial_ops_agent/agent/checkpoints.py`：持久化 graph checkpoint 和 CAS 冲突控制。
- `src/industrial_ops_agent/agent/events.py`、`agent/ag_ui.py`：append-only Agent event 和 AG-UI 投影。
- `src/industrial_ops_agent/api/routes/agent_events.py`、`api/routes/diagnoses.py`：Agent SSE/AG-UI 和诊断 API。

## 工具、权限、审批和企业系统

- `src/industrial_ops_agent/tools/registry.py`：ToolDefinition、JSON Schema、版本、风险、审批、限流配置。
- `src/industrial_ops_agent/tools/gateway.py`：工具校验、授权、审批、幂等、企业调用和结果记录。
- `src/industrial_ops_agent/tools/contracts.py`：工具 transport、只读/业务执行适配器和错误契约。
- `src/industrial_ops_agent/tools/mcp.py`、`tools/enterprise_http.py`：MCP/HTTP 企业工具接入。
- `src/industrial_ops_agent/auth/`、`security/`、`persistence/tenant.py`：身份、OPA、租户和数据边界。

## 多模态和媒体

- `src/industrial_ops_agent/media/service.py`、`media/runner.py`：上传、对象存储、隔离扫描和媒体状态。
- `src/industrial_ops_agent/multimodal/providers.py`：PaddleOCR、VLM、QR、Gateway provider 和结构化 finding。
- `src/industrial_ops_agent/multimodal/processor.py`：图片/视频识别编排、候选融合和证据结构。
- `src/industrial_ops_agent/multimodal/video.py`：PyAV 关键帧、音频、ASR 和 temporal VLM。
- `src/industrial_ops_agent/multimodal/vlm_runtime.py`：受管 VLM GPU runtime 和图片边界。
- `src/industrial_ops_agent/api/routes/uploads.py`、`api/routes/recognition.py`：媒体上传、识别任务和人工复核 API。
- `web/app/incidents/drafts/[draftId]/recognition/page.tsx`：前端 OCR/VLM/视频候选复核界面。

## 模型层、训练、RL 和评测

- `src/industrial_ops_agent/model_gateway/service.py`：Release/Deployment/Alias/Quota/Manifest/Inference governance。
- `src/industrial_ops_agent/model_gateway/openai.py`：OpenAI-compatible `/v1/chat/completions` transport。
- `src/industrial_ops_agent/model_gateway/router_runtime.py`：诊断/VLM endpoint router。
- `src/industrial_ops_agent/prompting/registry.py`：Prompt Bundle registry 和 content hash。
- `src/industrial_ops_agent/training/backend.py`：SFT、DPO、GRPO、PPO 以及专用模型训练 backend。
- `src/industrial_ops_agent/training/config.py`：训练方法、reward contract、revision 和 Adapter 配置。
- `src/industrial_ops_agent/training/grpo_reward_profile.py`、`training/reward_contracts.py`：确定性 reward contract。
- `src/industrial_ops_agent/agent/ppo_runtime.py`、`agent/grpo_runtime.py`、`agent/dpo_runtime.py`：实际 GPU Adapter runtime。
- `src/industrial_ops_agent/evaluation/backend.py`、`evaluation/runner.py`、`evaluation/metrics.py`：候选/基线评测、指标和 verifier。
- `src/industrial_ops_agent/simulation/`：训练、模型推广、发布 rollout 和项目验收实验代码；不能直接当作线上生产证据。

## 部署、CI 和可复现边界

- `.github/workflows/ci.yml`：静态类型、OpenAPI、Web build、Compose Lite、Vault/Helm/Terraform/供应链契约检查；没有标准 pytest 调用。
- `.github/workflows/supply-chain.yml`：模型 runtime 镜像、SBOM、漏洞和签名证据流程。
- `docker/`：API、Web、Worker、模型、训练和多模态镜像。
- `infra/helm/`、`infra/terraform/`、`infra/kserve/`：部署和模型 serving 配置。
- `scripts/`：`m1_verify.sh`、`real_model_business_loop.sh`、`gpu_model_promotion_lab.sh`、`ppo_kserve_rollout.sh`、`grpo_kserve_rollout.sh` 等验证/发布脚本。
- 当前 ZIP 中未发现 `artifacts/`、模型权重或可直接复核的训练/部署产物；因此验收脚本和 simulation 文件本身只能证明“存在验证逻辑”，不能证明本次快照已完成对应真实运行。
