# PRD Review

**Artifact:** `docs_agent/prd-v1.6.10-skill-run-v121-public-conformance.md`  
**Mode:** initial  
**Verdict:** PASS

## Evidence Reuse

- `source_revision`: `AD-SKILL-AGENT-V16@1.5.0/RM-12`（与 APPROVED Architecture `AD-SKILL-AGENT-V16@1.5.0`、Roadmap Item RM-12 一致）
- `grounded_commit`: `630da4e9c7a0d48910467fc2b375c65e95610f95`（与 HEAD 相同；subject 为 `docs(roadmap): 增加 RM-12 冻结 v1.2.1 公共面符合性`）
- Architecture v1.5.0 `APPROVED`；Roadmap RM-06 / RM-11 `DONE`；RM-12 `READY` 且 Depends On 均为 DONE；RM-09 仍 `BACKLOG` 且依赖 RM-08
- `python tools/agent-skills/validate_prd.py docs_agent/prd-v1.6.10-skill-run-v121-public-conformance.md --require-evidence`：通过
- `python tools/agent-skills/evidence_freshness.py ... --source-revision AD-SKILL-AGENT-V16@1.5.0/RM-12`：`REUSE`（source 与仓库 revision 未变）
- 本轮不做 full Grounding；只对 PRD 已记录锚点做独立 Gate 判断，并抽查 MCP 入队拷贝、Workspace 证明、HermesTask 幂等、Public 信封与 SSE 白名单

## Blocking Findings

无。RM-12 是 READY 项的唯一 Stage PRD；工作包合同 `SKILL-RUN-CONTRACT@1.2.1` 保持 RELEASED；未把仓外 Work 或 RM-04 分布式验收当作本项退出条件。

## Major Findings

无。Installation Routing 与 Execution Authorization 分列，Workspace ACL / Agent Event SoT / 冻结合同均为 KEEP。C01–C07 都是既有 Owner 上的 MODIFY；C04 把 TTL 预留限制在 Runtime Skill Run Owner 内，未新建 Idempotency Service。C08 禁止改写 v1.2.1。用户草稿未再充当 SOT。

## Minor Findings

1. **员工幂等冲突的运输面需要 Plan 写死，但不足以 REVISE。** 冻结合同同时给出 `tools/call` success `[200]`、全局 `idempotency.conflict.status=409` 与 JSON-RPC `error.data.errorCode`。当前 `POST /api/v1/mcp` 捕获 `AppException` 后仍 HTTP 200 返回 JSON-RPC；`IDEMPOTENCY_CONFLICT` 未进入 MCP jsonrpc numeric code 表，会回退 `-32060`。AC-07 的 HTTP 409 + `IDEMPOTENCY_CONFLICT` 成立，但必须保持 MCP JSON-RPC 错误信封，不得掉进 Portal `{code:40900}`，也不得改全局 exception handler。REST `/api/v1/runs/*` 不是幂等入口。
2. **C01/C07 一行两个 Production Owner。** Product Boundary 已冻结 Runtime Skill Run 为 `execution.workspace_id` 的唯一写入者。Plan 必须把 WRITE_OWNER 拆开：MCP Gateway 只停止注入 Installation Workspace 并停止合并 Installation/HermesTask 身份；Runtime 负责证明、装配与 accepted 合同字段。不得形成第二套授权上下文。
3. **「显式受信任 Execution Workspace」没有员工公共请求字段。** v1.2.1 manifest 将 `attachments` 标为 `unsupported`。AC-03/AC-04 是内部/RM-06 回归，不得为迁就附件而新增 Public workspace 请求字段（那会改合同，违反 C08）。Prompt-first 员工面以 AC-01/AC-02/AC-09 为准。
4. **员工 `event_stream` 不得附带 Hermes task token。** Evidence 已记录 employee 分支会把 Hermes SSE `token=` 拼到 `/api/v1/runs/{id}/events`。Public 事件流走员工鉴权，AC-09 的「指向 `/api/v1/runs/...`」应理解为无内部 token 查询串。
5. **Accepted 状态必须用合同枚举。** Evidence 已记录 queued 被写成 `RUNNING`；冻结 fixture 为 `QUEUED`。AC-09「合同状态」覆盖此点，Plan 不得继续输出 `running`/`RUNNING` 冒充已接受。
6. **Inventory 将消费端验收资产标 MODIFY，Change Classification 无对应 Change ID。** AC-16 已约束本仓 consumer Postman/Newman 只作符合性证据、不宣称 RM-04 DONE。Plan 可复用既有 collection，不得把双 Central / 故障注入写进本项 Todo。
7. **C05 投影必须符合对应 payload schema。** 不能只扩大 event_type 白名单；`reasoning.summary` / `tool.call` / `clarify.requested` / `approval.requested` 的 payload 形状以冻结 `run-event.schema.json` 为准，禁止自然语言补字段。
8. **C03 历史失效引用的可观察范围。** 「不得作为活跃路由继续使用」不等于本项做全量数据产品化清理。新写入拒绝 + 活跃路由不再用失效 ID 即可；exact 迁移归 Plan。

## Plan Notes

- 禁止执行用户草稿 `docs_agent/prd-hotfix-skill-run-v1.2.1-postman-ready.md` 中的 SQL、新表名或文件清单；以本 PRD 的 C/AC 为 SOT。
- 禁止改写 `contracts/skill-run/v1.2.1/` 或移动 tag `skill-run-contract-v1.2.1`。
- 禁止新建 Idempotency Service；HermesTask 键可作回放锚点，TTL 必须能在不软删除任务的前提下过期。
- 禁止删除 Workspace ACL；禁止用 Installation Workspace 填附件/办公室缺口。
- 禁止把 fingerprint 去重当成 C04 幂等合同；`X-Idempotency-Key` 是员工公共幂等入口。
- 禁止把 Resume/Approve 或内部南向字段升格为 v1.2.1 承诺。
- 禁止把本项 Todo 并进 RM-04 / RM-07 / RM-10，或把仓外 Work 联调当作 Verification。
- Expert `/api/v1/hermes/tasks/*` 可保留，但不得再出现在员工 accepted / Public Run / SSE 面上。

## Closure Table

| Gate | Result | Evidence |
|---|---|---|
| G1 Scope（范围） | PASS | 只覆盖冻结 v1.2.1 员工公共面实现符合性；Non-Goals 排除改合同、RM-09、RM-08、RM-04 分布式验收、仓外 Work、新幂等服务 |
| G2 Existing Capability / duplicate owner（现有能力/重复归属） | PASS | Catalog/合同/ACL/Event SoT 为 EXISTS→KEEP；入队、证明、幂等、信封、SSE 为 PARTIAL→MODIFY；无把已有能力标成 MISSING 再 ADD 服务 |
| G3 Production Ownership（生产归属） | PASS | Runtime Skill Run 唯一装配 `execution.workspace_id`；Installation 只持路由元数据；Agent 仍是 Event/终态 Owner；Skill Run API 只投影。Minor 2 不改变 Owner 集合 |
| G4 KEEP/MODIFY/ADD/REPLACE/REMOVE（变更分类） | PASS | 无 REPLACE；无 ADD 新服务；C04 扩展存储仍在同一 Owner。Minor 6 验收资产无独立 Change ID，不改变分类方向 |
| G5 API/IPC/Auth/Contract/Security Boundary（接口/鉴权/合同/安全边界） | PASS | `org_id` 租户边界、跨组织 fail-closed、Public 无 HermesTask 身份、合同 KEEP 均已写。Minor 1/3/4 是运输与输入澄清，不改变边界 Owner |
| G6 Behaviour -> Acceptance Criteria（行为到验收） | PASS | C01↔AC-01/02/04，C02↔AC-02/03/14，C03↔AC-05，C04↔AC-06/07/08，C05↔AC-12/13，C06↔AC-10/11/14，C07↔AC-09，C08↔AC-15，C09↔AC-04/14，C10/总闸↔AC-16 |

## Independent Spot Checks

以下抽查对应当前 HEAD/`grounded_commit` `630da4e9`，用于独立判断，不是重新 discovery。代码树相对 Architecture `3d5a056c` 无 diff。

| Claim | Result |
|---|---|
| 员工 MCP 把 Installation Workspace 写入 Runtime 请求 | 已证实：员工 `org_mcp` 两条 Runtime 路径均 `workspace_id=installation.workspace_id` |
| Runtime 只要请求带 `workspace_id` 就进 Workspace 证明 | 已证实：`_build_authorized_execution_context` 在 `request.workspace_id` 为真时调用 `_assert_workspace_proof` |
| Workspace 证明不校验请求 `org_id` | 已证实：`org_id` 只进入 auth_version 哈希；`check_workspace_access` 按 Workspace 自己的组织查成员 |
| 办公室不存在返回 `errors.workspace.not_found` | 已证实 |
| Installation `workspace_id` 无引用完整性 | 已证实：可空 `String(36)`，无 FK |
| 幂等复用 HermesTask 键且无 TTL | 已证实：`find_idempotent_task` 与 `uq_hermes_tasks_idempotency_alive` 无过期条件；合同 TTL=86400 |
| Public 成功体套 Portal 信封 | 已证实：`GET /runs/{id}` 返回 `{"code": 0, "data": _public_run_view(...)}` |
| Public SSE 丢弃部分语义事件 | 已证实：`_public_run_event` 不放行 `reasoning.summary` / `tool.call` / `clarify.requested` / `approval.requested` |
| 员工 accepted 再合并 Installation 身份 | 已证实：`_merge_org_mcp_async_payload` 写入 `agent_id` / `workspace_id` / `installation_id` 等 |
| v1.2.1 已发布且不可改写 | 已证实：RM-11 DONE；tag `skill-run-contract-v1.2.1`；PRD C08 KEEP |
| RM-12 依赖已完成且未并入 RM-09 | 已证实：Roadmap RM-12 READY 依赖 RM-06, RM-11；RM-09 BACKLOG 依赖 RM-08 |
| 本阶段不做 full Grounding | 已证实：`evidence_freshness` 为 `REUSE` |

## Conclusion

该 Stage PRD 可以进入 `smc-prd-converge`。Minor 项写入 Plan 约束即可，不必 `smc-prd-grounding revision`。converge 不得改 C01–C10 的 Owner/Action，不得把用户草稿重新升为 SOT，不得把 RM-12 标成 RM-09。

本审查不修改 PRD，不 git commit。
