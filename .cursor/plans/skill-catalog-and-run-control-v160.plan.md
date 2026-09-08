---
plan_contract: smc.plan.v3.2
commit_policy: post_review
source_revision: AD-SKILL-AGENT-V16@1.0.0/RM-01
grounded_commit: 636af7adc7905776674074775c0da943ffa09d63
grounding_source: committed_baseline
working_tree_fingerprint: clean
---

# RM-01 Implementation Plan

## 前端表现变化

本次改动无前端表现变化。不开发 Work UI，不改 `work-expert v1.0.2` 冻结合同。员工端仍走 `/api/v1/mcp` 与 `/api/v1/runs/*`；变化在 API 合同与错误码映射，页面无新增、删除、状态、样式或交互行为变化。

## Approved PRD

[Approved PRD](../../docs_agent/prd-v1.6.0-skill-catalog-and-run-control.md)

## Scope

- In: Backend 公共 Catalog v1.1 投影、Chat Skill 发布门禁校验与元数据冻结、Run Resume 与 Approval 代理请求转发修复、Agent 4xx 稳定公共错误映射、Skill Run v1.1.0 合同包生成与校验、Accepted Result 可选 contract_version 兼容字段。
- Out: RM-02 语义事件（assistant/reasoning/tool/clarify/artifact）、RM-03 Edge Bundle 下载与原子安装、RM-04 分布式验收、Work UI 开发、新增独立微服务、改动 Agent 状态机或使 Backend 成为第二 Run 状态 Owner。
- Production Owner inherited from PRD: `nodeskclaw-backend` Run API、Hermes Skill 域（`SkillReleaseService`、`McpToolMapper`）、MCP Gateway（`RuntimeSkillRunService`）与 Contract Package。

## Grounding Evidence Ledger

| Change ID | Target | Baseline State | Symbol / Entry Resolution | Caller / Callee Evidence | Existing Reuse Search | Result |
|---|---|---|---|---|---|---|
| C01 | `nodeskclaw-backend/app/api/runs.py#_agent_post` | PARTIAL | `_agent_post` 顶层函数存在 | `resume_run` 与 `approve_run` 调用 `_agent_post` 传 `body=` | 现有 `_agent_post` 声明 `json_body`，直接复用并修正参数名 | PASS |
| C02 | `nodeskclaw-backend/app/services/hermes_skill/mcp_tool_mapper.py#McpToolMapper#_skill_to_tool_dict` | PARTIAL | `McpToolMapper._skill_to_tool_dict` 方法存在 | `list_tools` 迭代调用 `_skill_to_tool_dict` 投影已发布技能 | 现有 `McpToolMapper` 类已负责工具字典转换，直接复用 | PASS |
| C03 | `nodeskclaw-backend/app/services/hermes_skill/skill_release_service.py#SkillReleaseService#publish` | PARTIAL | `SkillReleaseService.publish` 方法存在 | API 端点调用 `publish` 创建并发布 Release 快照 | 现有 `SkillReleaseService` 负责发布生命周期，直接复用 | PASS |
| C04 | `nodeskclaw-backend/scripts/contracts.py#generate_skill_run_contracts` | PARTIAL | `generate_skill_run_contracts` 函数存在 | CLI entrypoint `--family skill-run` 调用生成函数 | 现有 `contracts.py` 生成链已存在，直接复用扩展 v1.1.0 | PASS |
| C07 | `nodeskclaw-backend/app/api/runs.py#_agent_post` | PARTIAL | `_agent_post` 顶层函数存在 | 代理向 Agent 发起 HTTP 请求时捕获 `HTTPStatusError` | 现有 `AppException` 体系支持结构化错误码与文案键映射，直接复用 | PASS |
| C08 | `nodeskclaw-backend/app/services/hermes_skill/runtime_skill_run_service.py#RuntimeSkillRunService#build_structured_content` | PARTIAL | `RuntimeSkillRunService.build_structured_content` 方法存在 | Gateway 接收 Agent 响应后调用构建 MCP structured content | 现有 `RuntimeSkillRunService` 负责结果封装，直接复用 | PASS |

## Requirement Coverage Ledger

| Requirement | Source | Obligation | Classification | Change IDs | Todo | Verification IDs | Evidence Class | Blocking |
|---|---|---|---|---|---|---|---|---|
| AC-01 | AC | 对有权访问且处于可恢复状态的 Run 调用 POST /api/v1/runs/{run_id}/resume 时，Backend 必须把原始 JSON 请求体及组织/用户执行身份转发给 Agent，不产生 unexpected keyword argument 或等价 Python 参数错误。 | BEHAVIOR | C01 | T1 | V01 | UNIT | yes |
| AC-02 | AC | 对有权访问的 Approval 调用 POST /api/v1/runs/{run_id}/approvals/{approval_id} 时，Backend 必须完整转发 decision（决策）与 evidence（证据）；Agent 返回的已处理结果必须安全投影，重复相同决策不得产生第二次状态副作用。 | LIFECYCLE | C01 | T1 | V02 | UNIT | yes |
| AC-03 | AC | 无权限、组织不匹配或响应中的 run_id/org_id 与请求上下文不一致时，Backend 必须 fail-closed，且不得返回 Agent Internal Token（内部令牌）、Runtime URL 或 traceback（调用栈）。 | SECURITY | C01 | T1 | V02 | UNIT | yes |
| AC-04 | AC | 每个 tools/list 条目必须具有 capabilityKind、interactionMode、supportsAttachments 和完整 annotations。Skill 还必须具有与 Published Release 一致的 skillReleaseId 与 skillReleaseDigest；Connector 不得伪造 SkillRelease 标识。 | CONTRACT | C02 | T3 | V04 | UNIT | yes |
| AC-05 | AC | 发布 interactionMode=chat 的 Release 时，缺失 promptField、字段不存在、字段类型不是字符串或字段属于禁止的运行路由键，均必须以 errors.skill.catalog.invalid_interaction_contract 拒绝；有效合同可发布并在后续 Catalog 请求中保持稳定。 | CONTRACT | C03 | T2 | V03 | UNIT | yes |
| AC-06 | AC | 对缺少 v1.1 元数据的既有 Published Release，Catalog 必须只依据该冻结 Release 的 Schema 与元数据做确定性映射；修改工作副本后，同一 Release 的 v1.1 投影不得改变。 | CONTRACT | C02 | T3 | V04 | UNIT | yes |
| AC-07 | AC | tools/list 携带 agent_alias/profile/workspace_id，或 tools/call.arguments 携带 _routing/_execution/route_config 等运行路由字段时，必须返回既有稳定拒绝错误；v1.1 不得放宽该边界。 | SECURITY | C06 | T3 | V05 | UNIT | yes |
| AC-08 | AC | 生成 v1.1.0 后，v1.0.0 的全部文件和 manifest checksum 必须保持不变。v1.1.0 的 Schema 必须验证其正向 Fixture，并拒绝缺少必填字段或枚举非法的负向 Fixture。 | CONTRACT | C04 | T5 | V06 | CONTRACT_RELEASE | yes |
| AC-09 | AC | tools/call 已接受响应中的 committed、run_id、status、tool_name、event_stream、result_url、artifact_url、execution_mode 和 request_trace_id 语义不变；新增 contract_version 时必须是可选字段，旧客户端忽略它后仍能工作。 | CONTRACT | C08 | T4 | V07 | UNIT | yes |
| AC-10 | AC | Agent 对 Resume/Approval 返回可预期 4xx 时，Backend 必须返回稳定 error_code、message_key 与安全 message，不能退化为未处理 HTTP client exception（HTTP 客户端异常）或 500。 | BEHAVIOR | C07 | T1 | V02 | UNIT | yes |
| DOD-01 | DOD | AC-01 至 AC-10 的阻断验证证据已全部留存；v1.0.0 合同文件与 checksum 不变；未新增独立 Catalog/Run Control 服务，Backend 也未成为第二 Run 状态 Owner。 | EVIDENCE | C01 | T1 | V01, V02, V03, V04, V05, V06, V07 | INTEGRATION | yes |

## Lifecycle Closure Matrix

| Journey | Requirements | Trigger | Nonterminal State | Success Writer | Failure / Cancel Writer | Evidence IDs |
|---|---|---|---|---|---|---|
| Resume Run Proxy | AC-01, AC-10 | POST /api/v1/runs/{run_id}/resume | SUSPENDED | Agent run_service.resume_run | Backend _agent_post 映射 / 鉴权拦截器 | V01 |
| Approval Run Proxy | AC-02, AC-03, AC-10 | POST /api/v1/runs/{run_id}/approvals/{approval_id} | WAITING_APPROVAL | Agent run_service.approve_run | Backend _agent_post 映射 / 鉴权拦截器 | V02 |
| Chat Skill Release Publish | AC-05 | POST /api/v1/hermes/skills/{skill_id}/releases | DRAFT | SkillReleaseService.publish | SkillReleaseService.publish 门禁校验 | V03 |

## Contract / Data Flow Closure Matrix

| Flow | Requirements | Producer | Transport / Schema | Consumer | Required Fields | Validation Owner | Failure Mapping | Retry / Idempotency Identity | Evidence IDs |
|---|---|---|---|---|---|---|---|---|---|
| Run Control 代理转发 | AC-01, AC-02, AC-03, AC-10 | Public Client | HTTP POST / JSON Payload | Agent Internal API | run_id, org_id, json_body, exec identity | Backend Run API | 404->not_found, 4xx->agent_error | run_id, approval_id | V01, V02 |
| Catalog 描述符查询 | AC-04, AC-06, AC-07 | Hermes Skill Store | MCP Tool Descriptor Schema v1.1 | Public Client (tools/list) | name, description, capabilityKind, interactionMode, annotations | McpToolMapper | errors.mcp.catalog_addressing_not_allowed | list_tools (read-only) | V04, V05 |
| Skill Run 合同生成与校验 | AC-08, AC-09 | contracts.py 生成器 | JSON Schema draft-07 / Fixture / SHA256SUMS | SDK / 外部集成方 | schema, fixture, checksums | contracts.py 校验器 | 校验失败 exit 1 | generate / check (deterministic) | V06, V07 |

## Verification Ledger

| Verification ID | Level | Entry Point / Command | Oracle | Negative / Regression | Evidence Output | Environment | Blocking |
|---|---|---|---|---|---|---|---|
| V01 | UNIT | pytest tests/hermes_skill/test_employee_runs_api.py -k test_resume_run | HTTP 200 且 Agent 收到原始 JSON 和身份头 | 参数传递错误抛出 500 时失败 | artifacts/rm01-v01.xml | LOCAL | yes |
| V02 | UNIT | pytest tests/hermes_skill/test_employee_runs_api.py -k "test_approve_run or test_agent_error" | HTTP 200 且 Agent 收到决策证据；Agent 4xx 映射为稳定公共错误 | 未处理 HTTP 异常导致 500 时失败 | artifacts/rm01-v02.xml | LOCAL | yes |
| V03 | UNIT | pytest tests/hermes_skill/test_skill_release.py | 校验通过发布成功；非法 prompt 字段返回 errors.skill.catalog.invalid_interaction_contract | 非法合同发布成功时失败 | artifacts/rm01-v03.xml | LOCAL | yes |
| V04 | UNIT | pytest tests/hermes_skill/test_mcp_tools_list.py | Catalog 返回统一 v1.1 字段且 Release 标识完整 | 缺失 v1.1 字段或未发布工作副本泄露时失败 | artifacts/rm01-v04.xml | LOCAL | yes |
| V05 | UNIT | pytest tests/mcp_skill_gateway/test_mcp_tools_list.py::test_tools_list_rejects_catalog_addressing_params tests/hermes_skill/test_mcp_tool_mapper_runtime_skill.py tests/hermes_skill/test_runtime_skill_registration.py::test_org_mcp_tools_call_rejects_route_override | 保持 Server-managed Route 拒绝目录寻址与路由覆盖 | 路由覆盖参数被透传时失败 | artifacts/rm01-v05.xml | LOCAL | yes |
| V06 | CONTRACT_RELEASE | python scripts/contracts.py generate --family skill-run && python scripts/contracts.py check | 生成 v1.1.0 通过 check 且 v1.0.0 SHA256SUMS 保持不变 | v1.0.0 改变或 v1.1.0 负向 Fixture 未拒绝时失败 | contracts/skill-run/v1.1.0/SHA256SUMS | LOCAL | yes |
| V07 | UNIT | pytest tests/mcp_skill_gateway/test_mcp_tools_call_format.py tests/hermes_skill/test_runtime_skill_run_service.py | Accepted Result 既有字段保持兼容，可选包含 contract_version | 破坏既有字段或类型时失败 | artifacts/rm01-v07.xml | LOCAL | yes |

## Immediate Read

- `nodeskclaw-backend/app/api/runs.py`
- `nodeskclaw-backend/app/core/exceptions.py`
- `nodeskclaw-backend/tests/hermes_skill/test_employee_runs_api.py`

## Triggered Read

- If executing T2: `nodeskclaw-backend/app/services/hermes_skill/skill_release_service.py` and `nodeskclaw-backend/tests/hermes_skill/test_skill_release.py`
- If executing T3: `nodeskclaw-backend/app/services/hermes_skill/mcp_tool_mapper.py` and `nodeskclaw-backend/tests/hermes_skill/test_mcp_tools_list.py`
- If executing T4: `nodeskclaw-backend/app/services/hermes_skill/runtime_skill_run_service.py` and `nodeskclaw-backend/tests/mcp_skill_gateway/test_mcp_tools_call_format.py`
- If executing T5: `nodeskclaw-backend/scripts/contracts.py`, `nodeskclaw-backend/app/schemas/skill_run/constants.py`, `nodeskclaw-backend/app/schemas/skill_run/mcp_jsonrpc.py`, and `nodeskclaw-backend/tests/contracts/test_contracts_check.py`

## Change Matrix

| Change ID | File / Symbol | Kind | Action | Existing Owner | Todo Owner | Target State | PRD Capability | New File? |
|---|---|---|---|---|---|---|---|---|
| C01 | `nodeskclaw-backend/app/api/runs.py#_agent_post` | PROD | MODIFY | `nodeskclaw-backend` Run API | T1 | 修复参数声明与传递为 json_body | Run Control 请求转发 | no |
| C01 | `nodeskclaw-backend/app/api/runs.py#resume_run` | PROD | MODIFY | `nodeskclaw-backend` Run API | T1 | 修复调用 _agent_post 传递 json_body | Run Control 请求转发 | no |
| C01 | `nodeskclaw-backend/app/api/runs.py#approve_run` | PROD | MODIFY | `nodeskclaw-backend` Run API | T1 | 修复调用 _agent_post 传递 json_body | Run Control 请求转发 | no |
| C01 | `nodeskclaw-backend/tests/hermes_skill/test_employee_runs_api.py` | TEST | MODIFY | `nodeskclaw-backend` Run API 测试 | T1 | 补充转发参数与执行身份断言 | Run Control 请求转发 | no |
| C07 | `nodeskclaw-backend/app/api/runs.py#_agent_post` | PROD | MODIFY | `nodeskclaw-backend` Run API | T1 | 捕获 Agent 4xx 并映射稳定公共错误 | Run Control 稳定错误映射 | no |
| C03 | `nodeskclaw-backend/app/services/hermes_skill/skill_release_service.py#SkillReleaseService#publish` | PROD | MODIFY | `nodeskclaw-backend` Hermes Skill 域 | T2 | 增加 Chat 交互合同门禁校验并冻结元数据 | Chat Skill 发布门禁 | no |
| C03 | `nodeskclaw-backend/tests/hermes_skill/test_skill_release.py` | TEST | MODIFY | `nodeskclaw-backend` Hermes Skill 测试 | T2 | 增加发布门禁校验与拒绝测试用例 | Chat Skill 发布门禁 | no |
| C02 | `nodeskclaw-backend/app/services/hermes_skill/mcp_tool_mapper.py#McpToolMapper#_skill_to_tool_dict` | PROD | MODIFY | `nodeskclaw-backend` Hermes Skill 域 | T3 | 输出 Catalog v1.1 字段且仅读冻结 Release 快照 | Catalog Descriptor 投影 | no |
| C02 | `nodeskclaw-backend/app/services/hermes_skill/mcp_tool_mapper.py#McpToolMapper#_list_public_connector_tools` | PROD | MODIFY | `nodeskclaw-backend` Hermes Skill 域 | T3 | 输出 Connector v1.1 字段且不伪造 Release 标识 | Catalog Descriptor 投影 | no |
| C02 | `nodeskclaw-backend/tests/hermes_skill/test_mcp_tools_list.py` | TEST | MODIFY | `nodeskclaw-backend` Hermes Skill 测试 | T3 | 增加 Catalog v1.1 描述符断言用例 | Catalog Descriptor 投影 | no |
| C08 | `nodeskclaw-backend/app/services/hermes_skill/runtime_skill_run_service.py#RuntimeSkillRunService#build_structured_content` | PROD | MODIFY | `nodeskclaw-backend` MCP Gateway | T4 | 可选写入 contract_version 保持已有字段兼容 | `tools/call` Accepted Result | no |
| C08 | `nodeskclaw-backend/tests/mcp_skill_gateway/test_mcp_tools_call_format.py` | TEST | MODIFY | `nodeskclaw-backend` MCP Gateway 测试 | T4 | 增加可选 contract_version 兼容断言 | `tools/call` Accepted Result | no |
| C04 | `nodeskclaw-backend/scripts/contracts.py#generate_skill_run_contracts` | BUILD | MODIFY | `nodeskclaw-backend` Contract Package | T5 | 生成器产出 v1.1.0 合同包 Schema 与 Fixture | Skill Run v1.1.0 合同包 | no |
| C04 | `nodeskclaw-backend/scripts/contracts.py#check_contracts` | BUILD | MODIFY | `nodeskclaw-backend` Contract Package | T5 | 校验器覆盖 v1.0.0 与 v1.1.0 并拒绝负向 Fixture | Skill Run v1.1.0 合同包 | no |
| C04 | `nodeskclaw-backend/app/schemas/skill_run/mcp_jsonrpc.py` | PROD | MODIFY | `nodeskclaw-backend` Contract Package | T5 | 增加 v1.1 增量模型类定义 | Skill Run v1.1.0 合同包 | no |
| C04 | `nodeskclaw-backend/app/schemas/skill_run/constants.py` | PROD | MODIFY | `nodeskclaw-backend` Contract Package | T5 | 声明 SKILL_RUN_CONTRACT_VERSION_V11 常量 | Skill Run v1.1.0 合同包 | no |
| C04 | `nodeskclaw-backend/tests/contracts/test_contracts_check.py` | TEST | MODIFY | `nodeskclaw-backend` Contract Package 测试 | T5 | 增加 contracts check 回归测试断言 | Skill Run v1.1.0 合同包 | no |
| C05 | `nodeskclaw-backend/contracts/skill-run/v1.0.0/` | CONFIG | KEEP | `nodeskclaw-backend` Contract Package | - | 保持 v1.0.0 文件与 checksum 不变 | Skill Run v1.0.0 冻结 | no |
| C06 | `nodeskclaw-backend/app/services/mcp_skill_gateway/handler.py` | PROD | KEEP | `nodeskclaw-backend` MCP Gateway | - | 保持 Server-managed Route fail-closed 拒绝 | Server-managed Route | no |

## Implementation Decisions

| Change ID | Strategy | Root-Cause / Reuse Evidence | Why This Is Minimum |
|---|---|---|---|
| C01 | MODIFY_EXISTING | `_agent_post` 声明 `json_body` 但调用方传 `body=` 导致 TypeError | 仅修复参数名称并透传身份头，不新增代理服务 |
| C02 | MODIFY_EXISTING | `_skill_to_tool_dict` 混用 `skill.extra_metadata` 导致未发布工作副本泄露 | 仅读取 Published Release 冻结元数据投影 v1.1 字段，不改写数据库历史记录 |
| C03 | MODIFY_EXISTING | `SkillReleaseService.publish` 缺失交互合同门禁校验 | 在现有发布方法写入前增加纯函数校验逻辑并冻结快照，不新建发布服务 |
| C04 | GENERATED_ENTRYPOINT | `scripts/contracts.py` 仅声明并生成 `1.0.0` 合同包 | 在现有生成脚本中增加 `1.1.0` 生成目标与 Schema 定义，单生成入口产出 |
| C07 | MODIFY_EXISTING | Agent 4xx 状态由 `raise_for_status` 抛出并退化为 500 | 在 `_agent_post` 中集中捕获 `HTTPStatusError` 映射为 `AppException`，不侵入每个端点 |
| C08 | MODIFY_EXISTING | 现有 `build_structured_content` 未声明 `contract_version` 键 | 字典构建时可选增加 `contract_version` 字段，现有字段类型与语义完全不变 |

## Write Ownership Ledger

| Todo | Owns Changes | Writes | Reads | Depends On | Parallel Safe |
|---|---|---|---|---|---|
| T1 | C01, C07 | `nodeskclaw-backend/app/api/runs.py#_agent_post`, `nodeskclaw-backend/app/api/runs.py#resume_run`, `nodeskclaw-backend/app/api/runs.py#approve_run`, `nodeskclaw-backend/tests/hermes_skill/test_employee_runs_api.py` | `nodeskclaw-backend/app/core/exceptions.py` | - | yes |
| T2 | C03 | `nodeskclaw-backend/app/services/hermes_skill/skill_release_service.py#SkillReleaseService#publish`, `nodeskclaw-backend/tests/hermes_skill/test_skill_release.py` | `nodeskclaw-backend/app/models/hermes_skill/skill_release.py` | - | no |
| T3 | C02 | `nodeskclaw-backend/app/services/hermes_skill/mcp_tool_mapper.py#McpToolMapper#_skill_to_tool_dict`, `nodeskclaw-backend/app/services/hermes_skill/mcp_tool_mapper.py#McpToolMapper#_list_public_connector_tools`, `nodeskclaw-backend/tests/hermes_skill/test_mcp_tools_list.py` | `nodeskclaw-backend/app/services/hermes_skill/skill_release_service.py` | T2 | no |
| T4 | C08 | `nodeskclaw-backend/app/services/hermes_skill/runtime_skill_run_service.py#RuntimeSkillRunService#build_structured_content`, `nodeskclaw-backend/tests/mcp_skill_gateway/test_mcp_tools_call_format.py` | `nodeskclaw-backend/app/schemas/skill_run/constants.py` | T5 | no |
| T5 | C04 | `nodeskclaw-backend/scripts/contracts.py#generate_skill_run_contracts`, `nodeskclaw-backend/scripts/contracts.py#check_contracts`, `nodeskclaw-backend/app/schemas/skill_run/mcp_jsonrpc.py`, `nodeskclaw-backend/app/schemas/skill_run/constants.py`, `nodeskclaw-backend/tests/contracts/test_contracts_check.py` | `nodeskclaw-backend/contracts/skill-run/v1.0.0/` | - | no |

## Integration Hotspots

| File | Owner Todo | Reason |
|---|---|---|
| `nodeskclaw-backend/scripts/contracts.py` | T5 | 合同生成脚本为单生成入口，由 T5 独占写入 |
| `nodeskclaw-backend/app/api/runs.py` | T1 | Run 代理接口与公共错误映射由 T1 独占写入 |

## Generated Outputs Ledger

| Source Change | Generator Owner | Generated Outputs | Command | Drift Check |
|---|---|---|---|---|
| C04 | T5 | `contracts/skill-run/v1.1.0/**` | `uv run python scripts/contracts.py generate --family skill-run` | `uv run python scripts/contracts.py check` |

## Todo T1 — Run Control 请求转发与公共错误映射

**Owns Changes**
- C01
- C07

**Goal**

修复 Run 控制代理在 `resume_run` 与 `approve_run` 中的请求体与身份头转发，捕获 Agent 4xx 状态并映射为稳定公共错误。

**Immediate anchors**
- `nodeskclaw-backend/app/api/runs.py#_agent_post`
- `nodeskclaw-backend/app/api/runs.py#resume_run`
- `nodeskclaw-backend/app/api/runs.py#approve_run`

**Changes**
- 将 `resume_run` 与 `approve_run` 调用 `_agent_post` 时的 `body=` 改为 `json_body=`。
- 在 `_agent_post` 中捕获 `httpx.HTTPStatusError`，404 映射为 `errors.run.not_found`，其余预期 4xx 映射为 `AppException` 并进行响应体消毒。
- 在 `nodeskclaw-backend/tests/hermes_skill/test_employee_runs_api.py` 中补充单测。

**Stop conditions**
- [ ] `pytest tests/hermes_skill/test_employee_runs_api.py` 全部通过。

**Triggered reads**
- None unless a listed trigger becomes true


## Todo T2 — Chat Skill 发布门禁

**Owns Changes**
- C03

**Goal**

在 `SkillReleaseService.publish` 中增加 Chat 交互合同发布门禁校验，冻结发布态交互元数据。

**Immediate anchors**
- `nodeskclaw-backend/app/services/hermes_skill/skill_release_service.py#SkillReleaseService#publish`

**Changes**
- 在 `publish` 方法中校验 `interactionMode=chat` 时 `promptField` 存在于 `input_schema.properties` 且为字符串类型，且不属于保留路由键。
- 校验不通过时抛出异常并设置 `message_key="errors.skill.catalog.invalid_interaction_contract"`。
- 在 `nodeskclaw-backend/tests/hermes_skill/test_skill_release.py` 中增加门禁测试。

**Stop conditions**
- [ ] `pytest tests/hermes_skill/test_skill_release.py` 全部通过。

**Triggered reads**
- None unless a listed trigger becomes true


## Todo T3 — Catalog Descriptor 投影

**Owns Changes**
- C02

**Goal**

在 `McpToolMapper` 中统一输出 Catalog v1.1 描述符，移除读取未发布工作副本的回退逻辑。

**Immediate anchors**
- `nodeskclaw-backend/app/services/hermes_skill/mcp_tool_mapper.py#McpToolMapper#_skill_to_tool_dict`
- `nodeskclaw-backend/app/services/hermes_skill/mcp_tool_mapper.py#McpToolMapper#_list_public_connector_tools`

**Changes**
- 在 `_skill_to_tool_dict` 中输出 `capabilityKind="skill"`、`interactionMode`、`promptField`、`supportsAttachments`、`skillReleaseId`、`skillReleaseDigest` 与 `annotations`。
- 完全移除 `published.extra_metadata or skill.extra_metadata` 回退逻辑，仅读冻结 Release。
- 在 `_list_public_connector_tools` 中输出 `capabilityKind="connector"`，不伪造 Release 标识。
- 在 `nodeskclaw-backend/tests/hermes_skill/test_mcp_tools_list.py` 中补充测试。

**Stop conditions**
- [ ] `pytest tests/hermes_skill/test_mcp_tools_list.py` 全部通过。

**Triggered reads**
- None unless a listed trigger becomes true


## Todo T4 — tools/call Accepted Result

**Owns Changes**
- C08

**Goal**

在 `RuntimeSkillRunService.build_structured_content` 中支持可选 `contract_version` 字段，保持现有字段完全兼容。

**Immediate anchors**
- `nodeskclaw-backend/app/services/hermes_skill/runtime_skill_run_service.py#RuntimeSkillRunService#build_structured_content`

**Changes**
- 在 `build_structured_content` 支持可选参数 `contract_version` 并写入字典。
- 保持已有的全部字段与类型不变。
- 在 `nodeskclaw-backend/tests/mcp_skill_gateway/test_mcp_tools_call_format.py` 补充测试。

**Stop conditions**
- [ ] `pytest tests/mcp_skill_gateway/test_mcp_tools_call_format.py tests/hermes_skill/test_runtime_skill_run_service.py` 全部通过。

**Triggered reads**
- None unless a listed trigger becomes true


## Todo T5 — Skill Run v1.1.0 合同包

**Owns Changes**
- C04

**Goal**

扩展 `scripts/contracts.py` 生成链输出 `v1.1.0` 合同包并进行校验，确保 `v1.0.0` 文件与 checksum 不变。

**Immediate anchors**
- `nodeskclaw-backend/scripts/contracts.py#generate_skill_run_contracts`
- `nodeskclaw-backend/scripts/contracts.py#check_contracts`

**Changes**
- 在 `constants.py` 增加 `SKILL_RUN_CONTRACT_VERSION_V11 = "1.1.0"` 常量。
- 在 `mcp_jsonrpc.py` 增加 v1.1 增量模型类。
- 在 `contracts.py` 中生成 `contracts/skill-run/v1.1.0/` 的 schema、fixture、manifest 与 checksum。
- 在 `check_contracts` 中校验 v1.0.0 与 v1.1.0。
- 在 `nodeskclaw-backend/tests/contracts/test_contracts_check.py` 补充测试。

**Stop conditions**
- [ ] `python scripts/contracts.py generate --family skill-run && python scripts/contracts.py check` 全部通过。

**Triggered reads**
- None unless a listed trigger becomes true


## Verification

Use the Verification Ledger as the only evidence SOT; this section orders the final commands.

```bash
uv run pytest tests/hermes_skill/test_employee_runs_api.py --junitxml=artifacts/rm01-v01.xml
uv run pytest tests/hermes_skill/test_employee_runs_api.py --junitxml=artifacts/rm01-v02.xml
uv run pytest tests/hermes_skill/test_skill_release.py --junitxml=artifacts/rm01-v03.xml
uv run pytest tests/hermes_skill/test_mcp_tools_list.py --junitxml=artifacts/rm01-v04.xml
uv run pytest tests/mcp_skill_gateway/test_mcp_tools_list.py::test_tools_list_rejects_catalog_addressing_params tests/hermes_skill/test_mcp_tool_mapper_runtime_skill.py tests/hermes_skill/test_runtime_skill_registration.py::test_org_mcp_tools_call_rejects_route_override --junitxml=artifacts/rm01-v05.xml
uv run python scripts/contracts.py generate --family skill-run && uv run python scripts/contracts.py check
uv run pytest tests/mcp_skill_gateway/test_mcp_tools_call_format.py tests/hermes_skill/test_runtime_skill_run_service.py --junitxml=artifacts/rm01-v07.xml
```

## Completion Gate

| Exit State | Allowed When | Blocking Evidence |
|---|---|---|
| IMPLEMENTED_AND_PROVEN | V01 至 V07 全部执行通过且产物存在 | V01, V02, V03, V04, V05, V06, V07 |
| IMPLEMENTED_NOT_PROVEN | 代码修改完成但缺少阻断性验证证据产物 | 任何缺失的验证证据 |
| BLOCKED | 运行环境或依赖阻塞无法执行验证 | 环境报错日志 |
| RETURN_PRD | 发现 Owner 或边界与已批准 PRD 存在冲突 | 冲突说明文档 |
