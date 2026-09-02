---
work_item_id: RM-07
version: 1.6.8
status: APPROVED
target_branch: main
review_verdict: PASS
approved_at: 2026-09-02T17:36:19+08:00
source_revision: AD-SKILL-AGENT-V16@1.4.0/RM-07
grounded_commit: dd924ab751225184958186e189810240a7add1a4
---

# DeskClaw 团队版 Edge Control Channel 安全闭环 PRD v1.6.8

本文定义 RM-07：在既有 Backend Edge 域与 Agent Edge Worker（边缘工作器）的出站控制通道上，收敛节点身份登记、可控轮换、请求认证和 Backend 下发命令完整性；使过期、重放、错节点或验签失败的控制消息在产生执行副作用前被拒绝。

## Scope

本阶段只升级 Backend↔Agent 的 Internal Edge Control Channel（内部边缘控制通道）。Backend Edge 域拥有节点登记、身份状态、Credential（凭证）生命周期、出站请求验证、控制命令签发与安全审计；Agent Edge Worker 拥有本地身份材料保管、出站请求证明、Backend 命令验签，以及重放命令的持久化拒绝。既有 EdgeJob/Delivery Generation（投递代次）、Run/Attempt/Step（运行/尝试/步骤）和 Agent 的唯一执行事实源保持不变。

控制通道必须具备一次性登记、有限期身份、受控轮换、双向签名、Node binding（节点绑定）、时间有效期、Nonce（随机数）与每个方向单调 Sequence（序列）语义。Backend 下发到 Edge 的每一项可执行或状态变更命令必须携带可验证的命令封套；Agent 只有在封套完整、目标节点匹配、未过期且未消费时才能产生 Connector、安装、Artifact 或 Job 状态副作用。Edge 向 Backend 的内部请求同样必须用当前有效节点身份证明；Backend 在写入心跳、租约、事件、Artifact、安装或 on-demand（按需）状态前验证其完整性与新鲜度。

本阶段不替换 HTTPS（生产环境仍要求 TLS），不改写已发布 Public Skill Run v1.0–v1.2.1 合同，不开放 Agent 入站端口，不引入 Platform Multi-Agent（平台多智能体）、第二个 Run/Event 状态机、外部 Work 前端，亦不把 RM-04 的多节点生产验收或 RM-10 的全局 Trace/Metrics（链路追踪/指标）并入本交付项。

## Product Boundary

节点运营者只能通过已鉴权的 Backend Edge 管理边界发起登记、启用、禁用或轮换；客户端、外部 Work 与 Agent 均不能自行声明节点身份、延长租期、选择另一个节点或伪造 Backend 命令。登记产生的 bootstrap material（引导材料）只可用于完成一次身份绑定，不能作为长期控制通道凭证。轮换后旧身份必须有明确、可审计的失效或有限迁移窗口；撤销、禁用、过期或未完成登记的身份均不得继续发起或接收控制操作。

Backend 是控制命令的唯一签发者，并将命令绑定到组织、目标 Node、用途、时间窗、Nonce、Sequence 与不可篡改的有效载荷摘要。Agent 不信任传输、缓存、Spool 或本地旧 Job 中的裸负载；它必须先验证 Backend 信任材料、命令封套和持久化的消费/序列状态。`delivery_generation` 仍只裁决租约代次与陈旧执行回传，不能替代身份验证、命令签名或重放防护。

身份秘密、私钥、签名原文和引导材料不得写入数据库明文、Run Snapshot、Job Payload、Spool、Event、Artifact、日志、审计明细或错误响应。审计仅保存 opaque identity/key reference、节点、用途、时间和拒绝类别；错误保持稳定、非敏感，并遵循 `error_code`、`message_key` 与 `message` 合同。

## Current Capability Inventory

当前能力以已提交基线 `dd924ab751225184958186e189810240a7add1a4` 为准。Grounding 模式为 `discover`；未提交工作树不计入本清单。

| Capability | Current State | Production Owner | Evidence | Grounding Result |
|---|---|---|---|---|
| Edge 节点登记与静态 Token | PARTIAL | Backend Edge 域 | `EdgeNodeService.register`、`EdgeNode.token_hash`、管理端 `POST /edge-nodes` | 运营者可创建节点并一次返回随机 Token，Backend 只保存 SHA-256；没有一次性登记证明、身份公钥、过期、轮换、撤销历史或安全审计；MODIFY |
| Edge→Backend 内部请求认证 | PARTIAL | Backend Edge 域 | `internal_edge._authenticate_edge`、`X-Edge-Token` | 每个 Internal Edge 路由只校验静态 Token Hash、可选节点 ID 与 disabled 状态；没有请求签名、时间窗、Nonce 或 Sequence；MODIFY |
| Agent Edge 出站身份使用 | PARTIAL | Agent Edge Worker | `EdgeWorker._headers`、`SKILL_AGENT_EDGE_TOKEN` | Worker 对心跳、拉取、续租、事件、安装和 Artifact 请求复用单个 Header Token；生产仅校验 HTTPS；无本地身份生命周期、请求证明或命令验签；MODIFY |
| Backend→Edge Job 与控制负载 | PARTIAL | Backend Edge 域 | `claim_edge_job`、Desired Installation 与 on-demand 路由 | Backend 已按已认证节点与组织返回 Job、安装和按需请求，但负载没有 Backend 签名、目标绑定封套、过期、Nonce 或命令 Sequence；MODIFY |
| Edge 执行侧命令消费 | PARTIAL | Agent Edge Worker | `EdgeWorker._claim_job`、`_reconcile_desired_installations`、`_pull_and_fulfill_on_demand_requests` | Agent 会直接消费已传输的 Job/安装/按需负载；没有验签、Node/有效期检查或跨重启的命令消费记录；MODIFY |
| Delivery Generation 租约栅栏 | EXISTS | Backend Edge Job 域 | `EdgeJob.delivery_generation`、Internal Edge renew/events/artifact 路由及 Edge Spool | Backend 对续租、事件和 Artifact 拒绝缺失或陈旧代次；这是执行投递栅栏，不能证明消息来源或阻止带有效代次的重放；KEEP |
| Internal Edge 组织/节点隔离 | EXISTS | Backend Edge 域 | `EdgeNode.org_id`、认证后的查询过滤、EdgeJob/Installation/Artifact 路由 | 现有组织与节点查询边界可复用；认证身份与命令完整性需在此边界内增强；MODIFY |
| 已发布 Public Skill Run 合同 | EXISTS | Backend Contract Package | `contracts/skill-run/` | Public Consumer Contract 已冻结；控制通道升级只能使用内部南向合同；KEEP |
| Hybrid 执行与唯一 Run/Event Owner | EXISTS | Agent Run 域 | Run/Attempt/Step 与 EdgeJob 链路 | Agent 的唯一执行事实和 Hybrid 编排边界已冻结；控制通道升级不改变其归属；KEEP |

## Target End-State Inventory

| Capability | Target State | Production Owner | Boundary |
|---|---|---|---|
| Node enrollment and identity lifecycle（节点登记与身份生命周期） | 运营者创建的一次性引导材料只完成节点身份绑定；Backend 记录可验证身份、状态、用途、有效期、轮换/撤销与最小审计。常规控制通道只接受已登记、启用且未过期的身份 | Backend Edge 域 | Backend 不保存私钥或明文长期秘密；外部 Work 不能直接发起身份操作 |
| Edge outbound request proof（Edge 出站请求证明） | Agent 使用本地有效身份为每项 Internal Edge 请求证明节点、方法/目标、有效载荷摘要、时间、Nonce 和单调请求 Sequence；Backend 在任何状态写入前验证并拒绝重复、错节点、过期或验签失败请求 | Agent Edge Worker | Backend 的对应验证和拒绝裁决由 C03 保有；本项只拥有本地证明生成与轮换过渡 |
| Signed command envelope（签名命令封套） | Backend 为 Job、安装与 on-demand 等所有下发的可执行或状态变更命令签发绑定组织、目标节点、用途、有效期、Nonce、命令 Sequence 与有效载荷摘要的封套 | Backend Edge 域 | 不向 Public Skill Run 包暴露内部签名材料；命令封套不替代 Run/Attempt/Delivery Generation |
| Edge command verification and replay guard（Edge 命令验签与重放防护） | Agent 在任何副作用前验证 Backend 信任材料、签名、Node、用途、时效、Nonce 与持久化命令 Sequence/消费记录；重放、旧序列、过期、错节点或验签失败均无副作用 | Agent Edge Worker | Spool/重启不能绕过消费记录；拒绝不得改变 Job、安装、Artifact 或 Connector 状态 |
| Delivery fencing（投递栅栏） | 保留现有 Job 租约和 Delivery Generation 校验，并在通过身份/命令验证后继续阻止旧投递回传 | Backend Edge Job 域 | 不把投递代次当成身份、签名或重放协议 |
| Security observability（安全可观测性） | 登记、轮换、撤销、过期、验签和重放拒绝以非敏感、安全可关联的审计/错误事实呈现 | Backend Edge 域 | 不记录引导材料、私钥、签名原文或业务 Payload |
| Public contract preservation（公共合同保持） | 已发布 Public Skill Run 合同保持字节与语义不变，Internal Edge 封套只存在于南向协议 | Backend Contract Package | 外部 Work 不消费或推断控制通道材料 |
| Hybrid execution ownership（混合执行归属） | EdgeJob 仍由既有 Hybrid Step Plan 和 Agent Run/Event 事实驱动；控制通道只认证与保护其传输 | Agent Run 域 | 不新增 Run/Event Owner 或改变 Central/Edge/Hybrid 资源放置 |

## Change Classification

| Change ID | Capability | Action | Production Owner | Observable Target |
|---|---|---|---|---|
| C01 | Node enrollment and identity lifecycle（节点登记与身份生命周期） | MODIFY | Backend Edge 域 | 一次性引导、身份绑定、启用/禁用、有效期、轮换和撤销均可验证与审计；静态 Token 不再作为长期控制信任 |
| C02 | Edge outbound request proof（Edge 出站请求证明） | MODIFY | Agent Edge Worker | 每个 Internal Edge 请求带有当前身份的签名、新鲜度、Nonce 和单调请求 Sequence；Agent 在不暴露秘密的前提下完成轮换过渡 |
| C03 | Internal Edge request verification and command issuance（内部请求验证与命令签发） | MODIFY | Backend Edge 域 | Backend 在状态写入前验证 C02，并为下发控制命令生成签名、Node 绑定、时间窗、Nonce、Sequence 和载荷摘要 |
| C04 | Edge command verification and replay guard（Edge 命令验签与重放防护） | MODIFY | Agent Edge Worker | Job、安装和 on-demand 命令只有通过验签、目标、时效和持久化反重放检查后才执行；失败不产生副作用 |
| C05 | Delivery Generation and existing Edge execution fencing（投递代次与既有 Edge 执行栅栏） | KEEP | Backend Edge Job 域 | 保持续租、事件、Artifact 的旧代拒绝，且不将其误用为身份或消息完整性证明 |
| C06 | Security audit and stable rejection contract（安全审计与稳定拒绝合同） | ADD | Backend Edge 域 | 身份生命周期与拒绝结果可审计；响应不含秘密并提供稳定错误语义 |
| C07 | Public Skill Run contract preservation（公共技能运行合同保持） | KEEP | Backend Contract Package | v1.0–v1.2.1 不改写；Internal Edge 命令封套不进入外部 Work 合同 |
| C08 | Hybrid execution ownership（混合执行归属） | KEEP | Agent Run 域 | 不新增 Run/Event Owner，不改变 Central/Edge/Hybrid 资源放置语义 |

## Behaviour And Security Contract

### Enrollment, Rotation And Revocation

节点登记必须将运营者身份、组织和节点名称绑定到一次性且有限期的引导材料。Agent 只能用该材料完成一次节点身份绑定；绑定后，日常心跳、拉取、回传与安装调谐不能继续把该材料当作长期 Token。Backend 必须能够为已登记节点发起受控轮换、设定有限迁移窗口并撤销旧身份；禁用、撤销、过期、重复使用、跨组织或节点不匹配的材料/身份必须 fail-closed。轮换期间不得以长期并行接受旧静态 Token 降级安全；迁移窗口结束后旧身份的每一种请求均被拒绝。

### Bidirectional Integrity

Agent 向 Backend 的每个 Internal Edge 请求必须证明当前节点身份、请求方法和目标、规范化有效载荷摘要、请求时间、Nonce 与单调请求 Sequence。Backend 必须在读取会造成消费、认领或状态改变的语义前验证上述要素，并为每个节点保留足以拒绝重放/乱序的最小状态。允许的时钟偏差、Sequence 恢复和轮换过渡必须是有限、可验证和 fail-closed 的，不能接受无限窗口或仅凭节点 ID 放行。

Backend 向 Agent 下发的 Job、Desired Installation、on-demand Artifact 等可执行或状态变更命令必须提供统一的签名命令封套。封套绑定组织、目标 Node、命令用途、命令 ID/Nonce、命令 Sequence、签发与过期时间和规范化 Payload 摘要。Agent 必须在解码负载、写入 Spool 或执行任何 Connector/安装/Artifact/Job 状态副作用之前完成验签与节点、时间、用途、Nonce、Sequence 的持久化检查。信任材料轮换必须能同时支持未过期命令的验证，不接受未知、撤销或过期签发者。

### Fencing, Fail-Closed And Data Minimization

命令或请求的身份/完整性验证不能替换 Delivery Generation、Run Generation、Attempt 或 Step 栅栏；通过验签的旧代回传仍须按现有规则拒绝。相反，具有当前 Delivery Generation 的伪造、重放、过期、错节点或签名失败消息也必须在副作用前被拒绝。网络重试或 Agent 重启可按协议安全恢复，但不得重新消费已接受的命令或复用已消费的 Nonce。

任何安全拒绝必须保持节点隔离、组织隔离和非敏感错误；不得回显 Token、引导材料、私钥、公钥以外的验证材料、完整签名或业务负载。审计与日志需要可关联到节点、身份版本、方向、用途和拒绝类别，但不得成为第二份 Job/Run/Event 事实源。

## Acceptance Criteria

- **AC-01 / C01**：运营者登记 Edge 节点后，只能在有限期内用一次性引导材料完成该节点的身份绑定；重复使用、超时、跨组织、错节点、未完成登记或禁用节点均被拒绝，且不建立有效控制身份。
- **AC-02 / C01/C06**：已登记节点可以受控轮换或撤销身份。轮换窗口内仅允许协议定义的有限过渡；窗口后旧身份、已撤销身份和长期静态 Token 都不能认证任一 Internal Edge 操作。生命周期操作与拒绝留下不含秘密的审计事实。
- **AC-03 / C02/C03**：心跳、Job 拉取与租约、事件、Artifact、安装和 on-demand 的每个 Internal Edge 请求均带有节点身份、规范化请求绑定、时间、Nonce 和单调请求 Sequence 的可验证证明。缺失、篡改、过期、重放、乱序、错节点或验签失败的请求在任何读取消费或状态写入前被拒绝。
- **AC-04 / C03/C04**：Backend 下发的 Job、Desired Installation、on-demand Artifact 与其它可执行/状态变更命令均携带签名封套，封套绑定目标 Node、组织、用途、Payload 摘要、时间、Nonce 与命令 Sequence。Agent 只接受可验证且未过期的 Backend 签发者。
- **AC-05 / C04**：重放、旧 Sequence、已消费 Nonce、错节点、过期、未知/撤销签发者或签名篡改的 Backend 命令，在 Agent 重启、网络重试或 Spool 重放后仍不会执行 Connector、安装、Artifact、Job 状态或其它外部副作用。
- **AC-06 / C05**：身份/命令验签通过后，既有 Delivery Generation、Run Generation、Attempt、Step 和取消栅栏继续生效；陈旧投递的续租、事件、Artifact 或命令回传仍无副作用。
- **AC-07 / C06**：身份登记、绑定、轮换、撤销、过期、请求验签和命令验签的成功/拒绝可按节点和身份版本关联；数据库、Agent 本地状态、Spool、Job Payload、Event、Artifact、日志、审计与错误响应均不保存或泄露引导材料、私钥、长期明文 Token、完整签名或业务负载。
- **AC-08 / C01–C08**：自动化验证覆盖登记、轮换/撤销、双向有效消息、请求与命令篡改、重放、乱序、错节点、过期、Agent 重启/Spool、Delivery Generation 兼容和 Public Contract 不变；不回归 RM-05 Connector 执行边界、RM-06 执行前授权复核或现有唯一 Run/Event Owner。

## Definition of Done

- **DOD-01**：C01–C08 均有正向、过期、撤销、篡改、重放、乱序、错节点与跨重启验证证据；所有失败案例证明没有 Backend 状态写入或 Agent 外部执行副作用。
- **DOD-02**：身份生命周期、命令签发、请求验证和安全审计仍由 Backend Edge 域拥有；本地证明、验签与命令消费仍由 Agent Edge Worker 拥有。未新增第二 Run/Event 状态机、平台级调度器、公开南向合同或外部依赖服务。
- **DOD-03**：实施时新建或变更模型随 Alembic 自动生成迁移提交；所有数据库删除继续使用逻辑删除；秘密扫描与自动化测试证明不泄露身份材料。
- **DOD-04**：Review 与 Verification 均 PASS，真实 implementation commit 和验证证据写入 Roadmap 后，RM-07 才可标记 `DONE`。
- **DOD-05**：Backend/Agent 控制通道的真实协议、Owner、轮换/反重放边界与测试证据同步至 `lat.md`，且 `lat check` 通过。

## Non-Goals

- 不替换 TLS 或新增 Agent 入站控制端口。
- 不改写 Public Skill Run v1.0–v1.2.1 合同，也不把 Internal Edge 命令封套发布给外部 Work。
- 不实现 Platform Multi-Agent、Child Run、第二个 Run/Event 状态机或新的 Hybrid 编排 Owner。
- 不实现 RM-04 的 Docker/多节点生产验收、RM-08 Shared Agent Execution Contract、RM-09 Consumer Contract 或 RM-10 全局 Trace/Metrics。
- 不把身份秘密、私钥或签名材料托管到外部服务，也不引入新的外部依赖作为本阶段前置条件。

## Evidence Baseline

当前证据以 `dd924ab7` 为准；Edge 仅有静态 Token 认证与 Delivery Generation 栅栏，尚无身份轮换或双向控制消息完整性。

| Claim | Evidence Anchor | Result |
|---|---|---|
| Edge 节点模型只保存 `token_hash` 与状态 | `nodeskclaw-backend/app/models/connector/edge_node.py#EdgeNode`、`nodeskclaw-backend/alembic/versions/a9063125204c_add_connector_center.py` at `dd924ab7` | PARTIAL：无身份密钥、引导材料生命周期、过期、轮换、撤销或重放状态；C01 MODIFY |
| 运营者登记直接返回随机 Token | `nodeskclaw-backend/app/services/connector/edge_node_service.py#EdgeNodeService#register`、`nodeskclaw-backend/app/api/hermes_skill/edge_nodes_router.py#register_edge_node` at `dd924ab7` | PARTIAL：一次返回明文 Token，但不是一次性登记或身份绑定；C01 MODIFY |
| Internal Edge 认证只比对静态 Token Hash | `nodeskclaw-backend/app/api/internal_edge.py#_authenticate_edge` at `dd924ab7` | PARTIAL：可选 Node ID 与 disabled 检查存在；无签名、新鲜度、Nonce 或 Sequence；C03 MODIFY |
| Backend 已有按节点隔离的 Job/安装/按需下发 | `nodeskclaw-backend/app/api/internal_edge.py#claim_edge_job`、`#get_desired_installations`、`#pull_edge_artifact_on_demand_requests` at `dd924ab7` | PARTIAL：返回的负载未带 Backend 签名命令封套；C03 MODIFY |
| Agent 使用单一 `X-Edge-Token` 访问全部 Internal Edge 操作 | `nodeskclaw-agent/app/config.py#Settings`、`nodeskclaw-agent/app/services/edge_worker.py#EdgeWorker#_headers` at `dd924ab7` | PARTIAL：Edge 生产仅强制 HTTPS；无身份材料轮换、请求签名或命令验签；C02/C04 MODIFY |
| Edge 已有 Job 代次与 Spool 重放防护 | `nodeskclaw-backend/app/models/connector/edge_job.py#EdgeJob`、`nodeskclaw-backend/app/api/internal_edge.py#renew_edge_job_lease`、`nodeskclaw-agent/app/services/edge_worker.py#EdgeWorker#_flush_spool` at `dd924ab7` | EXISTS：Delivery Generation 防旧代回传，不认证消息来源或命令；C05 KEEP |
| Internal Edge 测试覆盖静态 Token 与代次拒绝 | `nodeskclaw-backend/tests/connector/test_edge_internal.py`、`nodeskclaw-backend/tests/api/test_internal_edge_api.py`、`nodeskclaw-agent/tests/test_edge_worker.py` at `dd924ab7` | PARTIAL：测试未覆盖 enrollment、rotation、签名、Nonce、Sequence、命令重放或错节点；C01–C04/C06 ADD 验证 |
| Architecture 冻结 Backend/Agent/Hybrid/Runtime 边界 | `docs_agent/architecture/AD-SKILL-AGENT-V16.md#Ownership & Boundaries` and `#Runtime Delegation Entry` at `AD-SKILL-AGENT-V16@1.4.0` | EXISTS：Backend Edge 域拥有身份/控制面，Agent 是唯一执行面；不实现 Platform Multi-Agent 或第二 Run Owner；C07 KEEP |
| 已发布 Public Skill Run 合同不含 Internal Southbound | `nodeskclaw-backend/contracts/skill-run/` at `dd924ab7` | EXISTS：C07 KEEP，内部协议不改写已发布目录 |

## Dependencies And Handoff

RM-05 已 `DONE`，所以 RM-07 可进入 PRD Grounding。本 PRD待独立 `smc-prd-review initial`；只有 verdict 为 PASS 后才能由 `smc-prd-converge` 改为 `APPROVED`，并把 Roadmap Item 置为 `IN_PRD`。批准后由 `smc-plan-from-approved-prd-ponytail` 生成最小实施计划；RM-08 仍必须等待 RM-06 与 RM-07 都 `DONE`。
