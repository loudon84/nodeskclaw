---
name: smc-roadmap
description: 管理 APPROVED Architecture 下的持久 Delivery SOT。支持 create/check/next/update；一个 Roadmap Item 一个 Stage PRD，DONE 必须有真实 implementation commit + verification evidence。
version: 1.0.0
disable-model-invocation: true
---

# SMC Roadmap

## Role

Roadmap 是 Delivery 状态事实源，不是实现 Todo 列表。它只保存 stage outcome、依赖、状态和交付证据；exact file/symbol/Todo 属于 Plan。

读取 [`references/roadmap-contract.md`](references/roadmap-contract.md)。

## Modes

### `create`

输入必须是 APPROVED Architecture Decision。

把 `Roadmap Boundaries` 转成 item DAG：

- `RM-01`, `RM-02`...
- Outcome
- Depends On
- Exit Criteria
- initial status `BACKLOG` 或满足依赖时 `READY`

不要创建 Stage PRD 内容。

### `check`

执行：

```bash
python .agents/skills/smc-roadmap/scripts/validate_roadmap.py <roadmap>
```

### `next`

```bash
python .agents/skills/smc-roadmap/scripts/roadmap_next.py <roadmap>
```

只选择验证通过的第一个 READY item。

### `update`

实施完成后，必须先有：

1. APPROVED Stage PRD；
2. validated Plan；
3. Review PASS；
4. Verification PASS evidence；
5. real implementation commit SHA。

再更新该 item 为 DONE。

```bash
python .agents/skills/smc-roadmap/scripts/roadmap_update.py <roadmap> RM-01 \
  --status DONE \
  --prd docs_agent/...md \
  --plan .cursor/plans/...plan.md \
  --implementation-commit <sha> \
  --verification <evidence-path-or-id>
```

更新 Roadmap 后再创建**独立 Roadmap status commit**。

## Status

`BACKLOG | READY | IN_PRD | PLANNED | IMPLEMENTING | REVIEW | BLOCKED | DONE | SUPERSEDED`

## Frozen Delivery Invariant

```text
one Roadmap Item -> one Stage PRD
DONE -> real implementation commit + verification evidence

`real implementation commit` 由 validator 使用 `git cat-file -e <sha>^{commit}` 验证 Git 对象真实存在；只写一个 SHA 形状的字符串不能进入 DONE。
```

Roadmap 不保存“本次 Roadmap status commit SHA”，否则会形成自引用递归。

## Loop

DONE -> check -> next READY -> Stage PRD -> ...
