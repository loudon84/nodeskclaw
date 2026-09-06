# RM-16 PRD 原文要点与实施问题总结

- 日期：2026-09-05
- PRD：`docs_agent/prd-v1.6.14-hermes-provider-conformance-recovery.md`（v1.6.14，`status: APPROVED`，`review_verdict: PASS`）
- Architecture：`AD-SKILL-AGENT-V16-A1@1.6.0` / RM-16
- Plan：`.cursor/plans/rm-16_hermes-provider-conformance-recovery.plan.md`
- 本报告不是 RM-16 DONE 证明，也不改写 Roadmap。

**结论先说**：生产路径补丁和 live 套件已经写出来，但 **DOD-01 未满足**。真实 Hermes `v2026.8.31` 上 PC-01 至 PC-09 **没有全绿**。RM-16 **不能**标 `DONE`，也 **不能**声称 RM-02 Provider Conformance 已重新关闭。

---

## 1. PRD 是什么（原文定位）

标题：**DeskClaw 团队版 Hermes Provider Conformance & Recovery PRD v1.6.14**

原文开篇：

> 本文定义 RM-16：在真实 Hermes API Server（`>= v2026.8.31`）上取得 PC-01 至 PC-09 可复现实跑证据，并以此作为 RM-02 Provider Conformance 的再验证来源。范围严格止于 A1 Phase D，不吞并 RM-12 的 PC-10 至 PC-14，不把 RM-10 指标仓做成第二事件事实源。

原文 Scope：

> 本阶段用真实 Runtime 证明：Skill 调用 Hermes → Hermes 使用 Tool / 审批 / 长文本 / 委派 → Agent 持久化语义事件 → Backend 投影公共 SSE → Work 看到有意义的执行流。覆盖 Worker 重启 fencing、Hermes Runtime `interrupted`、版本地板失败关闭。禁止以 mock OpenAI `choices[].message.tool_calls`、mock reasoning、mock approval 单独结项。

原文产品边界：

- Work 只访问 Backend；Backend **不**直连 Hermes Native `/v1/runs` 作为员工执行面。
- Agent 是 Run / Attempt / Event / Terminal 的唯一 Production Owner，也是唯一 Hermes Native 调用方。
- Public 合同仍为冻结 v1.2.1。`runtime_run_id`、`runtime_session_id`、`child_session_id`、`subagent.*` 等不得进入 Public。
- 无本仓库前端表现变化。

这不是「给 Hermes 做产品验收」的 PRD。Hermes 只提供 Native Runtime；过关看的是员工 Public / Agent SoT 是否符合 v1.2.1。

---

## 2. PRD 原文：目标能力（PC-01 至 PC-09）

摘自 Target End-State Inventory。

| 能力 | PRD 原文目标 |
|---|---|
| PC-01 Plain Response | 真实 Hermes 纯文本；Public 文本完整；`assistant.message` 显著少于 token；无虚构 tool/approval；无 `reasoning.summary` |
| PC-02 Tool Run | 真实 Tool；`tool.started/completed` → Public `tool.call`；`call_id` 稳定；Work SSE 可观察 |
| PC-03 Approval | Work 批准/拒绝到达 Hermes `POST /approval` 且被接受；后续终态由 Runtime 事件 + Agent aggregator 决定；公共面仍只两档 |
| PC-04 Cancel | Work cancel → `/stop` → Agent terminal aggregation；覆盖 stop 404；员工路径可观察合同终态。HTTP 500 若挡住终态则必须闭合；不得只停在 `CANCELLING` |
| PC-05 Worker Recovery | 中途 kill/restart **NodeSKClaw Worker**（不是 Hermes）：旧 Attempt fencing、GET status reconcile、无重复 Public terminal、gap 已记录 |
| PC-06 Long Output | 长中文报告 coalescing；无「一两个汉字一条 event」；最终文本无丢失无重复且顺序正确 |
| PC-07 Runtime Delegation | Hermes subagent 仍单一 Public Run；`subagent.*` 不进 Public |
| PC-08 Runtime Restart | **Hermes 重启**得 `interrupted` → FAILED + `RUNTIME_INTERRUPTED`；不自动新 Attempt |
| PC-09 Version Floor | Runtime `< v2026.8.31` 在 Capability Probe 失败关闭 `RUNTIME_VERSION_UNSUPPORTED`；不降级 ChatCompletion |

原文 Recovery 对 PC-08 的刺激是「Hermes Runtime 重启」，**没有**规定必须用 `hermes gateway restart` / `hermes gateway stop`，也 **没有**禁止这两条 CLI。禁止的是：旧 Attempt 对错误 Runtime Run 发 HTTP `/stop`；以及恢复时重订阅 `/events`。

---

## 3. PRD 原文：验收与完成定义

### 3.1 Acceptance Criteria（须全部满足）

| AC | 对应 | 原文义务 |
|---|---|---|
| AC-01 | C02 / V01 | 纯文本 Public 完整；`assistant.message` 显著少于 token；无虚构 tool/approval；无 `reasoning.summary` |
| AC-02 | C03 / V02 | Public `tool.call` started 与 completed/failed 同一 `call_id` |
| AC-03 | C04 / V03 | 批准到达 Hermes `/approval` 且被接受（Native 证据含该路径） |
| AC-04 | C04 / V04 | 拒绝到达 `/approval` 且被接受；`session`/`always` 仍被拒 |
| AC-05 | C05 / V05 | cancel 调 `/stop` 后出现合同终态，不是只停在 `CANCELLING` |
| AC-06 | C06 / V06 | kill/restart **Worker** 后 fencing + 单一终态 + 可查询 gap |
| AC-07 | C07 / V07 | 长中文 coalescing，文本完整顺序正确 |
| AC-08 | C08 / V08 | 无 Public Child Run，敏感字段不进 Public |
| AC-09 | C09 / V09 | Hermes 重启 → `FAILED` + `RUNTIME_INTERRUPTED`，无自动新 Attempt |
| AC-10 | C10 / V10 | 旧版本 Capability Probe 失败关闭，无 ChatCompletion |
| AC-11 | C01/C11/C12 / V11 | 不新建 Adapter、Event Store、Worker 状态机或 Coalescer |
| AC-12 | C13 / V12 | `contracts/skill-run/v1.2.1/` 零修改 |
| AC-13 | C14/C15 / V13 | 不恢复 ChatCompletion parser；Backend 不做员工 Native 客户端 |
| AC-14 | C16 / V14 | 复用 RM-12..15 runner；记录 `hermes_runtime_version` 与 `auth_type=user_jwt` |
| AC-15 | C17 / V15 | PC-01 至 PC-09 证据包可被 RM-02 Revalidation Link 引用；mock-only 不得关闭 |
| AC-16 | C18 / V16 | live 公共面无 HermesTask 禁止字段或 `/api/v1/hermes/tasks/` |

原文明确：**不得把「HTTP 不是 500」当成 PC-03 / PC-04 出口。**

### 3.2 Definition of Done（原文）

- **DOD-01**：PC-01 至 PC-09 均有真实 Hermes 可复跑证据；C04/C05 不得以 HTTP 非 500 或 `CANCELLING` 代替出口。
- **DOD-02**：Backend 仍不直连员工 Native Run；`runtime_run_id` / `runtime_session_id` 不进 Public。
- **DOD-03**：v1.2.1 未被改写；ChatCompletion parser 未恢复；未新建第二 Adapter / Event Store。
- **DOD-04**：RM-15 已 DONE 且本项 Review / Verification PASS，implementation commit 与验证证据写入 Roadmap 后，RM-16 才可标 `DONE`。RM-02 状态变更是独立 Roadmap 更新。

### 3.3 原文 Non-Goals（节选）

不以 PC-10 至 PC-14 结项；不完成 RM-10 指标仓；不改写 v1.2.1；Backend 不变成员工 Native 客户端；不恢复 ChatCompletion parser；不以 `/events` 重订阅作为 Recovery；不把 `hermes gateway restart/stop` 写成产品功能或禁令。

---

## 4. 实施完成了什么

Plan 拆成 T1（生产修补）和 T2（live 套件）。Audit 摘要（`.smc/runs/RM-16-completion-audit-result.json`）对 **代码范围** 记 `PASS`：未新建第二 Adapter / Event Store，未改 v1.2.1，未恢复 ChatCompletion。这只证明 diff 范围，**不**等于 live 过关。

### 4.1 已提交的生产补丁

Commit `8767e2ac` `feat(agent): V16 RM-16`，仅 6 个 Agent 文件：

| PRD 缺口 | 代码行为 |
|---|---|
| C04 `/approval` 未被接受 | `control_generation`：`run.generation=0` 回落 Binding generation，避免控制面被栅栏成 `fenced` |
| C04 南向鉴权 | `runtime_control_headers` 从租约 mint Bearer，供 `/approval`、`/stop`、inspect 使用 |
| C05 cancel 停在 `CANCELLING` | `/stop` 后 `inspect_runtime_terminal`；`stop_404` 或 `run.cancelled`/`run.failed` 写合同终态 |
| C06 Worker gap | `_recover_stale_runs` 写 `kind=worker_restart_gap`；waiting/interrupted 仍禁止自动 `QUEUED` |

聚焦单测在 Agent 仓库内。这些测试不能代替 live Native。

### 4.2 写了但未进 `8767e2ac` 的内容

| 资产 | 状态 | 影响 |
|---|---|---|
| `nodeskclaw-backend/app/api/runs.py`：Agent 5xx → Public 409 `errors.run.agent_error` | 工作区有，**未进该 commit** | live Backend `:4510` 仍可能对 cancel 回 HTTP 500 |
| `tools/acceptance/run_rm16_live_conformance.py` | T2 已写，当时不在 `8767e2ac` | live 套件本身可用，但不是已发布 commit 的一部分 |
| Postman 70 文件夹 + `reports/live手工执行指导.dmd` | 手工复现资产 | 不能替代 Ledger 证据 |

KEEP 未改：Coalescer、v1.2.1、`hermes_api_server_client.py`、既有 RM-13 runner、PC-12 单测文件。符合 AC-11/12/13。

---

## 5. Live 实跑对照（证据文件）

环境：真实 Hermes Native，证据记录 `hermes_runtime_version=v2026.8.31`，`auth_type=user_jwt`。时间以 `docs_agent/evidence/RM-16-live-*.json` 为准（约 2026-09-05T14:36Z 一批，PC-05 文件更早）。

审批工具：`hermes_marketing__park-waiting-approval`（符合 PRD：禁止自动挑 Catalog `requiresApproval`）。  
PC-01/02/06 实际刺激：`hermes_marketing__customer-profiling`。

| 场景 | 证据结果 | PRD AC | 问题 |
|---|---|---|---|
| V14 preflight | PASS（capabilities / health，版本地板满足） | AC-14 | 无 |
| PC-03 approve | **PASS** `approve_http=200`，路径含 `/v1/runs/<id>/approval`，Hermes `waiting_for_approval` → `running` | AC-03 | 相对 RM-15 live 的 HTTP 400 **已闭合** |
| PC-03 deny | **PASS** `deny_http=200`；`session`/`always` HTTP 400 | AC-04 | 同上 |
| PC-07 | **PASS** 单一 Public Run，无泄漏 | AC-08 | runner **不强制** Hermes 真开子代理；隔离扫描过关，不是「Hermes 子代理产品验收」 |
| PC-09 | **PASS** `pc09_mode=probe_only_version_stub`，桩版本 `v2026.4.23` → `RUNTIME_VERSION_UNSUPPORTED` | AC-10 | Plan 允许无旧 Runtime 时用 probe-only 桩；**不是**真机旧网关全量证明 |
| PC-12 | **PASS** 无 HermesTask 禁止字段 | AC-16 | 无 |
| PC-01 | **FAIL** `COMPLETED` 但 `assistant_message_count=0` | AC-01 | 刺激 Skill 不产纯中文 `assistant.message` |
| PC-02 | **FAIL** `tool_call_count=0` | AC-02 | 同一 Skill 不产 Public `tool.call` |
| PC-06 | **FAIL** `assistant_message_count=0` | AC-07 | 同上，无法证明 Coalescer 长文 |
| PC-04 | **BLOCKED** `cancel HTTP 500` | AC-05 | 未打到 Hermes `/stop` 合同终态；远端 Backend 未吃到 409 映射 |
| PC-05 | 盘上 JSON 为 **BLOCKED**（13:52Z，缺 `RM13_BACKEND_BASE_URL`）；14:36 套件未刷新该文件。后续执行缺 `RM16_WORKER_KILL_CMD` | AC-06 | 没有杀 **Agent `:4580` Worker** 的命令；跳过 ≠ PASS |
| PC-08 | **BLOCKED** `RM16_HERMES_RESTART_UNAVAILABLE` | AC-09 | 没有打到 Hermes `:29401` 进程的重启命令。PRD 要求「重启 Runtime」，未指定 CLI |

合同边界抽查（AC-11～13、DOD-02/03）：live 未见 ChatCompletion；未见 Public `runtime_run_id` 泄漏（PC-12 PASS）。**范围守住了，出口没守住。**

---

## 6. 问题归类（根因，不是再猜 Hermes 坏了）

### A. 生产修补未部署到 live Backend（挡 PC-04）

PRD C05 要求 Public cancel 不能以 HTTP 500 挡终态观察。Agent 侧 cancel 终态逻辑已在 `8767e2ac`；Backend 5xx→409 在工作区 **未进该 commit**，live `:4510` 仍回 500。现象与 RM-15 live（`cancel_http=500`、`CANCELLING`）同类，RM-16 本应闭合却未在实跑环境闭合。

### B. 刺激 Skill 选错（挡 PC-01 / PC-02 / PC-06）

PRD 要求纯文本、真 Tool、长中文三条不同质量。实跑三条都用 `hermes_marketing__customer-profiling`。Run 能 `COMPLETED`（Hermes Native 南向是通的），但 SoT 没有 `assistant.message` / `tool.call`。这是 **投影质量刺激错误**，不是 capabilities 失败。

换工具前不要改 Coalescer / Normalizer（PRD C12 KEEP）。

### C. 故障注入命令缺失（挡 PC-05 / PC-08）

| 场景 | PRD 要杀/重启的对象 | 实跑缺什么 |
|---|---|---|
| PC-05 | NodeSKClaw **Worker**（Agent `:4580`） | `RM16_WORKER_KILL_CMD` |
| PC-08 | **Hermes Runtime** 进程（`:29401`） | `RM16_HERMES_RESTART_CMD`，且必须打到 Hermes 所在主机 |

本机 `hermes gateway restart` 若打不到远端 `:29401`，不能当 PC-08 证据。现场若禁止这两条 CLI，那是运维约束，**不是**本 PRD 禁令；PC-08 仍需要某种真重启 Hermes 的手段，否则只能 BLOCKED，不能 PASS。

### D. 治理状态

- Plan Todo T1/T2 可标 completed（代码/套件已写）。
- Verification 按 DOD-01 仍 **BLOCKED**。
- 不得把 Postman 绿勾、probe-only PC-09、跳过的 PC-05 写进 RM-02 再验证包当全绿。

---

## 7. 对照：PRD 要什么 vs 现在有什么

| PRD 出口 | 现在 |
|---|---|
| PC-03 `/approval` 被 Hermes 接受 | **已有** live PASS（相对 RM-15 的核心修补成立） |
| PC-04 `/stop` 后合同终态、非 HTTP 500 | **未过**：live cancel HTTP 500 |
| PC-01/02/06 文本与 tool 质量 | **未过**：刺激 Skill 无对应事件 |
| PC-05 Worker 重启 gap | **未取证** |
| PC-08 Hermes 重启 interrupted | **未取证** |
| PC-07 / PC-09 / PC-12 / 版本地板 | **有条件过关**（PC-09 为桩；PC-07 为隔离扫描） |
| 不新建 Adapter / 不改 v1.2.1 / 不恢复 ChatCompletion | **守住** |
| DOD-01 全套可复跑 PASS | **未达到** |
| RM-16 Roadmap DONE / RM-02 关闭 | **禁止声称** |

---

## 8. 若要继续闭合，只剩三件（与 PRD 最小范围一致）

1. **部署** Backend cancel 映射（工作区 `runs.py` 409）到 live `:4510`，复跑 PC-04，确认不是 500、不是 `CANCELLING`。
2. **换两个刺激名**：纯中文不调工具（PC-01/06）、真 Tool（PC-02）；审批继续 `hermes_marketing__park-waiting-approval`。
3. **给出打得到目标进程的命令**：Agent Worker（PC-05）、Hermes `:29401`（PC-08）。没有命令就保持 BLOCKED，不要伪造 PASS。

不要加新场景，不要改 v1.2.1，不要用 ChatCompletion mock 补 PC-09。

---

## 9. 证据索引

| 类型 | 路径 |
|---|---|
| PRD 原文 | `docs_agent/prd-v1.6.14-hermes-provider-conformance-recovery.md` |
| Plan | `.cursor/plans/rm-16_hermes-provider-conformance-recovery.plan.md` |
| Agent 实现 commit | `8767e2ac` |
| live JSON | `docs_agent/evidence/RM-16-live-pc*.json` |
| 手工步骤 | `reports/live手工执行指导.dmd` |
| Postman | `tools/postman/nodeskclaw-agent-full-flow.postman_collection.json` 文件夹 70 |
