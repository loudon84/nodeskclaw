---
name: smc-prd-grounding
description: 校准外部或 ChatGPT 生成的 NoDeskClaw 功能 PRD；优先复用已有能力，识别重复建设、错误 Owner 和必要缺口。支持 discover、verify、revision 三种模式，避免重复扫描源码。
version: 3.1.0
disable-model-invocation: true
---

# SMC PRD Grounding

## 目标

把功能方案校准到当前源码与有效合同，回答四件事：

1. Capability 是否已经存在；
2. 应 KEEP / MODIFY，还是确实需要 ADD / REPLACE；
3. 是否出现重复 Production Owner；
4. 是否缺少完成目标所必需的架构边界或行为。

本 Skill 处理 **PRD Architecture**，不冻结施工细节。具体函数、hook、fetch 参数、errorCode、测试文件和 mock 技术交给 `smc-plan-from-approved-prd`。

遵守：
- [`../../references/prd-contract.md`](../../references/prd-contract.md)
- [`../../references/architecture-convergence.md`](../../references/architecture-convergence.md)

## Mode

只使用一个模式：

| Mode | 使用场景 | 允许范围 |
|---|---|---|
| `discover` | 输入缺少可靠源码依据 | 发现 Current Capability，生成/重写 PRD-DRAFT |
| `verify` | ChatGPT/人工已分析源码，PRD 已有 Anchors/Inventory | 抽查、去重、Owner/分类校验、补必要缺口 |
| `revision` | 上一轮 Review=`REVISE` | 只关闭 OPEN Finding 和修订直接引入的 regression |

默认推断：
1. 有 Review Findings → `revision`
2. PRD 已有 Source Anchors / Current Inventory → `verify`
3. 其它 → `discover`

输出必须写明 mode。

## Context Budget

1. 读根 `AGENTS.md` 和受影响 subsystem `AGENTS.md`（如存在；本仓库当前仅有根 AGENTS.md）。
2. 只读受影响 Capability 的关键 Source Anchors。
3. PRD 已记录 branch/commit/Owner 且无变化证据时，复用证据，不重复读取。
4. `revision` 默认只打开 OPEN Finding 对应源码。
5. 仅在以下情况扩大读取：
   - 需要证明 `MISSING`；
   - Production Owner 将改变；
   - direct caller 可能绕过边界；
   - contract/security 存在冲突；
   - Finding 无法由已有证据确认。
6. 禁止扫描 monorepo、历史 PRD、build/runtime output 或无关 references。

独立验证不等于重新 discovery。

## PRD / Plan Boundary

PRD 冻结：

- Capability / Scope；
- Production Owner；
- Architecture / Trust Boundary；
- Observable Behaviour；
- Contract Semantics；
- KEEP / MODIFY / ADD / REPLACE / REMOVE；
- Acceptance Criteria。

默认下放 Plan：

- exact 私有函数；
- hook/effect；
- fetch option；
- 内部 errorCode；
- test file / mock；
- DOM/framework API；
- 非合同性的调用顺序。

只有当实现细节本身决定 **对外合同、安全、不变量、唯一 Owner 或用户可观察行为** 时才写入 PRD。

## Capability Grounding

最小 Current Inventory：

| Capability | Existing Owner | Current Behaviour | Evidence | Result |
|---|---|---|---|---|

Result：

- `EXISTS` → `KEEP`
- `PARTIAL` → 优先 `MODIFY existing owner`
- `MISSING` → 证明无等价/可扩展 Owner 后才 `ADD`
- `CONFLICT` → `REPLACE + REMOVE`
- `UNKNOWN` → 不猜测

重点检查与当前需求有关的：

- Service / Client / Controller；
- Store / State；
- Parser / Serializer / Adapter；
- IPC / HTTP / API；
- Lifecycle / Queue / Cache / Retry；
- Auth / Routing / Contract DTO。

不得因“新组件更干净”建立第二 Owner。

## 必要 Architecture Gap

只在需求实际涉及的范围检查：

### Execution Boundary
权限、approval、retry、routing、validation、安全门禁：
- 找主要生产入口；
- 明确最终 enforcement owner；
- 可绕过的 UI guard 不算最终防线。

### State / Lifecycle
只定义会改变 Behaviour 的状态和必要 latest-wins / stale-discard / cleanup 约束。

### Contract
只验证本 PRD 实际消费的 endpoint、shape、identity、required field、reject/fallback semantics。
Provider release/CI/deploy 不在 Scope 时不得扩张审计。

PRD 只写架构约束；具体实现算法交给 Plan。

## Change Classification

所有受影响 Capability 只能使用：

`KEEP | MODIFY | ADD | REPLACE | REMOVE`

规则：

- ADD 不能掩盖 MODIFY；
- ADD 不能掩盖 REPLACE；
- REPLACE 必须有 REMOVE；
- 一个 Capability 一个 Production Owner；
- compat/adapter/fallback/alias/legacy 必须有真实 Current Consumer 与 removal contract；
- 历史错误行为只留 tests/fixtures/golden evidence。

## Revision Closure

mode=`revision` 时，以旧 Finding 为主键：

| Finding | Reproduced | Resolution | Evidence | Status |
|---|---|---|---|---|

- `Status`: `CLOSED | OPEN`
- 无法复现 → `Reproduced=NO`，不得为了 PASS 创造事实。
- 已 CLOSED Finding 不重新展开。
- 只有修订直接引入 regression 或出现新权威证据时才增加新项。
- 不重新 full Grounding。

## Source Anchors

只记录证明 Owner/Boundary 的最小 Anchors，推荐：

`repository-relative/path#symbol`

Anchor 不是施工清单。私有 helper 不是架构决定时无需写入 PRD。

Reviewer 声称符号错误时重新验证具体差异，不机械接受。

## 输出

### discover / verify
PRD 至少保持 `prd-contract.md` 要求：
- Current Capability Inventory
- Target End-State Inventory
- Change Classification
- Acceptance Criteria

按需保留最小 Grounding Summary / Source Anchors。
文件名必须为 `*-DRAFT.md`；只有 `smc-prd-converge` 在 APPROVED 后去掉 `-DRAFT`。

### revision
做最小修订，并增加 `Grounding Closure Table`；不要重写已稳定章节。

状态：
- 仍有未知/外部语义 → `DRAFT`
- Grounding 完成可审查 → `REVIEW_REQUIRED`

不得设置 `APPROVED` 或 `review_verdict: PASS`。

## 禁止

- ChatGPT 已 Grounding 后再次全量扫描；
- REVISE 后重新审整个 PRD；
- 为了 PASS 把施工细节塞进 PRD；
- Provider release audit 扩张进 Consumer PRD；
- 新增第二 Production Owner；
- 用 ADD 规避已有 Owner；
- 把 Reviewer 推测当事实；
- 在 Grounding 中实现代码。

## Exit

完成时必须满足：

1. 重复建设已移除或改为 KEEP/MODIFY；
2. 关键 Current Capability 有足够证据；
3. Target Owner 唯一；
4. Change Classification 收敛；
5. PRD 只保留架构/行为约束；
6. revision 只关闭上一轮 Finding；
7. 状态为 `DRAFT` 或 `REVIEW_REQUIRED`。
