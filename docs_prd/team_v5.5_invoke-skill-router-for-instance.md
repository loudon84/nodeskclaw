# PRD v5.5：MCP Skill Router

## 1. 背景

v5.4 已完成 `/hermes/agents` 页面一键授权 MCP Skill Gateway，并能在 Hermes common-writer 容器中连接 `common-skills` MCP Server。

当前问题：

```text
用户必须输入英文 MCP tool name 才能稳定调用技能。
例如：
hermes_common_researcher__customer-profiling
hermes_xieyi__semiconductor-marketing-copy
```

这不适合普通业务用户。

v5.5 目标是在 nodeskclaw 中生成一个本地 Hermes Router Skill，让用户通过自然语言调用远程 MCP Skill。

## 2. 目标

在 `/hermes/agents` 页面增加：

```text
同步 MCP Skill Router
```

点击后，nodeskclaw 自动完成：

```text
读取实例 .env 中的 NODESKCLAW_MCP_URL / TOKEN / NAME
→ 调用 MCP tools/list
→ 获取远程 tool name / description / inputSchema
→ 生成本地 Router Skill：nodeskclaw-skill-router
→ 写入目标实例 Hermes skills 目录
→ 更新页面同步状态
```

用户体验从：

```text
请使用 hermes_common_researcher__customer-profiling 给研华科技做客户画像
```

变成：

```text
帮我分析研华科技这个客户，看看有哪些芯片销售机会
```

## 3. 非目标

v5.5 不实现：

```text
不修改 hermes-agent 源码
不修改 hermes-webui 源码
不自动执行 hermes mcp add
不自动执行 hermes mcp login
不自动重启 Docker 容器
不自动重启 Hermes gateway
不改变 MCP Gateway tools/call 协议
不实现复杂 LLM 意图分类服务
```

说明：v5.5 只生成本地 Router Skill 文件。是否重启 gateway 可以提示用户手动执行，或复用已有实例重启按钮。

## 4. 所属项目

主实现项目：

```text
nodeskclaw
```

依赖条件：

```text
nodeskclaw 已有 Docker 实例目录读写权限
nodeskclaw 已能读取 /data/copilot-docker/instances/{instance}/.env
nodeskclaw 已能写入实例 Hermes skills 目录
```

不需要改：

```text
hermes-agent
hermes-webui
```

Hermes 本身支持本地 skills，并支持 `hermes mcp` 管理 MCP server。

## 5. 核心设计

### 5.1 生成的本地 Skill

目标路径：

```text
/data/copilot-docker/instances/{instance_name}/data/hermes/skills/nodeskclaw-skill-router/SKILL.md
```

如果实例 profile 独立 home，则使用该 profile 的实际 `HERMES_HOME`：

```text
{profile_home}/skills/nodeskclaw-skill-router/SKILL.md
```

Skill 名称固定：

```text
nodeskclaw-skill-router
```

### 5.2 Router Skill 职责

Router Skill 不实现业务逻辑，只指导 Hermes：

```text
1. 理解用户自然语言意图
2. 从 common-skills MCP 工具中选择最合适 tool
3. 自动调用对应 MCP tool
4. 返回业务结果
5. 不要求用户输入英文 tool name
```

### 5.3 数据来源

调用 MCP Gateway：

```http
POST {NODESKCLAW_MCP_URL}
Authorization: Bearer {NODESKCLAW_MCP_TOKEN}
Content-Type: application/json
```

请求：

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/list",
  "params": {}
}
```

注意：v5.5 默认使用 `params:{}`，避免 `agent_alias/profile/workspace_id` 把组织级 Skill 过滤为空。MCP 文档中 `tools/list` 支持 header 和 params 上下文过滤，且 params 包括 `agent_alias`、`profile`、`workspace_id`。

## 6. 页面改造

页面：

```text
/hermes/agents
```

在每个实例卡片新增按钮：

```text
同步 MCP Skill Router
```

按钮状态：

| 状态         | 按钮                         |
| ---------- | -------------------------- |
| MCP 未授权    | 禁用，提示先授权 MCP Skill Gateway |
| MCP 已授权    | 同步 MCP Skill Router        |
| Router 已同步 | 重新同步 Router                |
| 同步失败       | 重试同步                       |

卡片新增状态：

```text
Router: 未同步
Router: 已同步
Router: 工具数 4
Router: 同步失败
Router: MCP 未授权
```

点击后弹窗：

```text
将从 common-skills MCP Gateway 读取 tools/list，
并生成本地 Hermes Skill：

nodeskclaw-skill-router

该操作不会重启容器，也不会执行 hermes mcp add。
```

## 7. 后端接口

### 7.1 同步 Router Skill

```http
POST /api/v1/hermes/agents/{agent_id}/mcp-skill-router/sync
```

请求：

```json
{
  "profile": "default",
  "force": true,
  "tool_filter": "skill_only",
  "include_registry_tools": false
}
```

字段说明：

| 字段                     | 说明                                  |
| ---------------------- | ----------------------------------- |
| profile                | 目标 Hermes profile                   |
| force                  | 已存在时是否覆盖                            |
| tool_filter            | `skill_only` / `all`                |
| include_registry_tools | 是否把 hermes.* / genehub.* 也写入 Router |

默认：

```json
{
  "profile": "default",
  "force": true,
  "tool_filter": "skill_only",
  "include_registry_tools": false
}
```

响应：

```json
{
  "ok": true,
  "agent_id": "uuid",
  "instance_name": "common-writer",
  "profile": "default",
  "mcp_name": "common-skills",
  "router_skill_name": "nodeskclaw-skill-router",
  "router_skill_path": "/data/copilot-docker/instances/common-writer/data/hermes/skills/nodeskclaw-skill-router/SKILL.md",
  "tool_count": 4,
  "tool_names": [
    "hermes_common_researcher__customer-profiling",
    "hermes_common_researcher__enterprise-risk-analysis",
    "hermes_common_researcher__manufacturer-profiling",
    "hermes_xieyi__semiconductor-marketing-copy"
  ],
  "synced_at": "2026-06-25T16:00:00+08:00"
}
```

### 7.2 查询 Router 状态

```http
GET /api/v1/hermes/agents/{agent_id}/mcp-skill-router/status?profile=default
```

响应：

```json
{
  "enabled": true,
  "router_skill_name": "nodeskclaw-skill-router",
  "router_skill_path": "/data/copilot-docker/instances/common-writer/data/hermes/skills/nodeskclaw-skill-router/SKILL.md",
  "exists": true,
  "tool_count": 4,
  "last_synced_at": "2026-06-25T16:00:00+08:00",
  "last_error": null
}
```

### 7.3 删除 Router Skill

```http
POST /api/v1/hermes/agents/{agent_id}/mcp-skill-router/delete
```

处理：

```text
删除 nodeskclaw-skill-router 目录
更新状态为未同步
```

## 8. 数据模型

在 Hermes 实例表增加字段：

```sql
ALTER TABLE hermes_agent_instances ADD COLUMN mcp_router_enabled BOOLEAN DEFAULT false;
ALTER TABLE hermes_agent_instances ADD COLUMN mcp_router_skill_name VARCHAR(128) DEFAULT 'nodeskclaw-skill-router';
ALTER TABLE hermes_agent_instances ADD COLUMN mcp_router_skill_path TEXT NULL;
ALTER TABLE hermes_agent_instances ADD COLUMN mcp_router_tool_count INTEGER DEFAULT 0;
ALTER TABLE hermes_agent_instances ADD COLUMN mcp_router_last_synced_at TIMESTAMP NULL;
ALTER TABLE hermes_agent_instances ADD COLUMN mcp_router_last_error TEXT NULL;
```

可选新增表，记录每次同步快照：

```sql
CREATE TABLE hermes_mcp_router_sync_logs (
  id UUID PRIMARY KEY,
  org_id UUID NOT NULL,
  agent_id UUID NOT NULL,
  instance_name VARCHAR(128) NOT NULL,
  profile VARCHAR(128) DEFAULT 'default',
  mcp_name VARCHAR(128),
  router_skill_name VARCHAR(128),
  router_skill_path TEXT,
  tool_count INTEGER DEFAULT 0,
  tool_snapshot JSONB,
  status VARCHAR(32) NOT NULL,
  error_message TEXT NULL,
  created_by UUID NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT now()
);
```

## 9. 服务拆分

新增服务：

```text
app/services/hermes_agents/mcp_skill_router_service.py
app/services/hermes_agents/router_skill_template_service.py
```

职责：

| 服务                           | 职责                                      |
| ---------------------------- | --------------------------------------- |
| `McpSkillRouterService`      | 编排读取 env、调用 tools/list、写入 SKILL.md、更新状态 |
| `RouterSkillTemplateService` | 根据 tools/list 生成 Router Skill Markdown  |

复用已有服务：

```text
EnvFileService
HermesAgentInstanceService
McpClientTokenService
```

## 10. tools/list 处理规则

### 10.1 过滤工具

默认只纳入业务 Skill 工具：

```text
包含：
hermes_common_researcher__*
hermes_xieyi__*
skill.*

排除：
hermes.instances.*
hermes.instance.*
hermes.skills.*
genehub.*
```

规则：

```python
def is_business_skill_tool(tool):
    name = tool["name"]
    if name.startswith("hermes.instances."):
        return False
    if name.startswith("hermes.instance."):
        return False
    if name.startswith("hermes.skills."):
        return False
    if name.startswith("genehub."):
        return False
    return True
```

### 10.2 提取字段

每个 tool 提取：

```json
{
  "name": "hermes_common_researcher__customer-profiling",
  "description": "半导体芯片分销企业的客户画像与销售机会分析...",
  "inputSchema": {}
}
```

### 10.3 生成触发词

从 description 中提取：

```text
当用户输入
请为XX公司做客户画像
分析XX公司的芯片采购需求
XX公司风险评估
撰写芯片推广文案
```

如果 description 中没有触发词，则使用 tool name 和 description 自动生成简短触发规则。

## 11. Router Skill 模板

生成文件：

```text
SKILL.md
```

模板：

```markdown
# nodeskclaw-skill-router

## 作用

你是 nodeskclaw MCP Skill Router。

你的任务是根据用户的自然语言需求，自动选择 common-skills MCP 中最合适的远程技能并调用。

用户不需要知道英文工具名。

## MCP 工具集

MCP Server 名称：

common-skills

## 可用远程技能

{{TOOLS_SECTION}}

## 路由规则

1. 用户提出业务需求时，不要求用户输入英文 skill 名称。
2. 根据用户意图、公司名称、产品类型、任务类型选择最匹配的远程技能。
3. 如果用户意图明确，直接调用对应 MCP tool。
4. 如果多个 tool 都匹配，选择最贴近用户最终产出的一个。
5. 只有在用户缺少必要参数时才追问。
6. 不要向用户暴露内部路由过程。
7. 不要要求用户说出 tool name。
8. 调用完成后，直接输出业务结果。
9. 如果 MCP 调用失败，说明失败原因，并给出下一步建议。

## 工具选择优先级

1. 用户明确要求客户画像、采购需求、销售机会 → 使用客户画像工具。
2. 用户明确要求风险评估、信用评级、经营风险 → 使用企业风险分析工具。
3. 用户明确要求芯片原厂、厂家画像、供应商合作 → 使用原厂画像工具。
4. 用户明确要求推广文案、产品介绍、技术方案营销 → 使用半导体营销文案工具。

## 禁止行为

- 不要让用户输入英文 tool name。
- 不要伪造远程工具结果。
- 不要绕过 common-skills MCP Gateway。
- 不要修改用户输入的公司名称、品牌、产品线。
```

单个工具段模板：

```markdown
### {{display_title}}

工具名：

`{{tool_name}}`

能力说明：

{{description}}

适合场景：

{{trigger_rules}}

调用要求：

当用户需求匹配以上场景时，调用 `{{tool_name}}`。
```

## 12. 示例生成结果

```markdown
### 客户画像与销售机会分析

工具名：

`hermes_common_researcher__customer-profiling`

能力说明：

半导体芯片分销企业的客户画像与销售机会分析。

适合场景：

- 用户要求为某公司做客户画像
- 用户要求分析芯片采购需求
- 用户要求分析销售机会
- 用户输入“帮我分析 XX 客户”

调用要求：

当用户需求匹配以上场景时，调用 `hermes_common_researcher__customer-profiling`。
```

## 13. 写文件规则

目标目录：

```text
{hermes_home}/skills/nodeskclaw-skill-router/
```

文件：

```text
SKILL.md
```

写入要求：

```text
1. 如果目录不存在则创建
2. 如果 SKILL.md 已存在，先备份
3. 使用临时文件 + rename 原子写入
4. 写入权限 644
5. 不写入 MCP Token
6. 不写入 Authorization Header
```

备份：

```text
SKILL.md.bak.20260625_160000
```

## 14. 路径解析规则

优先级：

```text
1. 使用 Hermes 实例绑定记录中的 profile_home / hermes_home
2. 使用实例目录：instances/{instance}/data/hermes
3. 使用默认路径：/data/copilot-docker/instances/{instance}/data/hermes
```

目标路径：

```python
router_skill_dir = f"{hermes_home}/skills/nodeskclaw-skill-router"
router_skill_file = f"{router_skill_dir}/SKILL.md"
```

如果 profile 独立 home：

```python
router_skill_file = f"{profile_home}/skills/nodeskclaw-skill-router/SKILL.md"
```

## 15. 后端主流程伪代码

```python
def sync_mcp_skill_router(agent_id, profile, current_user):
    assert_user_is_org_admin_or_operator(current_user)

    agent = get_hermes_agent_instance(agent_id)
    env = read_instance_env(agent.env_path)

    assert env["NODESKCLAW_MCP_ENABLED"] == "true"
    mcp_url = env["NODESKCLAW_MCP_URL"]
    mcp_token = env["NODESKCLAW_MCP_TOKEN"]
    mcp_name = env.get("NODESKCLAW_MCP_NAME", "common-skills")

    tools = fetch_mcp_tools_list(
        url=mcp_url,
        token=mcp_token,
        params={}
    )

    business_tools = filter_business_skill_tools(tools)

    if not business_tools:
        raise Error("MCP tools/list returned no business skill tools")

    skill_md = render_router_skill_md(
        mcp_name=mcp_name,
        tools=business_tools
    )

    router_path = resolve_router_skill_path(agent, profile)

    atomic_write(
        path=router_path,
        content=skill_md,
        backup=True
    )

    update_agent_router_status(
        agent_id=agent.id,
        enabled=True,
        path=router_path,
        tool_count=len(business_tools),
        last_synced_at=now()
    )

    create_sync_log(
        status="success",
        tool_snapshot=business_tools
    )

    return result
```

## 16. MCP 请求实现

```python
def fetch_mcp_tools_list(url, token, params=None):
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list",
        "params": params or {}
    }

    response = httpx.post(
        url,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
            "X-Client": "nodeskclaw-router-sync"
        },
        json=payload,
        timeout=30
    )

    response.raise_for_status()
    body = response.json()

    if "error" in body:
        raise Error(body["error"])

    return body["result"]["tools"]
```

## 17. 前端改造点

### 17.1 Agent 卡片新增状态

```tsx
<McpRouterStatusBadge status={agent.mcp_router_status} />
```

展示：

```text
Router: 未同步
Router: 已同步 · 4 tools
Router: 同步失败
```

### 17.2 Agent 卡片新增按钮

```tsx
<Button onClick={() => openMcpRouterSyncDialog(agent)}>
  同步 MCP Skill Router
</Button>
```

### 17.3 弹窗

内容：

```text
将同步 common-skills MCP 工具清单，并生成本地 Router Skill。

生成位置：
/data/copilot-docker/instances/common-writer/data/hermes/skills/nodeskclaw-skill-router/SKILL.md

本操作不会自动重启容器。
同步后请重启 Hermes gateway 或重建实例。
```

按钮：

```text
取消
确认同步
```

成功提示：

```text
已生成 nodeskclaw-skill-router，发现 4 个远程技能。
请重启 Hermes gateway 后使用自然语言测试。
```

## 18. 用户测试用例

同步完成并重启后，用户应能直接输入：

```text
帮我分析研华科技这个客户，看看有哪些芯片销售机会
```

期望调用：

```text
hermes_common_researcher__customer-profiling
```

用户输入：

```text
分析一下某某公司有没有合作风险
```

期望调用：

```text
hermes_common_researcher__enterprise-risk-analysis
```

用户输入：

```text
帮我写一段工业连接器的市场推广文案
```

期望调用：

```text
hermes_xieyi__semiconductor-marketing-copy
```

用户输入：

```text
分析一下英飞凌这个芯片原厂，看看有没有合作机会
```

期望调用：

```text
hermes_common_researcher__manufacturer-profiling
```

## 19. 错误处理

### MCP 未授权

```text
未找到 NODESKCLAW_MCP_TOKEN，请先执行“授权 MCP Skill Gateway”。
```

### tools/list 为空

```text
MCP tools/list 未返回可用业务技能。请检查 MCP Token 权限、Skill 是否 is_mcp_exposed、Installation 是否 installed。
```

### 文件写入失败

```text
Router Skill 写入失败，请检查 nodeskclaw 对实例目录的写入权限。
```

### MCP 请求失败

```text
无法连接 MCP Skill Gateway，请检查 NODESKCLAW_MCP_URL。
```

## 20. 安全要求

```text
不得在 SKILL.md 中写入 MCP Token
不得在日志中输出完整 Token
不得把 Authorization Header 写入 Router Skill
只有 org admin / operator 可同步 Router
同步日志只保存 tool name / description / schema
```

## 21. 审计日志

新增事件：

```text
mcp_router.sync.started
mcp_router.sync.completed
mcp_router.sync.failed
mcp_router.skill_file.written
mcp_router.skill_file.deleted
```

字段：

```json
{
  "org_id": "...",
  "actor_user_id": "...",
  "agent_id": "...",
  "instance_name": "common-writer",
  "profile": "default",
  "mcp_name": "common-skills",
  "tool_count": 4,
  "router_skill_path": ".../nodeskclaw-skill-router/SKILL.md",
  "status": "success"
}
```

## 22. Cursor 执行任务清单

### Task 1：DB migration

```text
为 hermes_agent_instances 增加 mcp_router_* 字段
可选新增 hermes_mcp_router_sync_logs 表
```

### Task 2：实现 RouterSkillTemplateService

```text
新增 app/services/hermes_agents/router_skill_template_service.py
实现 render_router_skill_md(mcp_name, tools)
实现 tool display title 生成
实现 trigger rules 提取
```

### Task 3：实现 McpSkillRouterService

```text
新增 app/services/hermes_agents/mcp_skill_router_service.py
读取实例 .env
调用 MCP tools/list
过滤业务 skill tools
解析目标 Hermes home
写入 SKILL.md
更新实例状态
写入同步日志
```

### Task 4：实现文件写入能力

```text
复用或扩展 EnvFileService
支持 mkdir
支持 atomic write
支持 backup
支持 chmod
```

### Task 5：新增 API

```text
POST /api/v1/hermes/agents/{agent_id}/mcp-skill-router/sync
GET  /api/v1/hermes/agents/{agent_id}/mcp-skill-router/status
POST /api/v1/hermes/agents/{agent_id}/mcp-skill-router/delete
```

### Task 6：前端页面改造

```text
/hermes/agents 卡片增加 Router 状态
增加“同步 MCP Skill Router”按钮
增加同步确认弹窗
成功后刷新 agent 状态
```

### Task 7：测试

```text
单测 tools/list 解析
单测 business tool 过滤
单测 SKILL.md 生成
单测 token 不写入 SKILL.md
接口测试 sync / status / delete
手工测试 common-writer WebUI 自然语言触发 skill
```

## 23. 验收标准

### 后端验收

```text
能读取 common-writer .env 中的 MCP 配置
能调用 MCP tools/list 并获取 4 个业务工具
能生成 nodeskclaw-skill-router/SKILL.md
SKILL.md 不包含 token
同步状态能回写到 agent 卡片
```

### 前端验收

```text
/hermes/agents 页面显示 Router 状态
点击“同步 MCP Skill Router”可成功生成 Router Skill
同步成功显示 tool_count
失败时显示明确错误
```

### 用户体验验收

```text
用户不输入英文 tool name，也能通过自然语言触发远程 skill
客户画像、风险分析、原厂画像、营销文案四类需求可自动路由
```

## 24. v5.5 完成定义

v5.5 完成后，nodeskclaw 能为任意已授权 MCP Skill Gateway 的 Hermes 实例生成本地 Router Skill，使用户在 Hermes WebUI 中通过自然语言调用远程 MCP Skills。

本版本不负责容器内 MCP 注册、不负责 gateway 重启、不修改 hermes-agent 源码。
