# NoDeskClaw MCP Skill Gateway PRD

## 版本

v5.6.1_hotfix

## 标题

修复用户级 Hermes Agent 调用组织级 MCP Runtime Skill 时的路由覆盖误判问题

## 负责人

后端：nodeskclaw-backend
模块：Hermes Skill / MCP Skill Gateway
影响范围：`/api/v1/hermes/mcp`、`McpToolMapper.call_tool()`、Runtime Skill 路由解析、MCP Router Skill 调用链

## 一、背景

NoDeskClaw 当前已经实现以下能力：

1. NoDeskClaw 控制 Docker 中运行的 Hermes Agent 实例。
2. Docker Hermes Agent 内的 runtime skill 可以注册到组织级 MCP Skill Gateway。
3. 注册后的 runtime skill 会以 `HermesSkill.source_type = hermes_api_server` 形式暴露为组织级 MCP tool。
4. 用户级独立 Hermes Agent 通过 MCP token 连接 NoDeskClaw MCP Gateway。
5. 用户在 Hermes WebUI 对话中，由 `nodeskclaw-skill-router` 根据自然语言意图选择合适的 MCP tool。
6. NoDeskClaw Gateway 创建 `HermesTask`，再由 `hermes_task_worker` 调用指定 Docker Hermes Agent 的 API_SERVER 执行 runtime skill。
7. Runtime Skill 执行结果通过 pull-only artifact bridge 物化到 NoDeskClaw 中心产物库。

当前 Postman 直接调用 `/api/v1/hermes/mcp` 可以正常创建任务，但用户级 Hermes Agent 内部通过 MCP 调用时出现：

```text
MCP gateway error
method=tools/call
reason=组织级 MCP 不允许覆盖 Hermes 实例路由
```

该问题不是 MCP 连接失败、token 失效或 Skill 未注册，而是 `tools/call` 阶段把 MCP token/header 自动携带的 profile/workspace 上下文误判为执行路由覆盖。

## 二、问题定义

### 2.1 当前错误链路

当前调用链如下：

```text
用户 Hermes WebUI
  → nodeskclaw-skill-router
  → MCP tool call
  → /api/v1/hermes/mcp
  → handler._handle_tools_call()
  → McpToolMapper.call_tool()
  → SkillRoutingService.extract_routing()
  → AgentAliasResolver.enrich_routing(profile_name=auth_ctx.profile)
  → routing 被填充 profile_id
  → source_type=hermes_api_server 且 routing 非空
  → 抛出 route_override_not_allowed
```

### 2.2 根因

`source_type=hermes_api_server` 的 Skill 本应只使用注册时保存的 `installation.routing_metadata` 作为执行路由来源。

但是当前 `tools/call` 阶段会将以下上下文也传入执行路由解析：

```text
MCP client token.profile
MCP client token.workspace_id
X-Hermes-Profile header
profile_name
workspace_id
```

这些字段原本应该只用于：

```text
tools/list 可见性过滤
审计上下文
客户端上下文
```

不应该参与：

```text
tools/call 执行实例选择
route_snapshot 覆盖
Hermes API_SERVER 目标实例选择
```

### 2.3 当前设计冲突

当前系统混用了两类 routing：

```text
A. Client Context Routing
用于 MCP token、profile、workspace、审计、tools/list 过滤。

B. Execution Routing
用于决定任务最终由哪个 Hermes Agent 实例执行。
```

对 `source_type=hermes_api_server` 的 Runtime Skill 来说，Execution Routing 必须由 `installation.routing_metadata.route_config` 固定决定，不允许调用方覆盖。

## 三、目标

### 3.1 业务目标

修复用户级 Hermes Agent 通过 MCP Gateway 调用组织级 Runtime Skill 失败的问题，使以下流程稳定可用：

```text
用户自然语言需求
  → nodeskclaw-skill-router 匹配业务 skill
  → 用户级 Hermes Agent 调用 MCP tool
  → NoDeskClaw MCP Gateway 创建 HermesTask
  → Worker 调用指定 Docker Hermes Agent API_SERVER
  → 返回 task_id / result_url / artifact_url
```

### 3.2 工程目标

1. `tools/list` 继续支持 MCP token/profile/workspace 做工具可见性过滤。
2. `tools/call` 对 `source_type=hermes_api_server` 的 Skill 不再使用 MCP token/header 的 profile_name 参与执行路由。
3. `tools/call` 仍然禁止调用方显式传入 `_routing`、`_execution`、`route_config`。
4. Runtime Skill 的执行目标只来自 `installation.routing_metadata`。
5. Worker 继续校验 `hermes_agent_instance_id`，禁止 fallback 到其他实例。
6. 不破坏 Registry 内置工具、GeneHub 工具、普通 Hermes Skill 工具调用。
7. 不修改数据库结构，尽量以服务层 hotfix 完成。

## 四、非目标

v5.6.1_hotfix 不解决以下问题：

1. 不重构整个 MCP Gateway 协议。
2. 不新增新的 MCP Server。
3. 不允许外部 Router 覆盖 Runtime Skill 执行实例。
4. 不改变 Runtime Skill 注册 API。
5. 不改变 Worker 调用 API_SERVER 的执行方式。
6. 不改变 pull-only artifact bridge。
7. 不新增多实例智能调度策略。
8. 不把 `nodeskclaw-skill-router` 升级为中心化调度器。
9. 不允许用户通过 MCP 参数指定目标 Hermes Docker 实例。

## 五、核心设计原则

### 5.1 Intent Routing 与 Execution Routing 分离

`nodeskclaw-skill-router` 只负责：

```text
自然语言意图 → MCP tool_name
```

MCP Gateway 负责：

```text
tool_name → Skill → Installation → route_snapshot → HermesTask
```

Worker 负责：

```text
route_snapshot → 指定 Hermes API_SERVER → Runtime Skill 执行
```

### 5.2 Runtime Skill 固定路由

对 `source_type=hermes_api_server` 的 Skill：

```text
执行路由唯一来源 = HermesSkillInstallation.routing_metadata
```

禁止以下来源影响执行路由：

```text
MCP token.profile
MCP token.workspace_id
X-Hermes-Profile
X-Device-Id
X-Client
params.agent_alias
params.profile
params.workspace_id
arguments._routing
arguments._execution
arguments.route_config
```

其中：

```text
arguments._routing / _execution / route_config
```

仍然作为显式覆盖行为，必须拒绝。

### 5.3 tools/list 与 tools/call 职责分离

`tools/list`：

```text
允许使用 token/profile/workspace 做可见性过滤。
允许按 allowed_skills 限制工具列表。
允许返回 agentAlias/profileId/workspaceId 作为展示信息。
```

`tools/call`：

```text
对 hermes_api_server Skill 不允许使用 token/header/profile 影响执行目标。
只允许使用 tool_name 和 installation.routing_metadata 创建任务。
```

### 5.4 安全边界不降低

v5.6.1_hotfix 不开放任何 route override 权限。

修复后的安全策略是：

```text
允许用户级 Hermes Agent 调用授权范围内的 MCP Skill。
不允许用户级 Hermes Agent 改变该 Skill 绑定的执行实例。
```

## 六、影响范围

### 6.1 主要修改文件

```text
nodeskclaw-backend/app/services/hermes_skill/mcp_tool_mapper.py
nodeskclaw-backend/app/services/hermes_skill/skill_routing_service.py
```

### 6.2 建议新增或修改测试文件

```text
nodeskclaw-backend/tests/services/hermes_skill/test_mcp_tool_mapper_runtime_skill.py
nodeskclaw-backend/tests/services/mcp_skill_gateway/test_runtime_skill_mcp_client_token.py
```

### 6.3 可能涉及文件

```text
nodeskclaw-backend/app/services/mcp_skill_gateway/handler.py
nodeskclaw-backend/app/services/hermes_skill/agent_alias_resolver.py
nodeskclaw-backend/app/services/mcp_skill_gateway/mcp_client_token_service.py
```

原则上 v5.6.1 不要求修改 `handler.py`，除非需要增强 debug 日志。

## 七、当前行为与目标行为

### 7.1 当前行为

#### 场景 A：Postman 使用用户 JWT

```text
Authorization: Bearer <user_jwt>
arguments = {"prompt": "..."}
```

结果：

```text
成功创建任务
```

原因：

```text
auth_ctx.profile = None
routing = {}
未触发 route_override_not_allowed
```

#### 场景 B：Hermes Agent 使用 MCP Client Token

```text
Authorization: Bearer ndsk_mcp_xxx.yyy
arguments = {"prompt": "..."}
```

结果：

```text
失败：组织级 MCP 不允许覆盖 Hermes 实例路由
```

原因：

```text
auth_ctx.profile = default
profile_name 被 enrich_routing 转成 profile_id
routing 非空
source_type=hermes_api_server 被拒绝
```

### 7.2 目标行为

#### 场景 A：Postman 用户 JWT

```text
继续成功
```

#### 场景 B：Hermes Agent MCP Client Token

```text
成功创建 HermesTask
返回 task_id / task_no / event_url / result_url / artifact_url
```

#### 场景 C：显式传 `_routing`

```json
{
  "prompt": "请为某公司做客户画像",
  "_routing": {
    "agent_alias": "common-writer"
  }
}
```

结果：

```text
拒绝：errors.skill.route_override_not_allowed
```

#### 场景 D：显式传 `_execution`

```json
{
  "prompt": "请为某公司做客户画像",
  "_execution": {
    "mode": "sync"
  }
}
```

结果：

```text
拒绝：errors.skill.route_override_not_allowed
```

#### 场景 E：显式传 `route_config`

```json
{
  "prompt": "请为某公司做客户画像",
  "route_config": {
    "agent_profile": "other-agent"
  }
}
```

结果：

```text
拒绝：errors.skill.route_override_not_allowed
```

## 八、详细方案设计

## 8.1 McpToolMapper.call_tool 改造

### 8.1.1 当前逻辑

当前逻辑大致如下：

```python
agent_arguments, routing = SkillRoutingService.extract_routing(arguments or {})
routing = await alias_resolver.enrich_routing(org_id, routing, profile_name=profile_name)

routing_result = await routing_service.resolve_by_tool_name(
    tool_name=tool_name,
    org_id=org_id,
    routing=routing,
)

skill = routing_result.skill
installation = routing_result.installation

if skill.source_type == "hermes_api_server":
    raw_args = arguments or {}
    if routing or raw_args.get("_execution") or raw_args.get("route_config"):
        raise BadRequestError(
            "组织级 MCP 不允许覆盖 Hermes 实例路由",
            "errors.skill.route_override_not_allowed",
        )
```

问题是：

```text
routing 已经混入 profile_name。
profile_name 可能来自 MCP token，而非调用方显式传入。
```

### 8.1.2 目标逻辑

调整为：

```python
raw_args = arguments or {}
agent_arguments, explicit_routing = SkillRoutingService.extract_routing(raw_args)

explicit_route_override_requested = (
    bool(explicit_routing)
    or "_execution" in raw_args
    or "route_config" in raw_args
)

routing_service = SkillRoutingService(self.db)

# 第一步：先不使用 profile_name，按 tool_name 解析 skill。
# 对 hermes_api_server 类型，必须走固定 installation 路由。
pre_result = await routing_service.resolve_by_tool_name(
    tool_name=tool_name,
    org_id=org_id,
    routing={},
    user_workspace_id=None,
)

skill = pre_result.skill

if skill and skill.source_type == "hermes_api_server":
    if explicit_route_override_requested:
        raise BadRequestError(
            "组织级 MCP 不允许覆盖 Hermes 实例路由",
            "errors.skill.route_override_not_allowed",
        )

    routing_result = await routing_service.resolve_runtime_skill_fixed_route(
        tool_name=tool_name,
        org_id=org_id,
    )
else:
    routing = await alias_resolver.enrich_routing(
        org_id,
        explicit_routing,
        profile_name=profile_name,
    )
    routing_result = await routing_service.resolve_by_tool_name(
        tool_name=tool_name,
        org_id=org_id,
        routing=routing,
    )
```

### 8.1.3 关键变化

1. `explicit_routing` 与 `routing` 分离。
2. 只有调用参数中真实出现 `_routing`、`_execution`、`route_config` 才视为 route override。
3. MCP token/header 自动携带的 `profile_name` 不再影响 `hermes_api_server` Skill。
4. 普通 Skill 仍保留原有 profile/agent/workspace 路由能力。
5. Runtime Skill 使用独立的固定路由解析方法。

## 8.2 新增固定路由解析方法

在 `SkillRoutingService` 中新增：

```python
async def resolve_runtime_skill_fixed_route(
    self,
    tool_name: str,
    org_id: str,
) -> RoutingResult:
    ...
```

### 8.2.1 设计目标

该方法只用于：

```text
HermesSkill.source_type = hermes_api_server
```

解析规则：

```text
1. 根据 tool_name 获取 HermesSkill。
2. 校验 Skill 存在、is_active=true、is_mcp_exposed=true。
3. 校验 source_type=hermes_api_server。
4. 查询该 Skill 的 installed installations。
5. 过滤不可调度 Agent。
6. 优先选择 is_default=true 的 installation。
7. 如果只有一个 installation，选择该 installation。
8. 如果多个 default，报 installation_ambiguous。
9. 如果多个 installation 且没有唯一 default，报 installation_ambiguous。
10. 校验 installation.routing_metadata 存在。
11. 校验 routing_metadata.route_type = hermes_api_server。
12. 校验 routing_metadata.force_instance = true。
13. 校验 routing_metadata.hermes_agent_instance_id 存在。
14. 校验 routing_metadata.agent_profile 存在。
15. 校验 routing_metadata.runtime_skill_id 存在。
16. 返回 RoutingResult。
```

### 8.2.2 伪代码

```python
async def resolve_runtime_skill_fixed_route(
    self,
    tool_name: str,
    org_id: str,
) -> RoutingResult:
    skill = await self._get_skill_by_tool_name(tool_name, org_id)
    if not skill:
        raise NotFoundError(
            f"MCP Tool {tool_name} 不存在",
            "errors.skill.tool_not_found",
        )

    if skill.source_type != "hermes_api_server":
        raise BadRequestError(
            "该方法仅支持 hermes_api_server Runtime Skill",
            "errors.skill.route_config_invalid",
        )

    installations = await self._list_installed(skill.skill_id, org_id)
    if not installations:
        raise NotFoundError(
            f"Skill {tool_name} 未安装到任何 Agent",
            "errors.skill.installation_not_found",
        )

    defaults = [
        i for i in installations
        if getattr(i, "is_default", False)
    ]

    if len(defaults) == 1:
        inst = defaults[0]
        reason = "matched_by_runtime_fixed_default"
    elif len(defaults) > 1:
        raise BadRequestError(
            "多个 default runtime installation 冲突",
            "errors.skill.installation_ambiguous",
        )
    elif len(installations) == 1:
        inst = installations[0]
        reason = "matched_by_runtime_fixed_single"
    else:
        raise BadRequestError(
            "Runtime Skill 存在多个 installation，请设置唯一 default",
            "errors.skill.installation_ambiguous",
        )

    route = inst.routing_metadata or {}
    if route.get("route_type") != "hermes_api_server":
        raise BadRequestError(
            "Runtime Skill route_config 缺少 hermes_api_server route_type",
            "errors.skill.route_config_invalid",
        )

    if route.get("force_instance") is not True:
        raise BadRequestError(
            "Runtime Skill route_config 必须启用 force_instance",
            "errors.skill.route_config_invalid",
        )

    required_keys = [
        "hermes_agent_instance_id",
        "agent_profile",
        "runtime_skill_id",
    ]
    missing = [key for key in required_keys if not route.get(key)]
    if missing:
        raise BadRequestError(
            f"Runtime Skill route_config 缺少字段: {', '.join(missing)}",
            "errors.skill.route_config_invalid",
        )

    return self._result(skill, inst, reason)
```

## 8.3 route_override 判断规则

### 8.3.1 显式覆盖字段

以下字段只要出现在 `arguments` 中，就视为调用方试图覆盖路由：

```text
_routing
_execution
route_config
```

### 8.3.2 不视为覆盖的字段

以下字段不视为 route override：

```text
auth_ctx.profile
auth_ctx.workspace_id
X-Hermes-Profile
X-Device-Id
X-Client
X-Proxy-Version
client_context
MCP token allowed_skills
MCP token allowed_tools
```

### 8.3.3 判断函数建议

新增私有函数：

```python
def _has_explicit_runtime_route_override(
    raw_args: dict,
    explicit_routing: dict,
) -> bool:
    return (
        bool(explicit_routing)
        or "_execution" in raw_args
        or "route_config" in raw_args
    )
```

注意：

```python
raw_args.get("_execution")
```

不够严谨，因为调用方传空对象也应视为覆盖尝试。

应使用：

```python
"_execution" in raw_args
"route_config" in raw_args
```

## 8.4 tools/list 行为保持不变

`tools/list` 继续允许：

```text
params.agent_alias
params.profile
params.workspace_id
auth_ctx.profile
auth_ctx.workspace_id
X-Hermes-Profile
allowed_skills
```

用于工具列表过滤。

目标：

```text
用户 agent 只能看到授权给它的工具。
用户 agent 的 profile/workspace 可以影响 tools/list 可见性。
```

不修改：

```python
_handle_tools_list()
_collect_tools()
McpToolMapper.list_tools()
```

## 8.5 tools/call 行为调整

### 8.5.1 handler._handle_tools_call

`handler._handle_tools_call()` 当前会提取：

```python
profile_name = auth_ctx.profile if auth_ctx and auth_ctx.profile else normalized.get(HEADER_HERMES_PROFILE.lower())
client_context = _build_client_context(request_headers)
```

该逻辑可以保留，但需要在 `McpToolMapper.call_tool()` 内部按 Skill 类型决定是否使用 `profile_name` 参与路由。

也就是：

```text
handler 不需要知道 Skill 类型。
mapper 负责区分 hermes_api_server 与普通 Skill。
```

### 8.5.2 McpToolMapper.call_tool

对于 `source_type=hermes_api_server`：

```text
profile_name 只能进入 client_context，不进入 routing。
```

对于普通 Skill：

```text
profile_name 继续参与 enrich_routing。
```

## 8.6 Task routing_metadata 保持兼容

任务创建时继续写入：

```json
{
  "agent_alias": "...",
  "agent_id": "...",
  "profile_id": "...",
  "workspace_id": "...",
  "installation_id": "...",
  "routing_reason": "...",
  "output_policy": "...",
  "route_snapshot": {
    "route_type": "hermes_api_server",
    "force_instance": true,
    "hermes_instance_name": "...",
    "hermes_agent_instance_id": "...",
    "agent_profile": "...",
    "profile_id": "...",
    "workspace_id": "...",
    "runtime_skill_id": "...",
    "api_server_model_name": "...",
    "default_execution_mode": "async",
    "timeout_seconds": 1800
  },
  "task_source": "org_mcp"
}
```

其中：

```text
profile_id / workspace_id
```

来自 installation，不来自 token/header。

## 8.7 Worker 不变

`hermes_task_worker` 不需要修改。

Worker 继续：

```text
读取 task.routing_metadata.route_snapshot
校验 route_type=hermes_api_server
校验 HermesDockerBindingService.get_by_profile()
校验 record.id == hermes_agent_instance_id
调用 execute_runtime_skill_via_api_server()
物化 server_artifacts
执行 ArtifactDiscoveryService
```

## 九、接口契约

## 9.1 MCP tools/call 请求

### 成功请求

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "hermes_xieyi__customer-profiling",
    "arguments": {
      "prompt": "请为研华科技做客户画像"
    }
  }
}
```

### 成功响应

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "任务已创建"
      }
    ],
    "structuredContent": {
      "tool_name": "hermes_xieyi__customer-profiling",
      "agent_alias": "common-writer",
      "agent_id": "...",
      "profile_id": "default",
      "workspace_id": "default",
      "status": "queued",
      "task_id": "...",
      "task_no": "...",
      "event_url": "...",
      "event_token_url": "/api/v1/hermes/tasks/{task_id}/events-token",
      "artifact_url": "...",
      "result_url": "/api/v1/hermes/tasks/{task_id}/result",
      "artifact_mode": "pull_only",
      "server_artifacts": [],
      "routing_reason": "matched_by_runtime_fixed_default",
      "installation_id": "..."
    },
    "isError": false
  }
}
```

## 9.2 显式 route override 请求

### 请求

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/call",
  "params": {
    "name": "hermes_xieyi__customer-profiling",
    "arguments": {
      "prompt": "请为研华科技做客户画像",
      "_routing": {
        "agent_alias": "other-agent"
      }
    }
  }
}
```

### 响应

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "error": {
    "code": -32603,
    "message": "组织级 MCP 不允许覆盖 Hermes 实例路由",
    "data": {
      "errorCode": "errors.skill.route_override_not_allowed"
    }
  }
}
```

## 十、数据库变更

v5.6.1_hotfix 不需要数据库 migration。

复用现有字段：

```text
HermesSkill.source_type
HermesSkill.tool_name
HermesSkillInstallation.routing_metadata
HermesSkillInstallation.is_default
HermesTask.routing_metadata.route_snapshot
HermesTask.routing_metadata.task_source
```

## 十一、权限与安全

### 11.1 保留权限检查

`McpToolMapper.call_tool()` 继续执行：

```text
skill:view
skill:invoke
HermesSkillAuthorizationService.can_invoke()
```

### 11.2 保留 MCP client token 限制

`handler._handle_tools_call()` 继续执行：

```text
mcp_client_token 不允许调用 genehub / hermes docker registry tools
mcp_client_token 只能调用 allowed_skills 内的工具
```

### 11.3 强化 Runtime Skill 安全边界

对 `hermes_api_server` Skill：

```text
调用方不能选择执行实例。
调用方不能选择 profile。
调用方不能选择 workspace。
调用方不能覆盖 route_config。
调用方不能覆盖 execution mode。
调用方只能提交业务参数 prompt/context。
```

### 11.4 防止空对象绕过

以下请求也必须拒绝：

```json
{
  "_routing": {}
}
```

```json
{
  "_execution": {}
}
```

```json
{
  "route_config": {}
}
```

判断标准是字段存在，而不是字段是否有值。

## 十二、日志与审计

## 12.1 成功日志

成功创建任务时继续记录：

```text
mcp_call_log.status = success
result_summary = {"task_id": "...", "status": "queued"}
```

Skill 审计继续记录：

```text
hermes.skill.routing.resolved
hermes.skill.routing.alias_resolved
hermes.skill.invoked
```

## 12.2 新增建议日志

建议在 `McpToolMapper.call_tool()` 中增加 debug 日志：

```python
logger.debug(
    "MCP runtime skill fixed route selected tool=%s installation=%s profile_from_token_ignored=%s",
    tool_name,
    installation.id,
    bool(profile_name),
)
```

当拒绝显式 override 时，建议记录：

```python
logger.warning(
    "MCP runtime skill route override denied tool=%s user=%s keys=%s",
    tool_name,
    user_id,
    [k for k in ["_routing", "_execution", "route_config"] if k in raw_args],
)
```

注意不要记录 token、Authorization、完整 prompt。

## 十三、测试方案

## 13.1 单元测试

### Case 1：MCP client token profile 不触发 route override

输入：

```python
arguments = {"prompt": "请为研华科技做客户画像"}
profile_name = "default"
skill.source_type = "hermes_api_server"
installation.routing_metadata.route_type = "hermes_api_server"
```

期望：

```text
成功 create_task
routing_reason = matched_by_runtime_fixed_default 或 matched_by_runtime_fixed_single
```

### Case 2：显式 `_routing` 被拒绝

输入：

```python
arguments = {
    "prompt": "请为研华科技做客户画像",
    "_routing": {"agent_alias": "common-writer"}
}
```

期望：

```text
BadRequestError
message_key = errors.skill.route_override_not_allowed
```

### Case 3：空 `_routing` 也被拒绝

输入：

```python
arguments = {
    "prompt": "请为研华科技做客户画像",
    "_routing": {}
}
```

期望：

```text
BadRequestError
message_key = errors.skill.route_override_not_allowed
```

### Case 4：显式 `_execution` 被拒绝

输入：

```python
arguments = {
    "prompt": "请为研华科技做客户画像",
    "_execution": {}
}
```

期望：

```text
BadRequestError
message_key = errors.skill.route_override_not_allowed
```

### Case 5：显式 `route_config` 被拒绝

输入：

```python
arguments = {
    "prompt": "请为研华科技做客户画像",
    "route_config": {}
}
```

期望：

```text
BadRequestError
message_key = errors.skill.route_override_not_allowed
```

### Case 6：普通 Skill 保持原有 profile 路由

输入：

```python
skill.source_type != "hermes_api_server"
profile_name = "default"
```

期望：

```text
继续调用 enrich_routing
继续支持 profile/workspace routing
```

### Case 7：多个 runtime installation 无唯一 default

输入：

```text
同一个 tool_name 对应多个 installed installation
is_default 全部 false
```

期望：

```text
BadRequestError
message_key = errors.skill.installation_ambiguous
```

### Case 8：runtime route_config 缺失

输入：

```text
installation.routing_metadata = null
```

期望：

```text
BadRequestError
message_key = errors.skill.route_config_invalid
```

## 13.2 集成测试

### Case 1：Postman 用户 JWT

```bash
curl -X POST "$BASE/api/v1/hermes/mcp" \
  -H "Authorization: Bearer $USER_JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "hermes_xieyi__customer-profiling",
      "arguments": {
        "prompt": "请为研华科技做客户画像"
      }
    }
  }'
```

期望：

```text
result.structuredContent.task_id 存在
isError=false
```

### Case 2：Hermes Agent MCP Client Token

```bash
curl -X POST "$BASE/api/v1/hermes/mcp" \
  -H "Authorization: Bearer $NODESKCLAW_MCP_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "hermes_xieyi__customer-profiling",
      "arguments": {
        "prompt": "请为研华科技做客户画像"
      }
    }
  }'
```

期望：

```text
不再返回“组织级 MCP 不允许覆盖 Hermes 实例路由”
成功创建 task
```

### Case 3：Hermes WebUI 对话触发 Router Skill

输入：

```text
请为研华科技做客户画像
```

期望：

```text
nodeskclaw-skill-router 选择 customer-profiling
MCP tools/call 成功
返回任务创建结果
最终可通过 result_url 获取报告结果
```

## 13.3 回归测试

必须确认以下能力不受影响：

```text
tools/list 正常返回授权工具
allowed_skills 生效
mcp_client_token 不能调用 hermes.instances.list
mcp_client_token 不能调用 genehub.*
普通用户 JWT 调用仍正常
普通非 hermes_api_server Skill 路由仍正常
Registry 内置工具审批逻辑仍正常
Runtime Skill Worker 执行仍使用 route_snapshot
Artifact Bridge 仍生成 server_artifacts
```

## 十四、验收标准

### 14.1 功能验收

1. 用户级 Hermes Agent 使用 MCP token 调用 `hermes_xieyi__customer-profiling` 成功。
2. 用户级 Hermes Agent 使用 MCP token 调用 `hermes_xieyi__enterprise-risk-analysis` 成功。
3. `nodeskclaw-skill-router` 在 Hermes WebUI 对话中能根据关键词调用对应 MCP tool。
4. 成功响应包含：

```text
task_id
task_no
event_url
event_token_url
artifact_url
result_url
artifact_mode=pull_only
server_artifacts=[]
```

5. 显式传 `_routing` 仍然被拒绝。
6. 显式传 `_execution` 仍然被拒绝。
7. 显式传 `route_config` 仍然被拒绝。
8. Worker 实际执行实例与 installation.route_snapshot 中的 `hermes_agent_instance_id` 一致。
9. 任务完成后可通过 `result_url` 读取结果。
10. 任务完成后如 output_policy 开启，中心产物库正常生成 materialized artifact。

### 14.2 日志验收

修复后不再出现：

```text
reason=组织级 MCP 不允许覆盖 Hermes 实例路由
```

除非调用方显式传入：

```text
_routing
_execution
route_config
```

### 14.3 安全验收

1. MCP client token 无法调用 Registry Hermes Docker 工具。
2. MCP client token 无法调用 GeneHub 工具。
3. MCP client token 无法调用 allowed_skills 之外的工具。
4. MCP client token 无法通过任何参数改变 Runtime Skill 执行实例。
5. Worker 仍然在绑定记录不一致时 mark_failed。

## 十五、实施步骤

## 15.1 第一步：修改 McpToolMapper.call_tool

目标：

```text
拆分 explicit_routing 与 effective_routing。
source_type=hermes_api_server 时不使用 profile_name enrich routing。
```

建议改造顺序：

1. 在 `call_tool()` 开头提取：

```python
raw_args = arguments or {}
agent_arguments, explicit_routing = SkillRoutingService.extract_routing(raw_args)
```

2. 新增：

```python
explicit_route_override_requested = self._has_explicit_runtime_route_override(
    raw_args,
    explicit_routing,
)
```

3. 先用固定 routing 解析 skill：

```python
pre_result = await routing_service.resolve_by_tool_name(
    tool_name=tool_name,
    org_id=org_id,
    routing={},
)
```

4. 如果 `skill.source_type == "hermes_api_server"`：

```python
if explicit_route_override_requested:
    raise BadRequestError(...)

routing_result = await routing_service.resolve_runtime_skill_fixed_route(
    tool_name=tool_name,
    org_id=org_id,
)
```

5. 否则保持原有普通 Skill routing。

## 15.2 第二步：新增 SkillRoutingService.resolve_runtime_skill_fixed_route

目标：

```text
为 Runtime Skill 提供独立、固定、安全的 installation 解析。
```

该方法必须校验：

```text
source_type
installation 唯一性
is_default 唯一性
routing_metadata.route_type
routing_metadata.force_instance
routing_metadata.hermes_agent_instance_id
routing_metadata.agent_profile
routing_metadata.runtime_skill_id
```

## 15.3 第三步：补充测试

优先补：

```text
test_mcp_client_token_profile_does_not_override_runtime_route
test_runtime_skill_explicit_routing_denied
test_runtime_skill_execution_override_denied
test_runtime_skill_route_config_override_denied
test_normal_skill_profile_routing_unchanged
```

## 15.4 第四步：本地验证

执行：

```bash
pytest nodeskclaw-backend/tests/services/hermes_skill/test_mcp_tool_mapper_runtime_skill.py -q
pytest nodeskclaw-backend/tests/services/mcp_skill_gateway/test_runtime_skill_mcp_client_token.py -q
```

然后用 curl 验证：

```bash
curl -X POST "$BASE/api/v1/hermes/mcp" \
  -H "Authorization: Bearer $NODESKCLAW_MCP_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "hermes_xieyi__customer-profiling",
      "arguments": {
        "prompt": "请为研华科技做客户画像"
      }
    }
  }'
```

## 十六、发布方案

### 16.1 发布类型

```text
hotfix
```

### 16.2 版本号

```text
v5.6.1_hotfix
```

### 16.3 发布顺序

1. 合并后端代码。
2. 重启 nodeskclaw-backend。
3. 重启 hermes_task_worker。
4. 不需要重新注册 Runtime Skill。
5. 不需要重新生成 MCP token。
6. 不需要重新同步 nodeskclaw-skill-router。
7. 如 Router Skill 旧内容未包含产物规则，可单独执行 sync，但不是本 hotfix 必需项。

### 16.4 回滚方案

如果发布后出现普通 Skill 路由异常：

1. 回滚 `mcp_tool_mapper.py`。
2. 回滚 `skill_routing_service.py`。
3. 重启 backend 与 worker。
4. 保留数据库不变。

因为本版本不做 migration，所以回滚成本低。

## 十七、风险分析

### 17.1 风险：多个 runtime installation 解析不唯一

如果同一个 Runtime Skill tool_name 存在多个 installed installation 且没有唯一 default，会报 ambiguous。

应对：

```text
通过注册服务确保 runtime skill installation is_default=true。
如果历史数据异常，提供 SQL 检查并人工修复。
```

### 17.2 风险：普通 Skill 路由被误改

应对：

```text
把 hermes_api_server 分支和普通 Skill 分支分开。
普通 Skill 保留原 enrich_routing 逻辑。
增加回归测试。
```

### 17.3 风险：MCP token allowed_skills 误以为被绕过

应对：

```text
allowed_skills 检查仍在 handler._handle_tools_call 中执行。
本 hotfix 不改 handler 的 token 限制逻辑。
```

### 17.4 风险：Router Skill 继续 fallback web_search 掩盖错误

应对：

```text
Router Skill 可以后续优化失败处理：
MCP 调用失败时直接暴露 MCP error，不自动 fallback web_search。
该项不纳入 v5.6.1 hotfix。
```

## 十八、数据检查脚本

### 18.1 检查 Runtime Skill route_config

```sql
select
  s.tool_name,
  s.source_type,
  i.id as installation_id,
  i.agent_id,
  i.profile_id,
  i.workspace_id,
  i.is_default,
  i.routing_metadata
from hermes_skills s
join hermes_skill_installations i
  on i.skill_id = s.skill_id
where s.source_type = 'hermes_api_server'
  and s.deleted_at is null
  and i.deleted_at is null
order by s.tool_name, i.created_at desc;
```

### 18.2 查找缺失 route_config 的 Runtime Skill

```sql
select
  s.tool_name,
  i.id as installation_id,
  i.routing_metadata
from hermes_skills s
join hermes_skill_installations i
  on i.skill_id = s.skill_id
where s.source_type = 'hermes_api_server'
  and s.deleted_at is null
  and i.deleted_at is null
  and (
    i.routing_metadata is null
    or i.routing_metadata->>'route_type' is distinct from 'hermes_api_server'
    or i.routing_metadata->>'hermes_agent_instance_id' is null
    or i.routing_metadata->>'agent_profile' is null
    or i.routing_metadata->>'runtime_skill_id' is null
  );
```

### 18.3 查找多个 default installation

```sql
select
  s.tool_name,
  count(*) as default_count
from hermes_skills s
join hermes_skill_installations i
  on i.skill_id = s.skill_id
where s.source_type = 'hermes_api_server'
  and s.deleted_at is null
  and i.deleted_at is null
  and i.status = 'installed'
  and i.is_default = true
group by s.tool_name
having count(*) > 1;
```

## 十九、Cursor 实施提示词

```text
请在 nodeskclaw-backend 中实现 PRD v5.6.1_hotfix。

目标：
修复 source_type=hermes_api_server 的 MCP Runtime Skill 在用户级 Hermes Agent 使用 ndsk_mcp token 调用时，被 token/profile/header 自动上下文误判为 route override 的问题。

核心要求：
1. tools/list 保持现状，允许 token profile/workspace 用于可见性过滤。
2. tools/call 中，对 source_type=hermes_api_server 的 Skill，不要让 auth_ctx.profile、X-Hermes-Profile、profile_name 参与执行路由选择。
3. hermes_api_server Skill 的执行路由只允许来自 HermesSkillInstallation.routing_metadata。
4. 显式传入 arguments._routing、arguments._execution、arguments.route_config 时仍然拒绝，返回 errors.skill.route_override_not_allowed。
5. 普通非 hermes_api_server Skill 保持原有 routing 行为。
6. 新增 SkillRoutingService.resolve_runtime_skill_fixed_route，用于固定解析 runtime skill installation，并校验 route_config。
7. 补充单元测试和集成测试，覆盖 MCP client token profile 不触发 route override、显式 override 仍被拒绝、普通 Skill routing 不变。
8. 不做数据库 migration。
9. 不修改 Worker 执行逻辑。
10. 不降低 allowed_skills、skill:view、skill:invoke、can_invoke 权限检查。
```

## 二十、最终结论

v5.6.1_hotfix 的本质是修正路由职责边界：

```text
tools/list 可以使用 MCP token/profile/workspace 过滤工具可见性。
tools/call 对 hermes_api_server Runtime Skill 只能使用 installation.route_config 决定执行实例。
```

修复后，用户级 Hermes Agent 可以通过 `nodeskclaw-skill-router` 正常调用组织级 MCP Runtime Skill，同时仍然禁止任何外部调用方覆盖 Hermes 实例执行路由。
