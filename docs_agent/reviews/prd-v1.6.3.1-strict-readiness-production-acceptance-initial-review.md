---
prd: docs_agent/prd-v1.6.3-strict-readiness-production-acceptance.md
work_item_id: RM-04
mode: initial
verdict: REVISE
reviewer: smc-prd-review
reviewed_at: 2026-09-09T13:05:00+08:00
source_revision: AD-SKILL-AGENT-V16@1.8.0/RM-04
grounded_commit: 8919e197e8ba3afddf60e06f6ca2f55128bdb5e4
---

# RM-04 Stage PRD v1.6.3.1 Initial Review

对 `docs_agent/prd-v1.6.3-strict-readiness-production-acceptance.md`（`version: 1.6.3.1`，`REVIEW_REQUIRED`）做一次性六门禁 + G7 审查。本轮是相对已发布 Public `SKILL-RUN-CONTRACT v1.5.0` 与 `AD-SKILL-AGENT-V16@1.8.0` 的修订，不是 v1.6.3 在 `6580bc94` 的重复 discovery。历史审查 `docs_agent/reviews/prd-v1.6.3-strict-readiness-production-acceptance-initial-review.md` 不得当作本版批准。本审查不修改 PRD，不 git commit。

## Evidence Reuse

- `source_revision`: `AD-SKILL-AGENT-V16@1.8.0/RM-04`，与父 AD@1.8.0 Roadmap Boundaries RM-04 行一致（独立验收项；Depends On RM-03）
- `grounded_commit`: `8919e197e8ba3afddf60e06f6ca2f55128bdb5e4`（`git cat-file` 为 commit，等于当前 HEAD；RM-19 Roadmap DONE）
- Architecture `AD-SKILL-AGENT-V16@1.8.0` `APPROVED`；Roadmap version `1.8.0`，RM-03 `DONE`，RM-04 `IN_PRD`，Plan 列 `-`
- `python tools/agent-skills/validate_prd.py docs_agent/prd-v1.6.3-strict-readiness-production-acceptance.md --require-evidence`：通过
- `python tools/agent-skills/evidence_freshness.py ... --source-revision AD-SKILL-AGENT-V16@1.8.0/RM-04`：`REUSE`
- Public Bundle `nodeskclaw-backend/contracts/skill-run/v1.5.0/` 存在；annotated tag `skill-run-contract-v1.5.0` peel `3a7fa5ac`
- 未把其它 Agent 的 ambient dirty 计入本审查

## Blocking Findings

无。依赖 RM-03 DONE、父 AD RM-04 行、C01/C02 Owner 与冻结「不发 v1.6.0」均可解析。没有把 Docker 未跑写成允许 DONE。

## Major Findings

1. **C03 KEEP 与 AC-08 / AC-10 的可观察 Behaviour 不对齐。** Inventory 把 Distributed Harness 写成 EXISTS，Change Classification 把 C03 标 KEEP，并声称阻断点只是 FRESH Docker 指纹、不再写 Harness。独立抽查 `tools/acceptance/harness.py#run_compose_acceptance`（`8919e197`）：
   - 场景名 `bundle_lifecycle` 只对 `GET http://127.0.0.1:4510/api/v1/hermes/skill-installations` 断言 HTTP 200，没有安装、升级、摘要失败回滚或卸载。
   - `kill_central_a` 的 oracle 把 `unique_terminal` 写成字面 `True`，`ok` 只要求 injected / recovered / late_rejected，不检查第二 Attempt 或单一终态。
   AC-08 要求 B 以新 Attempt 接管且只产生一个终态；AC-10 要求真实 Edge Worker 完成 RM-03 Published Bundle 的安装/升级/回滚/卸载。KEEP 会禁止 Plan 补这些 oracle，Verification 无法关闭这两条 AC。这会改变可观察 Behaviour 与 Change Classification，构成 MAJOR。关闭方式二选一（不得两套都含糊）：
   - 把 C03 改回 **MODIFY**，明确 Harness 必须补齐 AC-08/AC-10 的可观察 oracle；或
   - 收缩 AC-08/AC-10 到当前 Harness 已能证明的行为，并把完整 Bundle 生命周期明确 **REUSE_EVIDENCE** 到 RM-03，不得假装 Compose GET 200 等于生命周期闭环。

## G1 Scope

范围收束为：KEEP 已落地 Strict Readiness / 真实 S3 / Native 夹具；关闭分布式验收证据；合同门禁对齐 v1.0.0–v1.5.0 全族；Newman 公共 JWT 不得用内部 Token 冒充员工合同。明确排除新合同版本、改写已发布目录、ChatCompletion parser、RM-12 PC-10–14、RM-16 live、PC-05/PC-08、Work UI。与 AD「RM-04 保持独立验收项 / 不得伪造 DONE / 不得把 RM-12 符合性并进」一致。无 BLOCKER。MAJOR 见上（C03 KEEP 把验收 Behaviour 收得比 AC 窄）。

## G2 Existing Capability / duplicate owner

抽查锚点可解析：`health_live` / `health_ready`、`S3StorageDriver` / `probe_isolation`（无 `_memory_store`）、`RunWorker.last_successful_loop_at`、`docker-compose.acceptance.yml` MinIO + `hermes-test` + `SKILL_AGENT_INSECURE_MODE: false`、`hermes_test_server.py` 对 `/v1/chat/completions` 返回 404、`check_contracts` 默认族含 `1.5.0`、正式 Collection 路径 `tests/postman/nodeskclaw_acceptance_closure.postman_collection.json`。无第三执行服务、无第二 StoragePort、无新合同生成链。无 BLOCKER。

## G3 Production Ownership

就绪仍归 Agent `app.main`；Artifact 字节仍归 Agent StoragePort；Harness / Compose / Newman 仍是 Repository Acceptance Assets，不是生产 Owner。Agent 仍是终态裁决者。员工仍只访问 Backend。C05 夹具不是 live Hermes Provider。无 BLOCKER。

## G4 KEEP/MODIFY/ADD/REPLACE/REMOVE

C01/C02/C05 KEEP 与源码事实一致。C04 MODIFY 与当前 Collection 缺 `/decision`、缺 `POST /api/v1/attachments`、checker 仍声明「v1.2.1 journey」一致。无 REPLACE，无需 REMOVE 矩阵。C03 KEEP **不成立**（MAJOR 1）。

## G5 Boundary

Work 只走 Backend JWT；内部 Token 仅限 Edge/Bundle/故障；禁止 `/test/*` 与 ChatCompletion Event Source；不改写已发布 Bundle；Compose `kill_central_a` 不得写成 RM-16 PC-05。AC-14 把已发布 `/decision` 与 Public Attachment 收进 Newman，PRD 已写明这是拓扑服务已发布路由、不是重开 RM-17/RM-18/RM-19 实现。未把两项独立发布门禁合成一个 Product FAIL。无 BLOCKER。Plan 约束见 Minor。

## G6 Behaviour → AC

C01→AC-01–05，C02→AC-05/06，C03→AC-07–11，C04→AC-12–14，C05→AC-07，AC-15 聚合。C03 KEEP 无法支撑 AC-08/AC-10 的 Behaviour（MAJOR 1）。其余 AC 可观察（HTTP 状态、跨 Central 校验和、非零退出、合同全族、两连跑隔离）。

## G7 Acceptance / Blocking / Evidence Integrity

- 历史 v1.6.3「内存 S3 / 空转 Harness / 只验 v1.2.0」标 STALE 并作废，没有把已关闭的实现缺口洗回 observation。
- CL-04 Docker 实跑仍 MISSING / FRESH，没有「blocking FAIL 允许 DONE」。
- CL-03 Newman 缺口保留为 C04 MODIFY。
- CL-02 冻结 v1.5.0：检查器与 tag 存在；本项零改写。
- CL-05/CL-06：禁止 pc05/pc08 live、禁止并入 RM-12/17/18/19 实现。口径来自已 APPROVED AD 与 RM-16 v1.6.15，不是执行阶段临时放宽。
- PRD 冻结的是路由与拓扑行为，未绑定具体 pytest 函数名或 live Tool 名。
- MAJOR 1 是本轮残留的 blocking 行为缺口（oracle 不足），不是把 FAIL 甩到下一 RM。

## Minor Findings

1. **AC-14 的 `/decision` 与 Public Attachment 是拓扑可达性，不是 RM-17/RM-18 live 再验证。** Compose 无独立 Attachment 扫描栈。Plan 必须断言公共 JWT 合同信封（含 fail-closed 4xx），不得要求 RM-18 病毒扫描 happy path，也不得因这两条失败去改 RM-17/RM-18 生产 Owner。checker 禁止 2xx 与 4xx 混断言；不要写回当前 Approve 那种 `400|403|404` 空过。
2. **SSE `assistant.delta`。** AC-14 已正确把「终态前打字机」留给 RM-19 live。夹具当前 SSE 仍是 `assistant.message`。Plan 不得为凑 Newman 去改生产 Coalescer，也不得把夹具 delta 缺失当成 RM-19 FAIL。
3. **公共 JWT 与内部 Token 分区。** 正式集合 Public 文件夹已用 `Bearer {{JWT_TOKEN}}`；内部项仍用 `X-Skill-Agent-Token`。以 AC-14 为准：公共文件夹禁止内部 Token；内部文件夹不得冒充员工合同。历史 v1.6.3 Minor 1 未完全关闭，由 C04 继续收。
4. **`check_postman_collection.py` 仍把公共旅程标成 v1.2.1。** 这是 C04 实现细节，不是新 Owner。Plan 扩展 journey 模式时不得把 Internal Southbound 写进 Public。
5. **AC-09 Spool oracle 偏弱。** 当前用目录文件集合变化近似「只重放一次」。若 C03 改为 MODIFY，应同时把单次重放 / 旧代拒绝写成可观察 oracle；若收缩 AC-10，不要顺手把 AC-09 也洗成 GET 200。
6. **DOD-05 / 旧 Plan。** canonical 路径 `.cursor/plans/rm-04_strict_readiness_7c349609.plan.md` 仍钉 `AD@1.0.0`。治理约束正确；不要当成运行时 AC。未 APPROVED 前不得 ponytail。
7. **历史 v1.6.3 Minor 2–5（insecure 假绿、Edge TLS、稳定 code、Hermes 夹具）。** 当前 Compose `SKILL_AGENT_INSECURE_MODE: false`、Caddy TLS、`health_ready` 已有 `migration.*` / `worker.loop.*` / `storage.probe.*` / `edge.heartbeat.*`、夹具 ChatCompletion 404。本版已吸收；Plan 不得回退 insecure 假绿。

## Closure Table

| Gate | Result | Evidence |
|---|---|---|
| G1 Scope | PASS（受 MAJOR 1 约束） | 独立验收 + 全族冻结 + 不并入 RM-12/16/17/18/19 实现；C03 KEEP 过窄 |
| G2 Existing Capability | PASS | 就绪 / S3 / Compose / 夹具 / checker / Collection 锚点可解析；无重复 Owner |
| G3 Production Ownership | PASS | Agent 终态与 StoragePort；Harness 非生产 Owner |
| G4 Classification | REVISE | C01/C02/C05 KEEP、C04 MODIFY 成立；C03 KEEP 不成立 |
| G5 Boundary | PASS | JWT 公共面；夹具非 live；不改写 v1.5.0；kill ≠ PC-05 |
| G6 Behaviour → AC | REVISE | AC-08/AC-10 超出当前 Harness oracle |
| G7 Evidence Integrity | PASS | Docker 缺口未洗白；v1.5.0 冻结 KEEP；无「FAIL 也 DONE」 |

## Independent Spot Checks

| Claim | Result |
|---|---|
| grounded_commit 可解析且为 HEAD | 已证实：`8919e197` |
| `health_live` 无外部依赖 | 已证实：只返回 status/service/role |
| `health_ready` 精确 Head + `last_successful_loop_at` + `probe_isolation` | 已证实 |
| S3 非内存字典 | 已证实：无 `_memory_store`；`put_object` HTTP |
| Compose MinIO / Native hermes-test / insecure=false / linux/amd64 | 已证实 |
| 夹具 ChatCompletion 404 | 已证实：`send_error(404)` |
| `check_contracts` 默认含 1.5.0 | 已证实 |
| tag `skill-run-contract-v1.5.0` peel | 已证实：`3a7fa5ac` |
| Collection 无 `/decision`、无 `/api/v1/attachments` | 已证实 |
| Harness `bundle_lifecycle` 只 GET installations | 已证实 |
| `kill_central_a` `unique_terminal: True` 硬编码 | 已证实 |
| Roadmap RM-04 仍 `IN_PRD` | 已证实 |
| 父 AD 拒绝把 RM-12 符合性并进 RM-04 | 已证实：Option P |

## Plan Notes

不得在 MAJOR 1 关闭前 converge 或生成有效实施 Plan。关闭后的 Plan 仍须：

- REVISE 同一路径 `.cursor/plans/rm-04_strict_readiness_7c349609.plan.md`，禁止第二份 `.plan.md`
- C04 只改 Acceptance 资产与 checker 聚合；合同生成链 KEEP
- 公共 Newman 不请求 `/api/v1/hermes/tasks/`，不把 `tools/postman` 调试集升格
- 验收取证必须 `SKILL_AGENT_INSECURE_MODE=false`；Backend 不得 `depends_on` Agent `service_healthy` 造成就绪死锁
- `/health` 不是 liveness
- 禁止再测 PC-05 / PC-08 live；禁止 ChatCompletion mock 结项

## Verdict

REVISE（1 MAJOR，7 MINOR，0 BLOCKER）。下一步 `smc-prd-grounding` mode=`revision`：只关闭 MAJOR 1（C03 KEEP vs AC-08/AC-10 oracle），并顺手把 Minor 1/2 中会改变 AC 阅读的句子写清楚。不要重做 full Grounding，不要改 C01/C02/C05 KEEP，不要把 RM-17/RM-18/RM-19 实现拉进 Scope。不得 converge 为 `APPROVED`，不得 ponytail。`REVIEW_REQUIRED` 阶段禁止 git commit。
