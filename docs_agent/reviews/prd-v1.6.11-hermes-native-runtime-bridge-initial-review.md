# PRD Review

**Artifact:** `docs_agent/prd-v1.6.11-hermes-native-runtime-bridge.md`  
**PRD version:** 1.6.11  
**Mode:** initial  
**Verdict:** PASS

## Evidence Reuse

- `source_revision`: `AD-SKILL-AGENT-V16-A1@1.6.0/RM-13`
- `grounded_commit`: `81babaebae7c7a1400db5be6139633af47bf5161`（与 HEAD 相同）
- `python tools/agent-skills/evidence_freshness.py ... --source-revision AD-SKILL-AGENT-V16-A1@1.6.0/RM-13`：`REUSE`
- `python tools/agent-skills/validate_prd.py ... --require-evidence`：通过
- 本轮不做 full Grounding。只对已记录锚点做独立判断，并抽查 `execute_hermes_run`、`engine_port.py#execute_engine`、`run_attempts` 列、`get_capabilities` 调用点、仓内 `2026.4.23`
- A1 增补文档仍为 `PROPOSED`；Roadmap RM-13 为 `BACKLOG`（依赖 RM-11 已 DONE）。不把该上游状态写成 PRD REVISE
- Knowledge `KnowledgeRuntimeBinding` 已被正确排除

## Blocking Findings

无。范围止于 A1 Phase A；不吞并 RM-14 Coalescer、RM-15 控制闭环、RM-16 Conformance。Backend 不直连 Hermes 生产执行。Binding 单一事实源、禁止两套存储。REPLACE/REMOVE 有对应矩阵。

## Major Findings

无。生产 ChatCompletion Event Source 的 REMOVE 落在既有 Agent Hermes Adapter；Capability Probe / Native payload / Binding / reconciliation / stop / 稳定错误均为既有 Owner 上的 ADD。EnginePort、Event SoT、终态聚合 KEEP。未把 Knowledge Binding 借来当 Attempt Binding。

## Minor Findings

1. **C01 / C06 一行两个 Production Owner。** 版本地板探测与 Native 协调属于 Agent Adapter/Run；Dockerfile/seed 属于制品与 Backend seed。Plan 必须拆 WRITE_OWNER，不得让 Backend 成为 Runtime Adapter。
2. **Replacement 第二行（HermesTaskWorker API-server 执行器）超出本项 AC。** AC-08 只证明 Agent 生产路径不再调用 `/v1/chat/completions`。员工是否还命中 `HermesTaskWorker` 是 RM-12 单一平面。Plan 不得把删除/改造 HermesTaskWorker 写成 RM-13 WRITE_OWNER。
3. **Native `message.delta` 在本项的持久化语义未写成可观察 AC。** Behaviour 允许接入既有 Event SoT 且不要求 Coalescer，同时禁止把 ChatCompletion token delta 当作正式语义。Plan 可将 Native 控制/终态事件写入 SoT；assistant 文本保真归 RM-14；不得保留 ChatCompletion parser，也不得把逐 token durable 风暴标成 RM-13 DONE。
4. **Binding 存储二选一留给 Plan 是合法的。** Minimality 倾向扩展 `run_attempts`。Plan 必须只选一套事实源，Public 不返回 `runtime_run_id`。
5. **`HermesApiServerClient.get_capabilities` 已存在于 Backend。** Inventory 正确禁止把它升级为生产 Runtime Owner。Plan 在 Agent Attempt 路径实现 Probe，不要让 Backend 代为判定 Attempt Capability Snapshot。

## Plan Notes

- 禁止 silent fallback 到 `/v1/chat/completions`。
- 禁止 Backend → Hermes `/v1/runs`。
- 禁止重订阅 `/events` 作为 Recovery。
- 禁止借用 `nodeskclaw-knowledge` RuntimeBinding。
- 禁止把 RM-14/RM-15/RM-16 的 AC 写进本项 Todo。
- 与 RM-12 并行；本项 DONE 不要求 RM-12 DONE。
- converge 建议在 A1 Architecture Review PASS 之后执行。

## Closure Table

| Gate | Result | Evidence |
|---|---|---|
| G1 Scope | PASS | Phase A Native Bridge；Non-Goals 排除 Coalescer、Approval 闭环、PC-01–PC-09。Minor 2 把 Worker 删除从本项 DONE 中剔除 |
| G2 Existing Capability / duplicate owner | PASS | EnginePort/SoT/Fencing KEEP；Adapter PARTIAL→MODIFY/ADD；Knowledge Binding KEEP 且隔离；无第二 Runtime Owner |
| G3 Production Ownership | PASS | Agent 拥有 Run/Attempt/Event/Terminal；Hermes 只拥有 Attempt 内 Runtime 事实。Minor 1 要求拆 seed/Adapter 写入，不合并 Owner |
| G4 KEEP/MODIFY/ADD/REPLACE/REMOVE | PASS | C09 REMOVE 有 Replacement 第一行；C02–C08 ADD 于既有 Adapter/Run；C11 合同 KEEP |
| G5 API/IPC/Auth/Contract/Security Boundary | PASS | `API_SERVER_KEY` / `runtime_run_id` 不进 Public；v1.2.1 不改；fail-closed 与 fencing 已写 |
| G6 Behaviour -> Acceptance Criteria | PASS | C01↔AC-01/02；C02↔AC-03；C03/C04↔AC-04；C05/C06↔AC-05；C07↔AC-06；C08↔AC-07；C09↔AC-08；C04/C10↔AC-09；C11↔AC-10 |
| G7 External Contract Maturity | PASS | 不依赖未发布 Public 合同增量；内部 Runtime 错误不倒灌 v1.2.1 schema |
| G8 Cross-Repo Ownership | PASS | Work 不在本仓；Hermes Runtime 是外部执行面，Owner 边界已写 |
| G9 Global Change Traceability | PASS | C01–C12 稳定；Plan 可继承 |

## Independent Spot Checks

抽查对应当前 HEAD/`grounded_commit` `81babaeb`。

| Claim | Result |
|---|---|
| Agent 生产路径仍 `POST /v1/chat/completions` | 已证实：`hermes_engine.py#execute_hermes_run` |
| EnginePort 只分发 hermes/connector | 已证实：`engine_port.py#execute_engine` |
| `run_attempts` 无 Runtime Binding 字段 | 已证实：`db_metadata.py#run_attempts` |
| Backend `get_capabilities` 未被 Skill Run 调用 | 已证实：`hermes_skill/` 无引用 |
| 仓内默认版本仍为 `v2026.4.23` | 已证实：Dockerfile / `seed.py` / seed 测试断言 |
| cancel 不通知 Runtime | 已证实：`cancel_event.is_set()` 后 `return` |
| Knowledge Binding 是另一 Owner | 已证实：PRD KEEP C12 |

## Conclusion

该 Stage PRD 内容门禁 PASS。Minor 2/3 作为 Plan 约束即可，不必 grounding revision。converge 不得把 HermesTaskWorker 删除并进 C09，不得改变 Binding 单一 Owner。

本审查不修改 PRD，不 git commit。
