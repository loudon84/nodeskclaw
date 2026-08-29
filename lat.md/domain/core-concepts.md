# Core Domain Concepts

NoDeskClaw 的核心领域实体是组织、集群、实例、工作区与基因；它们共同描述租户边界、AI 员工部署与能力分发。

实体之间的从属关系：Organization（租户）拥有 Workspace 与 Instance；Instance 部署在 Cluster 上；Gene 安装到 Instance 以扩展 Agent 能力。协作语义见 [[collaboration]]。

## Organization

组织是多租户边界与配额容器，持有成员、套餐上限、可选专属集群与组织级 LLM Key。

所有 workspace、instance、usage 数据必须按 `org_id` 隔离。Portal 用 `org_memberships` 鉴权；管理后台用独立的 `admin_memberships`，二者职责分离。

权威模型：[[nodeskclaw-backend/app/models/organization.py#Organization]]。

快速创建人类成员支持 OA 姓名搜索快选：Portal 点「搜索」调用 `GET /orgs/{org_id}/members/oa-persons?q=`，后端代理 `OA_PERSON_API_URL`（`fd_name`）；未配置或失败不阻断手工填写。映射与代理见 [[nodeskclaw-backend/app/services/org_service.py#search_oa_persons]]。

## User

平台用户是登录主体，持有账号凭证、组织归属与任务治理标记。

`users.is_task_admin` 标记任务管理员（默认 `false`）。登录与 `/auth/me` 的 `UserInfo`、成员列表的 `MemberInfo` 均带出该字段；创建人类成员 `POST /orgs/{org_id}/members/create-human` 与更新资料 `PATCH /orgs/{org_id}/members/{membership_id}/profile` 可写入。直属下属查询：`GET /members/{member_id}/subordinate`（`member_id` 为 `users.id`）返回查询对象本人及其直属下属（`id, name, email, username, is_active`）。若该用户 `is_task_admin` 或 `is_super_admin`，则返回全部未软删除用户。契约见 [[nodeskclaw-backend/app/schemas/instance_member.py#DirectReportUser]]；路由 [[nodeskclaw-backend/app/api/portal/members.py#list_member_subordinates]]；实现见 [[nodeskclaw-backend/app/services/org_service.py#create_human_member]]、[[nodeskclaw-backend/app/services/org_service.py#update_member_profile]]、[[nodeskclaw-backend/app/services/org_service.py#list_subordinates]]。

权威模型：[[nodeskclaw-backend/app/models/user.py#User]]。

## Cluster

集群保存可编排的计算目标（KubeConfig 加密、健康状态），供实例部署与巡检使用。

生产默认走火山云 VKE；同一 kubeconfig 可有多 context，操作必须显式指定 context，并同时确认 namespace（staging / prod）。

权威模型：[[nodeskclaw-backend/app/models/cluster.py#Cluster]]。

## Instance

实例是可部署的 AI 员工运行单元（DeskClaw / Hermes 等），绑定集群、资源配额、LLM 配置与运行时状态。

状态机覆盖 creating → deploying → running → failed / deleting 等。部署按 `compute_provider` 分发到 k8s / docker / process（见 [[decisions/compute-providers]]）。

Working Plan 认证用 `wp_api_key`；Control UI / WebSocket 用 `proxy_token`。权威模型：[[nodeskclaw-backend/app/models/instance.py#Instance]]。

列表/详情响应用派生字段 `webui_port` 暴露 WebUI host_port（非 Gateway）：优先 `advanced_config.webui.host_port`，其次 `webui.port`，再回退 `env_vars.DOCKER_HOST_PORT`；解析逻辑见 [[nodeskclaw-backend/app/services/instance_service.py#_resolve_webui_port]]。Portal `/instances` 据此展示并做精确端口筛选。

### Instance Status

实例状态字段驱动 Portal 展示与编排决策，不允许前端自行猜测「已就绪」。

关键状态包括 `creating`、`pending`、`deploying`、`running`、`failed`、`deleting` 等（见 [[nodeskclaw-backend/app/models/instance.py#InstanceStatus]]）。健康另由 `health_status` 表达。

## Workspace

工作区是赛博办公室：多人与多 Agent 协作的容器，含黑板、消息、成员与可选集群绑定。

工作区不等于实例：一个工作区可关联多个 Agent / 实例节点；消息与黑板以 workspace 为作用域。模型：[[nodeskclaw-backend/app/models/workspace.py#Workspace]]。

## Gene

基因（Gene）是可安装到实例的能力包：Skill 内容、工具白名单、MCP 配置与 OpenClaw 合并项。

安装经 `gene_service` 选择 runtime 对应 adapter（OpenClaw / Hermes / noop）。模板变更后需评估 DeskHub 推送与已装实例同步。模型：[[nodeskclaw-backend/app/models/gene.py#Gene]]。基因安装流程见下节。

## Gene Installation

基因安装是异步编排：API 触发 → 选 adapter → 写入实例文件系统 → 校验 → 更新安装状态。

OpenClaw 写入 `.openclaw/skills/`；Hermes 走对应 adapter。学习回调需签名校验。入口：[[nodeskclaw-backend/app/services/gene_service.py#_get_gene_install_adapter]]。

## Skill Installation

Skill 安装定义了 Skill 在组织内特定执行目标上的部署绑定，支持云端 Remote 与私网 Edge 两种部署形态。

安装实体通过 [[nodeskclaw-backend/app/models/hermes_skill/skill_installation.py#HermesSkillInstallation]] 记录 Desired 期望配置（`desired_generation`）与边缘节点回报的 `actual_status` 与 `actual_generation` 状态；Edge 节点由 [[nodeskclaw-agent/app/services/edge_skill_installer.py#EdgeSkillInstaller]] 在本地隔离目录执行解压、防逃逸与校验等真实文件系统副作用。

## Connector Center

Connector Center 是连接企业外部 API、MCP 服务与数据库的连接器中枢，实现凭证隔离与安全调用。

核心模型包括 [[nodeskclaw-backend/app/models/connector/definition.py#ConnectorDefinition]]、[[nodeskclaw-backend/app/models/connector/instance.py#ConnectorInstance]]、[[nodeskclaw-backend/app/models/connector/tool.py#ConnectorTool]]、[[nodeskclaw-backend/app/models/connector/edge_node.py#EdgeNode]] 与 [[nodeskclaw-backend/app/models/connector/edge_artifact_on_demand_request.py#EdgeArtifactOnDemandRequest]]（管理边缘工件按需出站拉取与单次原子履约）；[[nodeskclaw-backend/app/models/connector/binding.py#SkillConnectorBinding]] 把已发布 SkillRelease 绑定到 Connector Instance，[[nodeskclaw-backend/app/models/connector/secret_ref.py#SecretRef]] 只保存密钥引用元数据，明文密钥不入库，经 Edge SecretStore 隔离管理。

