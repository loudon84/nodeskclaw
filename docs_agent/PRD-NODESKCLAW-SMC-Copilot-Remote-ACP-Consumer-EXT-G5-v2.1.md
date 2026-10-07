# PRD — SMC Copilot Remote ACP Consumer（EXT-G5 / Golden Consumer）v2.1

| Field | Value |
|---|---|
| Document ID | `PRD-NODESKCLAW-SMC-COPILOT-REMOTE-ACP-CONSUMER-EXT-G5-v2.1` |
| Status | `EXT-G5_PASS`（Golden 已关门；`productionGate=unpassed`） |
| Audience | SMC Copilot Desktop 工程 / Product / QA |
| Provider Contract | `REMOTE-EXPERT-FRONTEND-CONTRACT v2.1.0` |
| Provider Status | `FROZEN`（G4 PASS，staging discovery 已对齐） |
| Consumer Repo | `loudon84/smc-copilot` |
| Consumer Path | `apps/work` |
| Consumer Pin Commit | `e68554a84a16414b96da50118fb867120c868966` |
| Consumer Evidence Commit | `1d0eb5b223f583afc45bd1d3bb460254a7ee22ce` |
| Consumer Evidence | `smc-copilot/apps/work/test-results/remote-expert-g6.json`（`overall=PASS`） |
| Evidence Pointer | `docs_agent/evidence/remote-acp-v2.1/ext-g5/G6-SUMMARY.json` |
| Consumer PRD（仓内） | `smc-copilot/docs/expert/PRD-SMC-Copilot-Remote-ACP-Consumer-EXT-G5-v2.1.md` |
| Branch Baseline | `work/prd-v6.3`（evidence 生成时 `dirty=false`） |
| Upstream PRD | `docs_agent/PRD-NODESKCLAW-Remote-ACP-Semantic-Fidelity-and-Session-Continuity-v2.1.md` |
| Upstream Provider PRD | `docs_agent/PRD-NODESKCLAW-Remote-ACP-Provider-and-SMC-Copilot-Consumer-v2.0.md`（拓扑 / REQ-MIG / REQ-SMC 基线） |
| Handoff | `docs_agent/evidence/remote-acp-v2.1/CONSUMER_HANDOFF.md` |
| Pin File | `contracts/remote-expert-frontend/v2.1.0/consumer/smc-copilot-v2.1-handoff.json` |
| Production Claim | **禁止**：EXT-G5 PASS ≠ 生产门禁；须另开 production-gate PRD/Plan |

---

## 0. 推进结论（给 SMC 工程的一句话）

Provider `v2.1.0` **FROZEN**；SMC pin cutover + **EXT-G5 Golden `overall=PASS`**（`pin=2.1.0` / `extG5=mapped` / `productionGate=unpassed`；evidence `@1d0eb5b2`）。  
**下一步**：生产门禁见 `docs_agent/PRD-NODESKCLAW-Remote-ACP-Desktop-Production-Gate-v2.1.md`（`APPROVED_FOR_PLAN`）。**不得**把 EXT-G5 当作生产 Ready；契约树 `productionGate` 保持 `unpassed`；宣称看 evidence `claimAuthorized`。

---

## 1. 背景与问题

### 1.1 Provider 现状（已完成，本 PRD 不重做）

NodeSkClaw Agent / Backend 已提供：

- 公网 `GET /api/v1/remote-experts`、`GET /api/v1/remote-experts/contracts`
- 公网 `WSS /api/v1/remote-experts/{agent_ref}/acp`
- ACP Runtime Gateway → Hermes Native Bridge
- Event SoT + AssistantReconciler + rich tool projection + turn-scoped seq + ACP-only continuity fail-closed
- Provider Gates **G1–G4 PASS**，Contract **FROZEN**

### 1.2 Consumer 现状（已核实）

依据本地仓 `d:\git_ai\smc-copilot` 对 `remote-expert-g6.json` 的实查（`python json.load`，`generatedAt=2026-10-07T15:03:22.384Z`）：

| 项 | 状态 |
|---|---|
| Pin `2.1.0` + digest lock | **PASS**（cutover `e68554a8`） |
| EXT-G5 / G6 evidence | **`overall=PASS`** @ `1d0eb5b2`；`extG5=mapped` |
| `A-SMC-2101`…`2106` / `A-MIG-2101` / `A-MIG-2102` / `A-G5-ALL` | **全部 PASS** |
| Local 隔离（本 PRD `A-SMC-2107`） | 无独立键；由 `Local Chat regression` / `A-ROUTE-LOCAL-001` / `A-SMC-004` **PASS** 覆盖 |
| `productionGate` | **`unpassed`** |
| Desktop 生产宣称 | **仍禁止** |

本 PRD 的 Consumer Golden 目标已关闭；剩余仅独立生产门禁（Non-Goal）。

### 1.3 本 PRD 解决什么

把 SMC Copilot 变成 **唯一合法 Desktop Consumer**：

1. 首连前 Contract Gate 对齐 **v2.1.0** pin
2. Electron Main 持有 `RemoteAcpClient`，只连 Backend 公网 WSS
3. Original Chat 投影 v2.1 事件（assistant 合并、rich tools、seq、continuity/terminal 错误）
4. 拆除本地 ACP exe 与非法 fallback
5. 产出 EXT-G5 可机读证据；`productionGate` 仍保持 `unpassed`，直到产品另行开 G7/生产门禁

---

## 2. 目标与非目标

### 2.1 Goals

| ID | Goal |
|---|---|
| G-C-01 | Consumer pin 且仅 pin `frontendContractVersion=2.1.0` 与下方 digest |
| G-C-02 | mismatch 时零 WebSocket、零 `session/prompt` |
| G-C-03 | 拆除 `nodeskclaw-acp.exe` / spawn / stdio / adapter keyring |
| G-C-04 | 复用 Original Chat，不新建第二套 Remote Chat 生命周期 |
| G-C-05 | 正确投影 assistant / tool / seq / continuity / terminal |
| G-C-06 | Local Hermes 与 Remote Expert 失败域隔离 |
| G-C-07 | EXT-G5 Golden 全场景 PASS，证据可机读 |

### 2.2 Non-Goals

- 不修改 NodeSkClaw Provider 契约树 `v2.1.0`（已 FROZEN）
- 不把 `production_gate` / `productionGate` 标为 `passed`
- 不引入 Skill Run / Work Expert / Remote Agent REST 作为聊天通道
- 不直连 Agent 内网 URL / Hermes
- 不公开 `runtime_run_id` 给 Renderer 业务逻辑
- 不重做 Task / Knowledge 扩展
- 不在本仓 `nodeskclaw-portal` 写 Consumer 代码

---

## 3. 冻结 Pin（Consumer 硬编码唯一真相）

来源：`docs_agent/evidence/remote-acp-v2.1/CONSUMER_HANDOFF.md`  
对照：`contracts/remote-expert-frontend/v2.1.0/consumer/smc-copilot-v2.1-handoff.json`

| Field | Value |
|---|---|
| `frontendContractVersion` | `2.1.0` |
| `frontendContractDigest`（aggregate） | `b25a9edbf2fa5afd6f15cb1cc1f8b17d6cb63b613bf18a2212e75002c61b4aba` |
| `catalogContractDigest` | `d51d27a33e6776be780bf3556ffa4ef4f6dab7f731c0a48421683708364efd2c` |
| `remoteAcpContractDigest` | `86668a0a013ca3aef08f11611c6c32cb7643918caf21f5d530049b0d0a1a28be` |
| `runtimeContractDigest` | `0c796f63391a5585f7a57318d7b202eb57a65039ee27555adabefce53287e17a` |
| Transport | `nodeskclaw.remote-acp.v1` |
| Public Base | 部署环境 Backend 公网根（例 staging：`http://192.168.50.247:4510`） |
| Auth | 已登录用户 JWT；禁止 adapter 登录 / OS keyring 另存 Agent token |
| Provider G3 SHA | `3205fdcac003fc91d5a04349c2813b815bc0342b` |

**Gate 规则（MUST）**

```text
GET /api/v1/remote-experts/contracts
  .frontendContractVersion  == pinned 2.1.0
  .frontendContractDigest   == pinned aggregate
  .catalogContractDigest    == pinned catalog
  .remoteAcpContractDigest  == pinned remote-acp
→ 全部相等才允许创建 WebSocket
→ 任一不等 → REMOTE_EXPERT_PROVIDER_INCOMPATIBLE，UI 阻断，零 WS
```

`runtimeContractDigest` 供观测/排障展示；**不得**单独因 runtime digest 差异绕过 aggregate/catalog/remote-acp 闸门（与 Provider discovery 字段并存时，以 handoff JSON `pinRules` 为准）。

---

## 4. 目标拓扑

```text
SMC Renderer (Original Chat / Compose / MessageList)
        │ IPC（投影 only）
        ▼
SMC Electron Main
  ├─ ContractGate          GET .../remote-experts/contracts  vs pin 2.1.0
  ├─ ExpertCatalogClient   GET .../remote-experts
  └─ RemoteAcpClient       WSS  .../remote-experts/{agent_ref}/acp
        │ Bearer JWT
        ▼
Backend Public Ingress
        ▼
Agent ACP Runtime Gateway  ← Run / Session / Event SoT
        ▼
Hermes Native Runtime
```

**Ownership**

| Concern | Owner |
|---|---|
| Contract pin / Gate | SMC Electron Main |
| WS / ACP session / prompt / cancel / permission reply | SMC Electron Main |
| Run / Session / Event SoT | Agent（禁止 SMC 伪造 terminal） |
| Transcript / bubble / approval UI | SMC Renderer（投影） |
| Local Hermes Chat | SMC 现有本地路径（与 Remote 失败域隔离） |

---

## 5. 前端表现变化

本仓 `nodeskclaw-portal` / Admin：**本次改动无前端表现变化**。

产品可见变化在仓外 **DeskClaw 团队版 / SMC Copilot Original Chat**。

### 5.1 Compose — Remote Expert 连接闸门

**总结**: 选 Remote Expert 从「拉起本地 ACP / 不可用」改为「先对 v2.1 契约，再连 Backend WSS」。

**元素级变化**:
- Remote Expert 选择器：契约不匹配或 discovery 失败时 → **不可连接**（disabled 或拦截）
- 错误文案：**新增**「Provider 契约不兼容（期望 2.1.0），无法开始会话」；可操作指引：检查登录 / 网络 / 联系管理员升级 Provider
- 连接中：**新增**「正在连接远程专家」loading
- **删除**：「找不到 nodeskclaw-acp.exe / 正在启动本地适配器」类提示
- 无专家 / `unavailable`：空状态说明原因与下一步（联系管理员发布/拉起实例）

**改动前**:
```
┌─ Original Chat Compose ─────────────────────┐
│ [Remote Expert ▾]  marketing                │
│ 正在启动 nodeskclaw-acp.exe …               │
└─────────────────────────────────────────────┘
```

**改动后**:
```
┌─ Original Chat Compose ─────────────────────┐
│ [Remote Expert ▾]  marketing                │
│ 正在连接远程专家…（WSS Backend）              │
│ 契约不匹配时：                                │
│ ┌─────────────────────────────────────────┐ │
│ │ Provider 契约不兼容（期望 2.1.0）        │ │
│ │ 未建立 WebSocket；本地对话仍可用         │ │
│ └─────────────────────────────────────────┘ │
└─────────────────────────────────────────────┘
```

### 5.2 消息流 — Assistant 合并与工具卡片

**总结**: 同一 turn 多段 assistant 增量从「多气泡碎裂」改为「单气泡流式合并」；工具从「仅工具名」改为「可展开参数/结果摘要」。

**元素级变化**:
- Assistant 气泡：同一 `turn_id` / session update 序列 → **合并为一条**流式正文（禁止每条 delta 新开气泡）
- 工具卡片：**新增**可展开区显示 `arguments` 摘要与 `result` 摘要（当 Provider 提供 rich 字段时）
- Hermes 仅 `preview` 时：展示 preview 文本，**不得**伪造完整 args/result
- `toolCallId` 稳定：同一工具调用更新 → **原地刷新**卡片，不重复插入

**改动后**:
```
┌─ 消息列表 ──────────────────────────────────┐
│ 专家                                          │
│ ┌─ assistant ─────────────────────────────┐ │
│ │ （流式合并正文…）                         │ │
│ └─────────────────────────────────────────┘ │
│ ┌─ tool: xxx ─────────────────────────────┐ │
│ │ ▸ 参数摘要 / 结果摘要（可展开）            │ │
│ └─────────────────────────────────────────┘ │
└─────────────────────────────────────────────┘
```

### 5.3 Continuity / Terminal 错误态

**总结**: 会话连续性失败与终态从「卡住或静默」改为「明确错误条 + 可操作下一步」；本地输入框保持可用。

**元素级变化**:
- `ACP_RUNTIME_SESSION_BINDING_MISSING` / `ACP_RUNTIME_SESSION_CONTINUITY_LOST`：消息区 **新增**错误条；文案说明会话无法继续，引导「新开会话」或联系管理员；**禁止**静默重试伪造成功
- Failed run：按 JSON-RPC error 展示（`ACP_REMOTE_RUN_FAILED` 等），**禁止**当成成功 `stopReason`
- Terminal（`cancelled` / `failed` / `completed`）：气泡状态与 Provider terminal 对齐；SMC **不得**用本地超时单独把 run 标成功
- 审批条：复用允许一次 / 拒绝；禁止对用户暴露 session/always
- Local Chat：Remote 失败后输入框与发送 **保持可用**

**改动后**:
```
┌─ 消息列表 ──────────────────────────────────┐
│ ┌─ 错误 ──────────────────────────────────┐ │
│ │ 会话连续性已丢失                         │ │
│ │ （ACP_RUNTIME_SESSION_CONTINUITY_LOST）  │ │
│ │ [新开会话]                               │ │
│ └─────────────────────────────────────────┘ │
│ [附件] [发送]  ← 本地 Hermes 仍可用          │
└─────────────────────────────────────────────┘
```

---

## 6. 需求（Normative）

### REQ-SMC-2101 — Contract Gate Pin 2.1.0

- MUST 在 Electron Main 实现 ContractGate。
- MUST 首连前比对 §3 全部 pin 字段。
- MUST mismatch → `REMOTE_EXPERT_PROVIDER_INCOMPATIBLE`，零 WS、零 prompt。
- MUST NOT 用旧 pin `2.0.0` 或跳过 Gate「先连再说」。

**Acceptance:** A-SMC-2101

### REQ-SMC-2102 — RemoteAcpClient（Backend WSS Only）

- MUST 仅连接 `WSS /api/v1/remote-experts/{agent_ref}/acp`。
- MUST 使用用户 JWT；MUST NOT 持久化 Agent internal URL/token/capability。
- MUST 支持 `session/new`、`session/prompt`、`session/cancel`、`session/request_permission` 回复、`session/close`（字段以 remote-acp contract 为准）。
- MUST NOT spawn `nodeskclaw-acp.exe`、stdio、adapter keyring。
- MUST NOT 直连 Agent / Hermes / Remote Agent REST 聊天。

**Acceptance:** A-SMC-2102、A-MIG-2101

### REQ-SMC-2103 — Original Chat Projection（v2.1 语义）

- MUST 复用 Original Chat / ChatInput / Compose / MessageList。
- MUST 投影：streaming text、reasoning（若有）、tool、clarify、approval、artifact、resume。
- MUST assistant delta + matching snapshot 做 **对账合并**，禁止二次追加（`ACP_STREAM_RECONCILIATION_MISMATCH` 可见失败）。
- MUST 投影 rich tool 安全字段：`rawInput` / `content` / `structuredContent` / `errorCode` / `errorMessage` / `redacted` / `truncated`；缺失时降级 preview，禁止编造。
- MUST tool status `started` → UI `in_progress`；`pending` 禁止作为合法展示态。
- MUST 遵守 turn-scoped seq：乱序/缺口按 contract fail-closed（禁止吞掉导致假成功）。
- MUST NOT 新建第二套 Remote Expert Chat page/store lifecycle。

**Acceptance:** A-SMC-2103、A-SMC-2104、A-SMC-2105

### REQ-SMC-2104 — Continuity & Terminal Fail-Closed

- MUST 遵守 handoff continuity：同 Formal Session 复用已绑定 Hermes runtime session；never-bound 允许首 turn 重试；once-bound-then-missing → `ACP_RUNTIME_SESSION_CONTINUITY_LOST`。
- MUST 将 `ACP_RUNTIME_SESSION_BINDING_MISSING` / `ACP_RUNTIME_SESSION_CONTINUITY_LOST` / `ACP_REMOTE_RUN_FAILED` / `ACP_STREAM_RECONCILIATION_MISMATCH` 映射为用户可见错误。
- MUST 将 failed run 按 JSON-RPC error 处理，不得解释为成功 `stopReason`。
- MUST `clarify.requested` 仅作为唯一 `end_turn` 语义消费（与 Provider 一致）。
- MUST NOT 在连续性失败后静默 `session/prompt` 重试并当作成功。
- MUST NOT 由 Renderer 本地推断覆盖 Agent terminal。
- MUST Remote 失败不影响 Local Hermes 发送。
- MUST 新 Prompt（terminal 之后）使用 `after_seq=0`；dedupe key 为 `(turn identity, seq)`。

**Acceptance:** A-SMC-2106、A-SMC-2107

### REQ-SMC-2105 — Legacy Adapter Retirement

- MUST 包内 0 个 `nodeskclaw-acp.exe`。
- MUST 代码路径无 `resolveAcpBinary` / spawn ACP / stdio bridge。
- MUST NOT fallback Skill Run / Work Expert / `expert.start` 作为 Remote Expert 聊天替代。

**Acceptance:** A-MIG-2101、A-MIG-2102

### REQ-SMC-2106 — Evidence & Gates

- MUST 产出 EXT-G5 可机读 evidence JSON（场景列表见 §8）。
- MUST NOT 将 `productionGate` 标 `passed`。
- MUST 在 EXT-G5 PASS 前禁止对外宣称 Desktop 生产可用。

**Acceptance:** A-G5-ALL

---

## 7. 错误码（Consumer 面）

| Code | 何时 | UI |
|---|---|---|
| `REMOTE_EXPERT_PROVIDER_INCOMPATIBLE` | pin ≠ discovery | 阻断连接，说明期望 2.1.0 |
| `REMOTE_EXPERT_CONNECTION_FAILED` | WSS/鉴权/网络失败 | 可操作：检查登录/网络 |
| `REMOTE_EXPERT_TURN_FAILED` | 单回合失败（Consumer 包装） | 错误条，可新开回合 |
| `REMOTE_EXPERT_SESSION_FAILED` | 会话级失败（Consumer 包装） | 错误条，引导新开会话 |
| `ACP_RUNTIME_SESSION_BINDING_MISSING` | 首 turn 缺 session 绑定 | 可见错误；never-bound 可按 handoff 重试一次，禁止假成功 |
| `ACP_RUNTIME_SESSION_CONTINUITY_LOST` | 曾绑定后丢失 | 可见错误；引导新开会话 |
| `ACP_REMOTE_RUN_FAILED` | Provider failed run（JSON-RPC） | 错误条，不得当成功 stop |
| `ACP_STREAM_RECONCILIATION_MISMATCH` | assistant/stream 对账失败 | 错误条，禁止双写正文 |

（Provider 原始 code MUST 可观测；Consumer 包装不得掩盖；**禁止**映射成成功态。）

---

## 8. EXT-G5 Golden Acceptance

对齐 Provider PRD v2.1 §25–26 / handoff `goldenConsumerCriteria`。  
全部场景 MUST 有：自动化或半自动脚本 + 可机读 oracle JSON + commit SHA。

| ID | 场景 | 通过条件（摘要） |
|---|---|---|
| A-SMC-2101 | Contract mismatch | 故意改 pin 或 mock discovery → 零 WS |
| A-SMC-2102 | Happy connect | discovery 对齐 → WSS 建立 → `session/new` 成功 |
| A-SMC-2103 | Assistant merge | 多段 assistant update → UI 单气泡合并，无碎裂 |
| A-SMC-2104 | Rich tools | 有 preview/args 时卡片可展开；无 rich 时不伪造 |
| A-SMC-2105 | Seq integrity | 模拟乱序/缺口 → 不出现假完成 transcript |
| A-SMC-2106 | Continuity fail-closed | `ACP_RUNTIME_SESSION_BINDING_MISSING` / `ACP_RUNTIME_SESSION_CONTINUITY_LOST` 可见错误，无静默成功 |
| A-SMC-2107 | Local isolation | Remote 失败后 Local Hermes 仍可发送成功 |
| A-MIG-2101 | No ACP exe | 发行包 / 开发启动路径 0 exe、无 spawn |
| A-MIG-2102 | No illegal fallback | 断 Remote 时不自动改走 Skill Run / REST chat |
| A-G5-ALL | Bundle | 以上全部 PASS；`productionGate=unpassed` |

**证据落盘建议**

- SMC 仓：`docs/evidence/remote-acp-v2.1/A-SMC-*.json`（路径以 SMC 仓规范为准）
- 本仓可选指针：`docs_agent/evidence/remote-acp-v2.1/ext-g5/` 仅放摘要 + SMC commit SHA（无密钥）

---

## 9. Consumer 工程闸门（执行顺序）

| Gate | 名称 | 退出条件 | 状态 |
|---|---|---|---|
| CG0 | Baseline | 检出 `smc-copilot`；无秘密入 git | **PASS** |
| CG1 | Pin & Gate | ContractGate + A-SMC-2101 | **PASS**（G6 evidence） |
| CG2 | WSS Client | RemoteAcpClient + A-SMC-2102；无 exe | **PASS**（含 A-MIG-2101） |
| CG3 | Chat Projection | A-SMC-2103 / 2104 / 2105 | **PASS** |
| CG4 | Continuity UI | A-SMC-2106 + Local 隔离 | **PASS**（2106 + Local Chat / A-ROUTE-LOCAL / A-SMC-004） |
| CG5 | Golden Close | A-MIG-* + A-G5-ALL；本仓 handoff 指针 | **PASS**（`ext-g5/G6-SUMMARY.json`） |

SMC 证据：`apps/work/scripts/remote-expert-g6.mjs` → `test-results/remote-expert-g6.json` @ `1d0eb5b2`。  
live 脚本 `g7-golden-consumer.live.test.ts` 命名 G7 ≠ 本仓 / 产品生产门禁。

**禁止生产宣称**：即便 CG5 PASS，`productionGate` 仍为 `unpassed`；Roadmap / Release Note / 群公告不得写「Desktop Remote Expert 生产可用」，除非独立生产门禁 PRD/Plan PASS。

---

## 10. 与既有 v2.0 Consumer 计划的关系

| 项 | 处理 |
|---|---|
| `.cursor/plans/smc_acp_consumer_v2_g5g6_8f2c1a90.plan.md` | 视为 **superseded by pin**：实现目标改为本 PRD；勿再提交 2.0.0 pin |
| v2.0 REQ-SMC-001/002 / REQ-MIG-001 | 拓扑与拆除原则 **继承**；语义保真增量以本 PRD REQ-SMC-210x 为准 |
| Provider v2.0 aggregate digest | **废弃作为 Consumer pin**；唯一 pin 为 §3 |

---

## 11. 执行清单（SMC 仓，符号需实查）

执行前在 `smc-copilot` 用搜索定位，禁止假设路径：

1. `resolveAcpBinary` / `AcpBinaryResolver` / `nodeskclaw-acp` → 删除或永久禁用
2. Original Chat / ChatInput / Compose / permission UI → 接线 RemoteAcpClient 事件
3. 现有 Remote Expert catalog HTTP（若 v1.6.1 已接）→ 保留 catalog，聊天改 WSS
4. 新增：`RemoteExpertContractGate`、`RemoteAcpClient`、v2.1 pin 常量模块
5. i18n：契约不兼容 / 连接中 / continuity 错误 / 新开会话（禁止硬编码散落中文，按 SMC 仓 i18n 规范）

Implementation commit 仅在 **smc-copilot**；本仓只更新证据指针与（若需要）计划元数据。

---

## 12. 安全与合规

- 禁止把 JWT、DSN、Agent token 写入 evidence 或 commit
- 禁止 Renderer 持有 Agent capability / internal URL
- 附件继续走 Backend `attachment_prepare` + `resource_link`；非法 URI 拒绝并提示，不静默吞掉
- 产物下载走 Backend artifact URL，不直连 Agent 文件系统

---

## 13. 开放问题（Grilling 前默认值）

| # | 问题 | 默认（可在 APPROVED 前改） |
|---|---|---|
| Q1 | SMC 工作分支是否仍 `work/prd-v6.3`？ | 以仓库默认开发分支为准，PRD 不锁死分支名 |
| Q2 | EXT-G5 是否必须全自动 E2E？ | 允许半自动 + 可机读 oracle；但 A-SMC-2101/2102/2106 优先自动化 |
| Q3 | CG5 PASS 后是否立刻开生产门禁 G7？ | **否**；另开生产门禁 PRD/Plan |
| Q4 | 是否兼容短暂双 pin（2.0+2.1）？ | **否**；唯一 pin 2.1.0 |

---

## 14. 状态机（Consumer）

```text
IDLE
  → CONTRACT_CHECK   (GET contracts)
      → BLOCKED      (mismatch / network) [终态 until user retry]
      → READY_TO_CONNECT
          → CONNECTING (WSS)
              → SESSION_READY
                  → TURN_ACTIVE (prompt / stream / tools / approval)
                      → TURN_TERMINAL (completed|failed|cancelled)
                  → SESSION_FAILED (ACP_RUNTIME_SESSION_BINDING_MISSING|ACP_RUNTIME_SESSION_CONTINUITY_LOST|…)
              → CONNECTION_FAILED
```

Invariant：`BLOCKED` / `SESSION_FAILED` / `CONNECTION_FAILED` **不得**自动降级到本地 ACP exe 或 REST chat。

---

## 15. 批准门槛

本 PRD 从 `PROPOSED` → `APPROVED` 前必须确认：

1. Provider 仍为 FROZEN `2.1.0` 且目标环境 discovery 与 §3 一致  
2. 产品确认「唯一 pin 2.1.0、不做双 pin」  
3. SMC 工程确认执行仓与 Original Chat 复用边界  
4. 明确 CG5 ≠ 生产门禁  

批准后另写 **implementation plan**（`commit_policy: post_review`），在 `smc-copilot` 执行 CG0→CG5。

---

## 16. 修订记录

| Date | Change |
|---|---|
| 2026-10-07 | 初稿 PROPOSED：Provider G4+FROZEN 后，定义 SMC EXT-G5 推进路径与 v2.1 pin |
| 2026-10-07 | 核实 `smc-copilot@e68554a8` pin cutover；digest 对齐 handoff；状态 → `IN_PROGRESS`；主路径改为 CG5 Golden evidence |
| 2026-10-07 | 核实 G6 evidence `overall=PASS` @ `1d0eb5b2`（`productionGate=unpassed`）；状态 → `EXT-G5_PASS`；落盘 `ext-g5/G6-SUMMARY.json` |
| 2026-10-07 | 下一步指向独立生产门禁 PRD `PRD-NODESKCLAW-Remote-ACP-Desktop-Production-Gate-v2.1.md` |
