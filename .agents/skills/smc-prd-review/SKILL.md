---
name: smc-prd-review
description: 独立审查 NoDeskClaw PRD 的架构正确性与收敛性。支持 initial 与 closure；closure 只验证上一轮 Finding，防止多轮无界 Review 和 Token 浪费。
version: 3.1.0
disable-model-invocation: true
---

# SMC PRD Review

## 目标

本 Skill 是 **PRD Architecture Gate**，不是 Implementation Plan Review、Code Review 或 Provider Release Audit。

只审六个 Gate：

1. Scope
2. Existing Capability
3. Production Ownership
4. Change Classification
5. API/IPC/Auth/Contract/Security Boundary
6. Behaviour → Acceptance Criteria

Review 只读。使用 [`../../references/architecture-convergence.md`](../../references/architecture-convergence.md)。

## Mode

| Mode | 场景 | 范围 |
|---|---|---|
| `initial` | 首次独立审查 | 一次性检查六个 Architecture Gates |
| `closure` | 上一轮 `REVISE` 后 | 只验证上一轮 OPEN Finding + 修订 regression |

默认：
- 有上一轮 Review/Closure Table → `closure`
- 否则 → `initial`

输出必须标记 mode。

## Context Budget

1. 读 PRD。
2. 读根及受影响 subsystem `AGENTS.md`（如存在；本仓库当前仅有根 AGENTS.md）。
3. 优先复用 PRD 的 Source Anchors。
4. 只有某个 Gate 无法判断时才打开对应源码/test/contract。
5. `closure` 默认只打开 OPEN Finding 的 Evidence。
6. 禁止为了“独立”重新读取全部 Grounding 证据。
7. 禁止扫描 monorepo。

独立 = 独立判断，不等于重复 discovery。

## PRD / Plan Boundary

以下可阻止 PRD：

- duplicate/wrong Production Owner；
- ADD/MODIFY/REPLACE 误判；
- execution/trust boundary 可绕过；
- 必需合同语义缺失；
- 架构级 lifecycle/concurrency 缺口；
- Behaviour 与 AC 关键冲突。

以下通常属于 Plan，不能单独导致 REVISE：

- exact 私有函数；
- fetch option；
- React hook；
- 内部 errorCode 名；
- test file / mock；
- DOM/framework API；
- 非合同性调用顺序。

若这些只是某种可行实现，写入 `Plan Notes`。
只有它本身决定合同、安全、不变量、唯一 Owner 或可观察 Behaviour 时才升级 Finding。

## 六个 Architecture Gates

### G1 Scope
- 是否直接服务目标；
- 是否无关扩张 framework/store/service/protocol；
- 是否遗漏目标必需路径。

### G2 Existing Capability
只抽查高风险声明：
- False MISSING；
- False KEEP；
- duplicate Service/Store/Parser/Adapter/Lifecycle。

不重做完整 Current Inventory。

### G3 Ownership
- 一个 Capability 一个 Production Owner；
- 新文件不形成第二 Owner；
- projection 与 authoritative state 不混淆。

### G4 Classification
- EXISTS→KEEP
- PARTIAL→MODIFY
- 真 MISSING→ADD
- Owner 转移→REPLACE+REMOVE
- compatibility 有 removal contract。

### G5 Boundary
只检查当前 PRD 涉及的 API/IPC/Auth/Contract/security 与 alternate entrypoint。
需要证明最终 enforcement owner，不展开非必要施工调用图。

### G6 Acceptance
- 关键 Behaviour 有可验证 AC；
- AC 与 Behaviour 一致；
- AC 验证结果，不强制非必要私有实现。

## External Contract Guard

Reviewer 不是 Provider Release Auditor。

只验证本 PRD 实际依赖的 stable ref、endpoint、schema/field、identity、semantics。

除非 PRD Scope 明确包含 Provider 发布，否则以下不得 BLOCKED：

- Provider `main`；
- manifest 生成元数据；
- release CI / deploy；
- benchmark / load gate；
- manifest 是否回写 peeled SHA。

Consumer 尚未实施 Target Contract 是待实施工作，不是 BLOCKED。

外部问题只有同时满足才可 BLOCKED：

1. 属于当前 PRD Scope；
2. 真实阻止 Capability；
3. PRD 自身无法修正。

## Severity 与 Verdict

Finding Severity：

- `BLOCKER`：外部权威语义/SOT/人类架构决策缺失，PRD 自身无法解决。
- `MAJOR`：PRD 可修正的架构错误。
- `MINOR`：不影响架构正确性的表达/Anchor/次要遗漏。
- `NOTE`：Plan 阶段工程提示。

Verdict：

- 有 BLOCKER → `BLOCKED`
- 无 BLOCKER，有 MAJOR → `REVISE`
- 只有 MINOR/NOTE 或无 Finding → `PASS`

MINOR、NOTE、Plan 级实现选择不得阻止 PASS。

## Initial Review

1. 一次性跑六个 Gate。
2. 独立抽查关键 Owner/Boundary/ADD/REPLACE。
3. 只读产生 Finding 所需证据。
4. 一次性报告当前可识别的 BLOCKER/MAJOR。
5. 不把问题留到后续轮次继续无界下钻。

## Closure Review

以上一轮 Finding 为主键：

| Finding | Previous Severity | Closure Evidence | Status |
|---|---|---|---|

Status：

`CLOSED | OPEN | NOT_REPRODUCED`

只允许新增 BLOCKER/MAJOR，当：

1. 修复旧 Finding 直接引入 architecture regression；
2. 出现上一轮不可获得的新权威证据；
3. 同一根因的绕过路径只有在修订后才可观察。

禁止因为本轮又多读源码而增加与修订无关的新 Finding。

上一轮所有 BLOCKER/MAJOR 均 CLOSED/NOT_REPRODUCED，且无修订 regression：

→ `PASS`

## Evidence Quality

每个 BLOCKER/MAJOR 必须有：

- Finding
- Severity
- Evidence
- Violated Rule / Invariant
- Impact
- Required Correction

规则：

- Evidence 指向具体 source/contract/PRD section；
- “符号不一致”必须给出 `PRD identifier → Actual identifier` 的具体差异；
- 无法复现的推测不能作为 MAJOR；
- Required Correction 描述架构/行为，不写施工代码。

## Test Boundary

PRD Review 只验证测试策略是否能证明架构行为，例如真实 trust boundary、routing no-call、stale-result。

具体 test file、mock/spy/fixture 写法交给 Plan。

## 输出

```markdown
# PRD Review

**Review Mode：initial | closure**
**Verdict：PASS | REVISE | BLOCKED**

## Baseline
## Blocking Findings
## Required Revisions
## Minor Findings
## Plan Notes
## Architecture Convergence
## Closure Table   # closure only
## Review Conclusion
```

下一步：

- `PASS` → `smc-prd-converge`
- `REVISE` → `smc-prd-grounding` mode=`revision`
- `BLOCKED` → 等待真实外部证据/人类决策

## 禁止

- 修改 PRD；
- closure 重新 full review；
- Plan 细节升级为 MAJOR；
- Source Anchor 小问题阻止 PASS，除非导致 Owner/Boundary 错误；
- 审计无关 Provider release/manifest/CI/deploy；
- 默认 `doubt-driven-development`；
- 默认跨模型二审；
- 为“更保险”扩大源码读取；
- 把猜测写成 Finding。

## Exit

1. Verdict 只由 BLOCKER/MAJOR 决定；
2. initial 一次性覆盖 Architecture Gates；
3. closure 单调关闭旧 Finding；
4. MINOR/NOTE 不阻止 PASS；
5. PASS 后不再继续 PRD architecture discovery。
