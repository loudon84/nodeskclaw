---
title: "PRD-NODESKCLAW-v1.6.1-Contract-Release-Closure"
prd_id: "PRD-NODESKCLAW-V1.6.1-CONTRACT-RELEASE-CLOSURE"
version: "1.6.1-closure"
status: "APPROVED_FOR_PLAN"
product: "NodeSkClaw / ACP Remote Expert / SMC Copilot Desktop"
repository: "https://github.com/loudon84/nodeskclaw"
branch: "main"
current_main_commit: "28e5d0e4fe421432c7a47dcd2a9d5307c9ad1d6b"
implementation_commit: "896450ad479033afc2428852a2d02f70f77ab19e"
previous_acp_baseline_commit: "557a3b0f17677db911a42b36f1ad16855ef93c2e"
consumer_repository: "https://github.com/loudon84/smc-copilot"
consumer_branch: "work/prd-v6.3"
consumer_baseline_reference: "be619f66aa8483e716d32b614860da9a45759e4e"
created_at: "2026-10-04"
target_release: "Remote Expert Frontend Contract v1.0.0"
target_tag: "remote-expert-frontend-contract-v1.0.0"
change_type:
  - "CONTRACT_RELEASE_CLOSURE"
  - "CROSS_REPOSITORY_HANDOFF"
  - "RELEASE_IDENTITY_FIX"
  - "CONTRACT_DIGEST_REFREEZE"
  - "RELEASE_GUARD"
provider_component_contracts:
  - "REMOTE-EXPERT-CATALOG-CONTRACT v1.0.0"
  - "ACP-V1-ADAPTER-CONTRACT v1.1.0"
dependency_contracts:
  - "REMOTE-AGENT-PROVIDER-CONTRACT v1.5.0"
  - "INTEGRATION-ACCOUNT-CONTRACT v1.1.0"
golden_consumer: "smc-copilot/apps/work@work/prd-v6.3"
---

# PRD-NODESKCLAW v1.6.1 Contract Release Closure

## 0. 文档定位

本 PRD 是 `ACP Desktop Consumer Closure v1.6.1` 的发布闭环 PRD。

本 PRD **不新增 Remote Expert 业务能力**。目标是把当前：

```text
Implementation Ready
+
Contract Candidate
```

推进为：

```text
Frontend Contract Ready
```

供：

```text
smc-copilot/apps/work
```

基于一个明确、不可变、可校验的 Contract 基线开始：

```text
Original Chat
+
Compose
+
ACP Remote Expert
```

---

## 0.1 当前事实基线

截至 2026-10-04：

```text
nodeskclaw main
=
28e5d0e4fe421432c7a47dcd2a9d5307c9ad1d6b

docs(acp):
纳入 ACP Desktop Consumer Closure PRD v1.6.1
```

实际 v1.6.1 功能实现提交：

```text
896450ad479033afc2428852a2d02f70f77ab19e

feat(acp):
落地 Desktop Catalog、Session Proof 与 ACP Adapter v1.1
```

前一个 ACP v1 基线：

```text
557a3b0f17677db911a42b36f1ad16855ef93c2e
```

因此冻结：

```text
IMPLEMENTATION_COMMIT
=
896450ad479033afc2428852a2d02f70f77ab19e
```

---

## 0.2 已实现且本 PRD 不重做的能力

以下能力已经属于 v1.6.1 Implementation：

```text
Remote Expert Catalog
expert:invoke employee access
ACP v1 initialize
session/new
session/resume
session/close
next_turn_seq recovery
Managed Credential mode
in-memory access/refresh token rotation
Attachment ResourceLink
Artifact ResourceLink
structured Permission presentation
SMC v6.3 Golden Consumer fixtures
Windows standalone build script
Desktop bundle verification script
ACP Adapter Contract v1.1.0 candidate
Remote Expert Catalog Contract v1.0.0 candidate
```

本 Closure MUST NOT 重新设计上述功能。

---

## 0.3 当前 Release 问题

### ISSUE-RC-001 — ACP Contract manifest 指向错误 Implementation SHA

当前：

```text
nodeskclaw-acp/contracts/acp-v1-adapter/v1.1.0/manifest.json
```

仍声明：

```text
implementationHeadSha = 557a3b0f...
releaseCommitSha      = 557a3b0f...
```

但 `557a3b0f...` 只包含 ACP v1 基线，不包含 v1.6.1 Desktop Consumer Closure。

真正 Implementation：

```text
896450ad...
```

因此当前 manifest Release Identity 不可作为 Frontend Freeze 依据。

### ISSUE-RC-002 — Remote Expert Catalog manifest 同样指向旧 SHA

当前：

```text
nodeskclaw-backend/contracts/remote-expert-catalog/v1.0.0/manifest.json
```

同样声明：

```text
implementationHeadSha = 557a3b0f...
releaseCommitSha      = 557a3b0f...
```

而 Catalog 本身是在 `896450ad...` 实现。

### ISSUE-RC-003 — 修改 manifest 会导致 Final Consumer Digest 改变

Consumer Pin 采用：

```text
sha256(raw SHA256SUMS bytes)
```

而不是：

```text
contract version only
Git tag only
manifest.bundleDigest only
```

因此：

```text
manifest changes
→ hash(manifest.json) changes
→ SHA256SUMS changes
→ sha256(SHA256SUMS) changes
→ runtime constants / aggregate manifest pin changes
```

当前候选 digest：

```text
ACP candidate consumer digest
=
b4de0c63a370810403e18438618430ba8cac9bd790747d567937585812f13f8a

Catalog candidate consumer digest
=
cd38f8fbed0b41632fb0e7bbb7d6218ce6330d2cb2797555e9e6e62e14c38dba
```

只能视为：

```text
PRE-CLOSURE CANDIDATE
```

MUST NOT 成为最终 SMC Pin。

### ISSUE-RC-004 — 缺跨模块 Frontend Aggregate Contract

SMC 实际消费：

```text
Remote Expert Catalog
+
ACP Adapter
+
Remote Agent dependency
```

因此需要：

```text
REMOTE-EXPERT-FRONTEND-CONTRACT
```

作为 cross-repository handoff SOT。

### ISSUE-RC-005 — 缺前端冻结 Tag

Component Contracts 继续采用 digest pin，不要求各自创建 Git tag。

但由于本轮需要给 `smc-copilot` 一个稳定跨仓入口，本 PRD 新增一个前端聚合 Contract Tag：

```text
remote-expert-frontend-contract-v1.0.0
```

### ISSUE-RC-006 — Release Guard 不足

现有 Contract tests 尚未强制验证：

```text
implementationHeadSha == frozen implementation commit
releaseCommitSha == frozen implementation commit
runtime constant digest == sha256(SHA256SUMS)
aggregate component digest == real component consumer digest
tag target contains exact aggregate contract
```

因此 stale release identity 可以进入 main。

### ISSUE-RC-007 — Production Gate 尚未通过

当前：

```text
production_gate = unpassed
```

本 PRD 必须区分：

```text
Frontend Contract Ready
!=
Production Ready
```

Production LIVE 不属于本 Release Closure 的 blocking scope。

---

## 0.4 核心结论

本阶段：

```text
MUST freeze frontend contract
MUST fix release identity
MUST regenerate final digest
MUST add release guard
MUST produce immutable frontend contract tag
```

但：

```text
MUST NOT claim production ready
MUST NOT mark production_gate=passed
MUST NOT fabricate LIVE evidence
MUST NOT rewrite runtime behavior merely to create a release
```

---

## 0.5 No-Inference Rule

以下语义必须唯一：

```text
implementation commit
component consumer digest algorithm
aggregate contract identity
aggregate tag name
tag target
component tag policy
production gate meaning
release evidence format
```

如果 Plan / Coding Agent 无法从本 PRD 唯一得到答案：

```text
SPEC_SEMANTIC_GAP
```

必须阻塞对应 Todo。

---

# 1. 一句话目标

将已完成的 v1.6.1 Remote Expert Desktop Consumer 实现冻结为一个可由 `smc-copilot/apps/work` 安全消费的不可变 Frontend Contract Release：修正两个组件 Contract 的 implementation identity、重新生成并固定最终 SHA256SUMS consumer digest、增加 release guards、创建 `REMOTE-EXPERT-FRONTEND-CONTRACT v1.0.0` 聚合 Bundle，并准备 annotated tag `remote-expert-frontend-contract-v1.0.0`。

---

# 2. WHY

当前功能代码已经可以支持 SMC：

```text
Original Chat / Compose
→ ACP
→ Remote Expert
```

但跨仓工程不能以：

```text
main
latest
folder version only
candidate digest
```

作为长期依赖。

必须形成：

```text
immutable component digest
+
aggregate frontend contract
+
immutable Git tag
```

使 SMC 能明确回答：

```text
我消费的是哪个 Provider Contract？
对应哪个 Implementation？
组件 digest 是什么？
该 Tag 是否会漂移？
是否误宣称 Production Ready？
```

---

# 3. WHAT

本 PRD 交付：

```text
1. 修正 ACP v1.1.0 manifest Release Identity
2. 修正 Catalog v1.0.0 manifest Release Identity
3. 重算两套 Component SHA256SUMS
4. 生成两套 Final Consumer Digest
5. 更新 ACP runtime final pin constants
6. 增加 Component Release Guard
7. 新建 Remote Expert Frontend Aggregate Contract v1.0.0
8. 新建 Aggregate SHA256SUMS / manifest / RELEASE
9. 增加 Aggregate Contract tests
10. 形成 Release Evidence
11. 准备 annotated frontend contract tag
12. 明确 Production Gate 继续 unpassed
```

---

# 4. BOUNDARY

## 4.1 In Scope

```text
RC-SCOPE-001 ACP manifest release identity
RC-SCOPE-002 Catalog manifest release identity
RC-SCOPE-003 Component checksum regeneration
RC-SCOPE-004 Final consumer digest freeze
RC-SCOPE-005 Runtime digest constant update
RC-SCOPE-006 Contract integrity guards
RC-SCOPE-007 Frontend aggregate contract
RC-SCOPE-008 Aggregate contract checksum
RC-SCOPE-009 Aggregate consumer fixture reference
RC-SCOPE-010 Contract release evidence
RC-SCOPE-011 Annotated frontend contract tag specification
RC-SCOPE-012 SMC consumer handoff instruction
```

## 4.2 Out of Scope

```text
NON-GOAL-001 new Remote Expert feature
NON-GOAL-002 ACP v2
NON-GOAL-003 Work Expert changes
NON-GOAL-004 Skill Run changes
NON-GOAL-005 smc-copilot UI implementation
NON-GOAL-006 Windows clean-machine LIVE
NON-GOAL-007 Zed LIVE
NON-GOAL-008 production_gate=passed
NON-GOAL-009 provider-native triggers
NON-GOAL-010 Persistent Workspace
NON-GOAL-011 Multi-Agent
NON-GOAL-012 Remote Agent v1.5 wire change
NON-GOAL-013 Integration Account v1.1 wire change
NON-GOAL-014 component-specific ACP tag
NON-GOAL-015 component-specific Catalog tag
```

---

# 5. SOT

Release SOT：

```text
Implementation SOT
=
commit 896450ad479033afc2428852a2d02f70f77ab19e
```

Component Contract SOT：

```text
nodeskclaw-acp/contracts/acp-v1-adapter/v1.1.0/

nodeskclaw-backend/contracts/remote-expert-catalog/v1.0.0/
```

Frontend Aggregate SOT：

```text
contracts/remote-expert-frontend/v1.0.0/
```

Cross-repo immutable reference：

```text
remote-expert-frontend-contract-v1.0.0
```

---

# 6. Release Identity Semantics

## 6.1 implementationHeadSha

两套 Component manifest 的：

```text
implementationHeadSha
```

MUST 等于：

```text
896450ad479033afc2428852a2d02f70f77ab19e
```

定义：

> 实现该 Contract wire semantics 的实际 Provider implementation commit。

## 6.2 releaseCommitSha

本 Release Closure 将：

```text
releaseCommitSha
```

同样冻结为：

```text
896450ad479033afc2428852a2d02f70f77ab19e
```

定义：

> 被本 Contract Bundle 封印的实现基线。

它不是：

```text
tag object sha
closure commit sha
current main sha
```

这样避免 manifest 自引用 Git commit SHA。

## 6.3 Tag Target

Annotated Tag：

```text
remote-expert-frontend-contract-v1.0.0
```

MUST 指向：

```text
Contract Release Closure commit
```

该 commit 必须包含：

```text
final component manifests
final component SHA256SUMS
final runtime digest constants
aggregate frontend contract
aggregate SHA256SUMS
release guards
release evidence
```

---

# 7. Component Contract Policy

组件：

```text
ACP-V1-ADAPTER-CONTRACT v1.1.0
REMOTE-EXPERT-CATALOG-CONTRACT v1.0.0
```

继续采用：

```text
consumer pin = sha256(raw SHA256SUMS bytes)
```

MUST NOT 改为：

```text
version-only pin
branch pin
component Git tag pin
manifest.bundleDigest pin
```

---

# 8. Digest Terminology

## 8.1 artifact checksum

```text
sha256(file bytes)
```

写入：

```text
SHA256SUMS
```

## 8.2 component consumer digest

```text
sha256(raw SHA256SUMS file bytes)
```

SMC / Aggregate Contract 必须 pin 此值。

命名：

```text
consumerDigest
```

## 8.3 manifest bundleDigest

如果现有 manifest 保留：

```text
bundleDigest
```

它继续按原生成算法维护。

但：

```text
bundleDigest
!=
consumerDigest
```

MUST NOT 混用。

---

# 9. REQ-RC-001 — 修正 ACP v1.1.0 Release Identity

目标文件：

```text
nodeskclaw-acp/contracts/acp-v1-adapter/v1.1.0/manifest.json
```

MUST：

```json
{
  "implementationHeadSha": "896450ad479033afc2428852a2d02f70f77ab19e",
  "releaseCommitSha": "896450ad479033afc2428852a2d02f70f77ab19e"
}
```

MUST preserve：

```text
contractName
contractVersion=1.1.0
provider=nodeskclaw-acp
consumer=smc-copilot/apps/work
acpProtocolVersion=1
remoteAgentContractVersion=1.5.0
catalogContractVersion=1.0.0
conformance
production_gate=unpassed
```

---

# 10. REQ-RC-002 — 修正 Catalog v1.0.0 Release Identity

目标：

```text
nodeskclaw-backend/contracts/remote-expert-catalog/v1.0.0/manifest.json
```

MUST：

```json
{
  "implementationHeadSha": "896450ad479033afc2428852a2d02f70f77ab19e",
  "releaseCommitSha": "896450ad479033afc2428852a2d02f70f77ab19e"
}
```

MUST preserve：

```text
contractName=REMOTE-EXPERT-CATALOG-CONTRACT
contractVersion=1.0.0
provider=nodeskclaw-backend
consumer=smc-copilot/apps/work
production_gate=unpassed
```

---

# 11. REQ-RC-003 — Regenerate Component SHA256SUMS

修改 manifest 后：

```text
ACP SHA256SUMS
Catalog SHA256SUMS
```

必须重新生成。

禁止：

```text
手工只修改 manifest hash line
```

如果仓库有 generator：

```text
MUST use generator
```

如果没有：

```text
Plan 必须建立 deterministic regenerate command
```

排序：

```text
lexicographic relative path
```

编码：

```text
UTF-8
LF
```

格式：

```text
<64 lowercase hex><two spaces><relative path>
```

---

# 12. REQ-RC-004 — Freeze Final Component Consumer Digests

生成后：

```text
ACP_FINAL_DIGEST
=
sha256(acp-v1-adapter/v1.1.0/SHA256SUMS bytes)

CATALOG_FINAL_DIGEST
=
sha256(remote-expert-catalog/v1.0.0/SHA256SUMS bytes)
```

Plan 不得提前写死新值。

只有生成后才能记录：

```text
evidence.final_acp_consumer_digest
evidence.final_catalog_consumer_digest
```

---

# 13. REQ-RC-005 — Update Runtime Final Pins

当前：

```text
nodeskclaw-acp/app/constants.py
```

包含：

```text
ADAPTER_CONTRACT_DIGEST
CATALOG_CONTRACT_DIGEST
REMOTE_AGENT_CONTRACT_DIGEST
```

Closure 后：

```text
ADAPTER_CONTRACT_DIGEST = ACP_FINAL_DIGEST
CATALOG_CONTRACT_DIGEST = CATALOG_FINAL_DIGEST
```

Remote Agent v1.5 pin MUST remain：

```text
c8bc0ed8a1cf5b21fcbfb743a59a2d24480ff4dc90a651e8a0b5c057ca27b18c
```

除非其 frozen bundle 被证明发生非法漂移。

如果 Remote Agent digest 变化：

```text
BLOCK RELEASE
```

---

# 14. REQ-RC-006 — Version Probe Must Expose Final ACP Pin

```text
nodeskclaw-acp version --json
```

继续返回：

```text
adapterVersion=1.6.1
protocolVersion=1
adapterContractVersion=1.1.0
adapterContractDigest=<ACP_FINAL_DIGEST>
remoteAgentContractVersion=1.5.0
remoteAgentContractDigest=<frozen>
```

如果 Contract 值和 runtime constants 不一致：

```text
Release Gate FAIL
```

---

# 15. REQ-RC-007 — Component Release Guard

新增/加强自动测试。

最低必须验证：

```text
ACP manifest implementationHeadSha == IMPLEMENTATION_COMMIT
ACP manifest releaseCommitSha == IMPLEMENTATION_COMMIT

Catalog manifest implementationHeadSha == IMPLEMENTATION_COMMIT
Catalog manifest releaseCommitSha == IMPLEMENTATION_COMMIT

sha256(ACP SHA256SUMS) == ADAPTER_CONTRACT_DIGEST

sha256(Catalog SHA256SUMS) == CATALOG_CONTRACT_DIGEST

ACP manifest remoteAgentContractDigest
==
sha256(remote-agent/v1.5.0/SHA256SUMS)

ACP manifest catalogContractDigest
==
CATALOG_FINAL_DIGEST
```

---

# 16. REQ-RC-008 — Immutability Guard

Closure 之后：

```text
ACP v1.1.0
Catalog v1.0.0
Frontend v1.0.0
```

都视为 frozen。

后续 wire change：

```text
MUST create new contract version
```

MUST NOT：

```text
rewrite frozen files after tag
```

---

# 17. REQ-RC-009 — Frontend Aggregate Contract

新增：

```text
contracts/remote-expert-frontend/v1.0.0/
```

最少包含：

```text
RELEASE.md
manifest.json
SHA256SUMS
consumer/
  smc-copilot-v6.3.json
```

推荐：

```text
component-pins.json
```

---

# 18. Aggregate Contract Identity

```json
{
  "contractName": "REMOTE-EXPERT-FRONTEND-CONTRACT",
  "contractVersion": "1.0.0",
  "bundleFormatVersion": "1",
  "providerRepository": "loudon84/nodeskclaw",
  "consumer": "loudon84/smc-copilot/apps/work",
  "consumerBranchBaseline": "work/prd-v6.3",
  "implementationCommit": "896450ad479033afc2428852a2d02f70f77ab19e",
  "components": {
    "remoteExpertCatalog": {
      "version": "1.0.0",
      "consumerDigest": "<CATALOG_FINAL_DIGEST>"
    },
    "acpAdapter": {
      "version": "1.1.0",
      "consumerDigest": "<ACP_FINAL_DIGEST>"
    },
    "remoteAgent": {
      "version": "1.5.0",
      "consumerDigest": "c8bc0ed8a1cf5b21fcbfb743a59a2d24480ff4dc90a651e8a0b5c057ca27b18c"
    }
  },
  "acpProtocolVersion": 1,
  "productionGate": "unpassed",
  "frontendContractGate": "passed"
}
```

注意：`frontendContractGate` 只有 Acceptance 全部通过后才能写 `passed`。

---

# 19. Aggregate RELEASE.md

必须明确：

```text
1. 这是给 smc-copilot 的 cross-repository frontend handoff。
2. Remote Expert 必须走 ACP，不走 WORK-EXPERT-CONTRACT。
3. Remote Expert 不走 Skill Run。
4. Component contracts 仍以 SHA256SUMS digest 为 SOT。
5. Aggregate Git tag 是 discovery/freeze handle，不替代 digest validation。
6. production_gate 仍未通过。
7. Frontend development may proceed.
8. Production rollout must wait for separate live gates.
```

---

# 20. SMC Consumer Descriptor

```text
consumer/smc-copilot-v6.3.json
```

建议：

```json
{
  "repository": "loudon84/smc-copilot",
  "branchBaseline": "work/prd-v6.3",
  "integrationMode": "original-chat-compose-acp",
  "forbiddenDependencies": [
    "WORK-EXPERT-CONTRACT",
    "ExpertProjectionStore",
    "expert.start",
    "skillName",
    "SkillRunStore"
  ],
  "requiredCapabilities": [
    "remote-expert-catalog",
    "acp-v1",
    "session-resume",
    "managed-credential",
    "attachment-resource-link",
    "artifact-resource-link",
    "permission-bridge"
  ]
}
```

---

# 21. REQ-RC-010 — Frontend Contract Tag

目标：

```text
remote-expert-frontend-contract-v1.0.0
```

类型：

```text
annotated tag
```

MUST NOT：

```text
lightweight-only release marker
git tag -f
force replace existing tag
```

如果 tag 已存在：

```text
STOP
```

必须比对：

```text
existing tag target
aggregate digest
release evidence
```

---

# 22. Tag Message

推荐：

```text
REMOTE-EXPERT-FRONTEND-CONTRACT v1.0.0
ACP v1.1 + Remote Expert Catalog v1.0 for smc-copilot work/prd-v6.3
Frontend contract gate passed; production gate remains unpassed.
```

---

# 23. Tag Target Invariant

Tag MUST 指向：

```text
exact closure commit
```

该 commit MUST contain：

```text
all final component bundles
aggregate bundle
release tests
release evidence
```

Tag MUST NOT point：

```text
896450ad implementation commit
28e5d0 docs commit
a pre-closure candidate
```

---

# 24. Component Tag Policy

本轮禁止额外创建：

```text
acp-v1-adapter-contract-v1.1.0
remote-expert-catalog-contract-v1.0.0
```

除非后续治理另有明确授权。

原因：

```text
Component consumer identity = SHA256SUMS digest.
Aggregate frontend identity = annotated frontend tag.
```

---

# 25. REQ-RC-011 — Release Evidence

新增推荐：

```text
docs_agent/evidence/acp-v161-contract-release-closure.json
```

或项目统一 evidence 目录。

必须记录：

```json
{
  "release": "remote-expert-frontend-contract-v1.0.0",
  "implementationCommit": "896450ad479033afc2428852a2d02f70f77ab19e",
  "sourceMainAtStart": "28e5d0e4fe421432c7a47dcd2a9d5307c9ad1d6b",
  "acpContractVersion": "1.1.0",
  "acpConsumerDigest": "<final>",
  "catalogContractVersion": "1.0.0",
  "catalogConsumerDigest": "<final>",
  "remoteAgentContractVersion": "1.5.0",
  "remoteAgentConsumerDigest": "c8bc0ed8a1cf5b21fcbfb743a59a2d24480ff4dc90a651e8a0b5c057ca27b18c",
  "aggregateContractVersion": "1.0.0",
  "aggregateConsumerDigest": "<final>",
  "frontendContractGate": "PASS",
  "productionGate": "UNPASSED",
  "liveDesktopAcceptance": "NOT_CLAIMED",
  "tagName": "remote-expert-frontend-contract-v1.0.0"
}
```

---

# 26. REQ-RC-012 — Do Not Claim LIVE

本 Closure Evidence MUST NOT 写：

```text
LIVE-DESK PASS
Zed LIVE PASS
Windows Clean Machine PASS
Production Ready
```

除非真实环境执行并提供 fresh evidence。

本 PRD 默认：

```text
productionGate = UNPASSED
```

---

# 27. Frontend Ready vs Production Ready

冻结两套状态：

```text
frontendContractGate:
  pending | passed | failed
```

```text
productionGate:
  unpassed | passed
```

本 PRD DoD：

```text
frontendContractGate = passed
productionGate = unpassed
```

是合法状态。

---

# 28. REQ-RC-013 — Golden Consumer Consistency

已有：

```text
nodeskclaw-acp/contracts/consumer-fixtures/smc-copilot-v6.3/
```

Closure MUST verify：

```text
catalog
initialize
session-new
session-resume
session-close
text-turn
attachment-turn
tool-call
permission-request
artifact-resource-link
cancel
remote-error
```

全部仍与 Final Component Contract 一致。

如果 fixture 必须改变：

```text
说明 v1.6.1 implementation 语义仍未冻结
→ BLOCK
```

---

# 29. REQ-RC-014 — No Work Expert Dependency

Aggregate Contract Release Guard 必须扫描：

```text
WORK-EXPERT-CONTRACT
skillName
/expert/mcp
ExpertProjectionStore
expert.start
```

在 Frontend Contract required dependency 中：

```text
count = 0
```

文档提及 `forbidden` 不算依赖。

---

# 30. REQ-RC-015 — No Skill Run Dependency

必须证明：

```text
SkillRunStore
skill-run execution mode
Skill Catalog dependency
```

不是 Remote Expert frontend required dependency。

---

# 31. REQ-RC-016 — No Runtime Wire Change

本 Closure MUST NOT 修改：

```text
Remote Agent create request schema
Remote Agent public response schema
Remote Agent SSE event semantics
ACP JSON-RPC method semantics
ResourceLink URI semantics
Session Proof semantics
Managed Credential semantics
Permission semantics
```

若必须改：

```text
不是 Release Closure
```

必须进入新 PRD / 新 contract version。

---

# 32. REQ-RC-017 — No Hermes Runtime Change

本阶段 MUST NOT 修改：

```text
nodeskclaw-agent
Hermes request envelope
Hermes Gateway protocol
Hermes skill execution
```

---

# 33. REQ-RC-018 — Deterministic Contract Validation

推荐新增：

```text
tools/contracts/verify_remote_expert_frontend_contract.py
```

或放入现有 contract script。

输出：

```json
{
  "ok": true,
  "implementationCommit": "...",
  "acpConsumerDigest": "...",
  "catalogConsumerDigest": "...",
  "aggregateConsumerDigest": "..."
}
```

exit：

```text
0 PASS
non-zero FAIL
```

---

# 34. Validation Algorithm

必须顺序执行：

```text
1. verify component file lists
2. verify every SHA256SUMS file hash
3. compute component consumer digests
4. verify implementation identity
5. verify runtime constants
6. verify component dependency pins
7. verify aggregate component pins
8. verify consumer fixture presence
9. verify production gate not falsely passed
10. compute aggregate consumer digest
```

---

# 35. FAILURE

```text
FAIL-RC-001 ACP manifest implementationHeadSha != 896450ad... → FAIL
FAIL-RC-002 Catalog manifest implementationHeadSha != 896450ad... → FAIL
FAIL-RC-003 ADAPTER_CONTRACT_DIGEST != sha256(ACP SHA256SUMS) → FAIL
FAIL-RC-004 CATALOG_CONTRACT_DIGEST != sha256(Catalog SHA256SUMS) → FAIL
FAIL-RC-005 Aggregate pins old candidate digest → FAIL
FAIL-RC-006 Remote Agent v1.5 digest changed → BLOCK
FAIL-RC-007 productionGate set passed without live evidence → FAIL
FAIL-RC-008 frontend tag already exists with different target → BLOCK
FAIL-RC-009 closure changes public wire → BLOCK / SPEC_SEMANTIC_GAP
FAIL-RC-010 SMC fixture requires Work Expert / Skill Run → FAIL
```

---

# 36. Side-effect Matrix

| Operation | Runtime Behavior | Contract Files | Git Tag | External SaaS |
|---|---:|---:|---:|---:|
| fix manifest identity | NO | YES | NO | NO |
| regenerate sums | NO | YES | NO | NO |
| update constants | version/digest probe only | YES | NO | NO |
| aggregate contract | NO | YES | NO | NO |
| contract tests | NO | NO | NO | NO |
| release evidence | NO | YES | NO | NO |
| annotated tag | NO | NO | YES | NO |
| production live | OUT OF SCOPE | NO | NO | MAY |

---

# 37. Compatibility

## Existing ACP Clients

Must preserve：

```text
ACP protocolVersion=1
Zed profile semantics
standalone credential mode
```

## SMC Copilot

SMC MUST be able to：

```text
checkout/fetch tag
read aggregate manifest
verify aggregate SHA256SUMS
read component pins
verify component SHA256SUMS digest
generate client types / fixtures
```

---

# 38. Security

Release Closure MUST verify：

```text
no access token
no refresh token
no Authorization header
no provider token
no OAuth secret
no private key
no Windows user absolute private path
```

in：

```text
contracts/
evidence/
RELEASE.md
manifest.json
fixtures/
```

---

# 39. Observability

本阶段不增加 runtime metrics。

Release command SHOULD 输出：

```text
implementation_commit
acp_contract_version
acp_consumer_digest
catalog_contract_version
catalog_consumer_digest
aggregate_contract_version
aggregate_consumer_digest
frontend_contract_gate
production_gate
```

---

# 40. ACCEPTANCE

## AC-RC-001 — ACP Implementation Identity

```text
implementationHeadSha=896450ad...
releaseCommitSha=896450ad...
```

## AC-RC-002 — Catalog Implementation Identity

```text
implementationHeadSha=896450ad...
releaseCommitSha=896450ad...
```

## AC-RC-003 — ACP Final Digest

```text
sha256(final ACP SHA256SUMS)
==
app.constants.ADAPTER_CONTRACT_DIGEST
```

## AC-RC-004 — Catalog Final Digest

```text
sha256(final Catalog SHA256SUMS)
==
app.constants.CATALOG_CONTRACT_DIGEST
```

## AC-RC-005 — Remote Agent Dependency Frozen

```text
sha256(remote-agent/v1.5.0/SHA256SUMS)
==
c8bc0ed8a1cf5b21fcbfb743a59a2d24480ff4dc90a651e8a0b5c057ca27b18c
```

## AC-RC-006 — ACP → Catalog Final Pin

```text
ACP manifest.catalogContractDigest
==
CATALOG_FINAL_DIGEST
```

## AC-RC-007 — Aggregate Contract Exists

```text
contracts/remote-expert-frontend/v1.0.0/
```

包含：

```text
RELEASE.md
manifest.json
SHA256SUMS
consumer/smc-copilot-v6.3.json
```

## AC-RC-008 — Aggregate Pins Final Components

```text
acpAdapter.consumerDigest == ACP_FINAL_DIGEST
remoteExpertCatalog.consumerDigest == CATALOG_FINAL_DIGEST
remoteAgent.consumerDigest == frozen v1.5 digest
```

## AC-RC-009 — Frontend Architecture Boundary

```text
integrationMode=original-chat-compose-acp
```

且 Work Expert / Skill Run 只允许出现在 forbidden dependencies。

## AC-RC-010 — Production Gate Honest

```text
productionGate=unpassed
liveDesktopAcceptance=NOT_CLAIMED
```

## AC-RC-011 — Existing ACP v1.0.0 Immutable

```text
diff count=0
```

## AC-RC-012 — Existing Remote Agent v1.5 Immutable

```text
diff count=0
```

## AC-RC-013 — Golden Consumer Fixtures Present

required set：

```text
100% present
```

## AC-RC-014 — Contract Validator

```text
exit=0
ok=true
```

## AC-RC-015 — Negative Tamper Detection

临时篡改任一 contract byte / sum / pin：

```text
validator non-zero
```

## AC-RC-016 — Tag Preflight

```text
remote-expert-frontend-contract-v1.0.0
```

创建前必须不存在。

## AC-RC-017 — Tag Target

```text
peeled target commit == closure commit
```

## AC-RC-018 — Tag Freeze

从 tag checkout 重新运行 validator：

```text
PASS
```

---

# 41. Negative Acceptance

```text
NEG-RC-001 component manifest still pins 557a3b0f → FAIL
NEG-RC-002 component digest copied from pre-closure candidate → FAIL
NEG-RC-003 only version number pin → FAIL
NEG-RC-004 aggregate uses main branch as dependency → FAIL
NEG-RC-005 component tag required for ACP → FAIL
NEG-RC-006 component tag required for Catalog → FAIL
NEG-RC-007 frontend tag force-overwritten → FAIL
NEG-RC-008 production_gate=passed without live → FAIL
NEG-RC-009 Release claims Windows clean-machine PASS without evidence → FAIL
NEG-RC-010 Work Expert dependency reintroduced → FAIL
NEG-RC-011 Skill Run dependency reintroduced → FAIL
NEG-RC-012 Remote Agent wire changed → FAIL
NEG-RC-013 Integration Account wire changed → FAIL
NEG-RC-014 ACP v1.0.0 rewritten → FAIL
NEG-RC-015 Remote Agent v1.5.0 rewritten → FAIL
NEG-RC-016 tag points implementation commit instead of closure commit → FAIL
NEG-RC-017 tag exists and git tag -f used → FAIL
NEG-RC-018 release evidence contains secrets → FAIL
```

---

# 42. Failure Injection

| Injection | Expected |
|---|---|
| change ACP manifest one byte | checksum validation FAIL |
| change Catalog schema one byte | checksum validation FAIL |
| stale ADAPTER_CONTRACT_DIGEST | validator FAIL |
| stale CATALOG_CONTRACT_DIGEST | validator FAIL |
| stale aggregate component pin | validator FAIL |
| change Remote Agent v1.5 SHA | BLOCK |
| set productionGate=passed | validator FAIL without live evidence |
| remove SMC attachment fixture | validator FAIL |
| add WORK-EXPERT required dependency | validator FAIL |
| pre-create tag at wrong commit | release BLOCK |
| attempt force tag | policy FAIL |

---

# 43. Release Gates

```text
Gate RC-0  Baseline Freeze
Gate RC-1  Component Identity
Gate RC-2  Component Integrity
Gate RC-3  Runtime Pin
Gate RC-4  Dependency Freeze
Gate RC-5  Aggregate Contract
Gate RC-6  Consumer Boundary
Gate RC-7  Release Guard
Gate RC-8  Security
Gate RC-9  Frontend Contract Ready
Gate RC-10 Tag Preflight
Gate RC-11 Annotated Tag
```

Gate RC-9 的合法终态：

```text
frontendContractGate=passed
productionGate=unpassed
```

---

# 44. Evidence Matrix

| Acceptance | Evidence |
|---|---|
| AC-RC-001 | ACP manifest + validator |
| AC-RC-002 | Catalog manifest + validator |
| AC-RC-003 | ACP digest command |
| AC-RC-004 | Catalog digest command |
| AC-RC-005 | Remote v1.5 digest command |
| AC-RC-006 | ACP manifest final snapshot |
| AC-RC-007 | aggregate directory listing |
| AC-RC-008 | aggregate validator |
| AC-RC-009 | consumer descriptor |
| AC-RC-010 | manifest + evidence |
| AC-RC-011 | git diff frozen ACP v1.0 |
| AC-RC-012 | git diff remote v1.5 |
| AC-RC-013 | fixture listing |
| AC-RC-014 | validator stdout |
| AC-RC-015 | tamper test stdout |
| AC-RC-016 | tag preflight |
| AC-RC-017 | tag object / peeled target |
| AC-RC-018 | checkout tag validator |

---

# 45. Release Evidence Status Vocabulary

只允许：

```text
PASS
FAIL
BLOCKED
NOT_APPLICABLE
NOT_CLAIMED
```

禁止：

```text
probably
looks good
assumed
should pass
```

---

# 46. Expected File Changes

## Modify

```text
nodeskclaw-acp/contracts/acp-v1-adapter/v1.1.0/manifest.json
nodeskclaw-acp/contracts/acp-v1-adapter/v1.1.0/SHA256SUMS

nodeskclaw-backend/contracts/remote-expert-catalog/v1.0.0/manifest.json
nodeskclaw-backend/contracts/remote-expert-catalog/v1.0.0/SHA256SUMS

nodeskclaw-acp/app/constants.py

nodeskclaw-acp/tests/test_v11_contract.py
nodeskclaw-backend/tests/contracts/test_remote_expert_catalog_v1_bundle.py
```

## Add

```text
contracts/remote-expert-frontend/v1.0.0/RELEASE.md
contracts/remote-expert-frontend/v1.0.0/manifest.json
contracts/remote-expert-frontend/v1.0.0/SHA256SUMS
contracts/remote-expert-frontend/v1.0.0/consumer/smc-copilot-v6.3.json

tools/contracts/verify_remote_expert_frontend_contract.py

tests/contracts/test_remote_expert_frontend_contract.py
```

Test 路径可按仓库现有规范调整。

---

# 47. MUST NOT Change

```text
nodeskclaw-agent runtime
Hermes runtime
Remote Agent public wire
Remote Agent v1.5 frozen files
ACP v1.0.0 frozen files
Integration Account v1.1 frozen files
Work Expert contract
Skill Run contract
smc-copilot source
```

---

# 48. Transaction Model

Closure 逻辑上是一个原子发布单元：

```text
Fix
→ Recalculate
→ Pin
→ Aggregate
→ Verify
→ Evidence
→ Commit
→ Tag
```

禁止：

```text
Tag before final digest
Tag before validator
Tag before evidence
```

---

# 49. Commit Model

推荐：

```text
Commit A:
chore(acp): freeze v1.6.1 frontend contract release
```

包含：

```text
component identity fixes
digest regeneration
runtime pin
aggregate contract
guards
evidence
```

然后：

```text
Annotated Tag
remote-expert-frontend-contract-v1.0.0
```

Tag MUST 指向最终包含完整 aggregate/evidence 的 commit。

---

# 50. Tag Authorization Boundary

本 PRD 允许 Plan 包含 tag creation step，但执行时必须遵循仓库写入授权策略。

禁止：

```text
force tag
rewrite existing tag
```

---

# 51. SMC Handoff

Tag 完成后交付 SMC：

```text
tag:
remote-expert-frontend-contract-v1.0.0

aggregate:
contracts/remote-expert-frontend/v1.0.0/

component:
ACP-V1-ADAPTER-CONTRACT v1.1.0
REMOTE-EXPERT-CATALOG-CONTRACT v1.0.0
REMOTE-AGENT-PROVIDER-CONTRACT v1.5.0

pins:
component consumer digests
```

SMC SHOULD：

```text
pin tag for repository baseline
verify aggregate SHA256SUMS
verify component consumer digests
copy/generate contract types
consume Golden fixtures
```

---

# 52. SMC Must Not Pin

```text
main
latest commit at runtime
folder version only
pre-closure b4de...
pre-closure cd38...
manifest.bundleDigest as component identity
```

---

# 53. SMC Next PRD Unblocked By This Release

本 Closure 完成后允许进入：

```text
smc-copilot
Original Chat / Compose
ACP Remote Expert Integration
```

包括：

```text
RemoteExpertContextControl
ACP Process Manager
ACP Client
Managed Credential Bridge
Remote Expert Catalog Client
ACP session mapping
Attachment ResourceLink mapping
Artifact ResourceLink materialization
Permission UI bridge
```

---

# 54. Production Work Remains Separate

并行后续：

```text
Windows x64 standalone packaging
clean-machine execution
managed auth LIVE
session resume LIVE
PDF/XLSX attachment LIVE
external action approval LIVE
Shared IntegrationAccount LIVE
artifact download LIVE
Zed regression LIVE
security scan
```

只有这些通过后：

```text
productionGate=passed
```

---

# 55. Plan Generation Contract

状态：

```text
APPROVED_FOR_PLAN
```

严格 Todo 顺序：

```text
T0  Freeze release baseline
T1  Fix ACP v1.1 implementation identity
T2  Fix Catalog v1.0 implementation identity
T3  Regenerate Catalog SHA256SUMS
T4  Compute Catalog final consumer digest
T5  Regenerate ACP dependency pin to final Catalog digest
T6  Regenerate ACP SHA256SUMS
T7  Compute ACP final consumer digest
T8  Update runtime contract digest constants
T9  Add component release identity guards
T10 Add digest equality guards
T11 Create Remote Expert Frontend aggregate contract
T12 Create SMC v6.3 consumer descriptor
T13 Generate aggregate SHA256SUMS
T14 Add aggregate contract validator
T15 Add tamper negative tests
T16 Verify frozen dependency immutability
T17 Verify Golden Consumer consistency
T18 Run security / secret / path scan
T19 Generate release evidence
T20 Frontend Contract Gate
T21 Create closure commit
T22 Tag preflight
T23 Create annotated frontend contract tag
T24 Verify tag checkout and final evidence
```

---

# 56. Todo Schema

每一 Todo 必须：

```yaml
id:
requirement_refs:
acceptance_refs:
files_or_symbols:
implementation_goal:
preconditions:
state_transition:
side_effect_scope:
failure_cases:
verification:
status:
evidence:
```

Status：

```text
planned
implemented
verified
blocked
```

规则：

```text
implemented != verified
```

---

# 57. Critical Ordering

特别注意：

```text
Catalog manifest
→ Catalog SHA256SUMS
→ Catalog Final Digest
→ ACP manifest Catalog pin
→ ACP SHA256SUMS
→ ACP Final Digest
→ Runtime constants
→ Aggregate pins
→ Aggregate SHA256SUMS
```

顺序不可反转。

---

# 58. Digest Dependency Graph

```text
Catalog manifest
      ↓
Catalog SHA256SUMS
      ↓
CATALOG_FINAL_DIGEST
      ↓
ACP manifest.catalogContractDigest
      ↓
ACP SHA256SUMS
      ↓
ACP_FINAL_DIGEST
      ↓
runtime constants
      ↓
Aggregate manifest
      ↓
Aggregate SHA256SUMS
      ↓
AGGREGATE_FINAL_DIGEST
```

---

# 59. Acceptance Commands

Plan 必须给出真实仓库命令。

概念 Oracle：

```text
python -c "sha256(SHA256SUMS)"
pytest component contract tests
python tools/contracts/verify_remote_expert_frontend_contract.py
git diff frozen paths
git tag --list remote-expert-frontend-contract-v1.0.0
git show <tag>
```

具体命令由 Plan 按仓库环境冻结。

---

# 60. Definition of Done

```text
[ ] Current release baseline recorded
[ ] Implementation commit fixed to 896450ad...

[ ] ACP manifest implementationHeadSha fixed
[ ] ACP manifest releaseCommitSha fixed

[ ] Catalog manifest implementationHeadSha fixed
[ ] Catalog manifest releaseCommitSha fixed

[ ] Catalog SHA256SUMS regenerated
[ ] Catalog final consumer digest computed

[ ] ACP manifest pins final Catalog digest
[ ] ACP SHA256SUMS regenerated
[ ] ACP final consumer digest computed

[ ] ADAPTER_CONTRACT_DIGEST equals final ACP digest
[ ] CATALOG_CONTRACT_DIGEST equals final Catalog digest
[ ] REMOTE_AGENT_CONTRACT_DIGEST unchanged

[ ] ACP version --json exposes final digest

[ ] release identity tests added
[ ] digest equality tests added
[ ] tamper negative tests added

[ ] contracts/remote-expert-frontend/v1.0.0 exists
[ ] aggregate RELEASE exists
[ ] aggregate manifest exists
[ ] aggregate SHA256SUMS exists
[ ] SMC consumer descriptor exists

[ ] aggregate pins final ACP digest
[ ] aggregate pins final Catalog digest
[ ] aggregate pins frozen Remote Agent v1.5 digest

[ ] SMC Golden Consumer fixtures verified
[ ] no Work Expert required dependency
[ ] no Skill Run required dependency

[ ] ACP v1.0.0 unchanged
[ ] Remote Agent v1.5.0 unchanged
[ ] Integration Account v1.1 unchanged

[ ] frontendContractGate=passed
[ ] productionGate=unpassed
[ ] no fake LIVE evidence

[ ] secret scan PASS
[ ] absolute private path scan PASS

[ ] release evidence generated
[ ] validator PASS
[ ] tamper negative test PASS

[ ] closure commit created

[ ] target tag did not previously exist
[ ] annotated tag remote-expert-frontend-contract-v1.0.0 created
[ ] no force tag

[ ] tag peeled target == closure commit
[ ] validator PASS from tag checkout

[ ] smc-copilot handoff data complete
[ ] no SPEC_SEMANTIC_GAP
```

---

# 61. Final Engineering Invariants

```text
1. v1.6.1 功能实现基线是 896450ad。
2. 557a3b0f 不能作为 v1.6.1 implementation identity。
3. 28e5d0e4 是 docs 基线，不是 v1.6.1 implementation identity。

4. Component Consumer Pin = sha256(SHA256SUMS bytes)。
5. Component Consumer Pin != version only。
6. Component Consumer Pin != branch。
7. Component Consumer Pin != manifest.bundleDigest。
8. Component Consumer Pin != component Git tag。

9. ACP v1.1 component 不要求独立 Git tag。
10. Catalog v1.0 component 不要求独立 Git tag。

11. Cross-repository handoff 使用 REMOTE-EXPERT-FRONTEND-CONTRACT。
12. Frontend aggregate tag = remote-expert-frontend-contract-v1.0.0。
13. Frontend tag 是 annotated tag。
14. Frontend tag 不允许 force rewrite。
15. Frontend tag 指向 closure commit。

16. Aggregate Contract pin ACP final consumer digest。
17. Aggregate Contract pin Catalog final consumer digest。
18. Aggregate Contract pin Remote Agent v1.5 frozen digest。

19. Catalog Final Digest 必须先于 ACP Final Digest 生成。
20. ACP Final Digest 必须先于 Aggregate Final Digest 生成。

21. Runtime ADAPTER_CONTRACT_DIGEST 必须等于 ACP final consumer digest。
22. Runtime CATALOG_CONTRACT_DIGEST 必须等于 Catalog final consumer digest。

23. ACP v1.0.0 不得修改。
24. Remote Agent v1.5.0 不得修改。
25. Integration Account v1.1 不得修改。

26. 本 Closure 不修改 Remote Agent wire。
27. 本 Closure 不修改 ACP wire semantics。
28. 本 Closure 不修改 Session Proof semantics。
29. 本 Closure 不修改 ResourceLink semantics。
30. 本 Closure 不修改 Permission semantics。

31. 本 Closure 不引入 Work Expert。
32. 本 Closure 不引入 Skill Run。
33. SMC integration mode 固定为 Original Chat / Compose / ACP。

34. Frontend Contract Ready 与 Production Ready 是两个 Gate。
35. 本 Closure 目标是 Frontend Contract Gate PASS。
36. 本 Closure 不要求 Production Gate PASS。
37. productionGate 必须保持 unpassed，直到真实 LIVE 完成。
38. 不允许伪造 Windows/Zed/LIVE evidence。

39. Golden Consumer Fixtures 必须继续与 v6.3 consumer 语义一致。
40. 若 Closure 需要改变 Golden wire fixture，则说明实现未冻结，Release BLOCKED。

41. Release Guard 必须验证 implementation identity。
42. Release Guard 必须验证 digest equality。
43. Release Guard 必须验证 dependency pin。
44. Release Guard 必须验证 aggregate pin。
45. Release Guard 必须有 tamper negative test。

46. Tag 前必须做 existence preflight。
47. Tag 已存在且 target 不一致时必须 BLOCK。
48. 禁止 git tag -f。
49. Tag 后必须从 tag checkout 再跑 validator。

50. Release Evidence 必须记录 final component digests。
51. Release Evidence 必须记录 implementation commit。
52. Release Evidence 必须记录 productionGate=UNPASSED。
53. Release Evidence 不得含 secrets。

54. 完成本 PRD 后，smc-copilot 可以正式进入 Remote Expert ACP Consumer 开发。
55. Windows binary / LIVE acceptance 可与 SMC 前端开发并行推进。
```
