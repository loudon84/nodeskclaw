---
name: RM-09 Shared Contract Public Isolation
overview: 在 RM-08 Internal Topology 已冻结后，隔离员工 MCP Catalog 与 Public Run/SSE，禁止 Internal 南向字段泄漏或被客户端覆盖；不改写 Public skill-run，不发布 v1.5.0。
todos:
  - id: t1-mcp-southbound-isolation
    content: "T1 — MCP Catalog 与 tools/call overlay 隔离 [C07, C08]"
    status: completed
  - id: t2-public-run-sse-isolation
    content: "T2 — Public Run/SSE Internal 键否定 oracle [C09]"
    status: completed
  - id: t3-oracles-lat-evidence
    content: "T3 — Public 空 diff、回归、lat.md 与出口证据 [C11]"
    status: completed
isProject: false
plan_contract: smc.plan.v3.4
plan_id: RM-09
commit_policy: post_review
acceptance_contract: smc.acceptance.v1
domain_contract: smc.ges.domain-activation.v1
consumer_profile: generic@1.0.0
domain_policy_digest: sha256:78167a10490bbe109ad2f006cfe74ff1390b2187cb6728004964448f2a5c5907
source_revision: AD-SKILL-AGENT-V16@1.7.0/RM-09
grounded_commit: 2ed2f13796d813f9f5ad09bddc937185ae4ba181
grounding_source: committed_baseline
working_tree_fingerprint: dirty-unrelated-plans; production-at-ddf8a653; docs-head-999bdcb
---

# RM-09 Shared Contract 公共面隔离 实施计划

Canonical 落盘路径：[`.cursor/plans/rm-09_shared-contract-public-isolation.plan.md`](rm-09_shared-contract-public-isolation.plan.md)

`commit_policy: post_review`。下游只走 `smc-plan-delivery`。Todo 完成不得 commit。implementation commit 与 Roadmap DONE 分离。禁止第二份 `.plan.md`。

批准事实取 Stage PRD [`docs_agent/prd-v1.6.18-shared-contract-public-isolation.md`](../../docs_agent/prd-v1.6.18-shared-contract-public-isolation.md)（`APPROVED` / review PASS / `approved_at: 2026-09-08T13:10:00Z`）。生产代码基线 `grounded_commit: 2ed2f13796d813f9f5ad09bddc937185ae4ba181`。其后独立 docs commit：`829e9d30`（PRD）与 `999bdcb4`（Roadmap `IN_PRD`）。RM-08 freeze commit `ddf8a653`，tag `skill-agent-contract-v1.0.0`。

## 前端表现变化

本次改动无前端表现变化。不改 Portal / Admin / Work 页面、按钮、文案或路由。员工 Work 不渲染 Internal Topology；本项只收紧 Backend MCP 与 Public 投影。

## Approved PRD

[Approved PRD](../../docs_agent/prd-v1.6.18-shared-contract-public-isolation.md)

## Scope

- In: MCP `tools/list` 显式隔离 Internal 南向键；`tools/call` 对 Topology/capability/snapshot/成员 overlay 拒绝或剥离且不生效；Public GET/SSE/result 否定 oracle（无 Internal 键、无 `internal.runtime.trace`、单一 Parent Run）；Public v1.2.1～v1.4.0 空 diff；lat.md 与出口证据。
- Out: `SKILL-RUN-CONTRACT v1.5.0`；改写冻结 Public 三版；重做 RM-17/RM-18；RM-16 live 委派；Platform Multi-Agent / Child Run；删除 Portal 运营 `extra_metadata`；Work UI。
- KEEP: RM-08 freeze/fail-closed；Internal Bundle；入队 `client_context` 剥离；运营 Skill CRUD extra_metadata。

Plan 级冻结:

- 不得把 `published.extra_metadata` 整包 `update` 进 MCP tool 对象。
- Topology overlay 与 `_routing` 同类，不得静默改写服务器冻结值。
- 不得把运营 `GET /skills` extra_metadata 当成员工合同面去删。
- Catalog 实际符号是 `_skill_to_tool_dict`（PRD 简称 `_skill_to_tool`）。

## Domain Activation Ledger

None

## Grounding Evidence Ledger

| Change ID | Target | Baseline State | Symbol / Entry Resolution | Caller / Callee Evidence | Existing Reuse Search | Result |
|---|---|---|---|---|---|---|
| C01 | `nodeskclaw-backend/contracts/skill-run/v1.2.1` | EXISTS frozen Public | v1.2.1～v1.4.0 Schema 无 topology | Contract Package KEEP | 禁止改写 | PASS |
| C02 | `nodeskclaw-backend/contracts/skill-agent/v1.0.0/` | EXISTS RM-08 | tag `skill-agent-contract-v1.0.0` → `ddf8a653` | Internal KEEP | 禁止改写 Bundle | PASS |
| C03 | `runtime_skill_run_service.py#_enqueue_agent_run_outbox` | EXISTS freeze | 已剥离 client_context Topology | MCP call_tool → start → enqueue | KEEP 入队；MCP 补边界 | PASS |
| C04 | `hermes_engine.py#execute_hermes_run` | EXISTS fail-closed | UNAVAILABLE / NOT_SUPPORTED | Agent KEEP | 本项不改 Adapter | PASS |
| C07 | `mcp_tool_mapper.py#McpToolMapper#_skill_to_tool_dict` | PARTIAL cherry-pick | 读 `release_extra` 个别键；无显式 Internal denylist | handler tools/list | MODIFY 同一 mapper | PASS |
| C08 | `mcp_tool_mapper.py#RUNTIME_SKILL_FORBIDDEN_ARGUMENT_KEYS` | PARTIAL | 仅 `_routing`/`_execution`/`route_config` | call_tool / `_has_explicit_runtime_route_override` | MODIFY 扩展同类拒绝 | PASS |
| C08 | `handler.py#_copy_frozen_attachment_refs` | PARTIAL | 只拷 `attachment_refs` | tools/call | MODIFY 剥离 Internal overlay 键 | PASS |
| C09 | `runs.py#_public_run_event` | PARTIAL whitelist | 未知类型 `return None` | Public SSE | 补 Internal 键否定测试；泄漏则同函数收紧 | PASS |
| C10 | Roadmap RM-16 | BACKLOG | Depends On RM-15 | KEEP | 本项不得 READY RM-16 | PASS |
| C11 | `docs_agent/evidence/rm09-verification.md` | MISSING | 尚无 RM-09 出口证据 | Delivery 证据 | ADD markdown 证据；不伪造 FRESH JSON | PASS |

## Requirement Coverage Ledger

| Requirement | Source | Obligation | Classification | Change IDs | Todo | Verification IDs | Evidence Class | Blocking |
|---|---|---|---|---|---|---|---|---|
| AC-01 | AC | MCP `tools/list`（员工 `user_jwt` / `mcp_client_token` 可达集合）返回的每个 tool 对象及其嵌套字段不含 `delegation_topology`、`runtime_capability_ref`、ExecutionSnapshot、成员列表或 Internal `skill-agent/` 路径。 | SECURITY | C07 | T1 | V01 | UNIT | yes |
| AC-02 | AC | Published Release `extra_metadata` 含 Topology 时，Catalog 仍不映出这些键（不得 `update(extra_metadata)`）。 | SECURITY | C07 | T1 | V01 | UNIT | yes |
| AC-03 | AC | `tools/call` 在 arguments 或 `client_context` 携带 Topology/capability/snapshot/成员键时失败关闭或剥离后不生效；Outbox/Agent 所见仍为服务器冻结值。 | SECURITY | C08 | T1 | V02 | UNIT | yes |
| AC-04 | AC | 既有路由覆盖拒绝（`_routing`/`_execution`/`route_config`）回归仍成立。 | SECURITY | C08 | T1 | V03 | UNIT | yes |
| AC-05 | AC | `GET /api/v1/runs/{id}`、result、SSE 投影不含 Internal 南向键；`internal.runtime.trace` 与 `subagent.*` 不出现。 | SECURITY | C09 | T2 | V04 | UNIT | yes |
| AC-06 | AC | 同一 Public Run 在 `runtime_delegated` 下仍只有一个 `run_id`，无 Child Run 标识。 | SCOPE | C09 | T2 | V04 | UNIT | yes |
| AC-07 | AC | `git diff --exit-code <grounded_commit> -- nodeskclaw-backend/contracts/skill-run/v1.2.1 nodeskclaw-backend/contracts/skill-run/v1.3.0 nodeskclaw-backend/contracts/skill-run/v1.4.0` 为空；不存在新 Public 目录或 tag。 | CONTRACT | C01; C10 | T3 | V05 | DIFF_SCOPE | yes |
| AC-08 | AC | Internal Bundle 与 RM-08 freeze/fail-closed 回归仍 PASS。 | SCOPE | C02; C03; C04 | T3 | V06 | UNIT | yes |
| AC-09 | AC | 本项未重做 RM-17/RM-18；Roadmap 上 RM-16 仍 BACKLOG。 | SCOPE | C05; C06 | T3 | V07 | DOCUMENT_SEMANTIC | yes |
| AC-10 | AC | 实施与证据不含仓外 Work 源码、构建或发布路径。 | SCOPE | C10; C11 | T3 | V08 | DOCUMENT_SEMANTIC | yes |
| DOD-01 | DOD | AC-01 至 AC-10 的 Provider 侧验证证据已留存。 | EVIDENCE | C11 | T3 | V01; V04; V05; V07; V08; V09 | UNIT | yes |
| DOD-02 | DOD | 未发布新 Public 合同版本；未改写 v1.2.1～v1.4.0；未新增第三个服务。 | SCOPE | C01; C11 | T3 | V05 | DIFF_SCOPE | yes |
| DOD-03 | DOD | MCP/Public 隔离有自动化 oracle；员工 overlay 不生效。 | SECURITY | C07; C08; C09 | T1 | V01; V02; V04 | UNIT | yes |
| DOD-04 | DOD | Review 与 Verification 均 PASS；真实 implementation commit 写入 Roadmap 后 RM-09 才可 `DONE`。 | RELEASE | C11 | T3 | V09 | DOCUMENT_SEMANTIC | yes |
| DOD-05 | DOD | `lat.md` 写明员工公共面不暴露 Internal Topology，且 `lat check` 通过。 | RELEASE | C11 | T3 | V09 | DOCUMENT_SEMANTIC | yes |

## Lifecycle Closure Matrix

| Journey | Requirements | Trigger | Nonterminal State | Success Writer | Failure / Cancel Writer | Evidence IDs |
|---|---|---|---|---|---|---|
| Employee catalog | AC-01; AC-02 | MCP tools/list | extra_metadata 含 Topology | Mapper 写出无 Internal 键的 tool 对象 | 整包 extra 映出即失败 | V01 |
| Employee call overlay | AC-03; AC-04 | MCP tools/call | 客户端携带 Topology 键 | 拒绝或剥离；enqueue 仍服务器冻结 | 覆盖生效则失败 | V02; V03 |
| Public observe | AC-05; AC-06 | GET/SSE/result | Agent 可能有 internal.runtime.trace | 白名单投影丢弃内部事件 | 泄漏 Internal 键即失败 | V04 |

## Contract / Data Flow Closure Matrix

| Flow | Requirements | Producer | Transport / Schema | Consumer | Required Fields | Validation Owner | Failure Mapping | Retry / Idempotency Identity | Evidence IDs |
|---|---|---|---|---|---|---|---|---|---|
| MCP list | AC-01; AC-02 | McpToolMapper | JSON-RPC tools/list | Work / MCP client | Public Catalog 字段 only | MCP Gateway | Internal 键出现即测试失败 | org+user catalog | V01 |
| MCP call | AC-03 | handler + mapper + enqueue | tools/call arguments/client_context | RuntimeSkillRunService | 服务器 Topology | MCP + Runtime Skill Run | overlay 拒绝/剥离 | run_id + dispatch_id | V02 |
| Public SSE | AC-05 | runs.py | Public event schema v1.2.1～v1.4.0 | Work | 白名单 event_type | Skill Run API | unknown → drop | run_id + event_seq | V04 |

## Acceptance Claim Ledger

| Claim ID | Requirement | Observable Fact | Blocking | Prior Evidence | Prior Result | Evidence Action | Invalidation Reason | Verification IDs |
|---|---|---|---|---|---|---|---|---|
| CLM-01 | AC-01 | tools/list 无 Internal 南向键 | yes | mapper cherry-pick at grounded_commit | UNKNOWN | NEW_EVIDENCE | - | V01 |
| CLM-02 | AC-02 | extra_metadata 含 Topology 时 Catalog 仍不映出 | yes | mapper cherry-pick at grounded_commit | UNKNOWN | NEW_EVIDENCE | - | V01 |
| CLM-03 | AC-03 | call overlay 不进入冻结 payload | yes | RM-08 V03 enqueue | PROVEN_FRESH | TARGETED_RERUN | MCP 边界新增 Topology 拒绝/剥离 | V02 |
| CLM-04 | AC-04 | 既有路由覆盖拒绝仍 PASS | yes | mapper route override tests | UNKNOWN | TARGETED_RERUN | 扩展 forbidden keys 邻接既有拒绝 | V03 |
| CLM-05 | AC-05 | Public GET/SSE/result 无 Internal 键与 trace | yes | `_public_run_event` return None | PROVEN_BUT_AFFECTED | TARGETED_RERUN | 须用 Internal 键做否定 oracle | V04 |
| CLM-06 | AC-06 | runtime_delegated 仍单一 Public run_id | yes | Public 单一 Parent Run | PROVEN_BUT_AFFECTED | TARGETED_RERUN | 须证明无 Child Run 标识 | V04 |
| CLM-07 | AC-07 | Public 三版空 diff 且无 v1.5.0 | yes | RM-08 V02 | PROVEN_FRESH | NEW_EVIDENCE | - | V05 |
| CLM-08 | AC-08 | RM-08 freeze/fail-closed 回归 | yes | rm08-verification | PROVEN_FRESH | TARGETED_RERUN | 邻接 MCP/Public 边界 | V06 |
| CLM-09 | AC-09 | RM-16 仍 BACKLOG | yes | Roadmap | UNKNOWN | NEW_EVIDENCE | - | V07 |
| CLM-10 | AC-10 | 证据无 Work 源码路径 | yes | - | UNKNOWN | NEW_EVIDENCE | - | V08 |
| CLM-11 | DOD-01 | AC-01 至 AC-10 的 Provider 侧验证证据已留存 | yes | - | UNKNOWN | NEW_EVIDENCE | - | V01; V05; V07; V08; V09 |
| CLM-12 | DOD-02 | 未发布新 Public 合同版本；未改写冻结三版 | yes | - | UNKNOWN | NEW_EVIDENCE | - | V05 |
| CLM-13 | DOD-03 | MCP Catalog 隔离有自动化 oracle | yes | - | UNKNOWN | NEW_EVIDENCE | - | V01 |
| CLM-14 | DOD-04 | Review/Verification PASS；Roadmap DONE 另 commit | yes | - | UNKNOWN | NEW_EVIDENCE | - | V09 |
| CLM-15 | DOD-05 | lat.md 员工公共面不暴露 Topology 且 lat check 通过 | yes | skill-agent Runtime Delegation | UNKNOWN | NEW_EVIDENCE | - | V09 |

## Live Scenario Matrix

| Scenario ID | Claim IDs | Verification IDs | Subject / Fixture | Required Capabilities | Preconditions | Stimulus | Oracle | Environment ID |
|---|---|---|---|---|---|---|---|---|

## Live Environment Matrix

| Environment ID | Required Env Vars | Preflight Command | Fault Driver Env | Candidate Mode | Candidate Probe |
|---|---|---|---|---|---|

## Verification Ledger

| Verification ID | Claim IDs | Level | Acceptance Mode | Entry Point / Command | Oracle | Negative / Regression | Evidence Policy | Environment | Evidence Action | Blocking |
|---|---|---|---|---|---|---|---|---|---|---|
| V01 | CLM-01; CLM-02; CLM-11; CLM-13 | UNIT | LOCAL | uv --directory nodeskclaw-backend run pytest tests/hermes_skill/test_mcp_tool_mapper_runtime_skill.py -q -k "list_tools or catalog or topology or extra_metadata" | tools/list 无 delegation_topology / runtime_capability_ref / snapshot | extra_metadata 含 Topology 仍不映出 | LOCAL_TRANSIENT | local | NEW_EVIDENCE | yes |
| V02 | CLM-03 | UNIT | LOCAL | uv --directory nodeskclaw-backend run pytest tests/hermes_skill/test_runtime_skill_run_agent_enqueue.py tests/hermes_skill/test_mcp_tool_mapper_runtime_skill.py -q -k "topology or overlay or client_context or forbidden" | overlay 不进入冻结 payload | 覆盖生效则失败 | LOCAL_TRANSIENT | local | TARGETED_RERUN | yes |
| V03 | CLM-04 | UNIT | LOCAL | uv --directory nodeskclaw-backend run pytest tests/hermes_skill/test_mcp_tool_mapper_runtime_skill.py -q -k "route_override or forbidden or _routing" | 既有路由覆盖拒绝仍 PASS | 回归失败则本项失败 | LOCAL_TRANSIENT | local | TARGETED_RERUN | yes |
| V04 | CLM-05; CLM-06 | UNIT | LOCAL | uv --directory nodeskclaw-backend run pytest tests/hermes_skill/test_employee_runs_api.py -q -k "public_run or sse or internal.runtime or topology" | Public 投影无 Internal 键与 trace；单一 run_id | 泄漏或 Child Run 标识失败 | LOCAL_TRANSIENT | local | TARGETED_RERUN | yes |
| V05 | CLM-07; CLM-11; CLM-12 | DIFF_SCOPE | LOCAL | git diff --exit-code 2ed2f13796d813f9f5ad09bddc937185ae4ba181 -- nodeskclaw-backend/contracts/skill-run/v1.2.1 nodeskclaw-backend/contracts/skill-run/v1.3.0 nodeskclaw-backend/contracts/skill-run/v1.4.0 | 空 diff；无 v1.5.0 目录 | 任何 Public 改写失败 | REPO_SUMMARY | local git | NEW_EVIDENCE | yes |
| V06 | CLM-08 | UNIT | LOCAL | uv --directory nodeskclaw-backend run pytest tests/hermes_skill/test_runtime_skill_run_agent_enqueue.py -q -k "topology or delegation or enqueue" | freeze 回归 PASS | freeze 被削弱则失败 | LOCAL_TRANSIENT | local | TARGETED_RERUN | yes |
| V07 | CLM-09; CLM-11 | DOCUMENT_SEMANTIC | LOCAL | python -c "p=__import__('pathlib').Path('docs_agent/roadmaps/ROADMAP-SKILL-AGENT-V16.md'); t=p.read_text(encoding='utf-8'); rows=[ln for ln in t.splitlines() if ln.startswith(chr(124)+' RM-16 ')]; assert len(rows)==1 and 'BACKLOG' in rows[0]" | RM-16 仍 BACKLOG | READY/DONE 失败 | REPO_SUMMARY | local | NEW_EVIDENCE | yes |
| V08 | CLM-10; CLM-11 | DOCUMENT_SEMANTIC | LOCAL | python -c "from pathlib import Path; p=Path('docs_agent/evidence/rm09-verification.md'); t=p.read_text(encoding='utf-8'); assert 'nodeskclaw-work' not in t.lower() and 'apps/work' not in t" | 证据无 Work 源码路径 | 出现仓外 Work 路径失败 | REPO_SUMMARY | local | NEW_EVIDENCE | yes |
| V09 | CLM-11; CLM-14; CLM-15 | DOCUMENT_SEMANTIC | LOCAL | lat check | lat check PASS | lat 仍称员工可见 Topology 则失败 | REPO_SUMMARY | local | NEW_EVIDENCE | yes |

## Immediate Read

- `nodeskclaw-backend/app/services/hermes_skill/mcp_tool_mapper.py#McpToolMapper#_skill_to_tool_dict`
- `nodeskclaw-backend/app/services/hermes_skill/mcp_tool_mapper.py#McpToolMapper#list_tools`
- `nodeskclaw-backend/app/services/hermes_skill/mcp_tool_mapper.py#McpToolMapper#call_tool`
- `nodeskclaw-backend/app/services/hermes_skill/mcp_tool_mapper.py#McpToolMapper#_has_explicit_runtime_route_override`
- `nodeskclaw-backend/app/services/hermes_skill/mcp_tool_mapper.py#RUNTIME_SKILL_FORBIDDEN_ARGUMENT_KEYS`
- `nodeskclaw-backend/app/services/mcp_skill_gateway/handler.py#_copy_frozen_attachment_refs`
- `nodeskclaw-backend/app/api/runs.py#_public_run_view`
- `nodeskclaw-backend/app/api/runs.py#_public_run_event`
- `nodeskclaw-backend/app/api/runs.py#_public_run_result`
- `nodeskclaw-backend/app/services/hermes_skill/runtime_skill_run_service.py#RuntimeSkillRunService#_enqueue_agent_run_outbox`

## Triggered Read

- If `_skill_to_tool_dict` later copies arbitrary extra keys: denylist must still drop Internal keys
- If `_build_runtime_skill_tool_metadata` later emits instance/profile/member fields: strip them from Catalog
- If Public result embeds snapshot JSON: `_public_run_result` must strip Internal keys
- If MCP list has a second code path (connector tools): same denylist
- Otherwise: do not read

## Change Matrix

| Change ID | File / Symbol | Kind | Action | Existing Owner | Todo Owner | Target State | PRD Capability | New File? |
|---|---|---|---|---|---|---|---|---|
| C01 | `nodeskclaw-backend/contracts/skill-run/v1.2.1` | PROD | KEEP | Contract Package | - | 三版字节不变 | Public Skill Run v1.2.1～v1.4.0 | no |
| C02 | `nodeskclaw-backend/contracts/skill-agent/v1.0.0/` | PROD | KEEP | Contract Package | - | Internal 不改写 | Internal SKILL-AGENT-CONTRACT v1.0.0 | no |
| C03 | `nodeskclaw-backend/app/services/hermes_skill/runtime_skill_run_service.py#RuntimeSkillRunService#_enqueue_agent_run_outbox` | PROD | KEEP | Runtime Skill Run | - | 入队 freeze 不变 | Backend 入队 Topology freeze | no |
| C04 | `nodeskclaw-agent/app/services/hermes_engine.py#execute_hermes_run` | PROD | KEEP | Hermes Adapter | - | fail-closed 不变 | Agent Snapshot / fail-closed | no |
| C05 | `nodeskclaw-backend/contracts/skill-run/v1.3.0` | PROD | KEEP | Contract Package | - | Approval 不返工 | RM-17/RM-18 | no |
| C06 | `docs_agent/roadmaps/ROADMAP-SKILL-AGENT-V16.md` | DOC | KEEP | Roadmap | - | RM-16 BACKLOG | RM-16 / PMA | no |
| C07 | `nodeskclaw-backend/app/services/hermes_skill/mcp_tool_mapper.py#McpToolMapper#_skill_to_tool_dict` | PROD | MODIFY | MCP Gateway | T1 | Catalog 无 Internal 键 | MCP Catalog Internal 隔离 | no |
| C07 | `nodeskclaw-backend/app/services/hermes_skill/mcp_tool_mapper.py#McpToolMapper#list_tools` | PROD | MODIFY | MCP Gateway | T1 | list 出口剥离 Internal 键 | MCP Catalog Internal 隔离 | no |
| C07 | `nodeskclaw-backend/tests/hermes_skill/test_mcp_tool_mapper_runtime_skill.py` | TEST | MODIFY | MCP Gateway tests | T1 | extra_metadata Topology 不映出 | MCP Catalog Internal 隔离 | no |
| C08 | `nodeskclaw-backend/app/services/hermes_skill/mcp_tool_mapper.py#RUNTIME_SKILL_FORBIDDEN_ARGUMENT_KEYS` | PROD | MODIFY | MCP Gateway | T1 | Topology 键视为覆盖 | MCP tools/call overlay 拒绝 | no |
| C08 | `nodeskclaw-backend/app/services/hermes_skill/mcp_tool_mapper.py#McpToolMapper#_has_explicit_runtime_route_override` | PROD | MODIFY | MCP Gateway | T1 | 使用扩展 forbidden 集合 | MCP tools/call overlay 拒绝 | no |
| C08 | `nodeskclaw-backend/app/services/hermes_skill/mcp_tool_mapper.py#McpToolMapper#call_tool` | PROD | MODIFY | MCP Gateway | T1 | overlay 拒绝不改冻结值 | MCP tools/call overlay 拒绝 | no |
| C08 | `nodeskclaw-backend/app/services/mcp_skill_gateway/handler.py#_copy_frozen_attachment_refs` | PROD | MODIFY | MCP Gateway | T1 | 剥离 Internal overlay | MCP tools/call overlay 拒绝 | no |
| C09 | `nodeskclaw-backend/app/api/runs.py#_public_run_event` | PROD | MODIFY | Skill Run API | T2 | 否定 oracle；泄漏则收紧 | Public Run/SSE Internal 隔离 | no |
| C09 | `nodeskclaw-backend/app/api/runs.py#_public_run_view` | PROD | MODIFY | Skill Run API | T2 | GET 无 Internal 键 | Public Run/SSE Internal 隔离 | no |
| C09 | `nodeskclaw-backend/app/api/runs.py#_public_run_result` | PROD | MODIFY | Skill Run API | T2 | result 无 Internal 键 | Public Run/SSE Internal 隔离 | no |
| C09 | `nodeskclaw-backend/tests/hermes_skill/test_employee_runs_api.py` | TEST | MODIFY | Skill Run API tests | T2 | Internal 键与 trace 否定 | Public Run/SSE Internal 隔离 | no |
| C10 | `docs_agent/roadmaps/ROADMAP-SKILL-AGENT-V16.md` | DOC | KEEP | Roadmap | - | 无 Work Todo；RM-16 BACKLOG | 仓外 Work / 新合同版本 | no |
| C11 | `docs_agent/evidence/rm09-verification.md` | DOC | ADD | Repository Acceptance Assets | T3 | 出口证据 | lat.md 与出口证据 | yes |
| C11 | `lat.md/architecture/skill-agent.md#Runtime Delegation Boundary` | DOC | MODIFY | lat.md | T3 | 员工公共面不暴露 Topology | lat.md 与出口证据 | no |

## Implementation Decisions

| Change ID | Strategy | Root-Cause / Reuse Evidence | Why This Is Minimum |
|---|---|---|---|
| C07 | MODIFY_EXISTING | `_skill_to_tool_dict` 已樱桃采摘；缺 denylist 测试 | 不新建 Catalog 服务 |
| C08 | MODIFY_EXISTING | 已有 route override 拒绝与 enqueue 剥离 | 扩展同一 forbidden 集合与 client_context 拷贝 |
| C09 | MODIFY_EXISTING | `_public_run_event` 已丢弃未知类型；view/result 已白名单 | 先加否定测试；仅当泄漏才改投影 |
| C11 | MINIMAL_NEW | 无 rm09-verification；lat 未写员工公共面隔离 | markdown 证据 + 既有 lat 段落，不伪造 FRESH JSON |

## Write Ownership Ledger

| Todo | Owns Changes | Writes | Reads | Depends On | Parallel Safe |
|---|---|---|---|---|---|
| T1 | C07; C08 | `nodeskclaw-backend/app/services/hermes_skill/mcp_tool_mapper.py#McpToolMapper#_skill_to_tool_dict` ; `nodeskclaw-backend/app/services/hermes_skill/mcp_tool_mapper.py#McpToolMapper#list_tools` ; `nodeskclaw-backend/tests/hermes_skill/test_mcp_tool_mapper_runtime_skill.py` ; `nodeskclaw-backend/app/services/hermes_skill/mcp_tool_mapper.py#RUNTIME_SKILL_FORBIDDEN_ARGUMENT_KEYS` ; `nodeskclaw-backend/app/services/hermes_skill/mcp_tool_mapper.py#McpToolMapper#_has_explicit_runtime_route_override` ; `nodeskclaw-backend/app/services/hermes_skill/mcp_tool_mapper.py#McpToolMapper#call_tool` ; `nodeskclaw-backend/app/services/mcp_skill_gateway/handler.py#_copy_frozen_attachment_refs` | `nodeskclaw-backend/app/services/hermes_skill/runtime_skill_run_service.py#RuntimeSkillRunService#_enqueue_agent_run_outbox` | - | no |
| T2 | C09 | `nodeskclaw-backend/app/api/runs.py#_public_run_event` ; `nodeskclaw-backend/app/api/runs.py#_public_run_view` ; `nodeskclaw-backend/app/api/runs.py#_public_run_result` ; `nodeskclaw-backend/tests/hermes_skill/test_employee_runs_api.py` | `nodeskclaw-backend/app/api/runs.py#_public_run_view` | - | no |
| T3 | C11 | `docs_agent/evidence/rm09-verification.md` ; `lat.md/architecture/skill-agent.md#Runtime Delegation Boundary` | `docs_agent/roadmaps/ROADMAP-SKILL-AGENT-V16.md` | T1; T2 | no |

## Integration Hotspots

None

## Generated Outputs Ledger

| Output | Producer Todo | Generator | Consumers | Checked By |
|---|---|---|---|---|


## New File Justification

| Change ID | File | Necessity | Owner Impact |
|---|---|---|---|
| C11 | `docs_agent/evidence/rm09-verification.md` | AC/DoD 出口证据必须可引用 | T3 只写本项证据 |

## Todo T1 — MCP Catalog 与 tools/call overlay 隔离

**Owns Changes**
- C07
- C08

**Goal**
员工 MCP Catalog 不暴露 Internal 南向字段；tools/call overlay 不能覆盖服务器冻结 Topology。

**Immediate anchors**
- `nodeskclaw-backend/app/services/hermes_skill/mcp_tool_mapper.py#McpToolMapper#_skill_to_tool_dict`
- `nodeskclaw-backend/app/services/hermes_skill/mcp_tool_mapper.py#McpToolMapper#list_tools`
- `nodeskclaw-backend/app/services/mcp_skill_gateway/handler.py#_copy_frozen_attachment_refs`

**Changes**
- Catalog 投影显式丢弃 `delegation_topology`、`runtime_capability_ref`、snapshot、成员/profile Internal 键；禁止 `tool.update(release_extra)`。
- 扩展 forbidden argument keys；`_has_explicit_runtime_route_override` 与 `call_tool` 使用同一集合；`client_context` 拷贝路径剥离同样的键。
- 测试：extra_metadata 含 Topology 时 list 仍干净；overlay 不进入 enqueue 冻结值。

**Stop conditions**
- [ ] V01 V02 V03 PASS

**Triggered reads**
- None unless a listed trigger becomes true

## Todo T2 — Public Run/SSE Internal 键否定 oracle

**Owns Changes**
- C09

**Goal**
Public GET/SSE/result 不泄漏 Internal 南向字段或内部 trace；公开面单一 Parent Run。

**Immediate anchors**
- `nodeskclaw-backend/app/api/runs.py#_public_run_event`

**Changes**
- 增加 Internal 键与 `internal.runtime.trace` 否定测试。
- 若现有白名单已丢弃则保持实现；若测试发现泄漏，仅在 `_public_run_event` / `_public_run_view` / `_public_run_result` 收紧。

**Stop conditions**
- [ ] V04 PASS

**Triggered reads**
- None unless a listed trigger becomes true

## Todo T3 — Public 空 diff、回归、lat.md 与出口证据

**Owns Changes**
- C11

**Goal**
证明未改写 Public/Internal 合同，RM-16 仍 BACKLOG，lat 与出口证据闭环。

**Immediate anchors**
- `docs_agent/evidence/rm09-verification.md`
- `lat.md/architecture/skill-agent.md#Runtime Delegation Boundary`

**Changes**
- 跑 V05–V09；写入 `docs_agent/evidence/rm09-verification.md`。
- lat 写明员工公共面不暴露 Internal Topology。
- 本 Todo 不把 RM-09 标 DONE。

**Stop conditions**
- [ ] Public 空 diff、RM-16 BACKLOG、lat check PASS

**Triggered reads**
- None unless a listed trigger becomes true

## Verification

Run all blocking Verification Ledger entries through `smc-plan-delivery/scripts/evidence.py`.

## Completion Gate

| Exit State | Allowed When | Blocking Evidence |
|---|---|---|
| IMPLEMENTED_AND_PROVEN | all Cursor todos completed; completion audit FRESH PASS; implementation review FRESH PASS; all blocking Verification FRESH PASS; durable Evidence Manifest FRESH | V01 V02 V03 V04 V05 V06 V07 V08 V09 via markdown evidence export |
| IMPLEMENTED_NOT_PROVEN | implementation exists but proof is pending/stale | pending/stale gate IDs |
| BLOCKED | environment/dependency prevents proof | blocker record |
| RETURN_PRD | approved owner/boundary conflicts | PRD revision request |
