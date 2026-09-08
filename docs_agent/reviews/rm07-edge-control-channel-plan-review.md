# RM-07 Edge Control Channel Plan Review

**Plan:** `.cursor/plans/rm-07_edge-control-channel-security.plan.md`  
**Cursor wrapper:** `.cursor/plans/rm-07_edge_control_35ae0b87.plan.md`（与 canonical 合同同步，Execute 入口是 canonical）  
**Approved PRD:** `docs_agent/prd-v1.6.8-edge-control-channel-security-closure.md`  
**Mode:** REVISE 后语义审查（上次 REVISE 的四项 Must Fix 已写入 Plan）  
**Verdict:** PASS

## Trigger

`python .agents/skills/smc-plan-review/scripts/assess_plan_review.py .cursor/plans/rm-07_edge-control-channel-security.plan.md` 返回 `REQUIRED`：

- `NEW_DEPENDENCY`
- `MULTIPLE_NEW_PROD_FILES`
- `INTEGRATION_HOTSPOT`
- `SECURITY_OR_TRUST_BOUNDARY`

Contract / Data Flow Closure Matrix 非 `None`。

结构门禁（canonical）：

- `validate_generation_integrity.py` PASS
- `validate_plan.py` PASS

## Review

| Gate | Result | Evidence |
|---|---|---|
| PRD 忠实性 | PASS | C01/C03/C06 仍为 Backend Edge 域；C02/C04 仍为 Agent Edge Worker；C05 KEEP Delivery Generation；C07 KEEP Public Skill Run；C08 KEEP 唯一 Run/Event Owner。未开放 Agent 入站端口、未引入 KMS/Vault、未改写 v1.0–v1.2.1。Portal Edge 节点页仍是既有管理 API 的运营者客户端。 |
| REPLACE/REMOVE 完整 | PASS | 无 REPLACE/REMOVE。静态 Token 停止作为长期信任仍是既有 `_authenticate_edge` / `_headers` 上的 MODIFY。 |
| 单一 Writer / Hotspot | PASS | `internal_edge.py`（含 enroll、auth、command wrap、cancel-check）归 T1；Agent `_headers` / `_claim_job` / `_execute_job` / identity helper / lat.md 归 T2，且 `Depends On T1`。未出现第二 Edge gateway。 |
| 最小实现 | PASS | C02 `NEW_DEPENDENCY`（agent `cryptography`）仍成立：stdlib 无 Ed25519；HMAC 会把长期共享秘密写入 Backend。三份新 PROD 文件仍有 New File Justification。 |
| 跨边界闭环 | PASS | 新增 `Identity bind and issuer trust` 流：producer 为 `EdgeNodeService` bind/rotate（`POST /internal/edge/enroll` 与 rotate）；Required Fields 含 `issuer_key_id`、`issuer_public_key`、可选 previous issuer 与 `issuer_rotation_expires_at`；consumer 持久化 `edge-identity.json`；禁止 Settings 默认签发者、禁止从命令封套安装新公钥；窗口内 dual-verify。Enrollment 不再把 issuer 材料留给 consumer 默认值。 |
| 信任边界未被最小化削弱 | PASS | (1) `check_edge_job_cancel` 纳入 C03 wrap 与 C04 `_execute_job` 验签；V04 oracle 要求 unsigned `cancel_requested` 不得 `cancel_event.set()`。Triggered Read 不再把 cancel 排除在命令完整性之外。(2) `EdgeControlNonce` 改为 `OperationAuditLog` 式 append-only：`Base`、无 `deleted_at`、全表 unique、本阶段不软删不物理删。Lifecycle / V09 已删除 `deleted_at IS NULL` 的 Nonce 表述。 |

## Prior Must Fix

1. **Backend 签发者信任材料** — 已写入 Contract Matrix 独立流，bind/rotate 为权威 producer。`previous_issuer_*` 在无签发者轮换时可为 null，但 schema 由 Backend 下发，Agent 不得默认。  
2. **AC-04 封套覆盖 cancel-check** — C03/C04 Change Matrix、T1/T2 Writes、V04/V05 oracle 已同步。现网 `_cancel_loop` 副作用被显式覆盖。心跳/续租 JSON 明确禁止无封套 `rotation_required` 作为状态机触发。  
3. **Nonce 与软删除** — append-only 全表唯一；与 DOD-03「删除走逻辑删除」不冲突：Nonce 本阶段不被删除，例外模式与 `OperationAuditLog` 相同。  
4. **可验证 Plan 载体** — canonical `.cursor/plans/rm-07_edge-control-channel-security.plan.md` 的 YAML frontmatter 含 `plan_contract` / `commit_policy: post_review` / `source_revision` / `grounded_commit` / `grounding_source`。

## Notes

- C02 向 agent 增加 `cryptography` 不构成 PRD 禁止的「外部依赖服务」；不得再引入 KMS/Vault。
- C05 KEEP 与 T1 文件级拥有 `internal_edge.py` 可以共存，但 T1 改 `_authenticate_edge` 时不得改 Delivery Generation 谓词；V06 仍是阻断回归。
- DOD-02 现挂 V08 + V10。
- Execute 入口是 canonical 文件，不是 Cursor 包装文件的旧代码块 frontmatter。包装文件已与 canonical 同步且 `validate_plan.py` 亦 PASS。

## Conclusion

上次 REVISE 的四项均已在 Plan 内闭环，Owner/Capability/Hotspot/`NEW_DEPENDENCY` 仍忠实于 APPROVED PRD。本审查 **PASS**。可以按 `commit_policy: post_review` 进入 Execute（T1 然后 T2）；Todo 完成不得 commit。
