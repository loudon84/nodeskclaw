---
name: smc-delivery-receipt
version: 1.0.0
description: 将本地 Stage PRD、issue/bug、Plan、PR、commit 与 verification 生成标准 Delivery Receipt，供中央仓库同步。
---
# SMC Delivery Receipt

每个 Work Package 一个 Receipt：

```text
.agents/governance/receipts/<WORK_PACKAGE_ID>.yaml
```

Receipt 是本地交付事实的机器摘要，不替代本地 PRD/Plan/Evidence。

`receipt_version: "2"` 必须记录：

```text
feature_id
work_package_id
repository_id
source_revision
status
sync.kit (version/tag/commit/manifest_sha256)
sync.contract_pins (tag + full commit)
stage_prds / plans / verification as ArtifactRef v2
commits (full 40-char SHA)
acceptance
reported_at
```

Receipt 自称 PASS 不能让中央 Consumer Work Package 进入 VERIFIED。

Git commit 推荐加入 trailers：

```text
SMC-Feature: FEAT-...
SMC-Work-Package: WP-...
SMC-PRD: PRD-...
SMC-Plan: .cursor/plans/...
```

Issue/PR 推荐 labels：

```text
gov:feature:<FEATURE_ID>
gov:wp:<WORK_PACKAGE_ID>
gov:type:feature|bug|task
```
