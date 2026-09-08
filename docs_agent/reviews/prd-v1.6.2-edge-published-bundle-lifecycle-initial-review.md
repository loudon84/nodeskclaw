# PRD Review

**Artifact:** `docs_agent/prd-v1.6.2-edge-published-bundle-lifecycle.md`  
**Mode:** initial  
**Verdict:** REVISE

## Evidence Reuse

- `source_revision`: `AD-SKILL-AGENT-V16@1.0.0/RM-03`（与 APPROVED Architecture `AD-SKILL-AGENT-V16@1.0.0`、Roadmap Item RM-03 一致）
- `grounded_commit`: `884e2e334b4a024bae9fefd7b78425f97c029d4c`（与 HEAD 相同）
- Roadmap：RM-01 `DONE`，RM-02 `DONE`（implementation `e3744c4b`），RM-03 `IN_PRD`，RM-04 `BACKLOG`
- `python tools/agent-skills/validate_prd.py docs_agent/prd-v1.6.2-edge-published-bundle-lifecycle.md --require-evidence`：通过
- `python tools/agent-skills/evidence_freshness.py docs_agent/prd-v1.6.2-edge-published-bundle-lifecycle.md --source-revision AD-SKILL-AGENT-V16@1.0.0/RM-03`：`REUSE`（source 与仓库 revision 未变）
- 未提交工作树（plans、artifacts）不计入本审查
- 本轮不做 full Grounding；只对 PRD 已记录锚点做独立 Gate 判断，并抽查关键 Owner/合同行为

## Blocking Findings

无。Roadmap Item RM-03、APPROVED Architecture、RM-02 依赖 `DONE`、源码基线和 Evidence Baseline 均可解析。

## Major Findings

1. **失败 Actual 无法同时满足 AC-08 与现有 Backend Actual 写规则，且无 Change 拥有 Backend 这一侧。**  
   AC-08 要求 Edge 失败时上报稳定错误、**不得推进 `actual_generation`**、不得声称 `ready`。AC-09 要求 Actual 的 `generation == desired_generation`。  
   抽查 `report_installation_actual`：只要 `generation == desired_generation`，就会无条件执行 `installation.actual_generation = body.generation`，不区分 `ready` / 失败。Edge Worker 调谐条件是 `desired_gen != actual_gen`；一旦失败上报也把 `actual_generation` 推到 Desired，安装不会重试，与 Architecture / `lat.md`「失败保持可重试」冲突。  
   若 Edge 改用旧 `actual_generation` 上报失败，Backend 会按 `generation < desired_generation` 当作过期拒绝。  
   C04 Owner 只写 `Agent EdgeWorker`；C02 只覆盖 Desired 与授权下载，不覆盖 Actual 失败语义。这改变可观察调谐行为与 Actual 合同，必须在 Change Classification 中给 Backend Installation / Internal Edge 一个明确 MODIFY（或把 C04 Owner 扩成与 Target 表一致的双域），并冻结：失败 Actual 在同代可被接受、写入稳定错误、**不**把 `actual_generation` 提升为已成功对齐 Desired。

## Minor Findings

1. C01 Owner 写成 `Backend Hermes Skill Release / existing storage boundary`。Architecture 的发布事实源是 Hermes Skill 域；存储应 KEEP 现有 Backend 存储边界，不是第二 Bundle Service。以 Change Classification 的 Release Owner 为准，不要在 Plan 里另起存储 Owner。
2. Target「Immutable Bundle Descriptor」含 opaque bundle reference；AC-01 只锁 release ID、版本、size、SHA-256。引用字段由 AC-02 禁止 Storage Key / 长期 URL，Plan 必须冻结不透明引用形态，且不得把存储凭据写入 Desired。
3. `HermesSkillRelease.digest` 是工作副本内容摘要（`compute_skill_content_digest`），不是 ZIP SHA-256。C01 必须把包 size/SHA-256 与现有 content digest 分开，避免把工作副本 digest 当成 Bundle 校验值。
4. Architecture 要求 Bundle Descriptor 优先扩展现有 JSONB；DOD-03 允许新列+Alembic。PRD 未冻结 JSONB vs 新列。这不改 Owner；Plan 仅在 JSONB 无法稳定承载时才加列。
5. `report_installation_actual` 仅在 `installation.edge_node_id` 非空时校验节点。Edge 安装记录按现有 unique index 应有 `edge_node_id`；AC-09 跨节点拒绝仍应以节点绑定为准，不要弱化成只比 org。

## Plan Notes

- 在 Major #1 关闭前不要实施。失败路径的 Backend Actual 合同必须先写进 PRD Change/AC。
- C02 在现有 Internal Edge（`X-Edge-Token`、org/node、generation 栅栏）上增加受控字节流，不要新建 Bundle 下载服务，也不要复用 Run Artifact on-demand 或 Hermes Expert/实例 ZIP 安装路径（`expert_filesystem` / `upload_skill_zip` 是另一域）。
- C03 修改现有 `EdgeSkillInstaller`：当前 `install` 会先 `rmtree` 目标目录，checksum 失败也会删目录；`extractall` 前只有 `..` 前缀检查，不拒绝 ZIP 符号链接。必须先暂存再验证再切 Current。
- C04 当前 `_reconcile_desired_installations` 在 `desired_gen != actual_gen` 时调用 `install` 且不传 `zip_bytes`，成功后即报 `ready`。必须先走 C02 字节流，C03 成功后才同代 `ready`。
- 卸载 KEEP Backend `SkillInstaller#uninstall`（`uninstalling` + 递增 Desired Generation）；Agent 只做受控根内删除并报同代 `uninstalled`。
- 员工仍只访问 Backend；Edge 只出站。不要新增 Agent 公共下载入口。

## Closure Table

| Gate | Result | Evidence |
|---|---|---|
| G1 Scope（范围） | PASS | 只覆盖 Published Bundle 描述符、授权下载、安全展开/原子激活/卸载、同代 Actual；排除 Bundle Service、第二 Installation 状态机、客户端直连 Agent、永久 URL、存储凭据、RM-04、Work UI |
| G2 Existing Capability / duplicate owner（现有能力/重复归属） | PASS | 复用 SkillRelease、Desired/Actual、Internal Edge Token、EdgeSkillInstaller、EdgeWorker、SkillInstaller 卸载代次；缺口是不可变包描述符、授权字节流、原子回滚与失败不虚报代次。实例 ZIP / Expert filesystem 不是本阶段 Owner |
| G3 Production Ownership（生产归属） | **FAIL** | Backend 仍应是发布与 Installation Desired/Actual 唯一控制面；Agent 仍应是唯一文件副作用 Owner。但失败 Actual 是否推进 `actual_generation` 没有 Backend Change Owner，与 AC-08/AC-09 和现有写入行为冲突 |
| G4 KEEP/MODIFY/ADD/REPLACE/REMOVE（变更分类） | PASS（附 Major） | PARTIAL→C01–C04 MODIFY；卸载控制事实 KEEP。无 REPLACE，无需 REMOVE。Major #1 要求补一条 Backend Actual 失败语义的 MODIFY，而不是新增服务 |
| G5 API/IPC/Auth/Contract/Security Boundary（接口/鉴权/合同/安全边界） | PASS（附 Major） | Work 仍只走 Backend；Edge 出站 + Edge Token；禁止永久 URL/凭据进入 Snapshot/Desired/Actual/日志。Actual 失败合同未冻结，见 Major #1 |
| G6 Behaviour -> Acceptance Criteria（行为到验收） | **FAIL** | C01→AC-01/02，C02→AC-03/04，C03→AC-05/06/07 可观察。AC-08 与 AC-09 叠加现有 Actual 写入后无法同时成立；C04 未覆盖 Backend 失败对齐行为 |

## Independent Spot Checks

以下抽查对应当前 HEAD/`grounded_commit` `884e2e33`，用于独立判断，不是重新 discovery。

| Claim | Result |
|---|---|
| Desired/Actual 已有 org/node 与 generation 栅栏 | 已证实：`get_desired_installations` 按 org + `edge_node_id` 过滤；`report_installation_actual` 拒绝跨 node、旧代、超前代；同代写入 `actual_generation`/`actual_status` |
| Desired 不含可信 Bundle 引用/大小/摘要 | 已证实：返回 `id`/`skill_id`/`desired_status`/`desired_generation`/`actual_generation`/`install_metadata`/`routing_metadata`，无 release/size/SHA-256/包引用 |
| Edge 安装为空目录而非真实包 | 已证实：`_reconcile_desired_installations` 调用 `install` 不传 `zip_bytes`；无 zip 时只建目录并写 `installation_meta.json` 后报 `ready` |
| Installer 有摘要和路径穿越检查，但没有原子回滚 | 已证实：有 SHA-256 与 `..` 前缀检查；安装前 `rmtree` 目标；checksum 失败再 `rmtree`；`extractall` 不拒绝符号链接；无暂存/Current 切换 |
| Edge 卸载由 Desired Generation 驱动 | 已证实：`SkillInstaller.uninstall` 对 edge 置 `uninstalling` 并递增 `desired_generation`；Worker 卸载后报同代 `uninstalled`；Backend 再软删除 |
| Published Release 已冻结 content digest | 已证实：`HermesSkillRelease.digest` + `publish` 不回写工作副本；digest 来自 skill 内容哈希，不是 ZIP 包摘要；无 Bundle size/SHA-256 字段 |
| 不存在员工/Edge 技能包下载合同 | 已证实：Internal Edge 有 Run Artifact on-demand/中继，无 Installation Bundle 字节流；Expert/实例 `upload_skill_zip` 属另一域 |
| 失败 Actual 会推进代次并停止重试 | 已证实：Actual 成功条件只比 `generation == desired_generation`；Worker 仅在 `desired_gen != actual_gen` 时安装 |

## Conclusion

该 Stage PRD **不能**进入 `smc-prd-converge`。下一步：`smc-prd-grounding` **revision**，只关闭 Major #1（Backend 失败 Actual 与 `actual_generation` 合同 + 对应 Change Owner/AC），并顺手收紧 Minor 中与 Owner/描述符字段分叉相关的表述。不得改 Architecture，不得把 Edge 做成第二 Installation 状态机，不得引入 Bundle Service。

本审查不修改 PRD，不 git commit。
