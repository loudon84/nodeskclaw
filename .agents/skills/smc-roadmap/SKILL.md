---
name: smc-roadmap
description: 管理 APPROVED Architecture 下的持久 Delivery SOT。支持 create/check/next/update；一个 Roadmap Item 一个 Stage PRD，DONE 必须有真实 implementation commit + 可解析 verification evidence reference。与 smc-plan-delivery 对接。
version: 1.1.0
disable-model-invocation: true
---

# SMC Roadmap v1.1

## Role

Roadmap 是 Delivery 状态事实源，不是 implementation Todo 列表。exact file/symbol/Todo 属于 Plan。

读取 [`references/roadmap-contract.md`](references/roadmap-contract.md)。

## Modes

### create

输入 APPROVED Architecture Decision，创建 item DAG：

```text
RM-01, RM-02...
Outcome
Depends On
Exit Criteria
Status
```

### check

```bash
python .agents/skills/smc-roadmap/scripts/validate_roadmap_v11.py <roadmap>
```

### next

```bash
python .agents/skills/smc-roadmap/scripts/roadmap_next.py <roadmap>
```

只选择验证通过的第一个 READY item。

### update

Roadmap Item 到 DONE 前必须已经由 `smc-plan-delivery` 证明：

1. APPROVED Stage PRD；
2. canonical validated Plan；
3. Plan Completion Audit FRESH PASS；
4. Implementation Review FRESH PASS；
5. 所有 blocking Verification FRESH PASS；
6. real implementation commit SHA。

更新：

```bash
python .agents/skills/smc-roadmap/scripts/roadmap_update.py <roadmap> RM-01 \
  --status DONE \
  --prd docs_agent/...md \
  --plan .cursor/plans/...plan.md \
  --implementation-commit <sha> \
  --verification "smc-evidence:<plan_id>@<working-tree-fingerprint>"
```

`Verification Evidence` 可以是逻辑 evidence reference，不要求 raw XML/TXT 在 Git 中存在。

## Evidence Reference

v1.1 推荐：

```text
smc-evidence:<plan_id>@sha256:<fingerprint>
```

其含义是：Roadmap 指向与 implementation commit 前 ready content 对应的一组 FRESH PASS blocking evidence；v1.1 validator 会从该 implementation commit 读取 `docs_agent/evidence/<plan_id>-evidence.json` 并校验 Plan ID、fingerprint、Completion Audit、Implementation Review 与 blocking Verification 摘要。

若组织使用 CI/Artifact Store，也可保存：

```text
ci-artifact:<id-or-url>
external-artifact:<id-or-url>
```

但必须能追溯到同一 Plan / implementation content。

## Artifact Commit Gate

- create/check/next：Roadmap docs 自身按既有独立 docs commit policy；
- implementation commit 不得包含 Roadmap DONE 更新；
- Roadmap DONE validate PASS 后创建独立 Roadmap status commit。

## Status

```text
BACKLOG | READY | IN_PRD | PLANNED | IMPLEMENTING | REVIEW | BLOCKED | DONE | SUPERSEDED
```

## Frozen Invariant

```text
one Roadmap Item -> one Stage PRD
DONE -> real implementation commit + verification evidence reference
```

Roadmap 不保存自身 status commit SHA，避免自引用。
