---
plan_contract: smc.plan.v3.2
commit_policy: post_review
source_revision: AD-SKILL-AGENT-V16@1.3.0/RM-11
grounded_commit: 21bdc38afc44a780659f3d589daf37bdf6c47328
grounding_source: committed_baseline
working_tree_fingerprint: clean
---

# RM-11 累积 Public v1.2.1 合同导出实施计划

`commit_policy: post_review`。执行顺序：`Execute -> Review -> Verification -> Commit Implementation`。Todo 完成不得 commit。Roadmap `DONE` 必须另开独立 docs commit。禁止执行已废止的 [`.cursor/plans/rm-11_contract_export_7ec6f14f.plan.md`](rm-11_contract_export_7ec6f14f.plan.md)。跨边界流非 None，Execute 前必须 `smc-plan-review` PASS。

## 前端表现变化

本次改动无前端表现变化。不改 Portal / Admin / Work 页面、按钮、文案或路由。员工公共面仍是 Backend `/api/v1/mcp` 与 `/api/v1/runs/*`。

## Approved PRD

[Approved PRD](docs_agent/prd-v1.6.6-cumulative-public-consumer-contract.md)

## Scope

- In: 生成并发布累积 Public `contracts/skill-run/v1.2.1/` 与 annotated tag `skill-run-contract-v1.2.1`；version-aware generate/check；manifest 纳入 SHA256SUMS；exact bundle closure；LF writer；Public/Internal 边界；合同测试；`.gitattributes` eol=lf；本仓 Release Evidence。
- Out: 改写或删除 `v1.0.0`/`v1.1.0`/`v1.2.0`；移动 `skill-run-contract-v1.0.0`；Work UI/IPC/consumer-lock；RM-08 Internal `skill-agent` 目录；把 RM-09 标 READY；RM-04/RM-05 完成声明。
- Production Owner inherited from PRD: Backend Skill Run Contract Package（C04/C05）；Backend tests（C06）；Repository `.gitattributes`（C07）；Repository Acceptance Assets（C08）。Agent 仍是 Run SoT（C09 KEEP）。

## Grounding Evidence Ledger

| Change ID | Target | Baseline State | Symbol / Entry Resolution | Caller / Callee Evidence | Existing Reuse Search | Result |
|---|---|---|---|---|---|---|
| C04 | `nodeskclaw-backend/contracts/skill-run/v1.2.1/manifest.json` | absent at `21bdc38` | new Public Bundle root | Work 离线导入该目录；不写 Gateway | 复用 `v1.0.0` public-run/result/matrix 与 `v1.1.0`/`v1.2.0` catalog/events 作为累积源，不复用 v1.2.0 的 edge/installations | PASS |
| C05 | `nodeskclaw-backend/scripts/contracts.py#generate_skill_run_contracts` | exists at `21bdc38` | function resolves；`--version` 仅 1.0.0/1.1.0/1.2.0；check 固定 `v1.0.0` | `main` subparser `generate`/`check` | `_validate_checksums` 已做 listed 文件 hash；exact set 与 manifest-in-SHA256SUMS 未做；不得把 exact 规则套到冻结 v1.0.0 | PASS |
| C05 | `nodeskclaw-backend/scripts/contracts.py#_check_skill_run_contracts` | exists | 固定 `SKILL_RUN_CONTRACTS_HOME / "v1.0.0"` | `check_contracts(family=skill-run)` | 新增 version 参数；`--release` 必须校验 `skill-run-contract-v1.2.1` 指向 freeze commit，不得要求 tag==HEAD | PASS |
| C06 | `nodeskclaw-backend/tests/contracts/test_skill_run_v121_bundle.py` | absent | new test module | pytest 收集 `tests/contracts/` | 扩展 `test_contracts_check.py` 会把 v1.2.1 断言混进历史包测试；独立文件更小 | PASS |
| C07 | `.gitattributes` | exists | file-level hotspot | git checkout eol | 已有 `*.sh` lf；追加 skill-run json/md/SHA256SUMS，不对 binary 无差别 `text` | PASS |
| C08 | `docs_agent/evidence/rm11-verification.md` | absent | 无 RM-11 v1.2.1 证据 | Roadmap verification 列 | 格式复用 `docs_agent/evidence/rm01-verification.md` | PASS |

## Requirement Coverage Ledger

| Requirement | Source | Obligation | Classification | Change IDs | Todo | Verification IDs | Evidence Class | Blocking |
|---|---|---|---|---|---|---|---|---|
| AC-01 | AC | 存在完整 nodeskclaw-backend/contracts/skill-run/v1.2.1/ Public Bundle，目录集合与 Architecture 批准的 Public 面一致。 | CONTRACT | C04 | T1 | V01 | CONTRACT_RELEASE | yes |
| AC-02 | AC | v1.2.1 累积覆盖 v1.0 Public Run/Result/Artifact/matrix/idempotency、v1.1 Catalog 描述符与 v1.2 semantic events。 | CONTRACT | C04 | T1 | V01 | CONTRACT_RELEASE | yes |
| AC-03 | AC | v1.2.1 无 edge/**、installations/**、runs/execution-snapshot.schema.json。 | CONTRACT | C04 | T1 | V02 | CONTRACT_RELEASE | yes |
| AC-04 | AC | manifest.json 出现在 SHA256SUMS；SHA256SUMS 不含自身、不含 consumer-lock.json。 | CONTRACT | C05 | T1 | V03 | CONTRACT_RELEASE | yes |
| AC-05 | AC | checksum entries 与实际 Provider Bundle 文件集合完全相等（排除 SHA256SUMS 与 consumer-lock）。 | CONTRACT | C05 | T1 | V03 | CONTRACT_RELEASE | yes |
| AC-06 | AC | SHA256SUMS 为 UTF-8 LF-only，CR count = 0；所列摘要对真实 bytes 通过。 | CONTRACT | C05 | T1 | V03 | CONTRACT_RELEASE | yes |
| AC-07 | AC | 任一 v1.2.1 manifest/schema/fixture 被修改后 check 失败。 | CONTRACT | C05 | T1 | V04 | UNIT | yes |
| AC-08 | AC | python nodeskclaw-backend/scripts/contracts.py check --family skill-run --version 1.2.1 --release 在 tag 正确指向 freeze commit 时通过。 | OPERATIONS | C05 | T1 | V05 | CONTRACT_RELEASE | yes |
| AC-09 | AC | generate 不得静默覆盖 v1.0.0 / v1.1.0 / v1.2.0。 | OPERATIONS | C05 | T1 | V06 | DIFF_SCOPE | yes |
| AC-10 | AC | 合同测试覆盖 missing/extra/tamper/internal/LF/historical unchanged。 | EVIDENCE | C06 | T2 | V04 | UNIT | yes |
| AC-11 | AC | .gitattributes 对 skill-run json/md/SHA256SUMS 声明 eol=lf，不对未来 binary fixture 无差别强制 text。 | OPERATIONS | C07 | T1 | V07 | DIFF_SCOPE | yes |
| AC-12 | AC | 存在 annotated tag skill-run-contract-v1.2.1；禁止 git tag -f；git archive 解压后完整复验通过。 | RELEASE | C08 | T3 | V05 | CONTRACT_RELEASE | yes |
| AC-13 | AC | v1.0.0 / v1.1.0 / v1.2.0 目录和既有 v1.0.0 tag 未变化。 | CONTRACT | C01,C02,C03 | T1 | V06 | DIFF_SCOPE | yes |
| AC-14 | AC | Release Evidence 记录 contractName、contractVersion、backendCommit、releaseCommit、tagName、peeledTagCommit、bundleFileCount、checksum 与 archive 复验结果；证据不放入 Public Bundle 本体。 | EVIDENCE | C08 | T3 | V08 | DOCUMENT_SEMANTIC | yes |
| AC-15 | AC | 本仓证据不含 Work 源码路径作为通过条件；Backend 未成为第二 Run 状态 Owner。 | EVIDENCE | C09,C10 | T3 | V08 | DOCUMENT_SEMANTIC | yes |
| DOD-01 | DOD | AC-01 至 AC-15 的 Provider 侧验证证据已留存；v1.2.1 为 Work canonical；历史三版未改写；未新增合同服务；Work 导入不是本阶段完成条件；RM-09 仍不得因本项被标 READY。 | EVIDENCE | C04,C05,C06,C07,C08 | T3 | V08 | DOCUMENT_SEMANTIC | yes |

## Lifecycle Closure Matrix

None

## Contract / Data Flow Closure Matrix

| Flow | Requirements | Producer | Transport / Schema | Consumer | Required Fields | Validation Owner | Failure Mapping | Retry / Idempotency Identity | Evidence IDs |
|---|---|---|---|---|---|---|---|---|---|
| Public v1.2.1 Bundle | AC-01,AC-02,AC-03,AC-04,AC-05,AC-12 | `generate_skill_run_contracts` 写入 `v1.2.1/` | UTF-8 LF files + SHA256SUMS + annotated tag + git archive | 仓外 Work；本仓 check/archive 复验 | manifest.contractVersion=1.2.1, tagName, artifacts hashes, Public file set | `_check_skill_run_contracts` version 1.2.1 | missing/extra/CRLF/Internal/tamper -> SystemExit；错误 tag -> release check fail | freeze commit + tagName；禁止 tag -f | V01,V02,V03,V05 |

## Verification Ledger

| Verification ID | Level | Entry Point / Command | Oracle | Negative / Regression | Evidence Output | Environment | Blocking |
|---|---|---|---|---|---|---|---|
| V01 | CONTRACT_RELEASE | `cd nodeskclaw-backend && uv run python scripts/contracts.py generate --family skill-run --version 1.2.1` | `v1.2.1/` 含 Public MCP/run/result/artifact/matrix/events/unsupported 与累积 fixtures | 不得生成 edge/installations/execution-snapshot | `artifacts/rm11-v01-generate.txt` | local uv | yes |
| V02 | CONTRACT_RELEASE | python 枚举 `v1.2.1` 相对路径 | 无 edge/**、installations/**、execution-snapshot | 出现任一 Internal 路径即失败 | `artifacts/rm11-v02-boundary.txt` | local python | yes |
| V03 | CONTRACT_RELEASE | `cd nodeskclaw-backend && uv run python scripts/contracts.py check --family skill-run --version 1.2.1` | listed==actual；manifest 在 SHA256SUMS；CR=0；hash 匹配 | extra/missing/consumer-lock 必须失败 | `artifacts/rm11-v03-check.txt` | local uv | yes |
| V04 | UNIT | `cd nodeskclaw-backend && uv run pytest tests/contracts/test_skill_run_v121_bundle.py --junitxml=../artifacts/rm11-v04.xml` | missing/extra/tamper/internal/LF 负向失败 | 历史 v1.0.0/v1.1.0/v1.2.0 测试仍绿 | `artifacts/rm11-v04.xml` | local pytest | yes |
| V05 | CONTRACT_RELEASE | freeze 后 `check --family skill-run --version 1.2.1 --release` 与 `git archive --format=tar skill-run-contract-v1.2.1 nodeskclaw-backend/contracts/skill-run/v1.2.1` 解压复验 | annotated tag 指向 freeze commit；archive 再 check 通过 | 禁止 tag -f；tag 指错 commit 必须失败 | `artifacts/rm11-v05-release.txt` | local git | yes |
| V06 | DIFF_SCOPE | `git diff --exit-code 3e345519bcfa606553893234b59fb607ee57ac8a HEAD -- nodeskclaw-backend/contracts/skill-run/v1.0.0` 以及 v1.1.0/v1.2.0 相对其冻结 commit 无业务改写 | 三目录相对各自冻结点无 RM-11 改写 | generate 默认不得改这三目录 | `artifacts/rm11-v06-frozen.txt` | local git | yes |
| V07 | DIFF_SCOPE | `git check-attr eol -- nodeskclaw-backend/contracts/skill-run/v1.2.1/SHA256SUMS` | eol=lf | 未对无关 binary 加 text | `artifacts/rm11-v07-gitattributes.txt` | local git | yes |
| V08 | DOCUMENT | 读 `docs_agent/evidence/rm11-verification.md` | 含 PRD 要求的 Release Evidence 字段；无 Work 源码通过条件；未标 RM-09 READY | 证据文件进入 SHA256SUMS 即失败 | `docs_agent/evidence/rm11-verification.md` | local docs | yes |

## Immediate Read

- `docs_agent/prd-v1.6.6-cumulative-public-consumer-contract.md`
- `nodeskclaw-backend/scripts/contracts.py#generate_skill_run_contracts`
- `nodeskclaw-backend/scripts/contracts.py#_check_skill_run_contracts`
- `nodeskclaw-backend/app/schemas/skill_run/constants.py`
- `nodeskclaw-backend/contracts/skill-run/v1.0.0/SHA256SUMS`
- `nodeskclaw-backend/contracts/skill-run/v1.2.0/SHA256SUMS`

## Triggered Read

- If v1.2.1 需复制 v1.0 public-run/result schemas：`nodeskclaw-backend/scripts/contracts.py#_generate_skill_run_v10_public_contract`
- If `--release` 旧语义要求 tag==HEAD：只改 v1.2.1 分支，不破坏 work-expert `--release`
- If 生成 JSON 需固定 generatedAt：`SOURCE_DATE_EPOCH` 或 CLI 参数，不引入新依赖
- Otherwise: do not read Gateway / Agent / Work / RM-04 harness

## Change Matrix

| Change ID | File / Symbol | Kind | Action | Existing Owner | Todo Owner | Target State | PRD Capability | New File? |
|---|---|---|---|---|---|---|---|---|
| C01 | `nodeskclaw-backend/contracts/skill-run/v1.0.0/SHA256SUMS` | CONFIG | KEEP | Backend Contract Package | - | frozen v1.0.0 | frozen v1.0.0 | no |
| C02 | `nodeskclaw-backend/contracts/skill-run/v1.1.0/SHA256SUMS` | CONFIG | KEEP | Backend Contract Package | - | frozen v1.1.0 | frozen v1.1.0 | no |
| C03 | `nodeskclaw-backend/contracts/skill-run/v1.2.0/SHA256SUMS` | CONFIG | KEEP | Backend Contract Package | - | frozen v1.2.0 | frozen v1.2.0 | no |
| C04 | `nodeskclaw-backend/contracts/skill-run/v1.2.1/manifest.json` | CONFIG | ADD | - | T1 | cumulative Public Bundle exists | 累积 Public v1.2.1 Bundle | yes |
| C05 | `nodeskclaw-backend/scripts/contracts.py#generate_skill_run_contracts` | PROD | MODIFY | Backend `scripts/contracts.py` | T1 | generate --version 1.2.1 writes Public-only tree | Generator / Checker | no |
| C05 | `nodeskclaw-backend/scripts/contracts.py#_check_skill_run_contracts` | PROD | MODIFY | Backend `scripts/contracts.py` | T1 | check --version 1.2.1 exact closure + release tag | Generator / Checker | no |
| C05 | `nodeskclaw-backend/app/schemas/skill_run/constants.py` | PROD | MODIFY | Backend schemas | T1 | version and tagName constants for 1.2.1 | Generator / Checker | no |
| C06 | `nodeskclaw-backend/tests/contracts/test_skill_run_v121_bundle.py` | TEST | ADD | - | T2 | pytest covers missing/extra/tamper/internal/LF/history | v1.2.1 合同测试 | yes |
| C07 | `.gitattributes` | CONFIG | MODIFY | Repository | T1 | skill-run json/md/SHA256SUMS eol=lf | 文本 LF 属性 | no |
| C08 | `docs_agent/evidence/rm11-verification.md` | DOC | ADD | - | T3 | Release Evidence retained | 发布身份与证据 | yes |
| C09 | `nodeskclaw-backend/app/api/runs.py` | PROD | KEEP | Backend Skill Run API | - | public proxy unchanged | 员工公共面与 Agent SoT | no |
| C10 | `docs_agent/prd-v1.6.6-cumulative-public-consumer-contract.md` | DOC | KEEP | Work out of repo | - | no Work lock in Provider SHA256SUMS | Work 前端与 lock | no |

## Implementation Decisions

| Change ID | Strategy | Root-Cause / Reuse Evidence | Why This Is Minimum |
|---|---|---|---|
| C04 | GENERATED_ENTRYPOINT | Public 树由 `generate_skill_run_contracts` 写出；不手写平行 schema | 手写 v1.2.1 会形成第二事实源 |
| C05 | MODIFY_EXISTING | `generate_skill_run_contracts` 与 `_check_skill_run_contracts` 已是唯一生成/校验入口 | 新脚本会第二生成链 |
| C06 | MINIMAL_NEW | `test_contracts_check.py` 只覆盖存在性与 v1.0 fixtures，塞进会混淆冻结包 | 一个新测试模块承载 v1.2.1 负向用例 |
| C07 | MODIFY_EXISTING | 根目录 `.gitattributes` 已存在 | 不新建第二属性文件 |
| C08 | MINIMAL_NEW | 无 RM-11 v1.2.1 证据文件；`rm01-verification.md` 是别的 Item | 每 Item 一份 evidence |

## Write Ownership Ledger

| Todo | Owns Changes | Writes | Reads | Depends On | Parallel Safe |
|---|---|---|---|---|---|
| T1 | C04<br>C05<br>C07 | `nodeskclaw-backend/contracts/skill-run/v1.2.1/manifest.json`<br>`nodeskclaw-backend/scripts/contracts.py#generate_skill_run_contracts`<br>`nodeskclaw-backend/scripts/contracts.py#_check_skill_run_contracts`<br>`nodeskclaw-backend/app/schemas/skill_run/constants.py`<br>`.gitattributes` | - | - | no |
| T2 | C06 | `nodeskclaw-backend/tests/contracts/test_skill_run_v121_bundle.py` | `nodeskclaw-backend/scripts/contracts.py#_check_skill_run_contracts`<br>`nodeskclaw-backend/contracts/skill-run/v1.2.1/manifest.json` | T1 | no |
| T3 | C08 | `docs_agent/evidence/rm11-verification.md` | `nodeskclaw-backend/contracts/skill-run/v1.2.1/manifest.json` | T1<br>T2 | no |

## Integration Hotspots

| File | Owner Todo | Reason |
|---|---|---|
| `nodeskclaw-backend/scripts/contracts.py` | T1 | 唯一 generate/check 入口 |
| `.gitattributes` | T1 | 仓库级 eol 规则 |

## Generated Outputs Ledger

| Source Change | Generator Owner | Generated Outputs | Command | Drift Check |
|---|---|---|---|---|
| C04 | T1 `generate_skill_run_contracts` | `nodeskclaw-backend/contracts/skill-run/v1.2.1/**` except SHA256SUMS 自指 | `uv run python scripts/contracts.py generate --family skill-run --version 1.2.1` | `check --family skill-run --version 1.2.1`；git diff 生成树与命令重跑一致 |

## New File Justification

| Change ID | File | Necessity | Owner Impact |
|---|---|---|---|
| C04 | `nodeskclaw-backend/contracts/skill-run/v1.2.1/manifest.json` | 新合同版本必须新目录；禁止改写冻结三版 | 仍归 Contract Package |
| C06 | `nodeskclaw-backend/tests/contracts/test_skill_run_v121_bundle.py` | 负向用例不能绑在历史包测试上 | 测试 Owner 独立，生产 Owner 不变 |
| C08 | `docs_agent/evidence/rm11-verification.md` | RM-11 证据 SOT 不能写入 rm01/rm02 文件 | Acceptance Assets 单文件 |

## Todo T1 — 生成链与 Public v1.2.1 树

**Owns Changes**
- C04
- C05
- C07

**Goal**

扩展既有 `contracts.py` 使 `--version 1.2.1` 生成仅 Public 的累积包，check 做 exact closure / LF / Internal 拒绝 / manifest 进 SHA256SUMS；`.gitattributes` 声明 skill-run 文本 LF。不改冻结三版。

**Immediate anchors**
- `nodeskclaw-backend/scripts/contracts.py#generate_skill_run_contracts`
- `nodeskclaw-backend/scripts/contracts.py#_check_skill_run_contracts`

**Changes**
- constants 增加 v1.2.1 与 tag 名
- generate 累积 v1.0 public 面 + v1.1 catalog + v1.2 events；排除 Internal
- SHA256SUMS 含 manifest，不含自身与 consumer-lock
- check `--version`；`--release` 校验 tag `skill-run-contract-v1.2.1` 指向 freeze commit
- 运行 generate 写出 `v1.2.1/`

**Stop conditions**
- [ ] `generate --family skill-run --version 1.2.1` 后目录存在且无 Internal 路径
- [ ] `check --family skill-run --version 1.2.1` 通过
- [ ] v1.0.0/v1.1.0/v1.2.0 无本 Todo 改写
- [ ] 未执行已废止 KEEP-only Plan

**Triggered reads**
- If 需拆 v1.2.1 generate helper：留在 `contracts.py` 内，不新建模块
- Otherwise: none

## Todo T2 — v1.2.1 合同负向测试

**Owns Changes**
- C06

**Goal**

新增 pytest 覆盖 missing/extra/tamper/internal/LF 与历史包不变。

**Immediate anchors**
- `nodeskclaw-backend/tests/contracts/test_contracts_check.py`

**Changes**
- 只写 `test_skill_run_v121_bundle.py`（可另增 PRD 点名的闭包/换行/边界文件，若需要则仍归 T2，且须补 Matrix 行后再改；本 Plan 先用一个模块覆盖 AC-10）

**Stop conditions**
- [ ] `uv run pytest tests/contracts/test_skill_run_v121_bundle.py` 退出码 0
- [ ] 不修改 `contracts.py`

**Triggered reads**
- If 单文件不够拆分：仍由 T2 追加同目录测试文件并先修订本 Plan Matrix
- Otherwise: none

## Todo T3 — tag、archive 与 Release Evidence

**Owns Changes**
- C08

**Goal**

在产物 freeze commit 上打 annotated tag（不 `-f`），archive 复验，写入 `docs_agent/evidence/rm11-verification.md`。

**Immediate anchors**
- `docs_agent/evidence/rm01-verification.md`

**Changes**
- 记录 V01–V07 命令与字段；证据不进入 Public SHA256SUMS

**Stop conditions**
- [ ] evidence 文件含 AC-14 字段
- [ ] 无 Work 源码通过条件
- [ ] 未把 RM-09 标 READY

**Triggered reads**
- If tag 需独立 artifact commit：按产品 PRD 拆 generator commit 与产物 commit，仍不与 Roadmap commit 合并
- Otherwise: none

## Verification

```bash
cd nodeskclaw-backend && uv run python scripts/contracts.py generate --family skill-run --version 1.2.1
cd nodeskclaw-backend && uv run python scripts/contracts.py check --family skill-run --version 1.2.1
cd nodeskclaw-backend && uv run pytest tests/contracts/test_skill_run_v121_bundle.py --junitxml=../artifacts/rm11-v04.xml
```

- AC mapping: V01–V08 覆盖 AC-01 至 AC-15
- Expected: v1.2.1 Public 包可校验；冻结三版不变
- Negative/regression case: Internal 路径、extra file、CRLF、静默覆盖旧版本

## Completion Gate

| Exit State | Allowed When | Blocking Evidence |
|---|---|---|
| IMPLEMENTED_AND_PROVEN | all requirement evidence passed | V01,V02,V03,V04,V05,V06,V07,V08 output retained |
| IMPLEMENTED_NOT_PROVEN | implementation exists but evidence is pending | pending verification identified |
| BLOCKED | tag 或 uv 环境阻止证明 | blocker recorded |
| RETURN_PRD | approved owner or boundary conflicts | PRD revision requested |
