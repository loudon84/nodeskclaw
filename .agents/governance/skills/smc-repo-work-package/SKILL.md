---
name: smc-repo-work-package
version: 1.0.0
description: 将中央 Repo Work Package 映射为项目本地 Roadmap Item / Stage PRD 输入，不侵入本仓 implementation。
---
# SMC Repo Work Package

`Central Work Package → Local Roadmap Item → Stage PRD`。

必须保留：feature_id、work_package_id、global_change_ids、contract_inputs、contract_outputs、acceptance、evidence_required。

本地可以新增 Local Change ID，但必须保留 Global Change ID traceability。禁止中央 Work Package 指定 exact source file/symbol。
