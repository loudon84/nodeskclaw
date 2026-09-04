---
name: smc-plan-delivery
description: SMC canonical Plan 后半程唯一交付编排器。v1.1 增加 Plan-Scoped Delivery Workspace 与 Persistent Execution Context；执行 Static -> Semantic -> Scoped Execution -> Completion Audit -> Implementation Review -> Verification -> Evidence Freshness -> post_review scoped Commit -> Roadmap Update。
version: 1.1.0
---

# SMC Plan Delivery v1.1

## Role

本 Skill 是 SMC governed engineering 的 **唯一 Plan Delivery Orchestrator**。

v1.1 新增两个 runtime responsibility，但不改变业务规则 owner：

1. **Plan-Scoped Delivery Workspace Controller**：把 Plan identity、允许写集、audit/review/verification/commit scope 对齐到同一个 canonical Plan；
2. **Persistent Execution Context Controller**：以 `.smc/runs/<plan_id>/` 中的 resume capsule、per-agent ledger、error ledger 保存长任务运行状态，支持 context reset / compaction / session resume。

它仍然不替代 Plan Author、Plan Review、Implementation Review、Verification、Roadmap Skill。

唯一入口：

```text
Canonical Plan -> smc-plan-delivery
```

## Frozen Invariants

1. `commit_policy: post_review`；
2. Plan Static PASS != implementation complete；
3. Todo `completed` != `IMPLEMENTED_AND_PROVEN`；
4. 一个 production `path#symbol` 只有一个 Todo WRITE_OWNER；
5. explicit `PLAN_PATH` / `plan_id` 是 **binding，不是 hint**；解析失败不得 fallback 到其它 Plan；
6. Plan author owns Cursor todo `id/content`；Delivery runtime 只拥有 `status`；
7. Implementation Review / Verification / Completion Audit 必须绑定当前 **Plan scope fingerprint**；
8. delivery 启动前的 unrelated dirty 允许作为 `AMBIENT_PREEXISTING` 保留，但必须全程 byte/state stable；
9. Plan target write set 若启动前已有 dirty，返回 `DELIVERY_TARGET_CONFLICT`；不得自动 stash/覆盖；
10. delivery 期间新产生的非 Plan scope 修改返回 `DELIVERY_SCOPE_DRIFT`；治理工具突变返回 `DELIVERY_TOOLING_MUTATION`；
11. 所有 blocking Verification 必须 FRESH + PASS，并生成 durable Evidence Manifest 后才能 commit；
12. implementation commit 只能包含 Plan-owned implementation delta + canonical Plan + durable Evidence Manifest；
13. implementation commit 与 Roadmap status commit 分离；Roadmap DONE 必须引用真实 implementation commit；
14. execution continuation gate 只决定“Agent 是否继续工作”，绝不替代 SMC Completion Gate；
15. 不允许复制第二份 `.plan.md` 解决 Cursor metadata/UI 兼容问题。

## Required References

开始前读取：

1. [`references/delivery-state-machine.md`](references/delivery-state-machine.md)
2. [`references/workspace-contract.md`](references/workspace-contract.md)
3. [`references/execution-context-contract.md`](references/execution-context-contract.md)
4. [`references/evidence-contract.md`](references/evidence-contract.md)
5. [`references/review-contract.md`](references/review-contract.md)
6. [`references/completion-audit-contract.md`](references/completion-audit-contract.md)
7. [`references/recovery-contract.md`](references/recovery-contract.md)

# Input Binding

必须明确一个 canonical Plan：

```text
PLAN_PATH=.cursor/plans/<feature>.plan.md
```

若只有 `plan_id`：

```bash
python .agents/skills/smc-plan-delivery/scripts/resolve_plan.py --plan-id <PLAN_ID>
```

规则：

- 0 个 -> `PLAN_NOT_FOUND`；
- >1 个 -> `PLAN_ID_DUPLICATE`；
- 用户显式给出的路径不存在/不合法 -> 停止；
- **不得**因为 selector 失败去选 newest Plan / other Plan。

# State Machine

```text
PLAN_CREATED
  -> PLAN_STATIC_VALID
  -> PLAN_REVIEW_CLEARED
  -> IMPLEMENTING
  -> IMPLEMENTATION_COMPLETE
  -> COMPLETION_AUDIT_PASS
  -> IMPLEMENTATION_REVIEW_PASS
  -> VERIFICATION_PASS
  -> IMPLEMENTED_AND_PROVEN
  -> IMPLEMENTATION_COMMITTED
  -> ROADMAP_DONE
```

异常状态保持：

```text
PLAN_REVISE_REQUIRED
RETURN_PRD
IMPLEMENTATION_BLOCKED
COMPLETION_AUDIT_BLOCKED
REVIEW_BLOCKED
VERIFICATION_BLOCKED
ROADMAP_UPDATE_BLOCKED
```

# Phase 0 — Plan Identity / Run Preflight

## 0.1 Resolve exactly one Plan

```bash
python .agents/skills/smc-plan-delivery/scripts/resolve_plan.py --plan "$PLAN_PATH"
```

新交付要求 `plan_contract: smc.plan.v3.4`。legacy v3.2/v3.3 必须先迁移：

```bash
python .agents/skills/smc-plan-delivery/scripts/migrate_legacy_plan.py "$PLAN_PATH" --in-place
```

迁移只允许升级 contract / Cursor projection / evidence policy；Todo runtime status 必须保留，不重规划 implementation。

## 0.2 Initialize delivery state

```bash
python .agents/skills/smc-plan-delivery/scripts/delivery_state.py init "$PLAN_PATH"
```

此时只冻结 run identity / initial HEAD；**尚未建立 implementation workspace baseline**。已有 run 时进入 Resume，禁止无条件重新开始。

# Phase 1 — Plan Static Gate

```bash
python .agents/skills/smc-plan-validator/scripts/validate_plan_v34.py "$PLAN_PATH"
```

必须同时验证：SMC structural contract、Cursor `id/content/status` projection、Todo mapping、Change/ownership/verification ledgers。若 generation integrity script 存在也必须 PASS。

治理工具自身 crash/runtime incompatibility：返回 `DELIVERY_TOOLING_BLOCKED`。当前 business Plan 禁止顺手修改 validator/Skill 再继续证明自己 PASS。

全部 PASS -> `PLAN_STATIC_VALID`。

# Phase 2 — Plan Semantic Gate

保留 `smc-plan-review` router。`REQUIRED` 不是 PASS；`NOT_REQUIRED` 仍必须写 content-bound clearance record。真正 review 必须得到 `PASS | REVISE | RETURN_PRD`。

Plan semantic hash：

- 规范化 Cursor runtime `status`；
- 规范化 Cursor display `content`，因为 validator 必须证明其为 Markdown Todo 的确定性 projection；
- Markdown Todo/body/Change Matrix/Verification 等真实语义变化仍使 review `STALE`。

## 2.5 Freeze Plan-scoped workspace only after semantic clearance

在任何 implementation write **之前**：

```bash
python .agents/skills/smc-plan-delivery/scripts/workspace.py init "$PLAN_PATH" --json
```

从 Change Matrix 建立 Plan write set，并分类：

```text
PLAN_OWNED             当前 Plan / durable evidence / Plan write set
AMBIENT_PREEXISTING    启动前已存在、与 Plan 无关，可保留但不可变化
TARGET_CONFLICT        Plan 要写的 implementation path 已 dirty，硬阻断
TOOLING_BLOCKED        非本 Plan 的 governance tooling 已 dirty，硬阻断
```

不再要求整个 worktree clean；禁止自动 stash/reset/clean 或删除其它任务文件。

若 Semantic Gate 导致 Plan REVISE，必须在**尚无 implementation mutation**时重新完成 Static + Semantic 后再 `workspace.py init --refresh`；已经开始 implementation 后禁止用 refresh 掩盖 scope 漂移。

## 2.6 Initialize persistent execution context

```bash
python .agents/skills/smc-plan-delivery/scripts/execution_context.py refresh "$PLAN_PATH"
```

运行态文件：

```text
.smc/runs/<plan_id>/workspace-baseline.json
.smc/runs/<plan_id>/resume.json
.smc/runs/<plan_id>/ledger-<agent>.jsonl
.smc/runs/<plan_id>/errors.jsonl
```

它们是 working memory，不是新的 Plan SOT。完成后进入 `IMPLEMENTING`。

# Phase 3 — Scoped Execution + Persistent Context

默认 engine：`executing-plans`；满足原有并行安全条件时可使用 `subagent-driven-development`。

## 3.1 Controller / worker ownership

```text
Controller:
  owns canonical Plan runtime status
  owns resume capsule

Worker:
  owns assigned implementation slice
  appends own ledger
  MUST NOT rewrite canonical Plan specification/content
```

启动 Todo：

```bash
python .agents/skills/smc-plan-delivery/scripts/plan_state.py set "$PLAN_PATH" T1 in_progress
python .agents/skills/smc-plan-delivery/scripts/execution_context.py event "$PLAN_PATH" \
  --event TODO_STARTED --agent main --todo T1 --summary "start T1"
```

完成局部实现/局部 check 后：

```bash
python .agents/skills/smc-plan-delivery/scripts/execution_context.py event "$PLAN_PATH" \
  --event LOCAL_CHECK_PASS --agent main --todo T1 --summary "focused checks pass"
python .agents/skills/smc-plan-delivery/scripts/plan_state.py set "$PLAN_PATH" T1 completed
python .agents/skills/smc-plan-delivery/scripts/execution_context.py event "$PLAN_PATH" \
  --event TODO_DONE --agent main --todo T1 --summary "T1 complete"
```

Worker 可记录：

```text
TODO_STARTED
DISCOVERY
PROGRESS
ERROR
RETRY
LOCAL_CHECK_PASS
TODO_DONE
BLOCKED
NOTE
```

Error ledger 对 normalized failure signature 计数。相同失败不得无限执行同一个 action；重复失败应改变策略，达到 bounded retry 后进入 BLOCKED / escalate。

## 3.2 Workspace guards during execution

每个 Todo boundary / resume 前：

```bash
python .agents/skills/smc-plan-delivery/scripts/workspace.py assert-stable "$PLAN_PATH"
```

- pre-existing ambient 原样存在 -> 允许；
- ambient 被本 delivery/其它并发 session 改动 -> `DELIVERY_AMBIENT_MUTATED`；
- 新增非 Plan scope dirty -> `DELIVERY_SCOPE_DRIFT`；
- governance tooling 新增 mutation -> `DELIVERY_TOOLING_MUTATION`。

## 3.3 Long-running resume

每轮/compaction 后优先读取 compact capsule：

```bash
python .agents/skills/smc-plan-delivery/scripts/execution_context.py show "$PLAN_PATH" --json
```

它回答：

```text
current delivery state
active Todo
next step
completed/blocked Todos
last event
scope fingerprint
ambient status
```

需要具体 implementation semantics 时再 progressive-read canonical Plan 相应 Todo；不要每轮重读整个 Plan。

## 3.4 Execution continuation gate

在 Agent 准备结束但仍有 active/pending Todo 时可运行：

```bash
python .agents/skills/smc-plan-delivery/scripts/execution_context.py gate "$PLAN_PATH" --cap 20
```

它有 progress/stall/cap guard，防止无限循环。注意：

```text
CONTINUE / ALLOW_STOP
!=
IMPLEMENTED_AND_PROVEN
```

这是 execution continuation oracle，不是交付证明。

所有 Todo completed 后进入 `IMPLEMENTATION_COMPLETE`。

# Phase 4 — Plan-Scoped Completion Audit

Deterministic precheck：

```bash
python .agents/skills/smc-plan-delivery/scripts/completion_audit.py precheck \
  --plan "$PLAN_PATH" --base <delivery-base> --json
```

v1.1 不再用整个 repository `git diff <base>` 判断本 Plan，而比较：

```text
workspace baseline planned file states
        vs
current planned file states
```

必须证明：

- all canonical Cursor todos completed；
- Plan write set 有真实 implementation delta；
- unrelated ambient 未变化；
- 无新 scope drift；
- requested base 与 frozen delivery base 一致。

Fresh-context semantic audit 只读取：

```text
canonical Plan
Approved PRD
Plan-owned implementation delta
Plan referenced implementation files
```

结果仍必须：

```text
verdict=PASS
deferred=0
unverifiable=0
scope_drift=0
done=total_items
```

record 绑定 `scope_fingerprint + ambient_fingerprint`。

# Phase 5 — Implementation Review

使用 `code-review-and-quality`，review 范围必须是 **本 Plan-owned implementation delta**。

记录：

```bash
python .agents/skills/smc-plan-delivery/scripts/review_record.py implementation \
  --plan "$PLAN_PATH" --verdict PASS --reviewer code-review-and-quality
```

Implementation Review 绑定：

```text
scope_fingerprint
ambient_fingerprint
```

Plan scope implementation content 改变 -> Review `STALE`。
Ambient drift -> Review `STALE/BLOCKED`。

# Phase 6 — Verification

对每个 blocking Verification：

```bash
python .agents/skills/smc-plan-delivery/scripts/evidence.py run \
  --plan "$PLAN_PATH" --verification V01 -- <exact command>
```

记录：

```text
exact command
exit code
timestamp
scope fingerprint
ambient fingerprint
raw local log
Evidence Policy
```

raw evidence 默认：

```text
.smc/evidence/<plan_id>/ledger.jsonl
.smc/evidence/<plan_id>/logs/*.log
```

这些不进入 implementation commit。

# Phase 7 — Evidence Freshness + Durable Manifest

```bash
python .agents/skills/smc-plan-delivery/scripts/evidence.py check --plan "$PLAN_PATH" --all-blocking
python .agents/skills/smc-plan-delivery/scripts/evidence.py manifest --plan "$PLAN_PATH"
python .agents/skills/smc-plan-delivery/scripts/validate_delivery_completion.py "$PLAN_PATH"
```

Manifest：

```text
docs_agent/evidence/<plan_id>-evidence.json
```

必须证明当前：

```text
Plan semantic clearance FRESH
Completion Audit FRESH PASS
Implementation Review FRESH PASS
all blocking Verification FRESH PASS
scope fingerprint 一致
ambient fingerprint 一致且 ambient stable
no scope drift
```

只有 `DELIVERY_READY_TO_COMMIT` 才可进入 Phase 8。

# Phase 8 — Plan-Scoped post_review Implementation Commit

先 capture：

```bash
python .agents/skills/smc-plan-delivery/scripts/commit_guard.py capture "$PLAN_PATH"
```

allowed commit paths 由 guard 冻结，只允许：

```text
Plan-owned changed implementation files
canonical Plan
Durable Evidence Manifest
```

**不得 `git add -A`。** 应显式 stage guard 允许路径。

commit 后：

```bash
python .agents/skills/smc-plan-delivery/scripts/commit_guard.py verify "$PLAN_PATH" --commit HEAD
```

必须证明：

- committed paths 不超出 allowed set；
- Plan-owned implementation delta 全部进入 commit；
- Plan-owned paths 无 residual dirty；
- pre-existing ambient 仍保持原 dirty/content state；
- scope fingerprint 与 ready proof 相同。

因此 v1.1 允许：

```text
implementation commit 完成后
其它任务启动前就存在的 unrelated dirty 仍留在 worktree
```

这不再触发旧的 repository-wide `POST_COMMIT_WORKTREE_DIRTY`。

验证后：

```bash
python .agents/skills/smc-plan-delivery/scripts/delivery_state.py set-commit "$PLAN_PATH" --sha HEAD
```

# Phase 9 — Roadmap Update

保持现有 Roadmap single-writer / separate status commit contract。

Verification reference 绑定 durable manifest / scope fingerprint：

```text
smc-evidence:<plan_id>@sha256:<scope-fingerprint>
```

使用现有：

```bash
python .agents/skills/smc-roadmap/scripts/roadmap_update.py ...
python .agents/skills/smc-roadmap/scripts/validate_roadmap_v11.py <roadmap>
```

Roadmap `DONE` 必须引用真实 implementation commit。Roadmap status commit 与 implementation commit 分离。

# Deterministic State Recording

每个 Gate 后由 `delivery_state.py transition` 记录；对话中的文字声明不是状态事实。

# Resume / Recovery

重新调用时按此顺序：

```bash
python .agents/skills/smc-plan-delivery/scripts/resolve_plan.py --plan "$PLAN_PATH"
python .agents/skills/smc-plan-delivery/scripts/workspace.py inspect "$PLAN_PATH" --json
python .agents/skills/smc-plan-delivery/scripts/execution_context.py refresh "$PLAN_PATH" --json
python .agents/skills/smc-plan-delivery/scripts/delivery_state.py inspect "$PLAN_PATH"
python .agents/skills/smc-plan-delivery/scripts/readiness.py "$PLAN_PATH"
```

从第一个未满足或 STALE Gate 恢复。禁止无条件重跑全部昂贵步骤。

# Completion Report

只有 Roadmap update 成功后才报告完整交付完成：

```text
Plan: <path>
Plan ID: <id>
Static Gate: PASS
Semantic Gate: PASS | NOT_REQUIRED
Workspace: PLAN_SCOPED / AMBIENT_STABLE
Todos: n/n completed
Completion Audit: PASS
Implementation Review: PASS
Verification: n/n FRESH PASS
Ready Scope Fingerprint: <sha256>
Implementation Commit: <sha>
Roadmap Item: <id> DONE
Roadmap Commit: <sha>
```

# Explicit Non-Goals

本 Skill 不负责：创建 Architecture/PRD；静默改变 APPROVED boundary；生成第二份 Plan；替代 semantic review；伪造 verification；自动 push/merge/deploy；自动清理 unrelated dirty；在 business Plan 内自修 governance tooling。
