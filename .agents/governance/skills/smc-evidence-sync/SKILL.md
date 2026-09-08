---
name: smc-evidence-sync
version: 1.0.0
description: 在本地 Verification 后生成最小 Evidence Summary，供中央治理仓库更新 Work Package 状态。
---
# SMC Evidence Sync

必需字段：repository、feature_id、work_package_id、implementation_commit、verification_result、verification_refs、contract_refs、generated_at。

禁止同步 JWT、API Key、Secret、Prompt 全文、Artifact bytes、private endpoint、绝对本地路径。
