# 需求规格文档：team_v2.1.3_mcp-skill-product-completion

版本：team_v2.1.3
前置版本：team_v2.1.1_mcp_skill_gateway_hardening
项目：nodeskclaw — Hermes MCP Skill Gateway
日期：2026-06-06

---

## 需求总览

| 功能域 | 需求数 | P0 | P1 | P2 |
|--------|--------|----|----|-----|
| R1 Skill Scan | 6 | 3 | 3 | 0 |
| R2 Skill Installation | 6 | 1 | 4 | 1 |
| R3 Manifest Parser | 5 | 1 | 4 | 0 |
| R4 MCP tools/list | 5 | 2 | 3 | 0 |
| R5 MCP tools/call | 7 | 3 | 3 | 1 |
| R6 Task / SSE / Artifact | 7 | 1 | 5 | 1 |
| R7 Git Import | 5 | 0 | 4 | 1 |
| R8 Skill Collection | 4 | 0 | 3 | 1 |
| R9 权限与审计 | 5 | 1 | 3 | 1 |
| R10 路径安全 | 4 | 1 | 2 | 1 |
| R11 Portal P0 页面 | 5 | 0 | 4 | 1 |
| R12 测试 | 3 | 0 | 2 | 1 |
| **合计** | **62** | **13** | **40** | **9** |

---

## R1 Skill Scan（技能扫描）

### REQ-1.1 Skill Scan 组织归属

| 项目 | 内容 |
|------|------|
| ID | REQ-1.1 |
| EARS | The Hermes Skill Gateway shall write all scanned Skill records with the current organization ID (org_id) |
| 验收标准 | 1. POST /api/v1/hermes/skills/scan 后，hermes_skills 表中 org_id 字段不为空且等于当前请求组织；2. 不同组织扫描结果互不可见；3. org_id 为空时扫描请求返回 400 错误 |
| 优先级 | P0 |
| 来源 | PRD §9.1 实施要求 1-3；v2.1.1 P0-1 事务提交 |

### REQ-1.2 Agent Profile Skill 扫描

| 项目 | 内容 |
|------|------|
| ID | REQ-1.2 |
| EARS | When a scan request includes "agent_scanned" in source_types, the Hermes Skill Gateway shall scan Skills from the Agent Profile skills directory |
| 验收标准 | 1. 能扫描 writer-9601 profile 下的 skills 目录；2. source_type 写入 agent_scanned；3. is_read_only 写入 true；4. canonical_path 写入真实 skill 目录路径 |
| 优先级 | P1 |
| 来源 | PRD §3.1 功能目标 2；PRD §9.1 实施要求 5；Epic 2 |

### REQ-1.3 扫描失败容错

| 项目 | 内容 |
|------|------|
| ID | REQ-1.3 |
| EARS | If an individual Skill directory scan fails, the Hermes Skill Gateway shall continue scanning remaining directories and report the failure in the response errors list |
| 验收标准 | 1. 单个 Skill 扫描异常不中断整体扫描；2. 响应中 failed_count > 0 且 errors 列表包含失败路径和原因；3. is_partial 为 true 时表示部分失败 |
| 优先级 | P1 |
| 来源 | PRD §9.1 实施要求 6；PRD §9.1 响应 is_partial / errors |

### REQ-1.4 扫描结果审计

| 项目 | 内容 |
|------|------|
| ID | REQ-1.4 |
| EARS | When a Skill scan completes, the Hermes Skill Gateway shall create an audit record with action "hermes.skill.scanned" |
| 验收标准 | 1. 审计记录包含 scanned_count、added_count、updated_count、org_id；2. 审计记录持久化到数据库 |
| 优先级 | P1 |
| 来源 | PRD §9.1 实施要求 7；PRD §14.1 审计动作 |

### REQ-1.5 扫描范围支持

| 项目 | 内容 |
|------|------|
| ID | REQ-1.5 |
| EARS | The Hermes Skill Gateway shall support scanning Skills from central, marketplace, imported, and agent_scanned source types |
| 验收标准 | 1. source_types 参数包含 ["central", "marketplace", "imported", "agent_scanned"] 时全部扫描；2. body 为空时等价于 scope=all；3. 各 source_type 结果正确分类 |
| 优先级 | P1 |
| 来源 | PRD §9.1 请求 source_types；PRD §3.1 功能目标 1-2 |

### REQ-1.6 扫描事务提交

| 项目 | 内容 |
|------|------|
| ID | REQ-1.6 |
| EARS | When a Skill scan completes successfully, the Hermes Skill Gateway shall commit the database transaction to persist all scanned results |
| 验收标准 | 1. 扫描请求完成后，数据库中可查到新增/更新的 Skill 记录；2. 不出现只 flush 未 commit 导致的数据丢失 |
| 优先级 | P0 |
| 来源 | v2.1.1 P0-1 事务提交问题；PRD §9.1 |

---

## R2 Skill Installation（技能安装）

### REQ-2.1 安装目标校验

| 项目 | 内容 |
|------|------|
| ID | REQ-2.1 |
| EARS | When a Skill installation request is received, the Hermes Skill Gateway shall validate that the target Agent exists, the target Profile exists, and the Skill agent_type matches the Agent agent_type |
| 验收标准 | 1. 目标 Agent 不存在时返回 404；2. 目标 Profile 不存在时返回 404；3. agent_type 不匹配时返回 400 错误 |
| 优先级 | P0 |
| 来源 | PRD §9.3 实施要求 1-3；PRD §21 不通过条件 9 |

### REQ-2.2 真实安装路径

| 项目 | 内容 |
|------|------|
| ID | REQ-2.2 |
| EARS | The Hermes Skill Installer shall install Skill files to the target Agent Profile skills directory under {profile_root_path}/skills/ |
| 验收标准 | 1. installed_path 指向真实 profile skills 目录；2. 安装路径必须在目标 profile skills 目录内；3. 安装路径不在 profile skills 目录时拒绝安装 |
| 优先级 | P1 |
| 来源 | PRD §9.3 实施要求 5-6；PRD §6.2；Epic 4 |

### REQ-2.3 安装模式

| 项目 | 内容 |
|------|------|
| ID | REQ-2.3 |
| EARS | Where install_mode is included in the installation request, the Hermes Skill Installer shall execute the installation according to the specified mode (copy, symlink, docker_mount, registry_bind, api_deploy) |
| 验收标准 | 1. copy 模式复制目录到目标路径；2. symlink 模式创建软链接；3. docker_mount 模式记录 symlink_target 和 mount metadata；4. registry_bind 模式只绑定 registry 不做文件复制；5. install_mode 不在 gateway.yaml allowed_modes 中时拒绝安装 |
| 优先级 | P1 |
| 来源 | PRD §9.3 实施要求 4；PRD §10.2 gateway.yaml install.allowed_modes；Epic 4 |

### REQ-2.4 安装后触发重扫描

| 项目 | 内容 |
|------|------|
| ID | REQ-2.4 |
| EARS | When a Skill installation completes, the Hermes Skill Gateway shall trigger a profile skill rescan for the target Agent Profile |
| 验收标准 | 1. 安装完成后目标 profile 的 Skill 列表更新；2. 新安装的 Skill 出现在后续 tools/list 中 |
| 优先级 | P1 |
| 来源 | PRD §9.3 实施要求 8；PRD §7.2 Skill 安装规则 9 |

### REQ-2.5 安装审计

| 项目 | 内容 |
|------|------|
| ID | REQ-2.5 |
| EARS | When a Skill installation completes, the Hermes Skill Gateway shall create an audit record with action "hermes.skill.installed" |
| 验收标准 | 1. 审计记录包含 skill_id、agent_id、profile_id、install_mode、installed_by；2. 审计记录持久化 |
| 优先级 | P1 |
| 来源 | PRD §9.3 实施要求 7；PRD §14.1 |

### REQ-2.6 卸载规则

| 项目 | 内容 |
|------|------|
| ID | REQ-2.6 |
| EARS | When a Skill uninstallation is requested, the Hermes Skill Gateway shall remove the installed files according to the link_type and record the uninstallation in audit, and the uninstalled Tool shall no longer appear in tools/list |
| 验收标准 | 1. copy 模式删除目标目录；2. symlink 模式删除软链接不删源目录；3. docker_mount/registry_bind/api_deploy 不删除源目录；4. 卸载后 tools/list 不再返回该 Tool；5. 卸载写审计 |
| 优先级 | P2 |
| 来源 | PRD §9.4 实施要求 1-5 |

---

## R3 Manifest Parser（清单解析）

### REQ-3.1 SKILL.md 必填校验

| 项目 | 内容 |
|------|------|
| ID | REQ-3.1 |
| EARS | The Manifest Parser shall validate that SKILL.md frontmatter contains required fields "id" and "name" |
| 验收标准 | 1. id 为空时扫描失败并报错；2. name 为空时扫描失败并报错；3. id 不符合 skill_id 正则 `^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$` 时失败 |
| 优先级 | P1 |
| 来源 | PRD §10.1 必填字段和校验；Epic 3 |

### REQ-3.2 gateway.yaml 暴露规则校验

| 项目 | 内容 |
|------|------|
| ID | REQ-3.2 |
| EARS | Where expose_as_mcp is true in gateway.yaml, the Manifest Parser shall require that tool_name and input_schema are present |
| 验收标准 | 1. expose_as_mcp=true 但 tool_name 缺失时扫描失败；2. expose_as_mcp=true 但 input_schema 缺失时扫描失败；3. tool_name 不符合正则 `^[a-z][a-z0-9_]*$` 时失败 |
| 优先级 | P0 |
| 来源 | PRD §10.2 校验 1-2、4；PRD §21 不通过条件相关；Epic 3 |

### REQ-3.3 gateway.yaml 一致性校验

| 项目 | 内容 |
|------|------|
| ID | REQ-3.3 |
| EARS | The Manifest Parser shall validate that gateway.yaml skill_id equals SKILL.md frontmatter id |
| 验收标准 | 1. gateway.skill_id 与 SKILL.md id 不一致时扫描失败并报错 |
| 优先级 | P1 |
| 来源 | PRD §10.2 校验 3；Epic 3 |

### REQ-3.4 Schema 校验

| 项目 | 内容 |
|------|------|
| ID | REQ-3.4 |
| EARS | The Manifest Parser shall validate that input_schema and output_schema are valid JSON Schema and that install.allowed_modes only contains permitted values |
| 验收标准 | 1. input_schema 非法 JSON Schema 时扫描失败；2. output_schema 非法 JSON Schema 时扫描失败；3. allowed_modes 包含非法值时失败 |
| 优先级 | P1 |
| 来源 | PRD §10.2 校验 5-7；Epic 3 |

### REQ-3.5 无 gateway.yaml 处理

| 项目 | 内容 |
|------|------|
| ID | REQ-3.5 |
| EARS | If a Skill directory contains SKILL.md but not gateway.yaml, the Manifest Parser shall register the Skill with is_mcp_exposed set to false |
| 验收标准 | 1. 无 gateway.yaml 的 Skill 可入库；2. is_mcp_exposed = false；3. 该 Skill 不暴露为 MCP Tool |
| 优先级 | P1 |
| 来源 | PRD §7.1 Skill 暴露规则；Epic 3 验收 5 |

---

## R4 MCP tools/list（工具发现）

### REQ-4.1 安装状态过滤

| 项目 | 内容 |
|------|------|
| ID | REQ-4.1 |
| EARS | The MCP tools/list shall only return Skills that have an installation record with status "installed" |
| 验收标准 | 1. 未安装 Skill 不出现在 tools/list 结果中；2. installation status 非 installed 的 Skill 不出现；3. PRD §21 不通过条件 2 "tools/list 返回未安装 Skill" 不得发生 |
| 优先级 | P0 |
| 来源 | PRD §9.5 过滤条件 5；PRD §21 不通过条件 2；Epic 6 |

### REQ-4.2 权限过滤

| 项目 | 内容 |
|------|------|
| ID | REQ-4.2 |
| EARS | The MCP tools/list shall only return Skills for which the current user has both skill:view and skill:invoke permissions |
| 验收标准 | 1. 无 skill:view 权限的 Skill 不返回；2. 无 skill:invoke 权限的 Skill 不返回；3. PRD §21 不通过条件 3 "tools/list 返回未授权 Skill" 不得发生 |
| 优先级 | P0 |
| 来源 | PRD §9.5 过滤条件 6-7；PRD §21 不通过条件 3；Epic 6 |

### REQ-4.3 启用状态过滤

| 项目 | 内容 |
|------|------|
| ID | REQ-4.3 |
| EARS | While a Skill is inactive (is_active = false) or not MCP-exposed (is_mcp_exposed = false) or has no tool_name, the MCP tools/list shall not include that Skill |
| 验收标准 | 1. is_active = false 的 Skill 不返回；2. is_mcp_exposed = false 的 Skill 不返回；3. tool_name 为 null 的 Skill 不返回 |
| 优先级 | P1 |
| 来源 | PRD §9.5 过滤条件 2-4；PRD §7.1 Skill 暴露规则 |

### REQ-4.4 组织数据隔离

| 项目 | 内容 |
|------|------|
| ID | REQ-4.4 |
| EARS | The MCP tools/list shall only return Skills belonging to the current user's organization |
| 验收标准 | 1. hermes_skills.org_id = current_org_id；2. 不同 org 的 Skill 不可见 |
| 优先级 | P1 |
| 来源 | PRD §9.5 过滤条件 1；PRD §21 不通过条件 5 |

### REQ-4.5 tools/list 响应格式

| 项目 | 内容 |
|------|------|
| ID | REQ-4.5 |
| EARS | The MCP tools/list shall return a JSON-RPC 2.0 compliant response containing tool name, title, description, inputSchema, and version for each Skill |
| 验收标准 | 1. 响应符合 JSON-RPC 2.0 格式；2. 每个工具包含 name、title、description、inputSchema、version 字段 |
| 优先级 | P1 |
| 来源 | PRD §9.5 响应结构 |

---

## R5 MCP tools/call（工具调用）

### REQ-5.1 tool_name 路由

| 项目 | 内容 |
|------|------|
| ID | REQ-5.1 |
| EARS | When a tools/call request is received, the Hermes Skill Gateway shall look up the Skill by tool_name from params.name and route the request to the corresponding installed Skill |
| 验收标准 | 1. 按 tool_name 正确查找 Skill；2. params.name 缺失时返回 400 级 JSON-RPC 错误；3. v2.1.1 P0-2 修复：tool_name 必须传入路由匹配 |
| 优先级 | P0 |
| 来源 | v2.1.1 P0-2 tool_name 路由问题；PRD §9.6 实施要求 1；Epic 6 |

### REQ-5.2 输入校验

| 项目 | 内容 |
|------|------|
| ID | REQ-5.2 |
| EARS | When a tools/call request is received, the Hermes Skill Gateway shall validate that the arguments conform to the Skill input_schema |
| 验收标准 | 1. arguments 不符合 input_schema 时返回 JSON-RPC error code -32602；2. 缺少 required 字段时返回具体字段名和原因 |
| 优先级 | P1 |
| 来源 | PRD §9.6 实施要求 3；PRD §9.6 错误响应示例 |

### REQ-5.3 创建 Hermes Task

| 项目 | 内容 |
|------|------|
| ID | REQ-5.3 |
| EARS | When a tools/call request passes validation, the Hermes Skill Gateway shall create a hermes_tasks record with status "queued" and return the task_id in the response |
| 验收标准 | 1. hermes_tasks 表新增记录；2. task_id 不为 null；3. 初始状态为 queued；4. PRD §21 不通过条件 1 "tools/call 返回 task_id = null" 不得发生 |
| 优先级 | P0 |
| 来源 | PRD §9.6 实施要求 4-5、8-9；PRD §21 不通过条件 1；Epic 6 |

### REQ-5.4 调用权限校验

| 项目 | 内容 |
|------|------|
| ID | REQ-5.4 |
| EARS | When a tools/call request is received, the Hermes Skill Gateway shall verify that the current user has skill:invoke permission for the target Skill |
| 验收标准 | 1. 无 skill:invoke 权限时返回 JSON-RPC error；2. 有权限时正常创建 task |
| 优先级 | P1 |
| 来源 | PRD §9.6 实施要求 2；PRD §13.3 权限校验点 7 |

### REQ-5.5 Task 事件写入

| 项目 | 内容 |
|------|------|
| ID | REQ-5.5 |
| EARS | When a Hermes Task is created, the Hermes Skill Gateway shall write a task.created event to hermes_task_events |
| 验收标准 | 1. hermes_task_events 表新增 event_type = "task.created" 记录；2. 事件包含 task_id 和 status |
| 优先级 | P1 |
| 来源 | PRD §9.6 实施要求 6；PRD §8.4 事件类型 |

### REQ-5.6 JSON-RPC id 透传

| 项目 | 内容 |
|------|------|
| ID | REQ-5.6 |
| EARS | The Hermes Skill Gateway shall preserve the original JSON-RPC request id in the response |
| 验收标准 | 1. 响应中 id 等于请求中 id；2. 上游返回 id 为空时 Gateway 使用原始 id；3. 并发调用时响应 id 正确匹配 |
| 优先级 | P1 |
| 来源 | v2.1.1 P1-4 JSON-RPC id 丢弃；PRD §9.6 实施要求 10 |

### REQ-5.7 非阻塞响应

| 项目 | 内容 |
|------|------|
| ID | REQ-5.7 |
| EARS | The MCP tools/call shall return immediately with task_id, event_url, and artifact_url without waiting for the task to complete |
| 验收标准 | 1. tools/call 不阻塞等待长任务完成；2. 响应 structuredContent 包含 task_id、status、event_url、artifact_url |
| 优先级 | P2 |
| 来源 | PRD §3.2 产品目标 6；PRD §4 非目标 7；PRD §9.6 响应结构 |

---

## R6 Task / SSE / Artifact（任务 / 事件 / 产物）

### REQ-6.1 Task 状态查询

| 项目 | 内容 |
|------|------|
| ID | REQ-6.1 |
| EARS | The Hermes Skill Gateway shall provide a Task query API that returns the current status, associated skill, agent, and event/artifact URLs |
| 验收标准 | 1. GET /api/v1/hermes/tasks/{task_id} 返回完整 task 信息；2. 包含 status、skill_id、tool_name、agent_id、event_url、artifact_url；3. 无权限时返回 403 |
| 优先级 | P1 |
| 来源 | PRD §9.7 Task API；Epic 7 验收 2 |

### REQ-6.2 SSE 任务事件流

| 项目 | 内容 |
|------|------|
| ID | REQ-6.2 |
| EARS | When a client connects to the Task events SSE endpoint, the Hermes Skill Gateway shall stream task lifecycle events (task.created, task.started, task.completed, task.failed) in real time |
| 验收标准 | 1. GET /api/v1/hermes/tasks/{task_id}/events 返回 SSE 流；2. 推送 task.created、task.started、artifact.created、task.completed 事件；3. 事件格式符合 event/data 结构 |
| 优先级 | P1 |
| 来源 | PRD §9.7 SSE 响应；PRD §8.4 事件类型；v2.1.1 P2-2 SSE 混合模式 |

### REQ-6.3 Hermes Agent 适配

| 项目 | 内容 |
|------|------|
| ID | REQ-6.3 |
| EARS | When a Hermes Task transitions to running, the HermesAgentAdapter shall forward the task to the target Hermes Agent /v1/runs endpoint and convert Hermes run events to hermes_task_events |
| 验收标准 | 1. 调用目标 Agent /v1/runs 接口；2. hermes.run.* 事件转换为 task 事件；3. hermes_run_id 写入 hermes_tasks |
| 优先级 | P1 |
| 来源 | PRD §7.3 MCP 调用规则；Epic 7 任务 7、11 |

### REQ-6.4 Artifact 登记

| 项目 | 内容 |
|------|------|
| ID | REQ-6.4 |
| EARS | When a Hermes Task completes, the ArtifactService shall scan the task outputs directory and register each output file as a hermes_artifacts record with sha256 hash |
| 验收标准 | 1. 任务完成后扫描 {workspace_root_path}/.nodeskclaw/runs/{task_id}/outputs/；2. 每个文件写入 hermes_artifacts；3. sha256 字段正确；4. storage_type 默认 local |
| 优先级 | P1 |
| 来源 | PRD §8.5；PRD §6.3；Epic 7 任务 12-13 |

### REQ-6.5 Artifact 下载

| 项目 | 内容 |
|------|------|
| ID | REQ-6.5 |
| EARS | When an Artifact download request is received, the Hermes Skill Gateway shall verify the user has hermes_artifact:download permission and the artifact belongs to the current organization before serving the file |
| 验收标准 | 1. 无 hermes_artifact:download 权限时拒绝下载；2. artifact 不属于当前 org 时拒绝；3. 下载后 download_count 递增 |
| 优先级 | P1 |
| 来源 | PRD §9.7 Artifact 实施要求 1-2、5 |

### REQ-6.6 Artifact 路径安全

| 项目 | 内容 |
|------|------|
| ID | REQ-6.6 |
| EARS | The ArtifactService shall reject any download request where the file realpath is outside the allowed task outputs directory |
| 验收标准 | 1. 软链接逃逸被拒绝；2. workspace_root_path 外文件不可访问；3. outputs 目录外文件不可访问；4. PRD §21 不通过条件 6 不得发生 |
| 优先级 | P0 |
| 来源 | PRD §9.7 实施要求 3-4；PRD §15.2；PRD §21 不通过条件 6 |

### REQ-6.7 SSE 连接管理

| 项目 | 内容 |
|------|------|
| ID | REQ-6.7 |
| EARS | While an SSE connection is active, the Hermes Skill Gateway shall maintain the connection with heartbeat and clean up on disconnection |
| 验收标准 | 1. SSE 连接鉴权通过后才可订阅；2. 断线后连接资源释放；3. 连接建立/关闭/异常写入审计 |
| 优先级 | P2 |
| 来源 | v2.1.1 P2-2 SSE 混合模式修复要求；PRD §5 总体架构 SSE Event Service |

---

## R7 Git Import（Git 导入）

### REQ-7.1 Preview 拉取和扫描

| 项目 | 内容 |
|------|------|
| ID | REQ-7.1 |
| EARS | When a Skill import preview request is received, the GitImporter shall clone the repository to cache directory, scan for SKILL.md, and return the list of importable Skills with conflict status |
| 验收标准 | 1. 拉取仓库到 cache 目录；2. 扫描 SKILL.md 和 gateway.yaml；3. 返回 Skill 列表含 skill_id、name、version、has_gateway、is_mcp_exposed、conflict；4. 不执行仓库中任何脚本 |
| 优先级 | P1 |
| 来源 | PRD §11.1 Preview 要求 1-8；Epic 8 |

### REQ-7.2 Import 执行

| 项目 | 内容 |
|------|------|
| ID | REQ-7.2 |
| EARS | When a Skill import execution request is received, the GitImporter shall copy selected Skills from cache to /data/nodeskclaw/skills/imported and trigger an imported scan |
| 验收标准 | 1. Skill 复制到 imported 目录；2. 导入后触发 imported scan；3. hermes_skills 表写入记录；4. source_type = github 或 git；5. source_url 和 source_ref 正确写入 |
| 优先级 | P1 |
| 来源 | PRD §11.2 Import 要求 1、5-9；Epic 8 |

### REQ-7.3 敏感文件过滤

| 项目 | 内容 |
|------|------|
| ID | REQ-7.3 |
| EARS | The GitImporter shall not copy files with extensions .env, .pem, .key, or .secret during import |
| 验收标准 | 1. .env/.pem/.key/.secret 文件不复制；2. PRD §21 不通过条件 7 不得发生 |
| 优先级 | P1 |
| 来源 | PRD §11.2 Import 要求 2；PRD §21 不通过条件 7 |

### REQ-7.4 导入大小限制

| 项目 | 内容 |
|------|------|
| ID | REQ-7.4 |
| EARS | The GitImporter shall enforce total import size limit and individual file size limit during import |
| 验收标准 | 1. 导入总大小超过限制时拒绝；2. 单文件大小超过限制时拒绝 |
| 优先级 | P2 |
| 来源 | PRD §11.2 Import 要求 3-4 |

### REQ-7.5 Import 审计

| 项目 | 内容 |
|------|------|
| ID | REQ-7.5 |
| EARS | When a Skill import completes, the Hermes Skill Gateway shall create an audit record with action "hermes.skill.imported" or "hermes.skill.import.previewed" |
| 验收标准 | 1. preview 写入 hermes.skill.import.previewed 审计；2. execute 写入 hermes.skill.imported 审计；3. 审计包含 source_url、source_ref、imported_skills 数量 |
| 优先级 | P1 |
| 来源 | PRD §11.2 Import 要求 10；PRD §14.1 审计动作 |

---

## R8 Skill Collection（技能包）

### REQ-8.1 Collection 批量安装

| 项目 | 内容 |
|------|------|
| ID | REQ-8.1 |
| EARS | When a Collection install request is received, the Hermes Skill Gateway shall install each Skill in the Collection to the specified Agent and Profile, returning success/failed/skipped results per Skill |
| 验收标准 | 1. 每个 Skill 生成 installation 记录；2. 响应包含 success/failed/skipped 分类；3. collection.agent_type 与目标 agent_type 不匹配时拒绝 |
| 优先级 | P1 |
| 来源 | PRD §12.3 Install Collection；Epic 9 验收 3-4 |

### REQ-8.2 Required Skill 失败处理

| 项目 | 内容 |
|------|------|
| ID | REQ-8.2 |
| EARS | If a required Skill installation fails during Collection install, the Hermes Skill Gateway shall mark the Collection install result as "partial_failed" |
| 验收标准 | 1. is_required=true 的 Skill 失败时，整体结果为 partial_failed；2. is_required=false 的 Skill 失败时记录 failed 但不阻断其余 Skill |
| 优先级 | P1 |
| 来源 | PRD §12.3 要求 2-3；Epic 9 |

### REQ-8.3 Collection Skill 管理

| 项目 | 内容 |
|------|------|
| ID | REQ-8.3 |
| EARS | The Hermes Skill Gateway shall provide APIs to add and remove Skills from a Collection |
| 验收标准 | 1. POST /skill-collections/{collection_id}/skills 添加 Skill；2. DELETE /skill-collections/{collection_id}/skills/{skill_id} 移除 Skill；3. 支持 version_constraint 和 sort_order |
| 优先级 | P1 |
| 来源 | PRD §12.2；Epic 9 任务 1-2 |

### REQ-8.4 Collection 审计

| 项目 | 内容 |
|------|------|
| ID | REQ-8.4 |
| EARS | When a Collection install completes, the Hermes Skill Gateway shall create an audit record with action "hermes.skill.collection.installed" |
| 验收标准 | 1. 审计包含 collection_id、agent_ids、success/failed/skipped 列表；2. 审计持久化 |
| 优先级 | P2 |
| 来源 | PRD §12.3 要求 5；PRD §14.1 |

---

## R9 权限与审计（Permission & Audit）

### REQ-9.1 Skill 暴露权限

| 项目 | 内容 |
|------|------|
| ID | REQ-9.1 |
| EARS | The Hermes Skill Gateway shall enforce that a Skill is only exposed as MCP Tool when all conditions are met: SKILL.md exists, gateway.yaml exists, expose_as_mcp=true, tool_name is valid, is_active=true, Skill is installed, and user has skill:view and skill:invoke |
| 验收标准 | 1. 任一条件不满足时 Skill 不暴露；2. 条件全部满足时 Skill 可通过 tools/list 发现 |
| 优先级 | P1 |
| 来源 | PRD §7.1 Skill 暴露规则 1-7 |

### REQ-9.2 安装权限

| 项目 | 内容 |
|------|------|
| ID | REQ-9.2 |
| EARS | When a Skill installation is requested, the Hermes Skill Gateway shall verify the user has skill:install permission and management permission on the target Agent |
| 验收标准 | 1. 无 skill:install 权限时拒绝；2. 无 Agent 管理权限时拒绝 |
| 优先级 | P1 |
| 来源 | PRD §7.2 Skill 安装规则 1-2；PRD §13.3 权限校验点 2 |

### REQ-9.3 角色权限映射

| 项目 | 内容 |
|------|------|
| ID | REQ-9.3 |
| EARS | The Hermes Skill Gateway shall enforce role-based access control according to the defined permission mappings for org admin, operator, workspace manager, member, and viewer |
| 验收标准 | 1. org admin 拥有全部权限；2. viewer 仅有 skill:view + hermes_task:view + hermes_artifact:view；3. member 有 skill:invoke 但无 skill:install |
| 优先级 | P1 |
| 来源 | PRD §13.1-13.2 权限项和角色映射 |

### REQ-9.4 审计完整性

| 项目 | 内容 |
|------|------|
| ID | REQ-9.4 |
| EARS | The Hermes Skill Gateway shall record audit entries for all lifecycle actions: scan, import, install, uninstall, invoke, task lifecycle, and artifact download |
| 验收标准 | 1. 每个审计动作在 PRD §14.1 列表中；2. 审计 details 包含 skill_id、tool_name、agent_id、user_id 等上下文；3. 写操作审计包含 request_summary；4. 审计不可被关闭或绕过 |
| 优先级 | P0 |
| 来源 | PRD §14.1-14.2；v2.1.1 P1-3 审计字段不足 |

### REQ-9.5 审计查询权限

| 项目 | 内容 |
|------|------|
| ID | REQ-9.5 |
| EARS | Where skill:audit_read permission is included, the Hermes Skill Gateway shall allow the user to query audit records; otherwise the request shall be rejected |
| 验收标准 | 1. 有 skill:audit_read 权限的用户可查询审计；2. 无权限时返回 403；3. 审计查询支持按 action/skill_id/task_id/user_id 过滤 |
| 优先级 | P2 |
| 来源 | PRD §13.3 权限校验点 10；PRD §16.6 Audit 页面 |

---

## R10 路径安全（Path Security）

### REQ-10.1 文件路径校验

| 项目 | 内容 |
|------|------|
| ID | REQ-10.1 |
| EARS | The Hermes Skill Gateway shall validate that all file paths used in Skill operations are resolved to realpath and fall within the allowed root directory |
| 验收标准 | 1. 所有路径使用 realpath 解析；2. 路径必须在允许根目录内；3. 软链接逃逸被拒绝 |
| 优先级 | P0 |
| 来源 | PRD §15.1 基础要求 1-3；PRD §21 不通过条件 6、8 |

### REQ-10.2 禁止系统目录访问

| 项目 | 内容 |
|------|------|
| ID | REQ-10.2 |
| EARS | The Hermes Skill Gateway shall reject any file path that resolves to /etc, /root, or any arbitrary host directory outside the designated data paths |
| 验收标准 | 1. /etc、/root 等系统目录不可访问；2. 不根据用户输入拼接未校验路径 |
| 优先级 | P1 |
| 来源 | PRD §15.1 基础要求 4-5 |

### REQ-10.3 安装路径约束

| 项目 | 内容 |
|------|------|
| ID | REQ-10.3 |
| EARS | The SkillInstaller shall only install files within the target Agent Profile skills directory |
| 验收标准 | 1. 安装路径 realpath 必须以 profile skills 目录为前缀；2. 安装路径不在 profile skills 目录时拒绝；3. PRD §21 不通过条件 8 不得发生 |
| 优先级 | P1 |
| 来源 | PRD §7.2 Skill 安装规则 7；PRD §21 不通过条件 8 |

### REQ-10.4 禁止密钥文件下载

| 项目 | 内容 |
|------|------|
| ID | REQ-10.4 |
| EARS | The ArtifactService shall reject download requests for files with extensions .env, .pem, .key, or .secret |
| 验收标准 | 1. 密钥文件类型不可下载；2. 隐藏密钥文件不可下载 |
| 优先级 | P2 |
| 来源 | PRD §15.2 禁止文件类型 |

---

## R11 Portal P0 页面（门户页面）

### REQ-11.1 Skills 管理页面

| 项目 | 内容 |
|------|------|
| ID | REQ-11.1 |
| EARS | The Portal shall provide a Skills management page at /portal/hermes/skills that displays Skill list with filtering and supports Scan, Enable/Disable, and Install actions |
| 验收标准 | 1. Skill 列表展示 skill_id、tool_name、version、source_type、is_mcp_exposed、is_active；2. 按 source_type/agent_type/category/keyword 过滤；3. 管理员可执行 Scan；4. 可 Enable/Disable Skill；5. 可 Install Skill；6. 可查看 input_schema/output_schema |
| 优先级 | P1 |
| 来源 | PRD §16.1；Epic 10 任务 1 |

### REQ-11.2 Installations 管理页面

| 项目 | 内容 |
|------|------|
| ID | REQ-11.2 |
| EARS | The Portal shall provide a Skill Installations page at /portal/hermes/skill-installations that displays installation records and supports Install, Uninstall, and status sync |
| 验收标准 | 1. 安装记录列表展示；2. 按 agent_id/skill_id/status 过滤；3. 可安装/卸载 Skill；4. 可同步安装状态；5. 可查看失败原因 |
| 优先级 | P1 |
| 来源 | PRD §16.2；Epic 10 任务 2 |

### REQ-11.3 Imports 管理页面

| 项目 | 内容 |
|------|------|
| ID | REQ-11.3 |
| EARS | The Portal shall provide a Skill Imports page at /portal/hermes/skill-imports that supports entering Git URL, Preview, and Import |
| 验收标准 | 1. 可输入 GitHub/Git URL；2. 可 Preview 返回可导入列表和冲突状态；3. 可选择 Skill 后 Import；4. 可查看导入结果 |
| 优先级 | P1 |
| 来源 | PRD §16.3；Epic 10 任务 3 |

### REQ-11.4 Tasks 和 Artifacts 页面

| 项目 | 内容 |
|------|------|
| ID | REQ-11.4 |
| EARS | The Portal shall provide a Tasks page at /portal/hermes/tasks and an Artifacts page at /portal/hermes/artifacts for viewing task status, events, and downloading artifacts |
| 验收标准 | 1. 任务列表展示状态和失败原因；2. 可查看任务事件；3. Artifact 列表支持按 task_id/skill_id/agent_id 过滤；4. 可下载 Artifact 并显示 sha256 |
| 优先级 | P1 |
| 来源 | PRD §16.4-16.5；Epic 10 任务 4-5 |

### REQ-11.5 页面基础状态

| 项目 | 内容 |
|------|------|
| ID | REQ-11.5 |
| EARS | The Portal P0 pages shall display appropriate loading, error, and empty states for all data-dependent components |
| 验收标准 | 1. 数据加载中显示 loading 状态；2. 请求失败显示 error 状态；3. 无数据时显示 empty 状态；4. 所有 i18n 文案接入翻译词条 |
| 优先级 | P2 |
| 来源 | PRD §16；Epic 10 任务 8；AGENTS.md i18n 规则 |

---

## R12 测试（Testing）

### REQ-12.1 单元测试覆盖

| 项目 | 内容 |
|------|------|
| ID | REQ-12.1 |
| EARS | The Hermes Skill Gateway shall have unit tests covering ManifestParser, SkillScanner, ConflictDetector, SkillInstaller path safety, McpToolMapper, ArtifactService path safety, and GitImporter |
| 验收标准 | 1. 每个模块有对应测试文件；2. 关键路径安全测试通过；3. Manifest 解析边界条件覆盖 |
| 优先级 | P1 |
| 来源 | PRD §18.1；Epic 各验收标准 |

### REQ-12.2 API 测试覆盖

| 项目 | 内容 |
|------|------|
| ID | REQ-12.2 |
| EARS | The Hermes Skill Gateway shall have API tests covering all endpoints: /skills/scan, /skills, /skill-installations, /mcp tools/list, /mcp tools/call, /tasks, /artifacts, /skill-imports |
| 验收标准 | 1. 每个端点有正常和异常测试用例；2. 权限校验测试覆盖；3. PRD §21 不通过条件 10 "缺少核心接口测试" 不得发生 |
| 优先级 | P1 |
| 来源 | PRD §18.2；PRD §21 不通过条件 10 |

### REQ-12.3 集成测试通过

| 项目 | 内容 |
|------|------|
| ID | REQ-12.3 |
| EARS | The Hermes Skill Gateway shall pass all integration test cases: scan central Skill, install Skill, MCP tools/list, MCP tools/call, Artifact download, GitHub Import, and Collection batch install |
| 验收标准 | 1. PRD §18.3 用例 1-7 全部通过；2. 扫描→安装→发现→调用→产物全链路贯通 |
| 优先级 | P2 |
| 来源 | PRD §18.3；PRD §20 交付标准 18 |

---

## 附录 A：不通过条件映射

以下条件任一触发时，版本不得合并：

| 不通过条件 | 对应需求 ID | 说明 |
|------------|------------|------|
| tools/call 返回 task_id = null | REQ-5.3 | P0 创建 Hermes Task |
| tools/list 返回未安装 Skill | REQ-4.1 | P0 安装状态过滤 |
| tools/list 返回未授权 Skill | REQ-4.2 | P0 权限过滤 |
| Skill Scan 写入空 org_id | REQ-1.1, REQ-1.6 | P0 组织归属和事务提交 |
| 不同 org 之间 Skill 数据串联 | REQ-4.4, REQ-1.1 | P0 组织隔离 |
| Artifact 可读取 workspace 外文件 | REQ-6.6, REQ-10.1 | P0 路径安全 |
| GitHub Import 复制 .env/.pem/.key/.secret | REQ-7.3 | P1 敏感文件过滤 |
| 安装路径不在 profile skills 目录 | REQ-10.3 | P1 安装路径约束 |
| agent_type 不匹配仍可安装 | REQ-2.1 | P0 安装目标校验 |
| 缺少核心接口测试 | REQ-12.2 | P1 API 测试覆盖 |

---

## 附录 B：需求追溯矩阵

| Epic | 需求 ID |
|------|---------|
| Epic 1：修复 Skill Scan 组织归属 | REQ-1.1, REQ-1.6 |
| Epic 2：Agent Profile Skill 扫描 | REQ-1.2, REQ-1.5 |
| Epic 3：Manifest Parser 完善 | REQ-3.1, REQ-3.2, REQ-3.3, REQ-3.4, REQ-3.5 |
| Epic 4：SkillInstaller 真实安装路径 | REQ-2.1, REQ-2.2, REQ-2.3, REQ-2.4 |
| Epic 5：ConflictDetector 修复 | REQ-9.1 (部分) |
| Epic 6：MCP Tool Mapper 完善 | REQ-4.1, REQ-4.2, REQ-4.3, REQ-4.4, REQ-5.1, REQ-5.2, REQ-5.3, REQ-5.4, REQ-5.5, REQ-5.6 |
| Epic 7：Task / SSE / Artifact | REQ-6.1, REQ-6.2, REQ-6.3, REQ-6.4, REQ-6.5, REQ-6.6, REQ-6.7 |
| Epic 8：GitHub / Git Import | REQ-7.1, REQ-7.2, REQ-7.3, REQ-7.4, REQ-7.5 |
| Epic 9：Skill Collection 完善 | REQ-8.1, REQ-8.2, REQ-8.3, REQ-8.4 |
| Epic 10：Portal P0 页面 | REQ-11.1, REQ-11.2, REQ-11.3, REQ-11.4, REQ-11.5 |
