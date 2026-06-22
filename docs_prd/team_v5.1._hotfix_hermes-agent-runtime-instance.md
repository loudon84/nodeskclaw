# PRD：nodeskclaw Hermes Instance Skills MCP Gateway Hotfix

版本：team_v5.1.1_hotfix
模块：Hermes MCP / Hermes Agent Gateway / Skills MCP Gateway
目标：统一通过 Hermes API_SERVER 对外暴露实例级 Skills
状态：待开发 / Hotfix
优先级：P0

## 1. 背景

team_v5.1 已实现 Hermes Agent Detail 页面中的技能树、技能筛选、授权弹窗和 user/agent 授权校验修复。但经过实机验证后，发现原 v5.1 对 Hermes skills 的理解需要调整。

实测结果：

```text
GET http://192.168.102.247:28900/v1/skills?profile=researcher
```

和：

```bash
docker exec hermes-common-writer /app/venv/bin/hermes -p researcher skills list
```

本质上返回的是 **Hermes Agent 实例级别 skills**，不是严格意义上的 profile 独立对外 skills 服务。

因此，继续在 nodeskclaw 中维护 “同一个 hermes-agent container 下多个 profile 对外分别暴露 skills” 会带来语义混乱：

```text
common-writer container
  ├─ writer-zh profile
  └─ researcher profile
```

在当前阶段不再作为一个 container 内的多 profile skill gateway 暴露。

新的产品决策：

```text
一个 hermes-agent container = 一个对外 MCP Gateway 实例
一个 API_SERVER = 一个 skills runtime source
对外只暴露 default skills
writer-zh / researcher 拆成不同 hermes-agent container 后再分别对外服务
```

## 2. Hotfix 目标

team_v5.1.1_hotfix 的目标是：统一通过 Hermes API_SERVER 暴露实例级 skills，并完成 nodeskclaw 侧的 Hermes Instance Skills MCP Gateway。

具体目标：

1. 不再通过 docker exec 获取对外 runtime skills。
2. 不再通过 profile 参数决定对外暴露的 skills。
3. 统一调用 Hermes API_SERVER：

```http
GET {gateway_url}/v1/skills
```

或兼容：

```http
GET {gateway_url}/v1/skills?profile=default
```

4. nodeskclaw 对外 MCP Gateway 只暴露该 hermes-agent container 的 default skills。
5. 对 `common-writer` 下的 `writer-zh / researcher` 不再通过 profile 多路复用对外暴露。
6. 后续将 `writer-zh / researcher` 拆分为独立 container，每个 container 各自提供 API_SERVER 与 MCP Gateway。
7. 保留 Agent Detail 页面已有技能查看能力，但将其语义改为“实例 Skills”，不是“profile 对外 Skills”。
8. 保留现有 skill authorization 校验能力，作为 MCP tools/list 与 tools/call 的权限控制层。
9. 不修改 Hermes Agent 本体。
10. 不修改 Hermes WebUI。
11. 不继续实现本地目录 catalog merge 作为对外 gateway 数据源。

## 3. 非目标

本 hotfix 不做以下内容：

1. 不实现 profile 级 MCP Gateway。
2. 不对外暴露 `writer-zh / researcher` profile 参数。
3. 不将容器内部 skills 文件目录作为对外 skills 数据源。
4. 不使用 `docker exec hermes skills list` 作为主链路。
5. 不解析 Hermes CLI 表格输出作为主链路。
6. 不支持 `--json`，因为实测 Hermes CLI 不支持该参数。
7. 不实现 skill marketplace。
8. 不实现 skill 安装、卸载、更新的对外 MCP 能力。
9. 不改变 nodeskclaw 现有用户、角色、组织授权模型。
10. 不改变现有 `/hermes/skill-authorizations` 模块。

## 4. 核心设计决策

### 4.1 对外边界从 profile 改为 container instance

旧理解：

```text
一个 hermes-agent container
  ├─ profile writer-zh → 对外 skills A
  └─ profile researcher → 对外 skills B
```

新理解：

```text
一个 hermes-agent container
  └─ default runtime skills → 对外 MCP tools
```

后续拆分：

```text
hermes-writer-zh container
  └─ default skills = writer-zh skills

hermes-researcher container
  └─ default skills = researcher skills

hermes-common-writer container
  └─ default skills = common-writer skills
```

### 4.2 API_SERVER 是唯一 runtime skills 主数据源

MCP Gateway 不再直接读取：

```text
/data/hermes/profiles/{profile}/skills
```

也不再执行：

```bash
docker exec hermes-common-writer /app/venv/bin/hermes -p researcher skills list
```

统一读取：

```http
GET {gateway_url}/v1/skills
Authorization: Bearer {api_server_key}
```

### 4.3 profile 参数只保留给内部管理 UI

`/hermes/agents/{agent}?profile=researcher` 可以继续作为内部 profile 管理页面存在，用于：

```text
查看 profile 配置
备份 profile
导入 / 导出 profile
本地 skill 文件管理
```

但它不代表对外 MCP Gateway 的 skills 暴露范围。

### 4.4 对外只暴露 default Skills

MCP Gateway 对外不接受 profile 参数。

以下请求应被拒绝或忽略：

```text
profile=researcher
profile=writer-zh
```

建议策略：

```text
MCP Gateway 路由：直接不支持 profile 参数
内部调试 API：允许 profile 参数但标记 deprecated
前端页面：显示“对外 Gateway 使用实例 default skills”
```

## 5. 总体架构

```text
外部 MCP Client / AI 员工 / 工作流系统
        │
        ▼
nodeskclaw Hermes MCP Gateway
        │
        ├─ 鉴权：nodeskclaw user / role / org / agent
        ├─ 授权：skill can_list / can_invoke
        ├─ 工具列表：tools/list
        ├─ 工具调用：tools/call
        │
        ▼
Hermes Agent API_SERVER
        │
        ├─ GET  /v1/skills
        └─ POST /v1/chat/completions
        │
        ▼
Hermes Agent default runtime
        │
        ▼
skills / tools / memory / terminal / file / web capability
```

## 6. 数据流

### 6.1 tools/list

```text
MCP Client
  → nodeskclaw /hermes/mcp/{agent}/tools/list
  → nodeskclaw 读取绑定的 Hermes Agent record
  → 调用 {gateway_url}/v1/skills
  → 归一化为 MCP tools
  → 按 can_list 授权过滤
  → 返回 tools[]
```

### 6.2 tools/call

```text
MCP Client
  → nodeskclaw /hermes/mcp/{agent}/tools/call
  → 校验 skill_id 是否存在于 API_SERVER /v1/skills
  → 校验当前 subject 是否 can_invoke
  → 构造 Hermes Agent chat/completions 请求
  → POST {gateway_url}/v1/chat/completions
  → 返回 MCP tool result
```

### 6.3 Agent 拆分后的调用

```text
AI 员工调用 researcher skill
  → 选择 hermes-researcher agent
  → /hermes/mcp/hermes-researcher/tools/list
  → default skills 即 researcher skills

AI 员工调用 writer-zh skill
  → 选择 hermes-writer-zh agent
  → /hermes/mcp/hermes-writer-zh/tools/list
  → default skills 即 writer-zh skills
```

## 7. 后端设计

### 7.1 新增 / 调整 HermesApiServerClient

文件建议：

```text
nodeskclaw-backend/app/services/hermes_external/hermes_api_server_client.py
```

新增方法：

```python
async def list_skills(self) -> list[HermesApiSkill]:
    ...
```

请求：

```http
GET {gateway_url}/v1/skills
Authorization: Bearer {api_server_key}
```

兼容响应结构：

```json
[
  {
    "name": "arxiv",
    "description": "Search arXiv papers by keyword, author, category, or ID.",
    "category": "research"
  }
]
```

或：

```json
{
  "data": [
    {
      "name": "arxiv",
      "description": "Search arXiv papers by keyword, author, category, or ID.",
      "category": "research"
    }
  ]
}
```

归一化字段：

```python
class HermesApiSkill:
    name: str
    description: str | None
    category: str | None
    source: str | None = "api_server"
    status: str | None = "enabled"
```

### 7.2 新增 Instance Skills Service

新增文件：

```text
nodeskclaw-backend/app/services/hermes_external/hermes_instance_skill_service.py
```

职责：

1. 根据 agent_profile 查询绑定 Hermes Agent record。
2. 读取 `gateway_url`。
3. 读取 `api_server_key`。
4. 调用 Hermes API_SERVER `/v1/skills`。
5. 归一化 skills。
6. 缓存短时间结果。
7. 提供给 Agent Detail 页面和 MCP Gateway 共用。

核心函数：

```python
async def list_instance_skills(
    agent_profile: str,
    *,
    force_refresh: bool = False,
) -> HermesInstanceSkillList:
    ...
```

返回：

```json
{
  "agent_profile": "common-writer",
  "gateway_url": "http://192.168.102.247:28900",
  "source_mode": "api_server_default",
  "exposed_profile": "default",
  "total": 86,
  "skills": [
    {
      "name": "arxiv",
      "description": "Search arXiv papers by keyword, author, category, or ID.",
      "category": "research",
      "status": "enabled",
      "runtime_available": true,
      "callable": true
    }
  ],
  "warnings": []
}
```

### 7.3 不再使用 docker exec 作为对外数据源

以下逻辑从对外 Gateway 链路移除：

```text
docker exec hermes skills list --json
docker exec python -m hermes_cli.main
docker exec /app/venv/bin/hermes -p {profile} skills list
profile 本地目录 fallback
catalog merge
```

它们可以保留在内部诊断功能中，但不得作为 MCP Gateway skills 数据源。

### 7.4 MCP Gateway 路由

新增或调整后端路由：

```text
POST /api/v1/hermes/mcp/{agent_profile}
```

支持 JSON-RPC 风格：

```json
{
  "jsonrpc": "2.0",
  "id": "1",
  "method": "tools/list",
  "params": {}
}
```

返回：

```json
{
  "jsonrpc": "2.0",
  "id": "1",
  "result": {
    "tools": [
      {
        "name": "hermes_common_writer__arxiv",
        "description": "Search arXiv papers by keyword, author, category, or ID.",
        "inputSchema": {
          "type": "object",
          "properties": {
            "prompt": {
              "type": "string",
              "description": "User task or instruction for this Hermes skill."
            },
            "context": {
              "type": "object",
              "description": "Optional structured context."
            }
          },
          "required": ["prompt"]
        },
        "metadata": {
          "agent_profile": "common-writer",
          "skill_id": "arxiv",
          "category": "research",
          "source": "api_server_default"
        }
      }
    ]
  }
}
```

### 7.5 MCP tools/list 规则

`tools/list` 处理顺序：

```text
1. 读取 agent_profile
2. 校验 agent 是否已绑定 Hermes API_SERVER
3. 调用 list_instance_skills(agent_profile)
4. 按 skill authorization can_list 过滤
5. 转换为 MCP tool schema
6. 返回 tools[]
```

工具命名规范：

```text
hermes_{agent_slug}__{skill_slug}
```

示例：

```text
hermes_common_writer__arxiv
hermes_common_writer__powerpoint
hermes_researcher__blogwatcher
hermes_writer_zh__writer_outline
```

命名规则：

```text
小写
空格转 -
下划线保留或统一转 -
非字母数字字符替换为 -
agent 与 skill 之间使用双下划线
```

### 7.6 MCP tools/call 规则

请求：

```json
{
  "jsonrpc": "2.0",
  "id": "2",
  "method": "tools/call",
  "params": {
    "name": "hermes_common_writer__arxiv",
    "arguments": {
      "prompt": "Search recent papers about agent memory.",
      "context": {
        "language": "zh-CN"
      }
    }
  }
}
```

处理顺序：

```text
1. 解析 tool name，得到 agent_profile 与 skill_id
2. 校验 agent_profile 与 URL 中 agent_profile 一致
3. 调用 API_SERVER /v1/skills 确认 skill 存在
4. 校验 can_invoke
5. 构造 Hermes chat/completions 请求
6. POST {gateway_url}/v1/chat/completions
7. 转换结果为 MCP content[]
```

Hermes 请求建议：

```json
{
  "model": "common-writer",
  "messages": [
    {
      "role": "system",
      "content": "You are a Hermes Agent. Use the requested skill when it is relevant. Requested skill: arxiv."
    },
    {
      "role": "user",
      "content": "Search recent papers about agent memory."
    }
  ],
  "metadata": {
    "requested_skill": "arxiv",
    "source": "nodeskclaw_mcp_gateway"
  }
}
```

如果后续 Hermes API_SERVER 提供直接 skill invoke endpoint，可替换为：

```http
POST /v1/skills/{skill_name}/invoke
```

但本 hotfix 不依赖该 endpoint。

### 7.7 授权校验

继续复用 v5.1 已修复的授权模型。

权限语义：

```text
can_list：是否能在 MCP tools/list 中看到 skill
can_invoke：是否能调用 tools/call
can_manage：是否能管理授权或网关配置
can_install：本 hotfix 暂不使用
```

校验顺序：

```text
admin/operator 默认允许
user grant
role grant
agent grant
org grant
否则拒绝
```

未授权时：

```json
{
  "jsonrpc": "2.0",
  "id": "2",
  "error": {
    "code": -32003,
    "message": "skill_permission_denied",
    "data": {
      "skill_id": "arxiv",
      "required_permission": "can_invoke"
    }
  }
}
```

### 7.8 缓存策略

为了避免每次 tools/list 都访问 Hermes API_SERVER，增加短 TTL 缓存。

默认：

```text
cache_ttl_seconds = 30
```

缓存 key：

```text
hermes_instance_skills:{agent_profile}
```

刷新条件：

```text
force_refresh=true
API_SERVER status changed
Agent 绑定信息更新
管理员点击刷新
TTL 过期
```

缓存内容不能包含 API_SERVER_KEY。

### 7.9 错误处理

#### API_SERVER 未配置

```http
409 Conflict
```

```json
{
  "error": "api_server_not_configured",
  "message": "当前 Hermes Agent 未配置 API_SERVER，无法作为 MCP Gateway 暴露 skills。"
}
```

#### API_SERVER 离线

```http
503 Service Unavailable
```

```json
{
  "error": "api_server_offline",
  "message": "Hermes API_SERVER 当前不可用。"
}
```

#### /v1/skills 返回空

```http
200 OK
```

```json
{
  "source_mode": "api_server_default",
  "total": 0,
  "skills": [],
  "warnings": [
    "Hermes API_SERVER returned empty skills."
  ]
}
```

#### 请求 profile 参数

MCP Gateway 不接受 profile 参数。

```http
400 Bad Request
```

```json
{
  "error": "profile_not_supported",
  "message": "Hermes MCP Gateway exposes instance-level default skills only. Please deploy a separate Hermes Agent container for each profile."
}
```

## 8. 前端设计

### 8.1 Agent Detail 页面语义调整

页面：

```text
/hermes/agents/{agent_profile}?profile={profile}
```

保留 profile 管理能力，但技能总览区域增加提示：

```text
对外 MCP Gateway 使用实例 default skills。
当前 profile 仅用于内部配置与本地文件管理，不作为对外 skills 暴露边界。
```

### 8.2 新增 MCP Gateway 卡片

在 Agent Detail 概览页或技能清单页增加：

```text
MCP Gateway
状态：enabled / disabled
暴露范围：instance default skills
Skills 来源：Hermes API_SERVER /v1/skills
Endpoint：/api/v1/hermes/mcp/common-writer
Tools：86
最近刷新：2026-xx-xx xx:xx
[刷新 Skills] [复制 MCP Endpoint] [查看 Tools] [诊断]
```

### 8.3 技能清单 tab 调整

原 v5.1 的 “技能总览 / 本地技能管理” 保留，但改名：

```text
实例 Skills
本地 Profile 技能管理
```

`实例 Skills` 数据源：

```text
Hermes API_SERVER /v1/skills
```

`本地 Profile 技能管理` 数据源：

```text
profiles/{profile}/skills
```

页面顶部明确区分：

```text
实例 Skills：对外 MCP Gateway 暴露的可调用 skills。
本地 Profile 技能管理：仅用于当前 profile 文件管理，不代表对外 MCP Gateway 暴露范围。
```

### 8.4 移除 fallback 黄色警告的误导

不再显示：

```text
无法读取 Hermes runtime skills，已降级显示 profile 本地 skills
```

改为：

```text
无法连接 Hermes API_SERVER，MCP Gateway 暂不可用。
```

本地 profile skills 可以继续显示，但不作为 fallback 对外暴露。

## 9. 配置设计

### 9.1 Agent 绑定配置

每个 Hermes Agent 绑定记录必须包含：

```text
agent_profile
container_name
gateway_url
api_server_key_ref 或 encrypted_api_server_key
api_server_model_name
mcp_gateway_enabled
mcp_gateway_expose_default_only = true
```

示例：

```json
{
  "agent_profile": "common-writer",
  "container_name": "hermes-common-writer",
  "gateway_url": "http://192.168.102.247:28900",
  "api_server_key_ref": "secret:common-writer",
  "api_server_model_name": "common-writer",
  "mcp_gateway_enabled": true,
  "mcp_gateway_expose_default_only": true
}
```

### 9.2 禁止配置 profile_expose

以下配置不在 hotfix 中支持：

```json
{
  "profile": "researcher",
  "expose_profile_skills": true
}
```

如果历史配置存在，应标记 deprecated。

## 10. 安全设计

### 10.1 API_SERVER_KEY 不下发前端

前端只能看到：

```text
gateway status
model name
skills count
mcp endpoint
```

不能看到：

```text
API_SERVER_KEY
内部 Authorization header
加密前 secret
```

### 10.2 MCP Gateway 鉴权

MCP Gateway 必须先经过 nodeskclaw 鉴权。

支持：

```text
用户 token
Agent token
组织 API token
内部服务 token
```

不允许匿名调用 tools/list 或 tools/call。

### 10.3 Skill 授权过滤

`tools/list` 不应返回当前 subject 无权查看的 skill。

`tools/call` 即使用户猜到 tool name，也必须再次校验 `can_invoke`。

### 10.4 禁止任意 URL 转发

客户端请求中不允许传：

```text
gateway_url
api_server_url
container_name
api_server_key
```

所有目标地址必须从 nodeskclaw 已绑定 Agent record 中读取。

### 10.5 审计日志

每次 tools/call 记录：

```text
request_id
agent_profile
skill_id
subject_type
subject_id
org_id
status
latency_ms
error_code
created_at
```

不默认记录完整 prompt，避免敏感信息落库。可配置采样或脱敏记录。

## 11. 数据库与模型建议

### 11.1 HermesMcpGatewayConfig

可以复用 Agent record，也可以新增独立表。

建议字段：

```text
id
org_id
agent_profile
enabled
expose_default_only
cache_ttl_seconds
created_at
updated_at
```

### 11.2 HermesMcpSkillCache

可选表。如果已有 Redis，可优先用 Redis。

字段：

```text
id
agent_profile
source_mode
skills_json
skills_hash
expires_at
created_at
updated_at
```

### 11.3 HermesMcpCallAudit

字段：

```text
id
org_id
agent_profile
skill_id
tool_name
subject_type
subject_id
status
latency_ms
error_code
created_at
```

## 12. 后端任务拆分

### B1. HermesApiServerClient 增加 list_skills

```text
GET /v1/skills
```

要求：

```text
使用 API_SERVER_KEY
支持超时
支持 401/403/404/5xx 错误分类
支持 list/data/skills/items 多种返回结构
```

### B2. 新增 hermes_instance_skill_service

职责：

```text
读取 Agent record
调用 API_SERVER /v1/skills
归一化 skills
缓存
返回 instance skill list
```

### B3. 调整 profile_skill_inventory_service

对外 gateway 链路不再调用：

```text
docker exec
profile 本地目录 fallback
catalog merge
```

保留它仅供本地 profile 管理视图使用。

### B4. 新增 MCP Gateway API

路由：

```text
POST /api/v1/hermes/mcp/{agent_profile}
```

支持方法：

```text
initialize
tools/list
tools/call
ping
```

### B5. MCP tools/list 实现

```text
API_SERVER /v1/skills
→ authorization can_list
→ MCP tool schema
```

### B6. MCP tools/call 实现

```text
解析 tool name
→ 校验 skill 存在
→ authorization can_invoke
→ POST API_SERVER /v1/chat/completions
→ 返回 MCP content
```

### B7. 增加审计日志

记录 tools/call。

### B8. 增加错误码

新增错误码：

```text
api_server_not_configured
api_server_offline
profile_not_supported
skill_not_found
skill_permission_denied
mcp_tool_name_invalid
hermes_chat_completion_failed
```

## 13. 前端任务拆分

### F1. Agent Detail 增加 MCP Gateway 卡片

展示：

```text
Gateway 状态
Endpoint
暴露范围
Skills count
刷新按钮
复制 endpoint
```

### F2. 技能清单 tab 文案调整

将 “技能总览” 改为：

```text
实例 Skills
```

将 “本地技能管理” 改为：

```text
本地 Profile 技能管理
```

### F3. 增加 default-only 提示

提示文案：

```text
当前 MCP Gateway 仅暴露 Hermes Agent 实例 default skills。若需要 writer-zh 或 researcher 独立对外服务，请将对应 profile 拆分为独立 hermes-agent container。
```

### F4. API_SERVER 失败状态

显示：

```text
无法连接 Hermes API_SERVER，MCP Gateway 暂不可用。
```

不要再显示 profile fallback 作为 runtime fallback。

### F5. 查看 MCP Tools

新增弹窗或 tab：

```text
Tool Name
Skill ID
Category
Description
can_list
can_invoke
```

## 14. 兼容策略

### 14.1 保留现有 URL

```text
/hermes/agents/common-writer?profile=researcher
```

继续可访问。

但页面中必须说明：

```text
profile=researcher 只影响内部 profile 管理视图；
MCP Gateway 对外仍使用 common-writer 实例 default skills。
```

### 14.2 保留本地技能管理

现有功能继续保留：

```text
上传 zip
Git 安装
创建 profile skill
启用 / 禁用
删除
导入 / 导出 profile
```

但不把它作为 MCP Gateway 对外暴露来源。

### 14.3 历史授权记录继续有效

现有 `skill_id=arxiv` 这类授权继续有效。

如果不同容器有同名 skill，建议后续升级授权 scope：

```text
agent_profile + skill_id
```

本 hotfix 可以先在校验时结合 agent_profile 进行逻辑过滤，不强制数据库迁移。

## 15. 验收标准

### 15.1 API_SERVER 作为唯一主数据源

当执行：

```bash
curl -s -H "Authorization: Bearer xxx" \
  http://192.168.102.247:28900/v1/skills
```

返回 N 个 skills 时，nodeskclaw：

```text
/hermes/mcp/common-writer tools/list
```

也应返回同一批 skills，经授权过滤后数量小于或等于 N。

### 15.2 不再触发 docker exec

刷新 MCP Gateway skills 不应执行：

```text
docker exec hermes skills list
python -m hermes_cli.main
/app/venv/bin/hermes
```

### 15.3 不再出现 --json 错误

系统日志和页面不应出现：

```text
hermes: error: unrecognized arguments: --json
```

### 15.4 不再出现 hermes_cli.main 错误

系统日志和页面不应出现：

```text
ModuleNotFoundError: No module named 'hermes_cli'
```

### 15.5 profile 参数不影响 MCP Gateway

以下两个页面可以内部查看：

```text
/hermes/agents/common-writer?profile=writer-zh
/hermes/agents/common-writer?profile=researcher
```

但 MCP Gateway endpoint 始终是：

```text
/api/v1/hermes/mcp/common-writer
```

且始终暴露：

```text
common-writer 实例 default skills
```

### 15.6 tools/list 授权过滤有效

普通用户只能看到 `can_list=true` 的 skills。

管理员可看到全部 default skills。

### 15.7 tools/call 授权过滤有效

未授权用户调用 skill 返回：

```text
skill_permission_denied
```

授权用户可调用。

### 15.8 API_SERVER 离线时不 fallback 到本地目录

API_SERVER 离线时，MCP Gateway 返回：

```text
api_server_offline
```

不返回 profile 本地 skills。

## 16. 测试用例

### 后端测试

```text
test_list_instance_skills_from_api_server
test_list_instance_skills_requires_bound_gateway_url
test_list_instance_skills_requires_api_server_key
test_mcp_tools_list_returns_api_server_skills
test_mcp_tools_list_filters_by_can_list
test_mcp_tools_call_checks_skill_exists
test_mcp_tools_call_checks_can_invoke
test_mcp_tools_call_uses_chat_completions
test_mcp_rejects_profile_param
test_api_server_offline_does_not_fallback_to_profile_dir
test_no_docker_exec_called_in_mcp_gateway
```

### 前端测试

```text
renders_mcp_gateway_card
shows_default_only_notice
copies_mcp_endpoint
shows_api_server_skill_count
shows_api_server_offline_state
keeps_local_profile_skill_management_tab
does_not_show_profile_fallback_as_runtime
```

## 17. 部署与迁移

### 17.1 当前 common-writer

当前：

```text
common-writer container
  ├─ writer-zh profile
  └─ researcher profile
```

hotfix 后：

```text
common-writer MCP Gateway
  └─ 只暴露 common-writer default skills
```

### 17.2 后续拆分

建议拆成：

```text
hermes-common-writer
hermes-writer-zh
hermes-researcher
```

每个实例：

```text
API_SERVER_ENABLED=true
API_SERVER_HOST=0.0.0.0
API_SERVER_PORT=8642
API_SERVER_KEY=独立 key
API_SERVER_MODEL_NAME=实例名
HERMES_PROFILE=default
```

宿主机映射：

```text
common-writer    → 28900
writer-zh        → 28901
researcher       → 28902
```

nodeskclaw 绑定：

```text
common-writer  → http://192.168.102.247:28900
writer-zh      → http://192.168.102.247:28901
researcher     → http://192.168.102.247:28902
```

## 18. 风险与回滚

### 18.1 风险

1. API_SERVER `/v1/skills` 返回字段较少，可能只有 name/category/description。
2. skills 无参数 schema，因此 MCP tool inputSchema 只能先使用通用 prompt schema。
3. 通过 `/v1/chat/completions` 调用 skill 是间接方式，不能保证强制只使用某个 skill。
4. 同名 skill 在不同 container 中可能导致授权冲突，后续需要 agent_profile + skill_id scope。
5. 旧页面中 profile 参数容易让用户误解，需要明确 UI 提示。

### 18.2 回滚

回滚策略：

```text
关闭 mcp_gateway_enabled
隐藏 MCP Gateway 卡片
保留 Agent Detail 与本地 profile skill 管理
不影响 Hermes API_SERVER 原有调用
```

不需要数据库回滚，除非新增审计表已迁移。

## 19. 给 Cursor 的实施摘要

```text
请实现 nodeskclaw team_v5.1.1_hotfix：Hermes Instance Skills MCP Gateway。

核心变更：
1. MCP Gateway 对外只暴露 Hermes Agent 实例 default skills。
2. 不再按 profile 暴露 skills。
3. 不再使用 docker exec / CLI / profile 本地目录作为对外 Gateway skills 数据源。
4. 统一通过绑定 Agent 的 Hermes API_SERVER 调用 GET /v1/skills 获取 skills。
5. 新增 HermesApiServerClient.list_skills()。
6. 新增 hermes_instance_skill_service.py，负责 API_SERVER skills 获取、归一化、缓存。
7. 新增 POST /api/v1/hermes/mcp/{agent_profile}，支持 initialize / tools/list / tools/call / ping。
8. tools/list 使用 /v1/skills 并按 can_list 授权过滤。
9. tools/call 校验 skill 存在与 can_invoke 后，调用 /v1/chat/completions。
10. 如果请求 profile 参数，MCP Gateway 返回 profile_not_supported。
11. API_SERVER 离线时返回 api_server_offline，不 fallback 到本地 profile skills。
12. 前端 Agent Detail 增加 MCP Gateway 卡片，技能清单文案改为“实例 Skills / 本地 Profile 技能管理”。
13. 页面提示：MCP Gateway 仅暴露实例 default skills；writer-zh/researcher 需要拆成独立 hermes-agent container。
14. 保留 v5.1 已完成的授权修复与本地 profile skill 管理功能。
15. 增加测试，确保 MCP Gateway 不调用 docker exec。
```

## 20. 最终交付状态

完成 team_v5.1.1_hotfix 后，系统应达到：

```text
一个 Hermes Agent Container
  = 一个 API_SERVER
  = 一个 default skills runtime
  = 一个 nodeskclaw MCP Gateway
```

对外调用路径统一为：

```text
MCP Client
  → nodeskclaw MCP Gateway
  → Hermes API_SERVER /v1/skills
  → Hermes API_SERVER /v1/chat/completions
```

不再出现：

```text
同一 container 内按 writer-zh/researcher profile 暴露不同 skills
docker exec 读取 runtime skills
--json 参数错误
hermes_cli.main 模块缺失
profile 本地目录被误当成对外 runtime skills
```
