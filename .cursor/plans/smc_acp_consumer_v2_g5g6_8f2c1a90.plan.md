---
name: SMC ACP Consumer v2
overview: G5 将 SMC Consumer 从 blocked 转为 planned；G6 在 loudon84/smc-copilot@work/prd-v6.3 落地 RemoteAcpClient、契约发现闸门、拆除本地 ACP exe，并复用 Original Chat。G7 金标不在本计划。
commit_policy: post_review
prd: docs_agent/PRD-NODESKCLAW-Remote-ACP-Provider-and-SMC-Copilot-Consumer-v2.0.md
provider_contract: contracts/remote-expert-frontend/v2.0.0
provider_status: FROZEN
frontendContractGate: passed
productionGate: unpassed
consumer_repo: loudon84/smc-copilot
consumer_path: apps/work
consumer_branch_baseline: work/prd-v6.3
gate: G6
todos:
  - id: g5-unblock
    content: "G5：确认 v2 FROZEN + G4 PASS，Provider 计划 smc-consumer 转为 planned，本计划进入执行"
    status: pending
  - id: pin-discovery-gate
    content: "Electron Main：ContractGate 比对 GET /api/v1/remote-experts/contracts 与冻结 pin；mismatch 拦截 WS（A-SMC-001）"
    status: pending
  - id: remote-acp-client
    content: "Electron Main：RemoteAcpClient 只连 Backend WSS nodeskclaw.remote-acp.v1（A-SMC-002）"
    status: pending
  - id: original-chat-wire
    content: "Renderer：复用 Original Chat/Compose 渲染 stream/tool/approval/artifact/resume（A-SMC-003）"
    status: pending
  - id: retire-local-adapter
    content: "拆除 resolveAcpBinary / spawn / stdio / keyring；包内 0 个 nodeskclaw-acp.exe（A-MIG-001/002）"
    status: pending
  - id: local-chat-isolation
    content: "Remote 失败后 Local Hermes 仍可发消息（A-SMC-004）"
    status: pending
  - id: g6-evidence
    content: "G6 evidence JSON（A-MIG-001/002、A-SMC-001..004）；productionGate 保持 unpassed"
    status: pending
isProject: false
---

# SMC ACP Consumer v2（G5/G6）

I'm using the writing-plans skill to create the implementation plan.

**Goal:** 让 SMC Copilot 作为冻结 REMOTE-EXPERT-FRONTEND-CONTRACT v2.0.0 的消费者，经 Backend 公网 WSS 使用 Remote Expert，不再依赖 `nodeskclaw-acp.exe`。

**Architecture:** Electron Main 持有 ContractGate + RemoteAcpClient；Renderer 只投影 Original Chat。Run SOT 仍在 NodeSkClaw Agent。本计划代码改 `loudon84/smc-copilot`，本仓只放计划与 G6 evidence 指针。G7 金标另起。

**Tech Stack:** Electron Main + 现有 SMC Original Chat；Public `GET /remote-experts`、`GET /remote-experts/contracts`、WSS `/api/v1/remote-experts/{agent_ref}/acp`。

**Spec:** [docs_agent/PRD-NODESKCLAW-Remote-ACP-Provider-and-SMC-Copilot-Consumer-v2.0.md](docs_agent/PRD-NODESKCLAW-Remote-ACP-Provider-and-SMC-Copilot-Consumer-v2.0.md) P4 / REQ-MIG-001 / REQ-SMC-001 / REQ-SMC-002 / G5 / G6。

## Global Constraints

- Provider 已 FROZEN：`contracts/remote-expert-frontend/v2.0.0`，`frontendContractGate=passed`，`productionGate=unpassed`。
- Consumer pin：catalog `d51d27a33e6776be780bf3556ffa4ef4f6dab7f731c0a48421683708364efd2c`，remote-acp `8a48e74e363c71875739c33b2bcdcb6f6f2ea7ee15897ae9fb9b8e9407ee9d06`，transport `nodeskclaw.remote-acp.v1`。
- 聚合 digest 以 Backend `GET /api/v1/remote-experts/contracts` 的 `frontendContractDigest` 为准（当前常量 `22ad68dd1132a073f6df5d2bf9f219b683c73ebb7ea1fa48933c9b92a744ecd5`）。
- 用户 JWT 已登录 Backend；禁止 adapter 登录 / OS keyring。
- 禁止：spawn 本地 ACP、直连 Agent/Hermes、Remote Agent REST 当聊天通道、Skill Run / Work Expert fallback、公开 `runtime_run_id`、改 v1 历史契约树、把 `production_gate` 标 passed。
- 本计划 implementation commit 在 **smc-copilot**；本仓禁止把 Consumer 代码写进 portal。
- `commit_policy: post_review`；Todo 完成不得立刻 commit。

## 前端表现变化

本仓 `nodeskclaw-portal` / Admin：**本次改动无前端表现变化**。

产品可见变化在仓外 **DeskClaw 团队版 / SMC Copilot Original Chat**。

### 1. Compose 选择 Remote Expert

**总结**: 选 Remote Expert 从「拉起本地 ACP 进程或不可用」改为「先对契约，再连 Backend WSS」。

**元素级变化**:
- Remote Expert 选择器：契约不匹配或 discovery 失败时 -> **不可连接**（disabled 或拦截），文案说明「Provider 契约不兼容，无法开始会话」
- 不再出现「找不到 nodeskclaw-acp.exe / 正在启动本地适配器」类提示
- 连接中：新增「正在连接远程专家」loading；失败 toast 可操作（检查登录/网络/联系管理员）
- 无专家 / 专家 `unavailable`：空状态说明「没有可调用的远程专家」或「专家运行时未就绪」，引导联系管理员发布/拉起实例

**改动前**:
```
┌─ Original Chat Compose ─────────────────────┐
│ [Remote Expert ▾]  marketing                │
│ 正在启动 nodeskclaw-acp.exe …               │
│ 或：适配器缺失，无法对话                     │
└─────────────────────────────────────────────┘
```

**改动后**:
```
┌─ Original Chat Compose ─────────────────────┐
│ [Remote Expert ▾]  marketing                │
│ 正在连接远程专家…  （WSS Backend）          │
│ 契约不匹配时：                              │
│ ┌───────────────────────────────────────┐ │
│ │ Provider 契约不兼容，无法开始会话      │ │
│ │ 未建立 WebSocket，本地对话仍可用       │ │
│ └───────────────────────────────────────┘ │
└─────────────────────────────────────────────┘
```

### 2. 远程回合渲染

**总结**: 远程回合从适配器 stdio 事件改为同一套 Chat 气泡消费 ACP session/update。

**元素级变化**:
- 流式正文 / 推理 / 工具调用：沿用现有气泡，数据源改为 RemoteAcpClient
- 审批条：ACP `session/request_permission` 时 **新增/复用** 允许一次 / 拒绝；禁止 session/always 对用户暴露
- 附件：继续 attachment_prepare，发出 `resource_link`；非法 URI 展示资源被拒绝，不静默吞掉
- 产物：消息内 ResourceLink / 下载入口，指向 `/api/v1/remote-experts/{agent_ref}/acp/runs/.../artifacts/...`
- Local Chat：远程失败后输入框与发送 **保持可用**，本地 Hermes 回合成功

**改动后（审批）**:
```
┌─ 消息列表 ──────────────────────────────────┐
│ 专家：…工具调用…                            │
│ ┌─ 需要批准 ─────────────────────────────┐ │
│ │ [允许一次]  [拒绝]                     │ │
│ └────────────────────────────────────────┘ │
│ [附件] [发送]                               │
└─────────────────────────────────────────────┘
```

## 执行仓与入口

在 **smc-copilot** 检出 `work/prd-v6.3`（或其后继）后执行本计划。本工作区没有 `smc-copilot` 源码；执行前用仓库搜索定位等价符号，禁止假设路径：

- `resolveAcpBinary` / `AcpBinaryResolver` / `nodeskclaw-acp`
- Original Chat / ChatInput / Compose / permission UI
- 现有 Remote Expert catalog HTTP 客户端（若 v1.6.1 已接 `GET /remote-experts`）

## 目标拓扑

```text
SMC Renderer (Original Chat)
  -> IPC
SMC Electron Main
  -> GET /api/v1/remote-experts/contracts   (pin vs discovery)
  -> GET /api/v1/remote-experts
  -> WSS /api/v1/remote-experts/{agent_ref}/acp
Backend Public Ingress
  -> Agent ACP Runtime Gateway
  -> Hermes Native
```

## Todo 规格

```yaml
- id: g5-unblock
  requirement_refs: [G5]
  acceptance_refs: []
  files_or_symbols:
    - .cursor/plans/remote_acp_provider_v2_7b34c674.plan.md（smc_consumer_plan.status=planned）
    - .cursor/plans/smc_acp_consumer_v2_g5g6_8f2c1a90.plan.md
  implementation_goal: G5 关闭；Consumer 计划可执行
  preconditions: [G4 PASS, v2 FROZEN, frontendContractGate=passed]
  state_transition: smc-consumer blocked -> planned
  side_effect_scope: 本仓计划元数据
  failure_cases: [v2 未冻结仍开 Consumer 编码]
  verification: manifest status=FROZEN 且本计划存在
  status: pending
  evidence: contracts/remote-expert-frontend/v2.0.0/manifest.json

- id: pin-discovery-gate
  requirement_refs: [REQ-SMC-001]
  acceptance_refs: [A-SMC-001]
  files_or_symbols:
    - smc-copilot Electron Main RemoteExpertContractGate
    - contracts/remote-expert-frontend/v2.0.0/consumer/smc-copilot-v6.3.json
  implementation_goal: 首连前比对 frontendContractVersion/Digest 与 catalog/remoteAcp digest；失败 REMOTE_EXPERT_PROVIDER_INCOMPATIBLE，零 WS、零 session/prompt
  preconditions: [g5-unblock]
  state_transition: IDLE -> CONTRACT_CHECK -> READY|BLOCKED
  side_effect_scope: 只读 discovery
  failure_cases: [mismatch 仍连接]
  verification: 单元测试 pin≠discovery 时无 WebSocket
  status: pending
  evidence: docs_agent/evidence/remote-acp-v2/A-SMC-001.json

- id: remote-acp-client
  requirement_refs: [REQ-SMC-001]
  acceptance_refs: [A-SMC-002]
  files_or_symbols:
    - smc-copilot Electron Main RemoteAcpClient
  implementation_goal: Bearer + X-Org-Id + subprotocol nodeskclaw.remote-acp.v1；initialize/session/new/resume/prompt/cancel/close/permission；不存 Agent URL/token/capability
  preconditions: [pin-discovery-gate]
  state_transition: CONNECTING -> READY
  side_effect_scope: Backend 公网
  failure_cases: [连 Agent/Hermes]
  verification: 连接目标集合仅为 Backend origin
  status: pending
  evidence: docs_agent/evidence/remote-acp-v2/A-SMC-002.json

- id: original-chat-wire
  requirement_refs: [REQ-SMC-002]
  acceptance_refs: [A-SMC-003]
  files_or_symbols:
    - smc-copilot Renderer Original Chat / Compose
  implementation_goal: 不新建第二套 Chat page/store；投影 streaming/tool/clarify/approval/artifact；attachment 走 ResourceLink；resume/close
  preconditions: [remote-acp-client]
  state_transition: queued -> streaming -> terminal/approval
  side_effect_scope: UI store + session_ref 持久化
  failure_cases: [第二套 Chat 生命周期]
  verification: 集成测试提交 prompt 走现有气泡
  status: pending
  evidence: docs_agent/evidence/remote-acp-v2/A-SMC-003.json

- id: retire-local-adapter
  requirement_refs: [REQ-MIG-001]
  acceptance_refs: [A-MIG-001, A-MIG-002]
  files_or_symbols:
    - resolveAcpBinary / AcpBinaryResolver / spawn / stdio / keyring
  implementation_goal: v2 生产路径零 ACP exe；扫描源码与 Windows 包
  preconditions: [remote-acp-client]
  state_transition: FROZEN_LEGACY -> NOT_REFERENCED_BY_V2
  side_effect_scope: SMC runtime dependency
  failure_cases: [ACP_BINARY_MISSING 仍作为主路径]
  verification: 禁止符号计数=0；包内 exe=0
  status: pending
  evidence: docs_agent/evidence/remote-acp-v2/A-MIG-001.json

- id: local-chat-isolation
  requirement_refs: [REQ-SMC-002]
  acceptance_refs: [A-SMC-004]
  files_or_symbols:
    - smc-copilot Local Hermes chat path
  implementation_goal: Remote 不可用时本地回合仍成功
  preconditions: [original-chat-wire]
  state_transition: remote fail -> local turn PASS
  side_effect_scope: 本地 runtime only
  failure_cases: [远程失败拖死本地输入]
  verification: 远程断开后本地 Hermes 有回复
  status: pending
  evidence: docs_agent/evidence/remote-acp-v2/A-SMC-004.json

- id: g6-evidence
  requirement_refs: [REQ-MIG-001, REQ-SMC-001, REQ-SMC-002]
  acceptance_refs: [A-MIG-001, A-MIG-002, A-SMC-001, A-SMC-002, A-SMC-003, A-SMC-004]
  files_or_symbols:
    - docs_agent/evidence/remote-acp-v2/
  implementation_goal: G6 PASS 证据；productionGate 仍 unpassed
  preconditions: [前序 Todo]
  state_transition: G6 PASS；G7 仍 blocked
  side_effect_scope: evidence
  failure_cases: [把 G6 当成 productionGate passed]
  verification: 六份 JSON + SMC 测试命令记录
  status: pending
  evidence: docs_agent/evidence/remote-acp-v2/
```

## 明确不做（G7）

真实 SMC → 生产 Backend → Agent → Hermes 金标（A-REL-002、A-OBS-001、A-SEC-003/004、production_gate=passed）另起计划。

## Review 清单（PRD §32 消费侧）

1. 拓扑是否 SMC → Backend WSS → Agent → Hermes。
2. 是否仍有 local adapter / exe。
3. pin 是否只含 Public catalog + remote-acp-gateway。
4. mismatch 是否在 session/prompt 前拦截。
5. Original Chat 是否复用而非第二套页面。
6. Local Chat 是否隔离。
