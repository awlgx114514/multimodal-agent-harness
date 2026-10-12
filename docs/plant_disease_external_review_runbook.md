# Plant Disease 独立审核操作手册

1. 使用与来源提交人身份不同、具有 `MODEL_RELEASE_APPROVER` 角色的个人账号取得本地 OIDC access token。
2. 阅读 [PlantDoc 数据来源审核材料](plant_disease_source_review_packet.md)。
3. 调用 `GET /api/v1/public-evaluation-sources` 查看待审核记录，并核对来源标识、提交人、候选数量和清单 SHA-256。
4. 调用 `GET /api/v1/public-evaluation-sources/{source_id}/manifest` 查看服务保存的来源 manifest，检查固定版本、来源网址、许可摘要、归属文字、导入版本、抽样规则和原始标注来源。
5. 查看许可文件、36 条排除记录及候选样本审计信息，确认原始边界框和图像摘要可追溯。
6. 根据审核结果选择 `APPROVE` 或 `REJECT`，并填写审核理由。
7. 使用同一个 OIDC access token 调用 `POST /api/v1/public-evaluation-sources/{source_id}/decision`，确认返回审核人、决定时间、理由和来源状态。

来源列表和 manifest 查询，以及审核决定，均要求 `public_evaluation_source.review` 权限。决定请求字段为 `decision`（`APPROVE` 或 `REJECT`）和 `reason`。服务会拒绝提交人与审核人相同的决定，并验证已保存 manifest 的摘要及来源合同。

审核人必须使用个人授权身份完成判断。审核人不得将账号凭据交给自动化执行程序，也不得通过数据库操作或其他未授权途径修改审核状态。
