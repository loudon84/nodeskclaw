# PRD：hermes-plugin-nodeskclaw-knowledge v1.0

> 文档类型：需求产品设计文档（PRD） 项目：nodeskclaw-knowledge
> 模块：Hermes Agent Knowledge Plugin 版本：v1.0 目标：支持 hermes-agent
> v0.21 通过 Plugin Tool 调用 KnowledgeSet 检索能力
>
> Grill 决议已对齐（见 §12 / ADR-0001）

------------------------------------------------------------------------

# 1. 文档说明

## 1.1 背景

当前企业智能体架构中：

-   hermes-agent 负责 Agent Runtime、Task Planning、Tool Calling；
-   nodeskclaw-knowledge 负责企业知识管理、KnowledgeSet
    编排、RetrievalService、RAGFlow 检索；
-   RAGFlow 负责底层 Dataset 检索。

需要增加 hermes-agent 与 nodeskclaw-knowledge 的连接能力。

本需求采用：

**方案 B：由应用传入 KnowledgeSet**

即：

-   应用负责确定当前 Agent 使用的 KnowledgeSet，并写入 Hermes Session scope（本插件只读，不负责注入实现）；
-   Hermes Agent 通过 Plugin Tool 调用知识检索；
-   nodeskclaw-knowledge 负责完整 Retrieval Pipeline。

------------------------------------------------------------------------

# 2. 产品目标

## 2.1 目标

建设：

`hermes-plugin-nodeskclaw-knowledge`

源码落点（本仓）：

    nodeskclaw-knowledge/plugins/hermes-plugin-nodeskclaw-knowledge/

后续其它 Agent 产品插件统一放在 `nodeskclaw-knowledge/plugins/` 下。

使 Hermes Agent v0.21 可以：

1.  读取 Session 上的 KnowledgeSet 上下文（由应用注入；插件不负责写入）；
2.  从 Hermes plugin config / 环境变量读取 `SMC_KB_API_URL`、`SMC_KB_API_TOKEN`（禁止写死），调用已有 `knowledge.retrieve` API；
3.  以用户 JWT Bearer 透传鉴权（与 Desktop / Portal 相同的 `get_member_context`）；
4.  透传 Knowledge 检索结果（chunks / evidence 等）作为 **Tool Result** 交给 Agent（不做额外 Context 注入）；
5.  v1.0 服务侧默认零行为变更；允许补契约测试与 401 可操作性提示，不改检索语义。

配置说明边界：本 PRD **仅描述** Hermes `~/.hermes/.env` 与 `config.yaml` 的运维操作说明；不负责 `.env` 的创建、写入、加载或展开实现（由运维 + hermes-agent 完成）。

------------------------------------------------------------------------

# 3. 整体架构

    Application
        |
        | knowledge_set_id (Session 注入，本插件不实现)
        |
        v

    hermes-agent v0.21

        |
        | Plugin Tool: knowledge.retrieve
        |
        v

    hermes-plugin-nodeskclaw-knowledge
    (nodeskclaw-knowledge/plugins/...)

        |
        | HTTP POST + Authorization: Bearer <JWT>
        | {origin}/api/v2/agent/tools/knowledge.retrieve
        |
        v

    nodeskclaw-knowledge
    (get_member_context -> KnowledgePrincipal -> ACL)

        |
        v

    KnowledgeSet

        |
        +---- KnowledgeBase A
        +---- KnowledgeBase B
        +---- KnowledgeBase C

        |
        v

    RetrievalService

        |
        v

    Evidence (+ chunks)  --tool result-->  Agent

------------------------------------------------------------------------

# 4. 功能需求

## FR-001 Plugin 初始化

插件名称：

    hermes-plugin-nodeskclaw-knowledge

本仓库源码目录：

    nodeskclaw-knowledge/plugins/hermes-plugin-nodeskclaw-knowledge/

Hermes 运行时安装位置（运维拷贝/链接到）：

    ~/.hermes/plugins/hermes-plugin-nodeskclaw-knowledge/

目录结构：

    hermes-plugin-nodeskclaw-knowledge/

    ├── plugin.yaml
    ├── main.py
    ├── client.py
    ├── tools/
    │   └── knowledge.py
    ├── config.py
    └── README.md

------------------------------------------------------------------------

## FR-002 Tool 注册

插件需要向 Hermes 注册：

## Tool

名称：

    knowledge.retrieve

描述：

    Retrieve enterprise knowledge from assigned KnowledgeSet.

参数（v1.0 仅此三项；不暴露 application_id / channel / release_id）：

``` json
{
  "knowledge_set_id": {
    "type": "string",
    "description": "KnowledgeSet ID；缺省时回退 session.knowledge_set_id"
  },
  "query": {
    "type": "string",
    "description": "User question"
  },
  "top_k": {
    "type": "integer",
    "default": 10
  }
}
```

------------------------------------------------------------------------

## FR-003 KnowledgeSet Scope（只读）

应用启动 Hermes Session 时自行写入（**本需求不实现注入路径**）：

``` json
{
  "knowledge_context": {
    "knowledge_set_id": "ks-sales-product"
  }
}
```

插件行为：

- 读取当前 Session Knowledge Scope（若存在）；
- 调用 `knowledge.retrieve` 时：**Tool 参数 `knowledge_set_id` 优先**；缺省回退 `session.knowledge_set_id`；
- 两者皆缺则返回可操作错误（提示应用注入 Session 或在 Tool 参数中传入）。

------------------------------------------------------------------------

## FR-004 Retrieval 调用

`SMC_KB_API_URL` 为 **origin only**（例：`http://nodeskclaw-knowledge:4530`）。

插件拼接：

    POST {SMC_KB_API_URL}/api/v2/agent/tools/knowledge.retrieve

请求头：

``` text
Authorization: Bearer <SMC_KB_API_TOKEN>
Content-Type: application/json
```

说明：

- `SMC_KB_API_TOKEN` 为用户登录 nodeskclaw-backend（默认端口 4510）后获得的 JWT；
- 插件将该 Token 放入 `Authorization` Header 透传给 nodeskclaw-knowledge；
- nodeskclaw-knowledge 使用与 Desktop / Portal 相同的 `get_member_context` 鉴权，换取 `KnowledgePrincipal` 后再做 ACL 与检索；
- **不使用** `KNOWLEDGE_SERVICE_TOKEN` 作为本插件默认路径；
- 插件不得在包内写死 API URL 或 Token；
- 配置读取顺序：**plugin config（展开后的 url/token）优先，缺省回退 `os.environ` 的 `SMC_KB_*`**；
- v1.0 Token 为静态 `.env` 配置；过期后由运维更新 `.env` 并重启 Hermes；后续版本再评估 Session 动态注入。

请求体：

``` json
{
 "knowledge_set_id":"ks-sales-product",
 "query":"RK3568有哪些摄像头方案",
 "top_k":10
}
```

错误处理：

- HTTP / 业务错误优先透传 Knowledge 的 `error_code` / `message_key` / `message`；
- Token 缺失或无效（401）时：透传原错误，并在插件侧追加运维提示（检查 `SMC_KB_API_TOKEN`、更新 `~/.hermes/.env`、重启 Hermes），不改写 `error_code`。

------------------------------------------------------------------------

## FR-005 返回结构（透传服务端契约）

插件 **透传** `ApiResponse.data`（及错误契约），不对 chunks/evidence 做简化映射。

成功时 `data` 至少包含服务端已有字段（示意，以线上契约为准）：

``` json
{
  "query_id": "...",
  "chunks": [
    {
      "evidence_id": "...",
      "knowledge_base_id": "...",
      "source_file_id": "...",
      "file_name": "xxx.pdf",
      "content": "...",
      "similarity": 0.89,
      "weighted_score": 0.91,
      "page": 3,
      "highlight": "..."
    }
  ],
  "evidence": [
    {
      "evidence_id": "...",
      "evidence_type": "...",
      "content": "...",
      "score": 0.89,
      "source_refs": [],
      "payload": {
        "page": 3,
        "highlight": "..."
      }
    }
  ],
  "status": "...",
  "diagnostics": {},
  "latency_ms": 0
}
```

说明：

- Agent Context 中的「Evidence」= 上述 Tool Result；插件不做 hook 二次注入；
- 多 KnowledgeBase 部分失败等语义 **跟随** nodeskclaw-knowledge RetrievalService，插件不二次定义。

------------------------------------------------------------------------

# 5. Hermes Agent 注册流程

## 5.0 配置边界（重要）

本 PRD **仅描述** Hermes 侧运维人员需要准备的 `.env` / `config.yaml` 操作说明。

本 PRD / 本插件 **不负责**：

- 创建、写入、轮换或校验 `~/.hermes/.env`；
- 实现 Hermes 的 `.env` 加载与 `${VAR}` 展开（由 hermes-agent 自身完成）；
- 签发 JWT（由 nodeskclaw-backend 登录流程完成）；
- 将 `knowledge_set_id` 写入 Hermes Session（由应用负责）。

运维人员在 Hermes 环境中自行配置密钥；插件只读取已展开后的配置值（或环境变量）并调用 Knowledge API。

------------------------------------------------------------------------

## 5.1 安装插件

从本仓拷贝或链接到 Hermes plugins 目录：

``` bash
# 源码
nodeskclaw-knowledge/plugins/hermes-plugin-nodeskclaw-knowledge/

# 运行时
~/.hermes/plugins/hermes-plugin-nodeskclaw-knowledge/
```

------------------------------------------------------------------------

## 5.2 配置 plugin.yaml

示例：

``` yaml
name: nodeskclaw-knowledge

version: 1.0.0

description:
  Enterprise KnowledgeSet Retrieval Plugin

tools:
  - knowledge.retrieve

requires_env:
  - name: SMC_KB_API_URL
    description: nodeskclaw-knowledge origin (scheme://host:port), no path
  - name: SMC_KB_API_TOKEN
    description: Backend user JWT for Knowledge Authorization Bearer
    secret: true
```

------------------------------------------------------------------------

## 5.3 配置 Hermes（操作说明）

### 5.3.1 写入 ~/.hermes/.env（运维操作，本需求不实现）

由运维人员在 Hermes 主机上自行维护：

``` bash
# ~/.hermes/.env
SMC_KB_API_URL=http://nodeskclaw-knowledge:4530
SMC_KB_API_TOKEN=<backend登录后的用户JWT>
```

说明：

- 密钥必须放在 `~/.hermes/.env`，禁止写入插件源码或镜像层；
- `SMC_KB_API_URL` 仅为 origin，不含 `/api/v2`；
- JWT 过期后需运维更新 `.env` 并重启 Hermes（v1.0）；
- 本 PRD 只文档化变量名，不提供写 `.env` 的代码职责。

### 5.3.2 修改 ~/.hermes/config.yaml

可选嵌套 config（推荐用 `${VAR}` 引用，避免明文密钥进 yaml）：

``` yaml
plugins:

  enabled:
    - nodeskclaw-knowledge

  nodeskclaw-knowledge:

    enabled: true

    config:

      url: ${SMC_KB_API_URL}

      token: ${SMC_KB_API_TOKEN}
```

插件解析顺序：

1. `config.url` / `config.token`（若已由 Hermes 展开）；
2. 否则 `os.environ["SMC_KB_API_URL"]` / `os.environ["SMC_KB_API_TOKEN"]`；
3. 仍缺失则拒绝加载或 Tool 调用失败，并给出可操作提示。

------------------------------------------------------------------------

## 5.4 重启 Hermes

``` bash
hermes gateway restart
```

检查：

``` bash
hermes tools list
```

应该看到：

    knowledge.retrieve

------------------------------------------------------------------------

# 6. Session 使用流程

## 创建 Agent Session

应用（本插件不实现）：

``` json
{
 "agent":"sales-agent",
 "knowledge_set_id": "ks-semiconductor-sales"
}
```

------------------------------------------------------------------------

## 用户提问

    这个客户适合推广RK3588方案吗？

------------------------------------------------------------------------

## Hermes Tool Call

    knowledge.retrieve

参数（可省略 knowledge_set_id 以回退 Session）：

``` json
{
 "knowledge_set_id": "ks-semiconductor-sales",
 "query": "客户适合推广RK3588方案吗",
 "top_k": 10
}
```

------------------------------------------------------------------------

## Knowledge Gateway

执行：

    get_member_context
     -> KnowledgeSet
     -> KnowledgeBase(s)
     -> ACL
     -> Retrieval Planner
     -> RAGFlow
     -> Evidence / chunks
     -> Tool Result -> Agent

------------------------------------------------------------------------

# 7. 权限设计

原则：

Hermes Plugin 不管理权限。

权限由：

    nodeskclaw-knowledge

负责。

鉴权模式（与 Desktop / Portal 统一）：

1. 用户登录 nodeskclaw-backend（默认端口 4510）获得 JWT；
2. 运维将该 JWT 配置为 Hermes 环境变量 `SMC_KB_API_TOKEN`（见 §5.3，仅操作说明）；
3. 插件请求 Knowledge 时携带 `Authorization: Bearer <JWT>`；
4. nodeskclaw-knowledge 走 `get_member_context`，将 Bearer 转发给 backend 换取 `KnowledgePrincipal`；
5. 服务端再做 KnowledgeSet / KnowledgeBase ACL 校验。

调用链：

    User (backend JWT)
     -> Hermes Plugin (Bearer 透传)
     -> Knowledge Gateway (get_member_context)
     -> KnowledgePrincipal
     -> ACL Check
     -> Retrieval

------------------------------------------------------------------------

# 8. 非功能需求

## 性能

目标：

-   API 延迟 \< 3s
-   支持并发 Retrieval
-   支持 Streaming 后续扩展

## 安全

要求：

-   不保存用户知识数据；
-   不缓存敏感文档；
-   Token 使用 HTTPS `Authorization: Bearer` Header 透传；
-   Token 来源为 backend 用户 JWT（`SMC_KB_API_TOKEN`），不在插件包内写死；
-   `.env` 仅由运维维护；本需求文档只描述操作说明，不负责 `.env` 处理实现；
-   KnowledgeSet 权限由服务端 `get_member_context` + ACL 校验。

------------------------------------------------------------------------

# 9. 开发任务拆分

  编号   任务
  ------ --------------------------------------------------------------
  T01    在 nodeskclaw-knowledge/plugins/ 创建插件工程
  T02    实现 plugin.yaml（requires_env: SMC_KB_*）
  T03    实现 Tool 注册 knowledge.retrieve
  T04    实现 Client：origin 拼接路径；config 优先 / env 回退；Bearer 透传
  T05    实现 Session scope 只读 + Tool 参数优先回退
  T06    401 透传并追加运维提示
  T07    hermes-agent v0.21 安装与 tools list 验证
  T08    KnowledgeSet Retrieval 联调（透传真实契约）
  T09    （可选）服务侧契约测试 / 401 可操作性补强，不改检索语义
  T10    README：仅文档化 .env / config.yaml 操作说明

------------------------------------------------------------------------

# 10. 验收标准

## AC-001

Hermes 启动后能够发现：

    knowledge.retrieve

------------------------------------------------------------------------

## AC-002

指定 KnowledgeSet 后，`knowledge.retrieve` 返回与 Knowledge API 一致的 `data`（含 `chunks`、`evidence` 等真实字段），而非简化映射结构。

------------------------------------------------------------------------

## AC-003

KnowledgeSet 包含多个 KnowledgeBase 时，参与行为与失败语义与服务端一致（插件不二次定义）。

------------------------------------------------------------------------

## AC-004

无权限访问 KnowledgeSet：

返回：

    403 Forbidden

------------------------------------------------------------------------

## AC-005

插件包内不得出现写死的 Knowledge API URL 或 Token；联调时通过 Hermes `.env` 与可选 `config.yaml` 的 `${SMC_KB_*}` 生效；config 缺失时 env 回退仍可用。

------------------------------------------------------------------------

## AC-006

携带有效 backend 用户 JWT 时，Knowledge 走 `get_member_context` 成功；缺失或无效 Token 时透传 401，并带运维提示。

------------------------------------------------------------------------

## AC-007

未传 Tool `knowledge_set_id` 且 Session 有值时，使用 Session；Tool 有值时覆盖 Session。

------------------------------------------------------------------------

# 11. 后续演进

v1.1：

-   Session 动态注入 Token（替代静态 JWT）；
-   `knowledge.answer` 完整 RAG Answer；
-   可选暴露 `application_id` / `channel` / `release_id`。

v1.2：

    knowledge.query_rows

v2.0：

    Hermes MCP Client <-> nodeskclaw Knowledge MCP Server

------------------------------------------------------------------------

# 12. Grill 决议摘要

| ID | 决议 |
|----|------|
| Q1 | v1.0 静态 JWT；过期运维刷新；后续 Session 注入 |
| Q2 | FR-005 对齐真实 API；插件透传 |
| Q3 | 仅 knowledge_set_id + query + top_k |
| Q4 | Tool 参数优先，缺省回退 Session |
| Q5 | 目录插件；配置双读 |
| Q6 | config 优先，回退 os.environ |
| Q7 | Evidence 仅 Tool Result，无额外注入 |
| Q8 | 多 KB 失败语义跟随服务端 |
| Q9 | Session 注入由应用负责 |
| Q10 | 401 透传 + 运维提示 |
| Q11 | 见 ADR-0001 |
| Q12 | SMC_KB_API_URL = origin only |
| Q13 | 源码在 nodeskclaw-knowledge/plugins/ |
| Q14 | 服务侧允许小改（测试/可操作性），不改检索语义 |
| Q15 | 同步更新 PRD + ADR + CONTEXT |
