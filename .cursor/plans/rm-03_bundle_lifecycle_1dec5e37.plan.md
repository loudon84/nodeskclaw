---
plan_contract: smc.plan.v3.2
commit_policy: post_review
source_revision: AD-SKILL-AGENT-V16@1.0.0/RM-03
grounded_commit: 884e2e334b4a024bae9fefd7b78425f97c029d4c
grounding_source: committed_baseline
working_tree_fingerprint: clean
---

# RM-03 Edge Published Bundle 生命周期实施计划

Canonical 落盘路径：[`.cursor/plans/rm-03_bundle_lifecycle_1dec5e37.plan.md`](rm-03_bundle_lifecycle_1dec5e37.plan.md)

`commit_policy: post_review`。执行顺序：`Execute -> Review -> Verification -> Commit Implementation`。Todo 完成不得 commit。跨边界流非 None，Execute 前必须 `smc-plan-review` PASS。

## 前端表现变化

本次改动无前端表现变化。不改 Portal / Admin / Work 页面、按钮、文案或路由。员工与管理员仍只访问 Backend；Edge 仍只出站带 `X-Edge-Token`（边缘令牌）。

## Approved PRD

[Approved PRD](docs_agent/prd-v1.6.2-edge-published-bundle-lifecycle.md)

## Scope

- In: 发布时冻结不可变 ZIP 与包 SHA-256（与 content digest 分开）；Internal Edge Desired 返回最小描述符并提供代次栅栏字节流；Installer 暂存-校验-原子切换与受控卸载；Worker 成功才报同代 `ready`/`uninstalled`；Backend 同代失败接受错误但不推进 `actual_generation`。
- Out: Bundle Service、第二 Installation 状态机、客户端直连 Agent、永久下载 URL、存储凭据、Expert/实例 ZIP 安装域、Run Artifact on-demand 复用为包 Owner、发布时自动 bump 全部 Edge 代次、RM-04、Work UI。
- Production Owner inherited from PRD: Backend Hermes Skill Release（C01）、Backend Internal Edge（C02/C05）、Agent EdgeSkillInstaller（C03）、Agent EdgeWorker（C04）。卸载控制事实 KEEP [`SkillInstaller#uninstall`](nodeskclaw-backend/app/services/hermes_skill/skill_installer.py)。

Plan 级冻结（不改 PRD 语义）:

- `bundle_ref` 为 UUID 字符串，不是路径；字节落在 `{HERMES_SKILL_HUB_ROOT}/releases/{bundle_ref}.zip`，该路径不得出现在 Desired、Actual、Snapshot、日志。
- 模型新增列 `bundle_ref` / `bundle_sha256` / `bundle_size_bytes`，与现有 `digest`（内容摘要）并存。
- Desired 项增加 `bundle` 对象：`release_id`、`bundle_ref`、`version`、`size`、`sha256`。卸载态或无已发布 Release 时省略 `bundle`。不改冻结的 Skill Run v1.1.0/v1.2.0 `InstallationRead` schema。
- 同代描述符钉在 `install_metadata.published_bundle`（含 `generation`）。`get_desired_installations` 在钉与 `desired_generation` 不一致时按当前 published Release 重钉。下载只服务该钉，不接受客户端 path/URL/摘要覆盖。
- 下载：`GET /api/v1/internal/edge/installations/{installation_id}/bundle?generation=`，`X-Edge-Token`，`StreamingResponse` `application/zip`。
- Current 用 `{skill_id}/current.json` 指针，不用符号链接（Windows 与攻击面）。ZIP 符号链接条目必须拒绝。
- 同代 `ready` / `uninstalled` / `removed` 才把 `actual_generation` 对齐 Desired；`error` 写入 `error_message` + `meta.error_code`，不对齐代次。
- Plan C05 承接 PRD C04 的 Backend Actual 半边，与 C02 同文件同 Todo，避免 `internal_edge.py` 双写者。

```mermaid
flowchart LR
  publish[publish] --> hub[HubZipAndColumns]
  hub --> desired[DesiredBundlePin]
  desired --> download[AuthorizedZipStream]
  download --> installer[StageVerifySwap]
  installer --> actual[ActualReport]
```

## Grounding Evidence Ledger

| Change ID | Target | Baseline State | Symbol / Entry Resolution | Caller / Callee Evidence | Existing Reuse Search | Result |
|---|---|---|---|---|---|---|
| C01 | `nodeskclaw-backend/app/services/hermes_skill/skill_release_service.py#SkillReleaseService#publish` | PARTIAL at `884e2e33` | `publish` 存在；只翻 status，不写字节 | `releases_router` / `skills_router` -> `publish`；`get_skill` 已取 `canonical_path` | Hub 文件系统是技能字节 Owner；`digest` 是 metadata hash；禁止 `storage_service` / `expert_filesystem` / `agent_bundle_service` | PASS |
| C02 | `nodeskclaw-backend/app/api/internal_edge.py#get_desired_installations` | PARTIAL | 函数存在；`_authenticate_edge` + org/node 过滤 | EdgeWorker GET Desired；无 bundle 字段、无下载路由 | Run Artifact on-demand 与 Expert ZIP 是另一域；`install_metadata` JSONB 可钉描述符；FastAPI `StreamingResponse` 已用于其它下载 | PASS |
| C03 | `nodeskclaw-agent/app/services/edge_skill_installer.py#EdgeSkillInstaller#install` | PARTIAL | `install`/`uninstall`/`_get_skill_dir` 存在 | Worker 调 `install` 不传 `zip_bytes`；有 SHA 与 `..` 检查，预 `rmtree`，`extractall` 不拒符号链接 | 复用 stdlib `zipfile`/`hashlib`/`os.replace`；不引入 Backend `PathGuard` | PASS |
| C04 | `nodeskclaw-agent/app/services/edge_worker.py#EdgeWorker#_reconcile_desired_installations` | PARTIAL | 函数存在；inline httpx | `desired_gen != actual_gen` 时建空目录并报 `ready`；异常只 `logger.debug` | 下载 helper 仿 `_request_artifact` 放在同一 class；不新建 client 模块 | PASS |
| C05 | `nodeskclaw-backend/app/api/internal_edge.py#report_installation_actual` | PARTIAL | 函数存在；同代无条件写 `actual_generation` | Worker POST Actual；已拒跨 node/旧代/超前代；`error_message` 列存在但未写 | 不新建 Actual API；卸载 `uninstalled`/`removed` 软删除 KEEP | PASS |

## Requirement Coverage Ledger

| Requirement | Source | Obligation | Classification | Change IDs | Todo | Verification IDs | Evidence Class | Blocking |
|---|---|---|---|---|---|---|---|---|
| AC-01 | AC | 每个 Edge 目标的 Published Bundle 描述符必须绑定单一已发布 Release，包含稳定 release ID、opaque bundle reference、版本、size 和包 SHA-256；包 SHA-256 不得用现有 content digest 冒充。发布后工作副本或同名后续 Release 变化不得改变该描述符。 | CONTRACT | C01 | T1 | V01 | INTEGRATION | yes |
| AC-02 | AC | Bundle 描述符、Installation Desired、Actual、Release Snapshot、日志和审计元数据不得包含 Bundle 字节、Storage Key、长期签名 URL、认证头、Edge Token 或存储凭据。 | SECURITY | C01,C02 | T1 | V01 | UNIT | yes |
| AC-03 | AC | 仅认证且属于目标组织/节点的 Edge 可在 `generation == desired_generation` 时获得 Bundle；未发布 Release、跨节点/组织、旧代、超前代或卸载态请求必须 fail-closed（失败即关闭）。 | SECURITY | C02 | T2 | V02 | INTEGRATION | yes |
| AC-04 | AC | Backend 对 Bundle 交付只解析和传输已冻结的描述符，不执行 Edge 文件副作用，也不接受 Edge 传入的任意路径、URL 或摘要覆盖冻结事实。 | BEHAVIOR | C02 | T2 | V02 | INTEGRATION | yes |
| AC-05 | AC | Edge 在写入激活目录前验证下载字节数和 SHA-256，并拒绝绝对路径、`..` 路径、路径分隔符绕过、ZIP 符号链接、重复冲突条目和超出受控根目录的目标。 | SECURITY | C03 | T3 | V03 | UNIT | yes |
| AC-06 | AC | 升级在暂存目录完成展开和验证；只有完整验证成功才原子切换 Current。下载、解压、校验或切换失败时，旧 Current 仍可用，失败暂存内容不得成为可执行版本。 | LIFECYCLE | C03 | T3 | V03 | UNIT | yes |
| AC-07 | AC | 卸载只删除由 Installer 管理、且位于受控根目录内的目标版本/Current 引用；不存在、旧代或符号链接攻击不得删除宿主或其他 Skill 文件。 | SECURITY | C03 | T3 | V03 | UNIT | yes |
| AC-08 | AC | Edge 仅在 C03 成功后上报同代 `ready`，并携带不含秘密的 Release/摘要事实。失败必须以 `generation == desired_generation` 上报稳定错误代码，且不得声称 `ready`；不得为了“不推进代次”改报旧代或超前代。 | LIFECYCLE | C04 | T4 | V04 | INTEGRATION | yes |
| AC-09 | AC | Backend 只接受 `edge_node_id` 匹配且 `generation == desired_generation` 的 Actual，不得只比组织。同代 `ready` 或 `uninstalled` 幂等对齐 `actual_generation = desired_generation`。同代稳定失败必须接受并持久化不含秘密的错误，且不得把 `actual_generation` 提升为 `desired_generation`，以便 Desired 保持未对齐并允许重试。旧代、超前代、跨节点回报不得改变 Installation 状态。 | LIFECYCLE | C05 | T2 | V05 | INTEGRATION | yes |
| AC-10 | AC | 安装、升级、下载校验失败和卸载均有自动化证据，证明真实包内容、原子回滚、路径/符号链接防护、鉴权/代次栅栏和同代 Actual 闭环；不需要 Work 直连 Agent。 | EVIDENCE | C01,C02,C03,C04,C05 | T4 | V01,V02,V03,V04,V05 | INTEGRATION | yes |
| DOD-01 | DOD | C01–C04 均有正向、拒绝和回归自动化验证；测试覆盖真实 Bundle 字节与摘要，不以空目录模拟成功安装。 | EVIDENCE | C01,C02,C03,C04,C05 | T4 | V01,V02,V03,V04,V05 | INTEGRATION | yes |
| DOD-02 | DOD | Release、Desired、下载与 Actual 的唯一 Owner 保持 Backend；本地文件副作用的唯一 Owner 保持 Agent Edge Worker/Installer；无第二状态机或新服务。 | CONTRACT | C01,C02,C03,C04,C05 | T4 | V06 | DOCUMENT_SEMANTIC | yes |
| DOD-03 | DOD | 现有 Installation Generation、Edge Token 与软删除语义保持兼容；新增或修改持久模型时，Alembic 自动生成迁移并和实现同提交。 | OPERATIONS | C01 | T1 | V01 | INTEGRATION | yes |
| DOD-04 | DOD | `lat.md` 的 Installation Generation Closed Loop（安装代次闭环）与 Backend/Agent 边界同步，`lat check` 通过。 | EVIDENCE | C04 | T4 | V06 | DOCUMENT_SEMANTIC | yes |

## Lifecycle Closure Matrix

| Journey | Requirements | Trigger | Nonterminal State | Success Writer | Failure / Cancel Writer | Evidence IDs |
|---|---|---|---|---|---|---|
| Publish freeze | AC-01, DOD-03 | `SkillReleaseService.publish` | draft -> packing zip | `publish` 写 hub zip + bundle 列后才 `published` | `publish` 在 zip/校验失败时不翻 `published`、不写 bundle 列 | V01 |
| Stage and activate | AC-06 | Worker 下载后 `EdgeSkillInstaller.install` | `.stage-{gen}` 目录 | `install` 校验通过后 `os.replace` 到 `{skill_id}/{gen}` 并写 `current.json` | `install` 只删 staging；不改旧 Current；抛错给 Worker | V03 |
| Ready or error Actual | AC-08, AC-09 | C03 返回或抛错 | `desired_gen != actual_gen` | `report_installation_actual` 仅 `ready`/`uninstalled`/`removed` 对齐代次 | Worker 同代 POST `actual_status=error`；Backend 写 `error_message` 且不对齐 `actual_generation` | V04,V05 |
| Safe uninstall | AC-07, AC-09 | Desired `uninstalling` | 本地仍有 Current | Installer 只删托管根内目标；Worker 报同代 `uninstalled`；Backend 软删除 | 路径/符号链接攻击不删宿主；Actual 跨 node/旧代拒绝 | V03,V05 |

## Contract / Data Flow Closure Matrix

| Flow | Requirements | Producer | Transport / Schema | Consumer | Required Fields | Validation Owner | Failure Mapping | Retry / Idempotency Identity | Evidence IDs |
|---|---|---|---|---|---|---|---|---|---|
| Frozen bundle descriptor | AC-01, AC-02 | `SkillReleaseService.publish` | DB 列 `bundle_ref`/`bundle_sha256`/`bundle_size_bytes` + hub zip | `get_desired_installations` | `release_id`, `bundle_ref`, `version`, `size`, `sha256`；`digest` 保持内容摘要 | Backend Hermes Release | 无 `canonical_path` 或打包失败 -> 不发布 | `release_id` | V01 |
| Desired pin | AC-01, AC-03 | `get_desired_installations` | JSON item.`bundle`；钉在 `install_metadata.published_bundle` | `EdgeWorker#_reconcile_desired_installations` | 同上 + `desired_generation` | Internal Edge `_authenticate_edge` | 无 published 则无 `bundle`，不得编造 | `installation_id` + `desired_generation` | V02 |
| Authorized zip bytes | AC-03, AC-04, AC-05 | Internal Edge bundle GET | `application/zip` 流；无 URL/凭据 | Worker 下载 + Installer | 字节、长度、冻结 sha256 | Internal Edge；Installer 再校验 size/sha | 未认证/跨 node/旧代/超前代/卸载/未发布 -> 4xx；客户端摘要忽略 | `installation_id` + `generation` | V02,V03 |
| Actual status | AC-08, AC-09 | `EdgeWorker#_reconcile_desired_installations` | POST `/installations/actual`：`generation`,`actual_status`,`meta.error_code` | `report_installation_actual` | 同代；`ready`/`uninstalled`/`error` | Internal Edge node+generation 栅栏 | 失败不对齐代次；stale/future/cross-node 不改状态 | `installation_id` + `generation` + status class | V04,V05 |

## Verification Ledger

| Verification ID | Level | Entry Point / Command | Oracle | Negative / Regression | Evidence Output | Environment | Blocking |
|---|---|---|---|---|---|---|---|
| V01 | INTEGRATION | `cd nodeskclaw-backend && uv run pytest tests/hermes_skill/test_skill_release.py --junitxml=../artifacts/rm03-v01.xml` | 发布后存在真实 ZIP；`bundle_sha256 != digest`；改工作副本不改已发布描述符；元数据无路径/凭据 | 无 canonical_path 不得 published；digest 冒充包哈希失败 | `artifacts/rm03-v01.xml` | local pytest | yes |
| V02 | INTEGRATION | `cd nodeskclaw-backend && uv run pytest tests/api/test_internal_edge_api.py --junitxml=../artifacts/rm03-v02.xml` | 所属 Edge 同代可下载；Desired 含 bundle 且无秘密 | 伪造 token、跨 node、旧代、超前代、卸载态、未发布 -> fail-closed；query sha 不能覆盖冻结值 | `artifacts/rm03-v02.xml` | local pytest | yes |
| V03 | UNIT | `cd nodeskclaw-agent && uv run pytest tests/test_edge_skill_installer.py --junitxml=../artifacts/rm03-v03.xml` | 真实 zip 安装后 Current 指向新代；失败保留旧 Current | zip-slip、ZIP 符号链接、重复条目、checksum 失败、越界卸载 | `artifacts/rm03-v03.xml` | local pytest | yes |
| V04 | INTEGRATION | `cd nodeskclaw-agent && uv run pytest tests/test_edge_worker.py --junitxml=../artifacts/rm03-v04.xml` | 下载真实字节后才 `ready`；失败同代 `error` 且不报 `ready`；卸载报同代 `uninstalled` | 空目录不得再当成功安装；异常不得只 debug 吞掉 | `artifacts/rm03-v04.xml` | local pytest | yes |
| V05 | INTEGRATION | `cd nodeskclaw-backend && uv run pytest tests/hermes_skill/test_skill_installation_reconcile.py --junitxml=../artifacts/rm03-v05.xml` | 同代 `ready`/`uninstalled` 对齐代次；同代 `error` 写错误且 `actual_generation` 不变 | 跨 node、旧代、超前代不改状态；回归成功路径仍对齐 | `artifacts/rm03-v05.xml` | local pytest | yes |
| V06 | DOCUMENT | `lat check` | Installation Generation Closed Loop 与 Backend/Agent 边界一致 | 过期“空目录即成功”表述必须消失 | `artifacts/rm03-v06-lat-check.txt` | local lat | yes |

## Immediate Read

- `docs_agent/prd-v1.6.2-edge-published-bundle-lifecycle.md`
- `nodeskclaw-backend/app/services/hermes_skill/skill_release_service.py#SkillReleaseService#publish`
- `nodeskclaw-backend/app/models/hermes_skill/skill_release.py#HermesSkillRelease`
- `nodeskclaw-backend/app/api/internal_edge.py#get_desired_installations`
- `nodeskclaw-backend/app/api/internal_edge.py#report_installation_actual`
- `nodeskclaw-agent/app/services/edge_skill_installer.py#EdgeSkillInstaller#install`

## Triggered Read

- If publish 需要约束打包文件集：`nodeskclaw-backend/app/services/hermes_skill/hub_manager.py#HubManager#canonical_path`
- If Desired 钉写与现有 `install_metadata` 冲突：`nodeskclaw-backend/tests/api/test_internal_edge_api.py#test_get_desired_installations`
- If ZIP 符号链接判定在 Windows 不一致：stdlib `zipfile.ZipInfo.external_attr`
- If Alembic 未检出新列：autogenerate 输出后 Review，禁止手写 revision ID
- Otherwise: do not read

## Change Matrix

| Change ID | File / Symbol | Kind | Action | Existing Owner | Todo Owner | Target State | PRD Capability | New File? |
|---|---|---|---|---|---|---|---|---|
| C01 | `nodeskclaw-backend/app/models/hermes_skill/skill_release.py#HermesSkillRelease` | PROD | MODIFY | Backend Hermes Skill Release | T1 | 新增 `bundle_ref`/`bundle_sha256`/`bundle_size_bytes` | Published Bundle Descriptor | no |
| C01 | `nodeskclaw-backend/app/services/hermes_skill/skill_release_service.py#SkillReleaseService#publish` | PROD | MODIFY | Backend Hermes Skill Release | T1 | 从 `canonical_path` 打包 ZIP 写入 Hub，冻结 SHA-256/size/ref；失败不发布 | Published Bundle Descriptor | no |
| C01 | `nodeskclaw-backend/tests/hermes_skill/test_skill_release.py` | TEST | MODIFY | Backend 测试 | T1 | 真实字节、digest 分离、工作副本不可变、无秘密 | Published Bundle Descriptor | no |
| C02 | `nodeskclaw-backend/app/api/internal_edge.py#get_desired_installations` | PROD | MODIFY | Backend Internal Edge | T2 | 返回钉住的最小 `bundle`；无秘密 | Edge Desired 与授权下载 | no |
| C02 | `nodeskclaw-backend/app/api/internal_edge.py` | PROD | MODIFY | Backend Internal Edge | T2 | 新增同文件 bundle GET：Edge Token + generation 栅栏字节流 | Edge Desired 与授权下载 | no |
| C02 | `nodeskclaw-backend/tests/api/test_internal_edge_api.py` | TEST | MODIFY | Backend 测试 | T2 | Desired bundle 与下载正负例 | Edge Desired 与授权下载 | no |
| C03 | `nodeskclaw-agent/app/services/edge_skill_installer.py#EdgeSkillInstaller#install` | PROD | MODIFY | Agent EdgeSkillInstaller | T3 | 先暂存再校验再切换；拒符号链接；失败保旧 Current | 安全暂存、激活和卸载 | no |
| C03 | `nodeskclaw-agent/app/services/edge_skill_installer.py#EdgeSkillInstaller#uninstall` | PROD | MODIFY | Agent EdgeSkillInstaller | T3 | 只删托管根内代次/Current；拒符号链接逃逸 | 安全暂存、激活和卸载 | no |
| C03 | `nodeskclaw-agent/tests/test_edge_skill_installer.py` | TEST | ADD | Agent 测试 | T3 | 真实 zip、回滚、zip-slip、符号链接、越界卸载 | 安全暂存、激活和卸载 | yes |
| C04 | `nodeskclaw-agent/app/services/edge_worker.py#EdgeWorker#_reconcile_desired_installations` | PROD | MODIFY | Agent EdgeWorker | T4 | 下载冻结字节后才 install；成功 `ready`；失败同代 `error` | Edge 调谐与 Actual 闭环 | no |
| C04 | `nodeskclaw-agent/tests/test_edge_worker.py` | TEST | MODIFY | Agent 测试 | T4 | 真实包 reconcile；禁止空目录成功 | Edge 调谐与 Actual 闭环 | no |
| C04 | `lat.md/architecture/skill-agent.md` | DOC | MODIFY | lat.md | T4 | Closed Loop：真实包 + 失败可重试 | DOD-04 | no |
| C04 | `lat.md/decisions/skill-platform-execution.md` | DOC | MODIFY | lat.md | T4 | Desired/下载/Actual 边界 | DOD-04 | no |
| C04 | `lat.md/domain/core-concepts.md` | DOC | MODIFY | lat.md | T4 | 安装副作用含真实 Bundle | DOD-04 | no |
| C05 | `nodeskclaw-backend/app/api/internal_edge.py#report_installation_actual` | PROD | MODIFY | Backend Installation 域 | T2 | 仅 ready/uninstalled/removed 对齐代次；error 持久化且不对齐 | Edge 调谐与 Actual 闭环 | no |
| C05 | `nodeskclaw-backend/tests/hermes_skill/test_skill_installation_reconcile.py` | TEST | MODIFY | Backend 测试 | T2 | 失败不对齐；成功仍对齐；栅栏回归 | Edge 调谐与 Actual 闭环 | no |

## Implementation Decisions

| Change ID | Strategy | Root-Cause / Reuse Evidence | Why This Is Minimum |
|---|---|---|---|
| C01 | MODIFY_EXISTING | `publish` 已是唯一发布入口；字节已在 Hub `canonical_path`；`digest` 已是内容摘要 | stdlib `zipfile`+`hashlib` 在 `publish` 内打包；不新建 Bundle Service，不改 `SkillPackageManager` |
| C02 | MODIFY_EXISTING | Desired 已有 org/node 鉴权与 `install_metadata`；Internal Edge 已是 Edge 唯一入口 | 同文件加 GET 字节流；钉在现有 JSONB；不 bump 合同族、不复用 Artifact on-demand |
| C03 | MODIFY_EXISTING | `EdgeSkillInstaller.install` 已拥有解压与校验，缺的是顺序（预删）和符号链接门禁 | 在现有方法内改为 staging+`os.replace`；Current 用 json 指针避免 symlink |
| C04 | MODIFY_EXISTING | `_reconcile_desired_installations` 已按代次调谐并 POST Actual | 同 class 增加下载；成功才 `ready`；catch 后同代 `error`，不新建 Worker/client |
| C05 | MODIFY_EXISTING | `report_installation_actual` 已是唯一 Actual 写入口，无条件对齐是根因 | 按 `actual_status` 分支写 `actual_generation`；复用 `error_message` 列 |

## Write Ownership Ledger

| Todo | Owns Changes | Writes | Reads | Depends On | Parallel Safe |
|---|---|---|---|---|---|
| T1 | C01 | `nodeskclaw-backend/app/models/hermes_skill/skill_release.py#HermesSkillRelease`<br>`nodeskclaw-backend/app/services/hermes_skill/skill_release_service.py#SkillReleaseService#publish`<br>`nodeskclaw-backend/tests/hermes_skill/test_skill_release.py` | `nodeskclaw-backend/app/models/hermes_skill/skill.py`<br>`nodeskclaw-backend/app/services/hermes_skill/hub_manager.py#HubManager#canonical_path` | - | no |
| T2 | C02<br>C05 | `nodeskclaw-backend/app/api/internal_edge.py#get_desired_installations`<br>`nodeskclaw-backend/app/api/internal_edge.py`<br>`nodeskclaw-backend/app/api/internal_edge.py#report_installation_actual`<br>`nodeskclaw-backend/tests/api/test_internal_edge_api.py`<br>`nodeskclaw-backend/tests/hermes_skill/test_skill_installation_reconcile.py` | `nodeskclaw-backend/app/services/hermes_skill/skill_release_service.py#SkillReleaseService#publish`<br>`nodeskclaw-backend/app/services/hermes_skill/skill_release_service.py#SkillReleaseService#get_published` | T1 | no |
| T3 | C03 | `nodeskclaw-agent/app/services/edge_skill_installer.py#EdgeSkillInstaller#install`<br>`nodeskclaw-agent/app/services/edge_skill_installer.py#EdgeSkillInstaller#uninstall`<br>`nodeskclaw-agent/tests/test_edge_skill_installer.py` | - | - | no |
| T4 | C04 | `nodeskclaw-agent/app/services/edge_worker.py#EdgeWorker#_reconcile_desired_installations`<br>`nodeskclaw-agent/tests/test_edge_worker.py`<br>`lat.md/architecture/skill-agent.md`<br>`lat.md/decisions/skill-platform-execution.md`<br>`lat.md/domain/core-concepts.md` | `nodeskclaw-backend/app/api/internal_edge.py`<br>`nodeskclaw-agent/app/services/edge_skill_installer.py#EdgeSkillInstaller#install` | T2<br>T3 | no |

## Integration Hotspots

| File | Owner Todo | Reason |
|---|---|---|
| `nodeskclaw-backend/app/api/internal_edge.py` | T2 | Desired、下载、Actual 单写者 |
| `nodeskclaw-backend/app/models/hermes_skill/skill_release.py` | T1 | Release 持久化单写者 |
| `nodeskclaw-agent/app/services/edge_skill_installer.py` | T3 | 本地文件副作用单写者 |
| `nodeskclaw-agent/app/services/edge_worker.py` | T4 | 调谐与 Actual 上报单写者 |
| `nodeskclaw-agent/tests/test_edge_worker.py` | T4 | Worker 测试单写者，避免与 C03 争用 |

## Generated Outputs Ledger

| Source Change | Generator Owner | Generated Outputs | Command | Drift Check |
|---|---|---|---|---|
| C01 | T1 | `nodeskclaw-backend/alembic/versions/<autogen>_add_skill_release_bundle_descriptor.py` | `cd nodeskclaw-backend && uv run alembic revision --autogenerate -m "add skill release bundle descriptor"` | Review 迁移含三列且无误 DROP；禁止手写 revision ID |

## New File Justification

| Change ID | File | Necessity | Owner Impact |
|---|---|---|---|
| C03 | `nodeskclaw-agent/tests/test_edge_skill_installer.py` | `test_edge_worker.py` 是 T4 hotspot；Installer 隔离测试不能与 Worker 测试争同一文件 | 仅测试文件；生产 Owner 仍是 `EdgeSkillInstaller` |

## Todo T1 — 发布冻结不可变 Bundle

**Owns Changes**
- C01

**Goal**
`publish` 把 Hub 工作副本打成不可变 ZIP，冻结 `bundle_ref`/size/包 SHA-256；`digest` 仍是内容摘要。

**Immediate anchors**
- `nodeskclaw-backend/app/services/hermes_skill/skill_release_service.py#SkillReleaseService#publish`
- `nodeskclaw-backend/app/models/hermes_skill/skill_release.py#HermesSkillRelease`

**Changes**
- 模型三列；autogenerate 迁移并 Review
- `publish`：读 `skill.canonical_path`，stdlib zip，写入 `releases/{bundle_ref}.zip`，写列后再 `published`；已发布幂等返回
- 测试用真实文件树，断言 sha ≠ digest，改工作副本不影响已发布包

**Stop conditions**
- [ ] 已发布描述符含 ref/size/sha256 且无存储路径
- [ ] V01 通过

**Triggered reads**
- If canonical_path 为空：fail-closed 不发布
- Otherwise: none

## Todo T2 — Desired 钉住描述符、授权下载、失败 Actual

**Owns Changes**
- C02
- C05

**Goal**
所属 Edge 在当前代拿到冻结描述符和 ZIP 字节；同代失败 Actual 落错误但不对齐代次。

**Immediate anchors**
- `nodeskclaw-backend/app/api/internal_edge.py#get_desired_installations`
- `nodeskclaw-backend/app/api/internal_edge.py#report_installation_actual`

**Changes**
- Desired：按代钉 `published_bundle`，响应 `bundle`；卸载/未发布省略
- 同文件 GET bundle：Token + `edge_node_id` + `generation == desired_generation`；流式返回钉住的 zip；忽略客户端摘要/路径
- Actual：`ready`/`uninstalled`/`removed` 对齐代次；`error` 写 `error_message` 不对齐；KEEP 卸载软删除与 stale/future/cross-node 拒绝

**Stop conditions**
- [ ] 未授权/错代/卸载/未发布下载 fail-closed
- [ ] V02 与 V05 通过

**Triggered reads**
- If `get_published` 签名与 org/skill 过滤不一致：只读 `SkillReleaseService#get_published`
- Otherwise: none

## Todo T3 — 事务式安装与受控卸载

**Owns Changes**
- C03

**Goal**
真实 ZIP 在 staging 校验通过后才成为 Current；失败保留旧版本；卸载不逃出托管根。

**Immediate anchors**
- `nodeskclaw-agent/app/services/edge_skill_installer.py#EdgeSkillInstaller#install`

**Changes**
- 取消预 `rmtree` 目标
- 校验 size/sha256；拒绝绝对路径、`..`、重复名、ZIP 符号链接
- staging -> `os.replace` 到 `{skill_id}/{version}` -> 写 `current.json`
- `uninstall` 只删托管根内目标；不跟随符号链接

**Stop conditions**
- [ ] checksum/符号链接失败时旧 Current 仍可用
- [ ] V03 通过

**Triggered reads**
- If `os.replace` 在 Windows 对已存在目录失败：先替换进新代目录再写 current 指针，仍不得预删旧 Current
- Otherwise: none

## Todo T4 — Worker 真实包调谐与 lat.md

**Owns Changes**
- C04

**Goal**
Worker 按钉住描述符下载并交给 C03；成功才同代 `ready`；失败同代 `error`；空目录不再算安装成功。

**Immediate anchors**
- `nodeskclaw-agent/app/services/edge_worker.py#EdgeWorker#_reconcile_desired_installations`

**Changes**
- 无 `bundle` 且非卸载：同代 `error`，不 `ready`
- GET bundle 后 `install(zip_bytes=..., expected_sha256=...)`
- 失败不得只 `logger.debug`；必须同代 POST `error`
- 卸载传受管 version；更新 `test_edge_worker.py` 与 lat.md Closed Loop

**Stop conditions**
- [ ] 真实 zip 才 `ready`；失败可重试
- [ ] V04 与 V06 通过

**Triggered reads**
- If Desired 把 bundle 放在 `install_metadata` 而非顶层：同时读两处，权威仍是 Backend 钉
- Otherwise: none

## Verification

```bash
cd nodeskclaw-backend && uv run pytest tests/hermes_skill/test_skill_release.py tests/api/test_internal_edge_api.py tests/hermes_skill/test_skill_installation_reconcile.py --junitxml=../artifacts/rm03-backend.xml
cd nodeskclaw-agent && uv run pytest tests/test_edge_skill_installer.py tests/test_edge_worker.py --junitxml=../artifacts/rm03-agent.xml
lat check
```

- AC 映射：V01=AC-01/02/DOD-03；V02=AC-03/04；V03=AC-05/06/07；V04=AC-08；V05=AC-09；V01–V05=AC-10/DOD-01；V06=DOD-02/04
- Expected: 真实 ZIP 闭环；失败不对齐代次；无 Work 直连 Agent
- Negative: zip-slip、符号链接、错代下载、digest 冒充包哈希、空目录安装

## Completion Gate

| Exit State | Allowed When | Blocking Evidence |
|---|---|---|
| IMPLEMENTED_AND_PROVEN | 全部阻断验证通过且证据文件存在 | V01,V02,V03,V04,V05,V06 output retained |
| IMPLEMENTED_NOT_PROVEN | 代码已改但 junit/`lat check` 未留存 | 点名未完成的 Vnn |
| BLOCKED | 本地无 Hub 写权限或 pytest 环境不可用 | blocker recorded |
| RETURN_PRD | 必须新建 Bundle Service、第二状态机或改 Owner | PRD revision requested |
