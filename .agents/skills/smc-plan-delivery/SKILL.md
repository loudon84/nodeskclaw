---
name: smc-plan-delivery
description: SMC Plan 后半程唯一交付编排器。对 canonical Plan 执行 Static Gate -> Semantic Gate -> Execution -> Plan Completion Audit -> Implementation Review -> Verification -> Evidence Freshness -> post_review Commit -> Roadmap Update；支持中断恢复，禁止 Todo 阶段提前 commit。
version: 1.0.1
---

# SMC Plan Delivery v1.0

## Role

本 Skill 是 **SMC governed engineering 的 Plan Delivery Orchestrator**。

它不是新的 production runtime owner，也不重复实现 Plan、Review、Verification、Roadmap 的业务规则；它负责把既有专业 Skill 与确定性脚本按同一状态机串成一条可恢复、可审计的交付流水线。

用户在已有 canonical `.cursor/plans/*.plan.md` 后要求“执行这个 Plan / 完成 Plan / 一键交付 / delivery”时，优先使用本 Skill，而不是让用户手工串联多个 Skill。

唯一后半程入口：

```text
Canonical Plan
  -> smc-plan-delivery
```

## Frozen Invariants

以下规则不可被本 Skill 降级：

1. `commit_policy: post_review`；
2. Plan Static PASS != implementation complete；
3. Todo `completed` != `IMPLEMENTED_AND_PROVEN`；
4. 一个 production `path#symbol` 只有一个 Todo WRITE_OWNER；
5. Implementation Review 与 Verification 必须绑定实际 working-tree content；
6. working-tree content 变化后，旧 Review / Verification 自动 `STALE`；
7. 所有 blocking Verification 必须 `FRESH + PASS`，并生成 durable compact Evidence Manifest 后才能 commit；
8. raw logs 默认保留 `.smc/`/CI；`docs_agent/evidence/<plan_id>-evidence.json` 是可提交的长期审计摘要；
9. implementation commit 与 Roadmap status commit 分离；
10. Roadmap `DONE` 必须引用真实 implementation commit；
11. 不允许通过复制第二份 `.plan.md` 解决 Cursor UI metadata 与 SMC Plan body 的兼容问题。

## Required References

开始前读取：

1. [`references/delivery-state-machine.md`](references/delivery-state-machine.md)
2. [`references/evidence-contract.md`](references/evidence-contract.md)
3. [`references/review-contract.md`](references/review-contract.md)
4. [`references/completion-audit-contract.md`](references/completion-audit-contract.md)
5. [`references/recovery-contract.md`](references/recovery-contract.md)

## Inputs

必须明确一个 canonical Plan 路径：

```text
PLAN_PATH=.cursor/plans/<feature>.plan.md
```

若用户只提供 `plan_id`，先执行：

```bash
python .agents/skills/smc-plan-delivery/scripts/resolve_plan.py \
  --plan-id <PLAN_ID>
```

若找到 0 个：`PLAN_NOT_FOUND`。

若找到 >1 个：`PLAN_ID_DUPLICATE`，停止；不得猜一个继续执行。

## State Machine

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

异常状态：

```text
PLAN_REVISE_REQUIRED
RETURN_PRD
IMPLEMENTATION_BLOCKED
COMPLETION_AUDIT_BLOCKED
REVIEW_BLOCKED
VERIFICATION_BLOCKED
ROADMAP_UPDATE_BLOCKED
```

状态由：

```bash
python .agents/skills/smc-plan-delivery/scripts/delivery_state.py ...
```

保存到 `.smc/runs/<plan_id>.json`。状态文件只用于恢复与审计，不是产品运行时数据。

---

# Phase 0 — Preflight / Canonical Plan Identity

## 0.1 Resolve exactly one Plan

```bash
python .agents/skills/smc-plan-delivery/scripts/resolve_plan.py \
  --plan "$PLAN_PATH"
```

必须满足：

- `plan_contract: smc.plan.v3.3`，或明确的 legacy v3.2 兼容路径；
- `plan_id` 唯一；
- canonical Plan 同时承载 Cursor metadata 与 SMC body；
- 不存在第二份相同 `plan_id` 或语义重复 Plan。

新交付必须使用 v3.3。legacy v3.2 可先执行：

```bash
python .agents/skills/smc-plan-delivery/scripts/migrate_legacy_plan.py \
  "$PLAN_PATH" --in-place
```

迁移只改 Plan contract / Cursor todo metadata / Verification evidence policy，不重新规划实现。

## 0.2 Initialize delivery run

```bash
python .agents/skills/smc-plan-delivery/scripts/delivery_state.py \
  init "$PLAN_PATH"
```

若已有 run，则进入 resume 逻辑，禁止无条件从头执行。

## 0.3 Git baseline

读取：

```bash
git status --porcelain
git rev-parse HEAD
```

不要自动清理用户已有修改。若已有未归属于本 Plan 的脏改动会污染 diff/review/verification，返回：

```text
DELIVERY_WORKTREE_CONFLICT
```

由用户或父 orchestrator 明确隔离后再继续。

---

# Phase 1 — Plan Static Gate

对于 v3.3：

```bash
python .agents/skills/smc-plan-validator/scripts/validate_plan_v33.py \
  "$PLAN_PATH"
```

同时运行 generation integrity gate（若存在）：

```bash
python .agents/skills/smc-plan-from-approved-prd-ponytail/scripts/validate_generation_integrity.py \
  "$PLAN_PATH"
```

只有全部 PASS 才进入：

```text
PLAN_STATIC_VALID
```

静态校验只证明 Plan contract 自洽，不得表述为“实施完成”。

---

# Phase 2 — Plan Semantic Gate

先运行现有 review router：

```bash
python .agents/skills/smc-plan-review/scripts/assess_plan_review.py \
  "$PLAN_PATH"
```

必须区分：

```text
NOT_REQUIRED       = router 判断无需额外 semantic review
REQUIRED           = router 要求真正执行 semantic review
PASS/REVISE/...    = actual review verdict
```

`REQUIRED` **绝不是 PASS**。

若 router 返回 `NOT_REQUIRED`，也必须写一条 content-bound clearance record：

```bash
python .agents/skills/smc-plan-delivery/scripts/review_record.py \
  plan \
  --plan "$PLAN_PATH" \
  --verdict PASS \
  --reviewer smc-plan-review-router \
  --note NOT_REQUIRED
```

若 REQUIRED：使用 `smc-plan-review` 执行实际 semantic review；必须得到：

```text
PASS | REVISE | RETURN_PRD
```

并记录 Plan 内容 hash：

```bash
python .agents/skills/smc-plan-delivery/scripts/review_record.py \
  plan \
  --plan "$PLAN_PATH" \
  --verdict PASS \
  --reviewer smc-plan-review
```

只有 `review_record.py check --kind plan` 对当前 semantic Plan hash 返回 `FRESH_PASS`，才进入 `PLAN_REVIEW_CLEARED`。

Plan 后续若被修改，Plan Review 自动视为 stale，需要重新经过本 Gate。

---

# Phase 3 — Execution Engine

本 Skill 负责选择 engine，但不复制 engine 的实现规则。

## 3.1 Engine selection

默认选择：

```text
executing-plans
```

满足以下条件可选择：

```text
subagent-driven-development
```

- Plan 有多个明确 Todo；
- Write Ownership Ledger 已静态 PASS；
- Todo 间不存在未排序 write/read hazard；
- 当前宿主支持可靠 subagent；
- 使用 fresh implementer 能明显降低上下文污染。

无论哪种 engine：

- engine 只负责 implementation；
- engine 不得创建 Todo implementation commit；
- engine 不得把自己的局部验证当作 Final Verification；
- 每个 Todo 完成并通过其局部 spec/code check 后，只更新 canonical Plan 中对应 Cursor todo status。

更新状态：

```bash
python .agents/skills/smc-plan-delivery/scripts/plan_state.py \
  set "$PLAN_PATH" T1 completed
```

合法动态状态：

```text
pending | in_progress | completed | blocked
```

Markdown `## Todo Tn` 是稳定 specification，不承担动态状态 SOT。

所有 Todo 完成后：

```text
IMPLEMENTATION_COMPLETE
```

注意：这仍不等于 `IMPLEMENTED_AND_PROVEN`。

---

# Phase 4 — Plan Completion Audit

这是独立于 Implementer 的强制 Gate。

## 4.1 Deterministic precheck

```bash
python .agents/skills/smc-plan-delivery/scripts/completion_audit.py \
  precheck \
  --plan "$PLAN_PATH" \
  --base <delivery-base>
```

检查：

- canonical Cursor todos 是否全部 completed；
- Plan 中 Todo / Ledger 是否一致；
- 当前 diff 是否为空；
- diff 中是否出现明显超出 Change Matrix 的文件；
- 当前 working-tree fingerprint。

## 4.2 Fresh-context semantic audit

使用 fresh reviewer context 读取：

```text
canonical Plan
+ Approved PRD
+ git diff <base> --
+ Plan referenced implementation files
```

审计必须回答：

```text
每个 Todo 是否真实实现？
每个 Change ID 是否落地？
REPLACE 是否同时完成 REMOVE？
AC/DoD 是否存在明显 implementation gap？
是否出现 scope drift？
是否存在无法从代码/diff 证明的条目？
```

审计输出结构：

```json
{
  "total_items": 0,
  "done": 0,
  "changed": 0,
  "deferred": 0,
  "unverifiable": 0,
  "scope_drift": 0,
  "verdict": "PASS",
  "summary": "..."
}
```

将结果写入：

```bash
python .agents/skills/smc-plan-delivery/scripts/completion_audit.py \
  record \
  --plan "$PLAN_PATH" \
  --result-json <audit-result.json>
```

只有：

```text
verdict=PASS
deferred=0
unverifiable=0
scope_drift=0
record fingerprint == current fingerprint
```

才进入 `COMPLETION_AUDIT_PASS`。

如果宿主不支持 subagent，不允许伪装成 fresh context；应明确标记 audit executor 为 `INLINE_FALLBACK`，并仍执行完整 audit。高风险 Plan 可要求人工/第二模型复核。

---

# Phase 5 — Implementation Review

使用现有：

```text
code-review-and-quality
```

review 范围必须是本 Plan 对应 implementation diff，不是重新做 Plan Review。

至少覆盖：

- correctness；
- tests；
- architecture / owner fit；
- security boundary；
- performance / concurrency；
- scope drift；
- unnecessary complexity。

Review 完成后记录：

```bash
python .agents/skills/smc-plan-delivery/scripts/review_record.py \
  implementation \
  --plan "$PLAN_PATH" \
  --verdict PASS \
  --reviewer code-review-and-quality
```

该记录自动绑定当前 working-tree fingerprint。

若 Review 导致任何 code 修改：

```text
旧 implementation review = STALE
旧 verification evidence = STALE
```

必须回到本 Phase 重新 review，然后再 Verification。

只有 current fingerprint 上的 Review PASS 才进入：

```text
IMPLEMENTATION_REVIEW_PASS
```

---

# Phase 6 — Verification

Plan v3.3 的 Verification Ledger 不再要求 Git 内物理 `Evidence Output` 文件，而声明：

```text
Evidence Policy
```

对每个 blocking Verification ID，使用：

```bash
python .agents/skills/smc-plan-delivery/scripts/evidence.py \
  run \
  --plan "$PLAN_PATH" \
  --verification V01 \
  -- <exact command from Verification Ledger>
```

wrapper 必须：

- 透明传递 command exit code；
- 记录 exact command；
- 记录 timestamp；
- 记录 working-tree fingerprint；
- 保留 stdout/stderr local raw log；
- 生成 append-only JSONL ledger record；
- 不因为记录 evidence 自身改变 implementation fingerprint。

默认本地位置：

```text
.smc/evidence/<plan_id>/ledger.jsonl
.smc/evidence/<plan_id>/logs/*.log
```

这些路径必须 gitignored。

Verification command exit != 0：

```text
VERIFICATION_BLOCKED
```

不得 commit。

---

# Phase 7 — Evidence Freshness + Durable Manifest Gate

先确认 raw evidence freshness：

```bash
python .agents/skills/smc-plan-delivery/scripts/evidence.py check \
  --plan "$PLAN_PATH" --all-blocking
```

然后生成**可提交的紧凑 Evidence Manifest**：

```bash
python .agents/skills/smc-plan-delivery/scripts/evidence.py manifest \
  --plan "$PLAN_PATH"
```

默认输出：

```text
docs_agent/evidence/<plan_id>-evidence.json
```

Manifest 只保存长期审计所需摘要：Plan ID、ready working-tree fingerprint、Plan/Implementation Review、Completion Audit、每个 blocking Verification 的 command/exit/timestamp/policy 以及 raw log SHA256。raw stdout/XML/JUnit 仍保留在 `.smc/evidence/`、CI 或外部 Artifact Store，不默认进入 Git。

`docs_agent/evidence/` 被 working-tree fingerprint 排除，因此生成 Manifest **不会使刚获得的 Review/Verification 失效**。

最后执行：

```bash
python .agents/skills/smc-plan-delivery/scripts/validate_delivery_completion.py \
  "$PLAN_PATH"
```

该 Gate 必须同时证明：

```text
all Cursor todos completed
completion audit PASS + FRESH
implementation review PASS + FRESH
all blocking Verification PASS + FRESH
durable Evidence Manifest FRESH
current working-tree fingerprint == all blocking evidence fingerprint == manifest fingerprint
```

输出 `DELIVERY_READY_TO_COMMIT` 才允许进入 commit。代码在 Verification 后改变时旧 evidence/manifest 都必须变成 STALE。

---

# Phase 8 — post_review Implementation Commit

这是整个 implementation 第一个允许的 commit 点。

先冻结 ready fingerprint：

```bash
python .agents/skills/smc-plan-delivery/scripts/commit_guard.py \
  capture "$PLAN_PATH"
```

然后按项目 Git policy staging。**Evidence Manifest 必须与 implementation 一起进入本 implementation commit**；raw `.smc/evidence/` 不得 staging。再次执行 completion gate。

commit 后立即验证：

```bash
python .agents/skills/smc-plan-delivery/scripts/commit_guard.py \
  verify "$PLAN_PATH" --commit HEAD
```

必须证明：

- commit 前已 `DELIVERY_READY_TO_COMMIT`；
- committed content 与 ready fingerprint 对应；
- commit 后没有本 Plan 未提交的 implementation diff。

得到真实 commit 后必须登记：

```bash
python .agents/skills/smc-plan-delivery/scripts/delivery_state.py \
  set-commit "$PLAN_PATH" --sha HEAD
```

只有 commit guard 已验证该 SHA，state 才能进入：

```text
IMPLEMENTATION_COMMITTED
```

禁止将 Roadmap DONE 更新混进本 implementation commit。

---

# Phase 9 — Roadmap Update

从 Approved PRD / Plan 解析对应 Roadmap item。

Verification reference 使用逻辑 evidence ref；该 ref 必须能从 implementation commit 确定性解析到 `docs_agent/evidence/<plan_id>-evidence.json`，而不是依赖本机 `.smc/` raw log：

```text
smc-evidence:<plan_id>@<working_tree_fingerprint>
```

执行现有 Roadmap update：

```bash
python .agents/skills/smc-roadmap/scripts/roadmap_update.py \
  <roadmap> <RM-ID> \
  --status DONE \
  --prd <approved-prd> \
  --plan "$PLAN_PATH" \
  --implementation-commit <sha> \
  --verification "smc-evidence:<plan_id>@<fingerprint>"
```

然后：

```bash
python .agents/skills/smc-roadmap/scripts/validate_roadmap_v11.py <roadmap>
```

v1.1 validator 会确认：implementation commit 中确实存在该 Plan 的 durable Evidence Manifest，且 Plan ID / fingerprint / blocking verification proof 一致。PASS 后创建独立：

```text
Roadmap status commit
```

Roadmap status commit 成功后记录：

```bash
python .agents/skills/smc-plan-delivery/scripts/delivery_state.py \
  transition "$PLAN_PATH" --to ROADMAP_DONE
```

最终进入 `ROADMAP_DONE`。

---

# Deterministic State Recording

每完成一个 Gate，controller 必须记录状态；不能只在对话中声称“已进入下一阶段”：

```bash
python .agents/skills/smc-plan-delivery/scripts/delivery_state.py transition "$PLAN_PATH" --to PLAN_STATIC_VALID
python .agents/skills/smc-plan-delivery/scripts/delivery_state.py transition "$PLAN_PATH" --to PLAN_REVIEW_CLEARED
python .agents/skills/smc-plan-delivery/scripts/delivery_state.py transition "$PLAN_PATH" --to IMPLEMENTING
python .agents/skills/smc-plan-delivery/scripts/delivery_state.py transition "$PLAN_PATH" --to IMPLEMENTATION_COMPLETE
python .agents/skills/smc-plan-delivery/scripts/delivery_state.py transition "$PLAN_PATH" --to COMPLETION_AUDIT_PASS
python .agents/skills/smc-plan-delivery/scripts/delivery_state.py transition "$PLAN_PATH" --to IMPLEMENTATION_REVIEW_PASS
python .agents/skills/smc-plan-delivery/scripts/delivery_state.py transition "$PLAN_PATH" --to VERIFICATION_PASS
python .agents/skills/smc-plan-delivery/scripts/delivery_state.py transition "$PLAN_PATH" --to IMPLEMENTED_AND_PROVEN
```

commit_guard verify 后记录真实 implementation commit；Roadmap DONE 后再记录最终状态。状态文件是恢复索引，不替代各 Gate 的事实证据。

---

# Resume / Recovery

每次重新调用本 Skill，先执行：

```bash
python .agents/skills/smc-plan-delivery/scripts/delivery_state.py \
  inspect "$PLAN_PATH"

python .agents/skills/smc-plan-delivery/scripts/readiness.py \
  "$PLAN_PATH"
```

`readiness.py` 是 gstack-style readiness dashboard 的 SMC 实现：它重新计算 Static、Semantic、Todo、Audit、Review 与 Verification freshness。然后从第一个未满足 Gate 恢复，不重复已经 `FRESH` 的昂贵步骤。

但任何内容 fingerprint 变化都会使以下状态自动降级：

```text
COMPLETION_AUDIT_PASS -> stale
IMPLEMENTATION_REVIEW_PASS -> stale
VERIFICATION_PASS -> stale
IMPLEMENTED_AND_PROVEN -> stale
```

详见 `references/recovery-contract.md`。

# Completion Report

只有 Roadmap update 成功后才报告完整交付完成。

固定输出：

```text
Plan: <path>
Plan ID: <id>
Static Gate: PASS
Semantic Gate: PASS | NOT_REQUIRED
Todos: n/n completed
Completion Audit: PASS
Implementation Review: PASS
Verification: n/n FRESH PASS
Ready Fingerprint: <sha256>
Implementation Commit: <sha>
Roadmap Item: <id> DONE
Roadmap Commit: <sha>
```

如果只完成到某一中间阶段，必须按真实状态报告，不使用“done / complete / shipped”泛化描述。

# Explicit Non-Goals

本 Skill 不负责：

- 创建 Architecture Decision；
- 创建 Stage PRD；
- 重新 Grounding APPROVED PRD；
- 生成第二份 Plan；
- 替代 `smc-plan-validator`；
- 替代 `code-review-and-quality` 的语义审查；
- 替代真实 test runner；
- 自动 push / merge / deploy；
- 引入第二个 production runtime owner。
