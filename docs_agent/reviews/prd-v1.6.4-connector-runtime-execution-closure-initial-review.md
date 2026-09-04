# PRD Review

**Artifact:** `docs_agent/prd-v1.6.4-connector-runtime-execution-closure.md`  
**Mode:** initial  
**Verdict:** PASS

## Evidence Reuse

- `source_revision`: `AD-SKILL-AGENT-V16@1.1.0/RM-05`（与 APPROVED Architecture `AD-SKILL-AGENT-V16@1.1.0`、Roadmap Item RM-05 一致）
- `grounded_commit`: `8ed46fc35e766898a0ffaa45624ebc7caa596123`（与 HEAD 相同）
- Roadmap at HEAD：RM-01 `DONE`（`3a9b012a`）、RM-02 `DONE`（`e3744c4b`）、RM-03 `DONE`（`d6e7cb80`）、RM-04 `IN_PRD`、RM-05 `IN_PRD`（依赖 RM-03，Architecture 允许与 RM-04 分支推进）
- `python tools/agent-skills/validate_prd.py docs_agent/prd-v1.6.4-connector-runtime-execution-closure.md --require-evidence`：通过
- `python tools/agent-skills/evidence_freshness.py docs_agent/prd-v1.6.4-connector-runtime-execution-closure.md --source-revision AD-SKILL-AGENT-V16@1.1.0/RM-05`：`REUSE`（source 与仓库 revision 未变）
- 未提交工作树（Agent readiness/storage、acceptance harness、Roadmap working tree、plans、lat.md）不计入本审查
- 本轮不做 full Grounding；只对 PRD 已记录锚点做独立 Gate 判断，并抽查关键 Owner/合同行为

## Blocking Findings

无。Roadmap Item RM-05、APPROVED Architecture v1.1.0、RM-03 依赖 `DONE`、源码基线和 Evidence Baseline 均可解析。RM-04 仍为 `IN_PRD` 不构成本阶段 BLOCKER。

## Major Findings

无。未发现会改变合同、安全边界、唯一 Production Owner 或可观察 Behaviour 的缺口。C01–C08 都是对既有 Backend Connector / Agent Engine Port / Run Worker / Adapter 的 MODIFY 或 REPLACE+REMOVE；C09/C10 KEEP。AC-01–AC-16 覆盖统一入口、单次派发、审批、SecretRef、Trust Policy、DB 只读、取消/Fencing 和合同不回归。RM-05 不新增 Connector 服务、第二 Run 状态机、仓内 Work 前端或公共合同版本。

## Minor Findings

1. C05 Owner 写成 `Backend SecretRef + Agent SecretStore`。AC-10 的明文拒绝发生在 Connector Instance 创建/更新或发布门禁，现有实现是 `ConnectorService` 写入自由 JSONB `config`。以 Behaviour/SecretRef 节为准：C05 包含 Backend Connector 配置准入，不要把 C09 KEEP（组织隔离/软删除/公开门禁/路由覆盖拒绝）理解成禁止增加明文拒绝。
2. 现有 `_validate_ssrf` 对非 IP 主机名 `ValueError` 后直接放行，并不做 `getaddrinfo`。Inventory 说「私网 IP 已阻断」只对字面 IP 成立。C06/AC-12 必须以解析后地址和每跳重定向为准，不能只给 Edge 加 Allowlist、不补 DNS 复核。
3. Direct Edge 在 Mapper 建 Agent Run 后又直接 `EdgeJob()`；若 Agent Run 的 `placement.role` 不是 `edge`，Central Worker 仍会 claim 并走本地 `execute_engine`。C03 移除 Mapper 平行派发后，必须由 Agent Step Plan 为 Direct Edge 请求唯一 EdgeJob，且 Central 不得把 Edge Connector 当本地 REST/MCP/DB 执行。
4. `_call_connector_tool` 固定 `agent_profile="connector"` / `hermes_agent_instance_id="connector-central"`，随后 `_enrich_route_snapshot` 可能把 Hermes `gateway_url` / `credential_lease_ref` 写进同一 Route。C02 的规范 Connector Snapshot 不得混入 Hermes 物理路由。
5. `execute_engine` 允许的 engine 名是 `connector` / `http_connector` / `mcp_connector`；DB 是 Adapter 内 `connector_kind`。不要新增第四个 `db_connector` engine Owner。
6. AC-08「最终有效策略和来源可审计」是冻结 Snapshot/既有审计字段，不是 RM-10 Trace/Metrics。
7. AC-16 要求从 Backend `tools/call` 进入真实 AgentEnginePort。这不依赖 RM-04 的 Docker/多 Central/MinIO/Newman 两连跑；也不把那些未完成证据写成 RM-05 通过。
8. Catalog 已投影 `requiresApproval`，但不得为 Trust Zone、Edge Node、物理 URL 或 Placement 新增公共输出字段。C09/C10 KEEP 覆盖这条边界。
9. `worker.py` 模块注释仍写 hybrid dispatch 是 no-op，代码已向 `/api/v1/internal/edge/jobs/enqueue` POST。C03 的 Agent 派发 Owner 是这条已有编排链的 MODIFY，Mapper 直建 EdgeJob 才是 REMOVE。

## Plan Notes

- 在 C01 修好 Port/Adapter 参数之前，Central Connector 经 `execute_engine` 会因 `route_snapshot`/`org_id`/`cancel_event` 对不上 `snapshot` 而 TypeError。C08 的取消传播建立在 C01 合同一致之后。
- C02 只统一字段解释：允许传输封装不同，禁止「完整 Snapshot 再嵌套 `runtime_policy`」第二种读法。不要把规范形态做成新的公共 Skill Run 合同字段；需要新公共字段时按 DOD-04 退回 Architecture/Roadmap。
- 去掉 Mapper 平行 `EdgeJob` 后，Central Worker 现有 claim SQL 排除 `placement.role=edge`，且 `needs_edge_jobs` 只看 `runtime_policy.connector_bindings`。Direct Edge 必须仍由 Agent 编排链请求一次派发（claim-to-enqueue 或等价），不能回退成 Backend 在 `start()` 后直插任务。
- Hybrid 的 `_resolve_placement` 只返回 `{role, engine}`，`SkillConnectorBinding` 只有 binding ID。AC-05 的执行描述符要在接受调用时冻结进 Snapshot，不要派发时回读可变 Instance/Binding 补齐。
- C04：Connector Catalog 已声明 `requiresApproval`，`_call_connector_tool` 没有把它写入 `client_context`；`RuntimeSkillRunService` 只读 `client_context`。服务端元数据必须派生有效策略，客户端只能加严。Agent Approval 状态机 KEEP，不要另起审批 Owner。
- C05：`_sanitize_sensitive_keys` 会把含 `secret` 的键整段换成 `[REDACTED]`，`connector_secret_ref_id` 被破坏。保留 opaque ID，剥离明文。Edge `_prepare_snapshot` 不要把解析后的 Authorization/DB URL 写回可持久化 Snapshot 或 Event。
- C06：Trust Zone/Allowlist 是现有 Connector Instance/Definition 策略在 Snapshot 中的冻结，不是新 Policy 服务。Central 默认公网；Edge 仅匹配冻结协议/主机或网段/端口；元数据、link-local、未授权 loopback 永久拒绝。客户端 arguments 不得扩大目标。
- C07：现有门禁是 `SELECT|WITH` 前缀、`AUTOCOMMIT`、忽略 `SET TRANSACTION READ ONLY` 失败。必须以数据库只读事务成功 + 单语句/写 CTE/多语句拒绝 + 超时和行数上限为成功证据。
- C08：Adapter 必须接收 `cancel_event`；HTTP/MCP/DB 可取消；迟到 `completed` 走既有 Fencing，不推进终态。
- 验证必须经 Backend `tools/call` → 真实 `execute_engine` → Adapter。`test_connector_router.py` 的 6 个直调测试和 `test_execute_engine_dispatches_hermes_and_connector_fail_closed`（实际只跑 Hermes 与 unknown engine）不能关闭 C01/AC-16。
- 员工仍只访问 Backend MCP Catalog 与 Run API。不要新增 Agent 公共 Connector 入口，也不要把 RM-07 身份轮换/签名/Nonce 或 RM-06 Session/ContextBuilder 拉进本阶段。

## Closure Table

| Gate | Result | Evidence |
|---|---|---|
| G1 Scope（范围） | PASS | 只覆盖 Connector Definition/Instance/Tool/Binding → 冻结 Route Snapshot → Central/Edge 经 AgentEnginePort 执行；排除新 Connector 服务、第二 Run 状态机、Work 前端、Session/ContextBuilder、Edge Identity 升级、OpenTelemetry，以及把 RM-04 未完成验收宣称为通过 |
| G2 Existing Capability / duplicate owner（现有能力/重复归属） | PASS | 复用 Backend Connector 域、MCP Catalog/Mapper、RuntimeSkillRunService、Agent Engine Port、Connector Adapter、Run/Edge Worker、SecretStore、既有 Approval 状态机。缺口是 Port 合同、Snapshot 多形态、Mapper 平行 EdgeJob、审批派生、SecretRef 脱敏、Trust Policy、DB 只读证明和取消接入。不把 Hermes Enrichment、Task 记录或验收夹具做成第二执行 Owner |
| G3 Production Ownership（生产归属） | PASS | Backend 继续拥有组织鉴权、Connector 配置、Published Binding、审批策略和 Route 冻结；Agent 继续拥有 Run/Attempt/Event/Artifact、取消和终态。EdgeJob 仍是 Backend 控制面行，派发请求唯一归属 Agent Step Plan。未新增第三个服务 |
| G4 KEEP/MODIFY/ADD/REPLACE/REMOVE（变更分类） | PASS | EXISTS→C09 KEEP；PARTIAL→C04/C05/C06/C07/C08 MODIFY；CONFLICT→C01 MODIFY、C02/C03 REPLACE+REMOVE。无 ADD。C10 KEEP 公共合同。Trust Zone 是既有 Connector 策略扩展，不是新服务 |
| G5 API/IPC/Auth/Contract/Security Boundary（接口/鉴权/合同/安全边界） | PASS | 客户端不得提交物理 URL、DB URL、认证 Header、Secret、Edge Node 或 Placement。明文不得进入 Snapshot/Event/Artifact/日志。Central 默认公网、Edge 显式 Allowlist、元数据永久拒绝。Skill Run v1.0/v1.1/v1.2 不原地改写。员工只走 Backend |
| G6 Behaviour -> Acceptance Criteria（行为到验收） | PASS | C01→AC-01/16，C02→AC-02/03/05/06，C03→AC-04/05，C04→AC-07/08，C05→AC-09/10，C06→AC-11/12，C07→AC-13，C08→AC-14/15，C09/C10→AC-03/06/16。AC 描述调用入口、派发次数、审批状态、失败关闭和事件终态，而不是私有符号或测试文件 |

## Independent Spot Checks

以下抽查对应当前 HEAD/`grounded_commit` `8ed46fc3`，用于独立判断，不是重新 discovery。

| Claim | Result |
|---|---|
| Engine Port 与 Connector Adapter 参数合同不一致 | 已证实：`inspect.signature` 显示 Port 传 `route_snapshot`/`org_id`/`cancel_event`；Adapter 只接受 `snapshot`。Python 关键字参数无法绑定 |
| Central/Edge 使用不同嵌套方式传 Connector route | 已证实：Worker 对 connector 传完整 `snapshot`，对 Hermes 传 `runtime_policy`；Adapter 再 `snapshot.get("runtime_policy")`；Edge `_prepare_snapshot` 复制整包后再交给 Port |
| Direct Edge Connector 在 Mapper 创建 Agent Run 后又直接创建 EdgeJob | 已证实：`_call_connector_tool` 在 `RuntimeSkillRunService.start` 之后对 `placement==edge` 直接 `EdgeJob(...)` 并 `db.add` |
| Skill binding IDs 可决定 Placement，但没有冻结 binding 描述符 | 已证实：`_resolve_placement` 只返回 `{role, engine}`；`SkillConnectorBinding` 仅有 release/instance/role；Worker `build_hybrid_step_plan` 依赖 `runtime_policy.connector_bindings` |
| Connector Catalog 审批元数据已存在，但 Run 审批取自 client_context | 已证实：`list_tools` 投影 `requiresApproval`；`_call_connector_tool` 不写入该策略；`RuntimeSkillRunService` 用 `client_context.requires_approval` 决定 `WAITING_APPROVAL` 和 outbox |
| 通用脱敏器会破坏 connector_secret_ref_id | 已证实：`_sanitize_sensitive_keys` 对键名包含 `secret` 的字段整段替换为 `[REDACTED]`；`build_snapshot` 对 `route_snapshot` 调用该函数 |
| REST/MCP 已有基础 SSRF 但全部私网均被拒绝 | 已证实：字面 IP 的 `is_private`/`loopback`/`link-local` 等会拒绝；非 IP 主机名跳过；`follow_redirects=True` 后复核最终 URL 字符串。无 Trust Zone 字段 |
| DB 只读依赖前缀正则且忽略只读事务设置失败 | 已证实：`READ_ONLY_SQL_RE` 只匹配 `SELECT/WITH`；`SET TRANSACTION READ ONLY` 失败 `except: pass`；engine 使用 `AUTOCOMMIT` |
| 现有测试直调 Adapter，未覆盖 Connector Engine Port | 已证实：`test_connector_router.py` 6 个测试均 `execute_connector_run(..., snapshot=...)`；所谓 dispatch 测试只执行 Hermes 成功与 `unknown_engine` fail-closed |
| Skill Run v1.0/v1.1/v1.2 合同已发布 | 已证实：PRD Evidence Baseline 指向 `nodeskclaw-backend/contracts/skill-run/`；本阶段 C10 KEEP，抽查不要求重读合同包内容 |
| Connector 一等领域与 Catalog 路由覆盖拒绝已存在 | 已证实：`ConnectorDefinition/Instance/Tool/Binding/SecretRef` 模型存在；Mapper 拒绝 `_routing`/`_execution`/`route_config` |
| 未提交工作树不是本阶段已实现证据 | 已证实：PRD 写明以 `8ed46fc3` 为准；`evidence_freshness` 为 `REUSE`；working tree 含 RM-04 Agent/harness 改动，不计入本审查 |

## Conclusion

该 Stage PRD 可以进入 `smc-prd-converge`。Minor 项不阻断批准；converge 不得改 Owner、Change Classification 或 AC。未提交工作树若在 implementation 前合入并碰到证据锚点，必须先跑 Evidence Freshness，必要时 targeted reground。

本审查不修改 PRD，不 git commit。
