# Batch 2A.2 Evidence Provenance Audit

## Scope and conclusion

本次只做审计，不修改代码，不进入 Batch 2B，不修改 Multimodal。审计对象是
当前已完成的链路：

```text
MultimodalProcessor → PerceptionResult → RecognitionService → EvidenceBundle
```

结论是：持久化层已经保存了恢复闭环所需的大部分原始关联，但
`Diagnosis Manifest → Agent Context → Final Report Citation` 尚未建立。问题不是
EvidenceBundle 在迁移中丢失了 finding，而是 Diagnosis runtime 没有把已持久化的
recognition result 解析为 Agent 可引用的证据上下文。

## 1. EvidenceBundle storage audit

### 1.1 Domain model

`industrial_recognition/evidence.py` 中的 `EvidenceBundle` 仍然保留工业诊断所需
的完整语义：

- Bundle identity：`bundle_id`、`tenant_id`、`draft_id`、`asset_id`、`media_id`。
- Source binding：`source_sha256`、`source_type`。
- OCR：`OcrBlock.block_id`、文本、页码、归一化 bounding box、confidence，视频时
  还有 `source_frame_id`。
- Visual：`VisualFinding.finding_id`、label、区域、confidence、description、
  `model_release_id`，视频时还有 `source_frame_id`。
- ASR：`AsrSegment.segment_id`、时间范围、文本、confidence、
  `model_release_id`、音轨及其 entity candidate。
- Video：`VideoKeyframe.frame_id`、图像 hash；`VideoEvent.event_id`、时间范围、
  keyframe IDs、finding IDs、confidence 和 `model_release_id`。
- Entity/QR/security：实体的 `source_block_id`；QR 的 `candidate_id`；安全 finding
  的 `source_type` + `source_id` + policy/pattern/content hash。
- Review state：`FindingReview`、`OcrReview`、`TranscriptReview`、
  `VideoEventReview`、`QrReview`、human correction，以及 bundle 的
  `status`、`version`、`automation_eligible`、`automation_blockers`。

### 1.2 Persistence path

生产持久化路径位于 `application/incidents.py`：

```text
EvidenceBundle
  ├─ _evidence_record() → evidence_bundles
  └─ _evidence_result_records() → recognition_results
```

`persistence/models.py` 中的实际字段如下：

| 需要的关联 | 当前状态 | 实际路径 |
| --- | --- | --- |
| `finding_id` | 已存在 | `RecognitionResultRecord.payload["finding_id"]`，对应 `VISUAL_FINDING`；OCR 使用 `block_id`，ASR 使用 `segment_id`，视频事件使用 `event_id`，QR 使用 `candidate_id` |
| `source_id` | 部分存在 | 安全 finding 有明确的 `source_id`；实体有 `source_block_id`；视频结果有 `source_frame_id`；不存在所有 result 类型统一命名的 `source_id` 字段 |
| `provenance_id` | 缺失 | 没有独立的 provenance ID/表，也没有 recognition result 到 citation 的统一 provenance record |
| media reference | 已存在 | `EvidenceBundleRecord.media_id`、`RecognitionRunRecord.media_id`、bundle 的 `source_sha256`；视频 keyframe 另有 `image_sha256` |
| model output reference | 部分存在 | Visual/ASR/video event 保存 `model_release_id`；bundle 的 `processor_versions` 可保存模型执行证据，包括 inference request reference，但不是统一 finding provenance 外键 |
| OCR persistence | 已存在 | `recognition_results` 的 `OCR_BLOCK` payload，含 block ID、文本、bbox、confidence、frame reference |
| visual persistence | 已存在 | `recognition_results` 的 `VISUAL_FINDING` payload，含 finding ID、label、bbox、confidence、description、model release、frame reference |
| ASR persistence | 已存在 | `recognition_results` 的 `ASR_SEGMENT` payload，含 segment、时间、文本、confidence、model release、entity candidates |
| review persistence | 已存在 | `recognition_corrections`，按 target type/id 和 evidence version 保存 correction/review；bundle record 保存整体状态和 automation 状态 |
| citation record | 已存在但不适用 | `CitationAnchorRecord` 只锚定 Knowledge chunk/document/version；没有 EvidenceBundle 或 recognition result 外键 |

因此，现有 storage 足以定位：

```text
bundle_id
  → evidence_bundles
  → recognition_results(bundle_id, result_type, ordinal, payload)
  → payload 内的 finding/block/segment/event/candidate ID
  → bundle.media_id / source hash / model release information
```

但它不能直接给出：

```text
recognition result
  → diagnosis citation/provenance record
```

### 1.3 Persistence parity implication

这排除了“迁移时 EvidenceBundle 数据已经丢失”的假设。Batch 2A.1 service-level
验证已经实际执行 persist → reload → human confirmation，并读取到 OCR、visual
finding、区域、confidence、processor provenance、review state 和 automation
eligibility。缺口发生在 reload 之后的 Diagnosis context construction。

## 2. Diagnosis Manifest audit

### 2.1 Manifest model

`agent/models.py::DiagnosisManifest` 当前包含：

```text
incident_version
evidence_bundle_id
evidence_version
model_release
prompt_bundle
index_release_id
agent_graph_version
tool_versions
budget
created_at
prompt_bundle_hash
```

`application/diagnoses.py::DiagnosisService.start()` 从已确认的
`EvidenceBundleRecord` 读取 bundle/status/version，并只将：

```text
evidence_bundle_id
evidence_version
```

写入 `DiagnosisManifest`。这解释了当前为什么只有 `bundle_id/version`：该服务
把 EvidenceBundle 当作自动诊断准入和版本绑定对象，但没有把其 result-level
内容转换成 Diagnosis 输入证据。

### 2.2 Context builder

`orchestration/workflows.py` 的 Diagnosis Activity 调用
`DiagnosisRuntime._load_context()`。该函数加载 incident、asset、manifest 和
device-family context，但不通过 `EvidenceBundleRepository` 读取
`EvidenceBundleRecord`，也不通过 `list_results()` 读取
`RecognitionResultRecord`。

`DiagnosisRuntime.load()` 初始化：

```text
state["evidence"] = []
```

`DiagnosisRuntime.retrieve()` 只把 `HybridRetriever.search_with_trace()` 返回的
Knowledge `RetrievedEvidence` 写入这个 state。确认过的 perception finding 没有
进入 Agent state。

## 3. Agent evidence consumption audit

### 3.1 Agent needs evidence, not merely a bundle summary

从实际运行代码看，Agent step request 使用：

```text
state["evidence"][:4]
  → citation_id/title/content_checksum/content
  → authorized_evidence
```

因此 Agent 当前不是只需要一个 `bundle_id/version` summary。它需要一组可授权、可
引用的 evidence items。当前这组 items 仅由 Knowledge retrieval 提供。

### 3.2 Citation generation

`DiagnosisRuntime._report_from_model()` 的实际逻辑是：

```text
RetrievedEvidence.citation_id
  → RetrievedEvidence.citation_payload()
  → DiagnosisReport.citations
```

模型输出只提交 `citation_ids`。代码再从当前 retrieval evidence 映射这些 IDs，
而不是从 EvidenceBundle 或 recognition result 映射。

`RetrievedEvidence` 本身要求 Knowledge-specific 字段：
`chunk_id`、`document_id`、`document_version_id`、document version、title、
content/checksums、device model、ranking fields。`CitationAnchorRecord` 也只支持
Knowledge document/chunk anchor。因此不能把 industrial finding 直接伪装成
Knowledge citation；那会污染语义并造成错误 provenance。

### 3.3 Final report

`DiagnosisReport` 当前字段是：

```text
status / conclusion / citations / contradictions /
missing_information / next_checks / confidence / stop_reason
```

字段集合本身可以继续保留，但现有 `citations` 生成路径只能追溯到 Knowledge
retrieval item，不能追溯到：

```text
DiagnosisReport
  → persisted EvidenceBundle
  → original perception finding
```

## 4. Minimal bridge options

### Option A — runtime resolver only

运行时依据已有 manifest 的 `evidence_bundle_id` + `evidence_version`，读取
EvidenceBundleRecord 和 recognition results，构造 Agent context，再生成 industrial
evidence citation。

| 维度 | 判断 |
| --- | --- |
| Complexity | 中等；不改数据库，但需要 runtime resolver、result-to-context adapter 和 citation adapter |
| Migration risk | 低；现有记录已经包含所需 ID/ payload |
| Technical Incident Triage reuse | 中等；runtime 绑定强，其他入口需要重复理解 bundle/result 映射 |
| 限制 | 当前 Agent context/citation 是 Knowledge-specific；若不扩展内部 Agent evidence contract，就只能错误复用 `RetrievedEvidence` 字段 |

Option A 不能在保持语义正确的前提下只改一个 resolver。它适合已有 generic
evidence/citation contract 的系统，但当前仓库没有该 contract。

### Option B — manifest evidence references

DiagnosisService 在创建 manifest 时，从已确认 bundle 生成稳定、最小的
result-level references，例如：

```text
evidence_references:
  - bundle_id
    evidence_version
    result_id
    result_type
    source_id
    media_id
    source_sha256
    model_release/inference reference when present
    content/provenance hash
```

Agent context builder 只解析这些 immutable references，并在现有最终报告字段中
产生 citation；citation payload 增加能回指 bundle/result/media 的字段。Rejected 或
unconfirmed result 不进入 references。必要时将整组 references 的 canonical hash
绑定进 manifest，避免 runtime 读取到另一个版本。

| 维度 | 判断 |
| --- | --- |
| Complexity | 中等偏低；manifest builder、context adapter、citation adapter 三处局部变化 |
| Migration risk | 低；从现有 EvidenceBundle/RecognitionResultRecord 回填新 manifest，不需历史表迁移 |
| Technical Incident Triage reuse | 高；incident/triage/reanalysis 都可以消费同一组 opaque evidence references |
| 优点 | 明确冻结 diagnosis 输入；不把 industrial policy 塞回 Multimodal，也不依赖 Knowledge citation model |
| 限制 | 需要扩展 Agent 内部 evidence/context/citation contract；不需要改变最终 `DiagnosisReport` 字段集合或公开 Diagnosis request API |

### Option C — persistence schema change

增加独立的 normalized provenance/citation 表，或给 recognition result 增加统一
provenance 外键，再让 manifest/runtime 使用该表。

| 维度 | 判断 |
| --- | --- |
| Complexity | 高；新表/约束、回填、并发和跨版本迁移 |
| Migration risk | 高；需要历史数据回填和 PostgreSQL rehearsal |
| Technical Incident Triage reuse | 高，但只有在多个消费方都需要复杂 provenance 查询时才有价值 |
| 当前必要性 | 不必要；`bundle_id`、`result_id`、result type/payload、media ID、hash 和部分 model refs 已经存在 |

## 5. Recommended minimal design and stop condition

推荐 **Option B 的无数据库迁移版本**：

1. 以现有 `EvidenceBundleRecord` + `RecognitionResultRecord` 为 source of truth；不
   新增 provenance persistence schema。
2. 在 Diagnosis manifest 中保存确认后、版本绑定的最小 result references，而不是
   复制完整 finding payload。
3. 由 Diagnosis context adapter 把 references 解析成 Agent 可消费的 domain-neutral
   evidence item；读取时重新校验 tenant、bundle/version、review/confirmation、
   result ID、media hash 和 provenance hash。
4. 由 citation adapter 生成同时包含 `citation_id` 与 bundle/result/media/finding
   回指信息的 citation payload。
5. 保持现有 `DiagnosisReport` 字段集合和模型 step 的 `citation_ids` 机制；不要
   修改 Multimodal、Knowledge/RAG、Tool runtime 或业务领域。

但当前仓库的 `RetrievedEvidence` 是 Knowledge-specific，且
`_report_from_model()` 只接受它。因此要正确实施 Option B，至少需要扩展 Agent
内部 evidence/context/citation contract。若“Agent contract”包括该内部 contract，
则已触发本任务的 Stop Condition 3。

本次按要求停止，不实现 Option B，也不采用把 industrial finding 填入
`RetrievedEvidence` 的伪适配方式。

## 6. Required changes if implementation is later authorized

这些是后续实施前的边界清单，不是本次修改：

- `application/diagnoses.py`：从 confirmed persisted bundle 生成最小 immutable
  evidence references。
- `agent/models.py` 或相邻 generic agent-context contract：定义 domain-neutral
  evidence reference/context，不复制 Knowledge-specific ranking fields。
- `agent/diagnosis_runtime.py`：加载、校验并合并 confirmed evidence；citation 只能
  选择当前 authorized context 中的 reference。
- `agent/contracts.py`/citation adapter：保持模型只输出 `citation_ids`，由运行时将
  ID 映射到可追溯 payload；确认是否需要扩展 schema 的 citation payload，而不是
  修改最终 DiagnosisReport 字段集合。
- 现有 `EvidenceBundleRecord`、`RecognitionResultRecord`：本方案不要求 migration，
  继续作为 source of truth。

不得在后续实现中：

- 把 EvidenceBundle 或工业 finding 重新放回 Multimodal；
- 把工业 finding 伪装为 Knowledge chunk/citation；
- 为此创建新的通用 ontology、schema registry 或通用表达式语言；
- 修改公开 Diagnosis request API；
- 进入 Retrieval applicability、fulfillment deletion 或 Batch 2B。

## 7. Answers

### 1. 当前缺失在哪一层？

缺失在 **Diagnosis context/citation bridge**：持久化 EvidenceBundle 和 result
records 存在，Diagnosis manifest 只保存 bundle ID/version，Agent runtime 只消费
Knowledge retrieval evidence，最终 citation 没有 recognition-result provenance。

### 2. 最小修复是什么？

在不改 persistence schema 的前提下，采用 **Option B：manifest evidence references
+ Agent context/citation adapter**。它是最小的语义正确方案；Option A 单独不足以
绕开当前 Knowledge-specific Agent contract。

### 3. 是否需要 migration？

**不需要数据库 migration。** 现有 `evidence_bundles`、`recognition_results`、
`recognition_corrections` 已经保存必要的 identity/result/review/hash 信息。只需在
运行时生成版本绑定的 manifest references；历史 bundle 的回填策略需在后续实施时
定义，但不是表结构迁移。

### 4. 是否可以继续 Batch 2A 实施？

**不能继续当前 Batch 2A 实施。** Stop Condition 3 已触发：要保持 provenance
语义正确，必须扩展 Agent 内部 evidence/context/citation contract；本任务明确要求
只做 audit，因此不实现。Batch 2A 保持停止，Batch 2B 不启动。

```text
Batch 2A structural goals:
FAIL — persisted EvidenceBundle result provenance is not bridged into the Agent context and final DiagnosisReport citations; implementation requires an Agent evidence/citation contract extension and is intentionally not performed in this audit.
```

## Implementation follow-up

审计建议已按 Option B 的无数据库迁移版本实施。新增的 `evidence_refs[]` 只保存
result-level immutable references，不复制完整 EvidenceBundle payload；Industrial
Diagnosis resolver 在运行时重新读取 persisted records，并根据 review corrections
过滤被拒绝或未确认结果。通用 Agent layer 只知道 Recognition/Knowledge 两种证据
类别和最小 item/context/protocol，不知道 Industrial Recognition 的结果类型规则。

实际验证已覆盖：

```text
persist → reload → confirm
  → Diagnosis Manifest.evidence_refs[]
  → DiagnosisEvidenceResolver
  → Agent state
  → final citation
```

没有新增 migration。PostgreSQL rehearsal 仍记录为：
`NOT RUN — no disposable PostgreSQL environment available`。

因此本审计结论中的“不能继续实施”仅表示审计当时的 stop condition，现已由后续
授权的 Batch 2A.2 implementation follow-up 解除；Batch 2B 仍未启动。
