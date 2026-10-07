# PRD — Remote ACP Desktop 生产门禁（Production Gate）v2.1

| Field | Value |
|---|---|
| Document ID | `PRD-NODESKCLAW-REMOTE-ACP-DESKTOP-PRODUCTION-GATE-v2.1` |
| Status | `APPROVED_FOR_PLAN` |
| grilling_lock | Q1–Q16 locked 2026-10-07（见 §16） |
| Audience | Product / SMC Copilot Desktop / NodeSkClaw Release / QA |
| Provider Contract | `REMOTE-EXPERT-FRONTEND-CONTRACT v2.1.0`（`FROZEN`） |
| Consumer Pin | `2.1.0` |
| Preconditions | Provider G1–G4 PASS；EXT-G5 Golden `overall=PASS`；契约树 `productionGate=unpassed` |
| EXT-G5 Evidence | `docs_agent/evidence/remote-acp-v2.1/ext-g5/G6-SUMMARY.json`（`smc-copilot@1d0eb5b2`） |
| Upstream | Provider v2.0 §G7；Fidelity v2.1；Consumer EXT-G5 v2.1 |
| SMC Live Runner | `smc-copilot/apps/work/scripts/remote-expert-g7.mjs` + `tests/remote-expert/live/g7-golden-consumer.live.test.ts` |
| Goal Artifact | Evidence 写 `productionGate=passed` + `claimAuthorized=true` 后，允许对外宣称 DeskClaw 团队版 Desktop Remote Expert 生产可用 |
| Non-Artifact | **禁止**改冻结树 `v2.1.0/manifest.json` 的 `productionGate`；verifier 继续要求契约树 `unpassed` |

---

## 0. 一句话结论

EXT-G5（G6）已 PASS。本门禁在 **L2 生产** 跑通 SMC G7 live（任一 `BLOCKED`/`SKIPPED`=FAIL），人工完成三侧观测 join，evidence 写 `productionGate=passed`；再经 provenance + 工程/产品双签将 `claimAuthorized=true` 后，才允许对外宣称。契约树始终 `unpassed`。

---

## 1. 背景

| 已完成 | 证据 |
|---|---|
| Provider READY（G1–G4）+ Contract FROZEN `2.1.0` | 本仓 freeze / discovery |
| SMC pin cutover | `smc-copilot@e68554a8` |
| EXT-G5 Golden（G6 mapped） | `overall=PASS`，evidence `productionGate=unpassed` @ `1d0eb5b2` |

| 本 PRD 关闭 | 说明 |
|---|---|
| L1 缩集预跑 | LIVE-001…003 → `staging-prerun-SUMMARY.json` |
| L2 G7 live 全套 | `A-G7-LIVE-001`…`016` 全 PASS |
| Evidence `productionGate=passed` | 不含契约树 flip |
| `claimAuthorized` | provenance + 双签后 |
| 对外宣称 | 仅文档/公告；应用内不展示 |

历史命名：

| 名称 | 含义 |
|---|---|
| Provider G1–G4 | 本仓 Provider Ready |
| EXT-G5 / SMC G6 | Consumer Golden（已 PASS） |
| **本 PRD / SMC G7 live** | 生产门禁 |
| 契约树 `manifest.productionGate` | **永远 unpassed**（Evidence-only，Q3=A） |

**Verifier 事实**：`tools/contracts/verify_remote_expert_frontend_contract_v21.py` 要求契约树 `productionGate == unpassed`；`SHA256SUMS` 含 `manifest.json`。本 PRD **不得**为宣称去改冻结 manifest。

---

## 2. Goals / Non-Goals

### 2.1 Goals

| ID | Goal |
|---|---|
| G-PG-01 | L1 缩集预跑 + L2 生产 G7 live 全套 Required PASS |
| G-PG-02 | 关闭 v2.0 生产 AC：`A-REL-002` / `A-OBS-001` / `A-SEC-003` / `A-SEC-004` / `A-RES-001` / `A-RES-002` |
| G-PG-03 | 无 exe / 无密钥入 evidence / 无直连 Agent |
| G-PG-04 | Evidence-only：`productionGate=passed` + 后续 `claimAuthorized=true`（commit-bound） |
| G-PG-05 | 双签后授权对外首次宣称 |

### 2.2 Non-Goals

- 不改 `v2.1.0` 契约正文 / 不 reseal 仅为 gate 状态
- 不改 v21 verifier 放行契约树 `passed`
- 不重开 EXT-G5；不把 staging 单独抬成生产 Ready
- 不扩展 Task / Knowledge / 新 Contract 大版本
- 不在应用内展示 productionGate 或以其做功能开关（Q8=A）
- 不在本 PRD 改 Portal Admin UI

---

## 3. 前置条件（缺一不可）

1. Provider：`frontendContractGate=passed`，`status=FROZEN`，`frontendContractVersion=2.1.0`
2. 目标环境 discovery 与 Consumer pin **exact-match**
3. EXT-G5：`ext-g5/G6-SUMMARY.json` 中 `overall=PASS`
4. SMC HEAD 含 pin `2.1.0` 且 digests 未漂
5. Live 凭证仅 env/密钥库，禁止入 git / evidence 明文
6. 存在可机读 `staging-prerun-SUMMARY.json`（§6.1）后才允许开 L2

---

## 4. 前端表现变化

本仓 portal/Admin：**无前端表现变化**。

DeskClaw 团队版 / SMC Copilot：

### 4.1 对外宣称（仅 `claimAuthorized=true` 之后）

**总结**: 允许在 Release Note / 群公告声明生产可用；应用内不新增 productionGate UI。

**元素级变化**:
- Release Note / 群公告：**允许**首次「DeskClaw 团队版 Desktop Remote Expert 生产可用（Contract 2.1.0）」+ Desktop semver/commit
- 应用内关于页 / 功能入口：**不**展示 `productionGate`；Remote Expert 可用性仍只靠 ContractGate + pin
- 门禁执行期：无终端用户 UI 变更

---

## 5. 需求（Normative）

### REQ-PG-2101 — Environment Bound

- MUST 先完成 §6.1 L1 缩集预跑并落盘。
- MUST 在 §6.2 L2（`envId=nodeskclaw-prod`）执行 G7（`SMC_REMOTE_EXPERT_G7=1`）。
- MUST discovery exact-match pin `2.1.0`。
- MUST NOT 用 mock / 仅 staging 将 evidence `productionGate` 标 `passed`。

**Acceptance:** A-PG-2101；`A-G7-LIVE-001`…`003`

### REQ-PG-2102 — Live Golden Consumer E2E

- MUST L2 真实 WSS 完成 session/prompt/transcript/resume/reconnect/permission/cancel/artifact/close/长回合。
- MUST 关闭 `A-REL-002`。
- MUST 任一 case `FAIL`/`BLOCKED`/`SKIPPED` → 门禁 FAIL（Q12=A）。

**Acceptance:** A-PG-2102；`A-G7-LIVE-004`…`013`、`016`

### REQ-PG-2103 — Resource Authority Live

- MUST `A-RES-001` / `A-RES-002`（LIVE-009 / LIVE-012）。

**Acceptance:** A-PG-2103

### REQ-PG-2104 — Security Boundary Live

- MUST `A-SEC-003` / `A-SEC-004`（含 LIVE-014）。
- MUST evidence/JSONL secret scan；命中 → FAIL。

**Acceptance:** A-PG-2104

### REQ-PG-2105 — Observability Join（人工）

- MUST 单次 remote prompt 的 `traceId`/`operationId` 与 Backend/Agent 日志指针写入 `PG-SUMMARY`（Q5=A）。
- MUST NOT 无 join 标 PASS。

**Acceptance:** A-PG-2105

### REQ-PG-2106 — Local Isolation Live

- MUST `A-G7-LIVE-015` PASS。

**Acceptance:** A-PG-2106

### REQ-PG-2107 — Evidence `productionGate=passed`（非契约树）

仅当 A-PG-2101…2106 PASS 后：

- MUST SMC G7 evidence（或等价 release oracle）写 `productionGate=passed`，`claimAuthorized=false`（Q9=A）。
- MUST 本仓写 `docs_agent/evidence/remote-acp-v2.1/production-gate/PG-SUMMARY.json`（同语义）。
- MUST NOT 修改 `contracts/remote-expert-frontend/v2.1.0/manifest.json` 的 `productionGate`。
- MUST NOT 为本字段 reseal 冻结 bundle。
- MUST 记录：`envId`、k8s context/namespace、G7 commitSha、cases、obs 指针、`passedAt`、`expiresAt=passedAt+14d`（Q14=A）。

**Acceptance:** A-PG-2107

### REQ-PG-2108 — Claim Authorization

- MUST 在 `expiresAt` 前完成：可分发构建 provenance（`work-build-info.json` 或等价）+ 工程签字 + 产品签字（Q6=C，Q7=C）。
- MUST 然后写 `claimAuthorized=true`，并记录 Desktop semver + commit + contract `2.1.0`。
- MUST 超时未宣称 → 作废 evidence `passed`，须重跑 L2（Q14=A）。
- MUST 仅此时允许对外宣称；称呼「DeskClaw 团队版」。

**Acceptance:** A-PG-2108

### REQ-PG-2109 — Drift Invalidation

- MUST L2 discovery 相对 pin `2.1.0` 漂移 → 立即作废 evidence `productionGate=passed` 与未完成宣称；须重跑（Q16=A）。

**Acceptance:** A-PG-2109

---

## 6. 环境

### 6.1 L1 Staging 缩集预跑（强制）

| 项 | 值 |
|---|---|
| 目的 | 降低首次打 L2 翻车（Q4=C） |
| 最少用例 | `A-G7-LIVE-001`…`003` |
| 证据 | `docs_agent/evidence/remote-acp-v2.1/production-gate/staging-prerun-SUMMARY.json`（Q11=A） |
| 可否单独宣称 | **否** |

建议坐标：`namespace=nodeskclaw-staging`，同一 infra context（URL 不入库）。

### 6.2 L2 Production（唯一可写 evidence `passed`）

| 项 | 值 |
|---|---|
| envId | `nodeskclaw-prod`（Q15=A） |
| k8sContext | `nodesk-infra-vke-dev-dmz-01` |
| namespace | `nodeskclaw-system` |
| Backend URL | 仅运行时 env 名 `SMC_REMOTE_EXPERT_G7_BACKEND_URL`（Q10=A）；**禁止**入 git |
| 执行方式 | 联席：SMC 操作 runner，NodeSkClaw 盯集群/日志 join（Q13=C） |

| 级别 | 可否 evidence `productionGate=passed` | 可否 `claimAuthorized` |
|---|---|---|
| L0 mock | 否 | 否 |
| L1 staging | 否 | 否 |
| L2 prod | 是（live+§5 收口后） | 是（再 + provenance + 双签） |

---

## 7. SMC G7 Live 映射

缺 env → `BLOCKED` → **本门禁 FAIL**（Q12=A）。无 waiver。

| Live ID | 场景 | AC |
|---|---|---|
| A-G7-LIVE-001…003 | Discovery / Catalog / WSS | A-PG-2101 |
| A-G7-LIVE-004…008,010,011,013,016 | E2E 会话与控制 | A-PG-2102 |
| A-G7-LIVE-009,012 | Attachment / Artifact | A-PG-2103 |
| A-G7-LIVE-014 | Security route | A-PG-2104 |
| A-G7-LIVE-015 | Local isolation | A-PG-2106 |

| v2.0 AC | 本 PRD |
|---|---|
| A-REL-002 | A-PG-2102 |
| A-OBS-001 | A-PG-2105 |
| A-SEC-003/004 | A-PG-2104 |
| A-RES-001/002 | A-PG-2103 |

---

## 8. Acceptance Bundle

| ID | 通过条件 |
|---|---|
| A-PG-2100 | `staging-prerun-SUMMARY.json` LIVE-001…003 PASS |
| A-PG-2101…2106 | 见 §5 |
| A-PG-2107 | Evidence `productionGate=passed`，`claimAuthorized=false`；契约树仍 `unpassed` |
| A-PG-2108 | provenance + 双签 → `claimAuthorized=true`（≤14 天） |
| A-PG-2109 | 漂移作废规则可执行（文档+检查清单） |
| A-PG-ALL | 宣称前：2100–2109 所需项齐；任一 FAIL/BLOCKED/SKIPPED → FAIL |

**Oracle**

- SMC：`apps/work/test-results/remote-expert-g7.json`（及 cases JSONL）
- 本仓：`production-gate/staging-prerun-SUMMARY.json`、`production-gate/PG-SUMMARY.json`

`PG-SUMMARY` 最小字段：`envId`、`k8sContext`、`namespace`、`pin`、`g7CommitSha`、`g7SourceSha256`、`cases`、`obsJoin`、`productionGate`、`claimAuthorized`、`passedAt`、`expiresAt`、`desktopVersion`、`desktopCommit`（宣称时填）、`engineeringSignoff`、`productSignoff`。

---

## 9. 闸门顺序

| Gate | 退出条件 |
|---|---|
| PG0 | §3 前置 |
| PG1 | A-PG-2100 L1 缩集预跑 |
| PG2 | L2 凭证就位（不入库）+ 联席窗口 |
| PG3 | G7 LIVE-001…016 全 PASS |
| PG4 | A-PG-2103…2106；写 evidence `productionGate=passed`（A-PG-2107） |
| PG5 | provenance + 双签 → `claimAuthorized=true`（A-PG-2108）；对外宣称 |

PG5 前：**禁止** Release Note / 群公告写生产可用。

---

## 10. 所有权

| 工作 | Owner |
|---|---|
| G7 runner 与 SMC evidence | SMC（联席操作） |
| L2 环境 / discovery / 日志 join | NodeSkClaw（联席） |
| 本仓 SUMMARY 指针 | NodeSkClaw Release |
| 产品签字与对外文案 | Product |
| 工程签字与 provenance | SMC Desktop Release |

Plan：`commit_policy: post_review`。

---

## 11. 状态机

```text
EXT-G5_PASS ∧ manifest.productionGate=unpassed
  → PG0
  → PG1 staging prerun SUMMARY
  → PG2 L2 ready (joint)
  → PG3 G7 live all PASS
  → PG4 evidence productionGate=passed, claimAuthorized=false
       (expiresAt = passedAt + 14d)
  → PG5 claimAuthorized=true → public claim allowed
```

漂移（Q16）或过期（Q14）：回到 PG1/PG3；契约树始终 `unpassed`。

---

## 12. 与既有文档

| 文档 | 关系 |
|---|---|
| Provider v2.0 §G7 | AC 来源；本 PRD 映射到 G7 live + evidence-only |
| Fidelity v2.1 | Provider READY 不变 |
| Consumer EXT-G5 v2.1 | 前置；不重开 |
| v21 verifier | 契约树保持 `unpassed`；与本 PRD 一致 |

---

## 13. 批准与下一步

- grilling Q1–Q16 已锁 → Status `APPROVED_FOR_PLAN`
- 下一步：生成 implementation plan（`commit_policy: post_review`）
- 执行：联席 L1 预跑 → L2 G7 → PG-SUMMARY → provenance/双签 → 宣称

---

## 14. Grilling Lock（不得改选，除非修订本 PRD）

| ID | Decision |
|---|---|
| Q1 | **A** 推进生产宣称，执行本 PRD |
| Q2 | **A** 仅 L2 生产可写 evidence `passed` / 宣称 |
| Q3 | **A** Evidence-only；冻结 manifest 永不改 `productionGate` |
| Q4 | **C** L2 前强制 L1 缩集预跑 LIVE-001…003 |
| Q5 | **A** 观测 join 人工 + 可机读指针 |
| Q6 | **C** provenance 卡宣称（PG5），不挡 A-PG-2107 |
| Q7 | **C** 工程 + 产品双签 |
| Q8 | **A** 仅对外文档/公告；应用内不展示 |
| Q9 | **A** live 收口写 `productionGate=passed`；宣称用 `claimAuthorized` |
| Q10 | **A** envId + k8s 坐标；URL 仅 env 名 |
| Q11 | **A** 强制 `staging-prerun-SUMMARY.json` |
| Q12 | **A** 任何 BLOCKED/SKIPPED = FAIL |
| Q13 | **C** 联席执行 |
| Q14 | **A** 14 天宣称窗；超时作废重跑 |
| Q15 | **A** `envId=nodeskclaw-prod` → context `nodesk-infra-vke-dev-dmz-01` / ns `nodeskclaw-system` |
| Q16 | **A** discovery 漂移立即作废 passed 与未完成宣称 |
| Q17 | **A** 授权写入本 PRD 并结束 grilling |

---

## 15. 修订记录

| Date | Change |
|---|---|
| 2026-10-07 | 初稿 PROPOSED |
| 2026-10-07 | Grilling Q1–Q16 锁定；Evidence-only；L2+L1 缩集；claimAuthorized 双相；Status → `APPROVED_FOR_PLAN` |
| 2026-10-07 | 实施代码批：SMC G7 evidence/prerun/claim；本仓 drift/SUMMARY 校验与 RUNBOOK；live 运维待凭证（`OPS-STATUS.json`） |
