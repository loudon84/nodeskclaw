---
name: mcp-runtime-route-hotfix
overview: 修复用户级 Hermes Agent 通过 MCP token 调用组织级 Runtime Skill 时，token/header 自动携带的 profile 被误判为路由覆盖、报 route_override_not_allowed 的问题（PRD v5.6.1_hotfix）。纯服务层改动，不动数据库与 Worker。
todos:
  - id: fixed-route
    content: SkillRoutingService 新增 resolve_runtime_skill_fixed_route 与 get_exposed_skill，含新 routing_reason 常量与 route_config 校验
    status: completed
  - id: call-tool
    content: 改造 McpToolMapper.call_tool：分离 explicit_routing/profile，hermes_api_server 走固定路由，按字段存在判断覆盖，补 debug/warning 日志
    status: completed
  - id: tests
    content: 扩展/新增单测覆盖 PRD Case 1-8（固定路由、空对象覆盖拒绝、普通 Skill 路由不变），跑 pytest + ruff
    status: completed
  - id: docs
    content: 回写 docs/backend/mcp_skill_gateway.md 与 hermes_skill.md 的路由职责分离说明
    status: completed
isProject: false
---

## 背景与根因

用户级 Hermes Agent 用 `ndsk_mcp` token 调用 `source_type=hermes_api_server` 的 Runtime Skill 时，[mcp_tool_mapper.py](nodeskclaw-backend/app/services/hermes_skill/mcp_tool_mapper.py) 无条件执行 `enrich_routing(profile_name=...)`，把 token 自带的 `profile` 转成 `profile_id` 写进 `routing`，随后 `if routing or ...` 判定为「路由覆盖」并抛 `errors.skill.route_override_not_allowed`。

修复核心：**区分 Client Context Routing（token/profile/header，仅用于 tools/list 与审计）与 Execution Routing（仅来自 installation.routing_metadata）**。对 `hermes_api_server` Skill，执行路由只走固定 installation，profile_name 不参与；仅当调用方在 `arguments` 显式传 `_routing`/`_execution`/`route_config` 时才拒绝。

## 前端表现变化

本次改动无前端表现变化（纯后端服务层 hotfix，不涉及任何 UI、API 响应结构变更；成功/失败响应字段与 PRD §9 现有契约一致）。

## 实施

### Task 1：新增 `SkillRoutingService.resolve_runtime_skill_fixed_route`

文件：[skill_routing_service.py](nodeskclaw-backend/app/services/hermes_skill/skill_routing_service.py)

- 新增 reason 常量：`ROUTING_REASON_RUNTIME_FIXED_DEFAULT = "matched_by_runtime_fixed_default"`、`ROUTING_REASON_RUNTIME_FIXED_SINGLE = "matched_by_runtime_fixed_single"`。
- 新增方法 `async def resolve_runtime_skill_fixed_route(self, tool_name, org_id) -> RoutingResult`，逻辑按 PRD §8.2.2：
  - 复用 `_get_skill_by_tool_name` / `_list_installed` / `_result`。
  - 校验 `skill.source_type == "hermes_api_server"`，否则 `errors.skill.route_config_invalid`。
  - 选 installation：唯一 default → `RUNTIME_FIXED_DEFAULT`；多 default → `errors.skill.installation_ambiguous`；单 installation → `RUNTIME_FIXED_SINGLE`；多 installation 无唯一 default → `errors.skill.installation_ambiguous`。
  - 校验 `routing_metadata`：存在、`route_type == "hermes_api_server"`、`force_instance is True`、必填 `hermes_agent_instance_id`/`agent_profile`/`runtime_skill_id`，缺失 → `errors.skill.route_config_invalid`。
- 新增轻量公开方法 `async def get_exposed_skill(self, tool_name, org_id) -> HermesSkill | None`（薄封装 `_get_skill_by_tool_name`），供 mapper 在不触发 installation 选择的前提下判断 `source_type`。

> 偏离 PRD 说明：PRD §8.1.2 用 `resolve_by_tool_name(routing={})` 做预解析取 skill，但对「多安装无 default 的普通 Skill」会提前抛 `installation_ambiguous`，误伤正常 profile 路由。改用 `get_exposed_skill` 只取 skill 判类型，普通 Skill 分支保持原 `enrich_routing + resolve_by_tool_name` 不变。

### Task 2：改造 `McpToolMapper.call_tool`

文件：[mcp_tool_mapper.py](nodeskclaw-backend/app/services/hermes_skill/mcp_tool_mapper.py)

替换第 186-230 行的路由解析与覆盖判断：

1. `raw_args = arguments or {}`；`agent_arguments, explicit_routing = SkillRoutingService.extract_routing(raw_args)`。
2. 新增私有方法 `_has_explicit_runtime_route_override(raw_args) -> bool`，返回 `"_routing" in raw_args or "_execution" in raw_args or "route_config" in raw_args`。
3. 先 `skill = await routing_service.get_exposed_skill(tool_name, org_id)`；为空则抛 `errors.skill.tool_not_found`（保留现有 routing.failed 审计）。
4. 分支：
   - `skill.source_type == "hermes_api_server"`：若 `_has_explicit_runtime_route_override(raw_args)` 为真 → `BadRequestError(errors.skill.route_override_not_allowed)`（保留 routing.failed 审计 + 新增 `logger.warning`，记录命中的 key 列表，不记 token/prompt）；否则 `routing_result = await routing_service.resolve_runtime_skill_fixed_route(tool_name, org_id)`，并设 `routing = {}`（不再 enrich profile_name），加 `logger.debug` 记录 `profile_from_token_ignored=bool(profile_name)`。
   - 普通 Skill：`routing = await alias_resolver.enrich_routing(org_id, explicit_routing, profile_name=profile_name)` → `resolve_by_tool_name(tool_name, org_id, routing=routing)`（行为不变）。
5. 第 224-230 行旧的 `if skill.source_type == "hermes_api_server": if routing or ...` 块删除（已被分支取代）。
6. 下游 `routing_metadata` 组装、`task_source="org_mcp"`、`output_policy`、`server_artifacts=[]`、返回结构全部保持不变（PRD §8.6 / §9.1）。`profile_id`/`workspace_id` 继续取自 `installation`。

> 偏离 PRD 说明：PRD §8.3.3 的 `bool(explicit_routing)` 无法捕获空 `_routing: {}`（`extract_routing` 规整为 `{}`），与 PRD Case 3/§11.4「空对象也拒绝」矛盾。按「字段存在即拒绝」统一用 `"_routing" in raw_args`。

### Task 3：测试

沿用现有测试目录约定（非 PRD 写的 `tests/services/...`）：

- 扩展 [tests/hermes_skill/test_skill_routing_service.py](nodeskclaw-backend/tests/hermes_skill/test_skill_routing_service.py)：`resolve_runtime_skill_fixed_route` 的 default/single/ambiguous/route_config_invalid 用例（PRD Case 7、8）。
- 新增 `tests/hermes_skill/test_mcp_tool_mapper_runtime_skill.py`：
  - Case 1：`profile_name="default"` + `hermes_api_server` + 无显式覆盖 → 成功建任务，reason 为 `matched_by_runtime_fixed_*`，profile 不影响选择。
  - Case 2-5：显式 `_routing`（含空 `{}`）、`_execution: {}`、`route_config: {}` → `errors.skill.route_override_not_allowed`。
  - Case 6：普通 Skill + `profile_name` → 仍走 `enrich_routing`（mock 校验被调用）。
- 运行：`uv run pytest tests/hermes_skill/test_mcp_tool_mapper_runtime_skill.py tests/hermes_skill/test_skill_routing_service.py -q` 与 `uv run ruff check app/services/hermes_skill/`。

### Task 4：回写设计文档（实现 + review 后，按双轨规则）

- [docs/backend/mcp_skill_gateway.md](docs/backend/mcp_skill_gateway.md)：在 tools/call 数据流与「安全约束」处补充——`hermes_api_server` 执行路由只来自 installation.routing_metadata，token/header/profile 仅用于 tools/list 与审计；覆盖判断按字段存在（`_routing`/`_execution`/`route_config`）。
- [docs/backend/hermes_skill.md](docs/backend/hermes_skill.md)：MCP 调用链路第 3 步更新为「Intent Routing 与 Execution Routing 分离」，并记 `resolve_runtime_skill_fixed_route` 与新 routing_reason。

## 不改动项（PRD §四 / §7-8）

- 不改数据库（复用现有字段）、不改 `hermes_task_worker`、不改 `handler.py` 的 token/allowed_skills 限制、不改 tools/list 与 `list_tools`、不改 Registry/GeneHub 工具链路、不降 `skill:view`/`skill:invoke`/`can_invoke` 权限。

## 待确认的小项（不阻塞）

- 新增 message_key（`errors.skill.route_config_invalid` 等）主要是 Runtime Skill 防御性校验，正常流程不触发；与现存 `route_override_not_allowed` 一样面向 MCP 客户端而非 portal UI，portal i18n 暂无对应词条。计划默认不新增 portal 词条（与现状一致），如需补充请告知。
