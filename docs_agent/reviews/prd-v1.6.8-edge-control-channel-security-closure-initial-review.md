# PRD Review

**Artifact:** `docs_agent/prd-v1.6.8-edge-control-channel-security-closure.md`

**Mode:** initial
**Verdict:** PASS

## Evidence Reuse

- `source_revision`：`AD-SKILL-AGENT-V16@1.4.0/RM-07`，与 APPROVED Architecture v1.4.0 的 Runtime Delegation（运行时委派）边界一致。
- `grounded_commit`：`dd924ab751225184958186e189810240a7add1a4`；`python tools/agent-skills/evidence_freshness.py ...` 返回 `REUSE`，本轮仅作独立 Gate 判断，不重复 full Grounding。
- `python tools/agent-skills/validate_prd.py ... --require-evidence` 通过；Roadmap 校验通过，RM-07 的唯一依赖 RM-05 为 `DONE`，所以进入 `READY` 合法。
- 未提交工作树（`nodeskclaw-agent/app/db_metadata.py` 与 `.cursor/plans/`）不计入本审查；PRD Evidence Baseline 已明确只以 `dd924ab7` 为准。

## Blocking Findings

无。RM-07、APPROVED Architecture、依赖、源码基线和 Evidence Baseline 均可解析。

## Major Findings

无。PRD 将 Backend Edge 域与 Agent Edge Worker（边缘工作器）的相邻协议职责拆为独立 Capability：Backend 唯一拥有身份生命周期、请求验证、命令签发和审计；Agent 唯一拥有本地证明生成、命令验签与重放消费记录。没有 Owner/Hybrid（混合归属）歧义。

## Minor Findings

无。

## Gate Results

| Gate | Result | Independent judgement |
|---|---|---|
| G1 Scope | PASS | 只关闭 Internal Edge Control Channel；RM-04 生产验收、RM-08 Shared Contract、RM-10 Trace/Metrics、Public Work 与 Runtime Delegation 实现均明确排除 |
| G2 Existing Capability / reuse | PASS | 静态 Token、节点绑定、Delivery Generation 和出站轮询均被准确列为可复用但不充分的现状；没有把代次栅栏误报为命令完整性 |
| G3 Production Ownership | PASS | C01/C03/C05/C06 是 Backend Edge 域，C02/C04 是 Agent Edge Worker，C07 是 Backend Contract Package，C08 是 Agent Run 域；每项只有一个 Production Owner |
| G4 Change Classification | PASS | 安全协议和本地消费均为 MODIFY，审计为 ADD，投递栅栏、Public Contract、Hybrid 归属为 KEEP；没有隐含 REPLACE 或删除承诺 |
| G5 API/IPC/Auth/Contract/Security Boundary | PASS | 明确区分一次性登记材料、有限期身份、双向签名、Node/用途/摘要/时间/Nonce/Sequence 绑定、过期/撤销和 TLS；内部命令封套不进入 Public Contract，秘密不进入持久化或日志 |
| G6 Behaviour -> Acceptance Criteria | PASS | AC-01 至 AC-08 覆盖登记、轮换、双向有效证明、验签、重放/乱序/错节点/过期、跨重启 Spool、Delivery Generation 兼容、数据最小化和既有执行边界 |

## Independent Spot Checks

| Claim | Result |
|---|---|
| 当前 Backend 只接受 `X-Edge-Token` Hash | 已证实：`internal_edge._authenticate_edge` 仅比对 `EdgeNode.token_hash`、可选 node ID 和 disabled 状态 |
| 当前 Agent 对所有 Internal Edge 请求复用静态 Header | 已证实：`EdgeWorker._headers` 只返回 `X-Edge-Token`；各心跳、轮询、事件、安装与 Artifact 调用复用该 Header |
| 现有 Delivery Generation 不是身份或命令验证 | 已证实：它只在续租、事件、Artifact 等路由校验投递代次；Job/安装/按需负载没有签名封套 |
| 唯一 Run/Event 与 Hybrid Owner 未被 RM-07 改写 | 已证实：PRD 仅在 Internal Edge 南向通道加入认证/完整性，C08 与 Non-Goals 保持 Agent 既有执行事实和资源放置边界 |

## Conclusion

Initial Gate PASS。PRD 可以由 `smc-prd-converge` 仅进行状态收敛为 `APPROVED`；随后 Roadmap RM-07 可从 `READY` 进入 `IN_PRD`。本审查不包含实施计划、精确私有符号或实现 Todo。
