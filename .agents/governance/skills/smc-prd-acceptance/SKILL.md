---
name: smc-prd-acceptance
version: 1.0.0
description: 将 APPROVED Stage PRD 的 AC/DOD 映射到可执行 verification，并生成 Acceptance Report；中央只验证报告，不远程执行项目代码。
---
# SMC PRD Acceptance

## 模型

```text
Stage PRD AC/DOD
   ↓
Acceptance Manifest
   ↓
Unit / Contract / Static / Integration commands
   ↓
Acceptance Report
   ↓
Delivery Receipt
   ↓
Central Acceptance Gate
```

## 不变量

1. 每个 `AC-nn` / `DOD-nn` 至少映射一个 Verification ID。
2. `VERIFIED/DONE` Work Package 的 blocking verification 必须 PASS。
3. 中央 CI 不执行其他仓库任意命令；命令只在项目自身 CI/开发环境执行。
4. Report 必须 pin `source_revision` 与 `repository_commit`。
5. stdout/stderr 只记录 SHA-256，不把日志全文同步到中央。

脚本见 `scripts/run_acceptance.py`。
