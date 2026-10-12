# PlantDoc 数据来源审核材料

## 审核范围

请审核以下公开数据能否作为 Plant Disease 评测候选来源，并核对来源、许可、归属、原始标注保留方式和排除记录。该材料不代表审核已批准，也不代表候选样本已经成为正式 GOLD。

数据集：PlantDoc Object Detection  
来源：<https://github.com/pratikkayal/PlantDoc-Object-Detection-Dataset>  
固定版本：`4730a233a555b30ee98e0879c63ad25d82407455`  
许可：`CC-BY-4.0`  
归属：PlantDoc: A Dataset for Visual Plant Disease Detection; Davinder Singh, Naman Jain, Pranjali Jain, Pratik Kayal, Sudhakar Kumawat and Nipun Batra。

归档 SHA-256：`45811ced89d3e40fac185dbe56eb7935745aad34c5c1402d937f0281eae0d813`  
许可文件 SHA-256：`95df2e9564862e51d69683a899b6dcc8218d577057bdf67322880769ff85f29e`  
候选清单：`artifacts/plant_disease/candidates/plantdoc-source-v2/plant_disease_gold_v1-600/manifest.json`  
候选文件字节 SHA-256：`3e2a5d3a94f48a66c9fbd090c029c386555276eebfb91b818fec3a47b9c44033`  
来源服务按排序键和紧凑 JSON 序列化后保存的 SHA-256：`fd91fb19af30f9c4238f226a763495362fecc3130e2d5cb5a8e5a25fd36292d2`

## 候选内容

固定导入版本包含 600 张真实图片、29 个来源类别和 2,130 个原始边界框。清单保留来源图片标识、图片 SHA-256、原始 CSV 行及注释、来源注释标识、原始 XML 信息、图片尺寸、类别和像素坐标。评测区域由原始像素 XYXY 坐标确定性转换为归一化 XYWH 坐标；来源标注范围是类别标记的目标框，不声明框内区域为病灶范围。

导入器记录了 36 条存在质量问题的源记录并从候选集合排除。记录包含问题类型和原始来源信息。样本选择使用固定种子 `plant_disease_gold_v1`，按清单中的确定性类别轮换规则选取，按图片内容 SHA-256 去重，并保留所选图片的全部原始标注。导出过程会校验归档、许可和图片内容摘要；相同输入重复导出必须产生相同清单摘要。

复核时请检查清单的 `source`、`sampling`、`source_quality.excluded` 和 `cases` 字段。请用服务保存的摘要核对规范化 JSON 内容，并用候选文件摘要核对磁盘文件字节。运行以下只读检查可重算候选数据的准备结果：

```powershell
.venv\Scripts\python.exe scripts\demo\plant_disease\dataset_readiness.py readiness
```

重新生成候选文件时，使用：

```powershell
.venv\Scripts\python.exe scripts\demo\plant_disease\dataset_readiness.py prepare-candidates
```

此操作不会创建审批决定，也不会将候选状态改为已批准。

## 安全与数据限制

审核重点是公开数据来源和评测使用范围。图片可能包含真实种植环境中的非受控背景；当前清单不执行身份识别，也不推断图片中人员身份。样本类别分布不均，来源采集条件、病害阶段和图像质量存在差异。标注由原始数据集提供，导入器保留其来源和内容，并通过确定性校验排除结构或一致性有问题的记录；系统没有重新标注数据。

该审核仅涵盖固定 PlantDoc 版本、其许可及归属、清单中 600 个候选样本及其保留的原始标注，以及该来源用于受治理的 Plant Disease 评测。审核不批准模型、推理结果、Evaluation Policy、模型发布或生产用途。

## 审核决定

请由具有 `MODEL_RELEASE_APPROVER` 角色和 `public_evaluation_source.review` 权限的授权人员完成审核。审核人身份必须独立于提交来源的身份。请通过正式审核接口核对服务保存的清单摘要及清单内容，再选择 `APPROVE` 或 `REJECT` 并填写可供后续审计的理由。

正式操作为调用 `POST /api/v1/public-evaluation-sources/{source_id}/decision`，请求内容包含 `decision` 和 `reason`。批准表示审核人确认上述来源和候选数据范围可以进入后续 GOLD suite 治理；拒绝表示来源不得用于该评测流程。该决定由审核人本人承担，任何自动化流程均不得代替。
