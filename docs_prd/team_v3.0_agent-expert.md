依据当前源码判断，`nodeskclaw` 已经有 `ComputeRegistry`，内置 `k8s/docker/process` 三类 provider，适合把专家服务接成一个新的 CE runtime，而不是另做后台。 现有部署请求也已经支持 `runtime`、`env_vars`、`advanced_config`、`template_id` 等字段，可承载 Hermes 专家部署参数。 `copilot-docker` 当前提供的是 Hermes WebUI + Hermes Agent in-process + Obsidian Vault + Hindsight external 的单容器专家实例套件。 下面 PRD 已按 **CE 产线** 和 **Hermes 私有仓库** 两个约束重写。

# PRD：team_v3.0_agent-expert

## 1. 版本信息

版本号：team_v3.0_agent-expert
产品范围：nodeskclaw CE
目标模块：Hermes Expert Runtime / Hermes WebUI Expert Asset Pack / Expert Skill Management
目标用户：nodeskclaw 管理员、开发团队、Agent 专家服务维护人员
核心目标：在 nodeskclaw 中集中管理、部署和维护 Hermes Agent 专家服务，并支持专家技能包管理。

---

## 2. 背景

当前团队已有两条能力线：

第一条是 nodeskclaw。它是 CE 化产线，用于集中管理 Agent 实例、运行时、部署记录、Docker/K8s compute provider、Portal 管理界面、实例生命周期。

第二条是 copilot-docker。它已经沉淀了一套 Hermes Agent 专家 Docker 部署脚本，用于部署 writer、finance 等专用 Hermes Agent WebUI 实例。该套件包含 Hermes WebUI、Hermes Agent runtime、专家 SOUL/MEMORY/USER 文件、skills、workspace、Obsidian Vault 目录、Hindsight external memory 配置。

当前问题是：Hermes 专家实例仍然依赖脚本部署，缺少 nodeskclaw 后台集中管理能力。后续需要在 nodeskclaw 中形成统一入口，完成专家服务创建、部署、启动、停止、重启、日志查看、WebUI 访问、专家模板注入、技能安装与管理。

---

## 3. 必须遵循的基础原则

### 3.1 CE 产线原则

本版本只服务 nodeskclaw CE，不设计、不实现、不预留 EE 功能点。

禁止纳入本版本范围的能力：

* 不做商业版授权校验。
* 不做付费模板市场。
* 不做企业版高级 RBAC。
* 不做跨企业租户隔离计费。
* 不做插件市场分发。
* 不做 SaaS 运营后台。
* 不做高级审计合规报表。
* 不做私有云多租户商业管控。
* 不做 EE License Feature Flag。

本版本只使用 nodeskclaw CE 已有的用户、组织、实例、运行时、部署记录、Docker compute provider、Portal 管理能力。

### 3.2 私有仓库原则

Hermes Agent 与 Hermes WebUI 均为私有 Git 仓库，不允许写死公开 GitHub 地址。

所有 Hermes 相关代码源、镜像源、构建参数必须通过环境变量、系统配置或后台配置维护。

必须支持以下配置项：

```text
HERMES_AGENT_REPO
HERMES_AGENT_REF
HERMES_WEBUI_REPO
HERMES_WEBUI_REF
HERMES_WEBUI_BASE_IMAGE
HERMES_EXPERT_IMAGE
PRIVATE_GIT_USERNAME
PRIVATE_GIT_TOKEN_SECRET
PRIVATE_REGISTRY_URL
PRIVATE_REGISTRY_USERNAME
PRIVATE_REGISTRY_PASSWORD_SECRET
```

默认值中不得出现公开 Hermes Agent GitHub 仓库地址。

### 3.3 控制面与数据面分离原则

nodeskclaw 是控制面，Hermes 专家容器是数据面。

nodeskclaw 负责：

* 专家实例元数据管理
* 专家模板管理
* 专家技能管理
* Docker Compose 生成
* 部署流程编排
* 端口分配
* 启停重启
* 健康检查
* 日志查看
* WebUI 地址展示
* 配置备份与恢复

Hermes 专家容器负责：

* Hermes WebUI 服务
* Hermes Agent runtime 执行
* SOUL/MEMORY/USER 加载
* skills 执行
* workspace 文件读写
* Obsidian Vault 文件读写
* Hindsight external memory 连接

---

## 4. 产品目标

### 4.1 核心目标

在 nodeskclaw 中新增 `hermes-webui-expert` runtime 资产包，使 nodeskclaw 可以集中部署和管理 Hermes Agent 专家服务。

### 4.2 业务目标

* 管理员可以在 Portal 中创建 writer、finance 等专家服务。
* 管理员可以选择专家模板并一键部署。
* 管理员可以查看专家服务状态、端口、WebUI 地址和日志。
* 管理员可以重启、停止、删除专家服务。
* 管理员可以为专家服务安装、更新、启用、禁用技能。
* 专家模板可以沉淀 SOUL、MEMORY、USER、skills、workspace、Obsidian Vault 初始化结构。
* 所有 Hermes Agent 与 Hermes WebUI 代码来源均支持私有 Git 仓库。

### 4.3 技术目标

* 不破坏现有 nodeskclaw runtime 体系。
* 不覆盖现有 `runtime=hermes`。
* 新增 `runtime=hermes-webui-expert`。
* 复用现有 `compute_provider=docker`。
* 复用现有 DeployRecord 与 SSE 部署进度。
* 复用现有 Instance 生命周期。
* 将 copilot-docker 的脚本逻辑产品化为 Python service。
* 后端不直接依赖手工执行 bash 脚本。
* 支持后续从 Docker Compose 演进到 K8s 部署，但本版本优先 Docker CE 场景。

---

## 5. 非目标

本版本不做以下内容：

* 不做 EE 版商业能力。
* 不做 Hermes Agent 核心代码改造。
* 不做 Hermes WebUI 大规模前端改造。
* 不做独立 Agent Marketplace。
* 不做跨节点调度器。
* 不做完整 DevOps CI/CD 平台。
* 不做多租户计费。
* 不做 Obsidian GUI 容器化。
* 不做 Hindsight 服务本身的部署管理。
* 不做 MCP 服务中心完整治理。
* 不做 K8s 生产编排增强。
* 不做专家自动训练闭环。

---

## 6. 术语定义

### 6.1 Hermes Expert Runtime

指 nodeskclaw 中新增的运行时类型：`hermes-webui-expert`。

它代表一个 All-in-One Hermes 专家容器，包含：

* Hermes WebUI
* Hermes Agent runtime
* 专家配置文件
* 专家技能目录
* workspace
* Obsidian Vault 目录
* Hindsight external memory 配置

### 6.2 Expert Template

专家模板。用于定义一个专家实例的初始能力边界。

模板内容包括：

```text
SOUL.md
memories/MEMORY.md
memories/USER.md
config.yaml
hindsight/config.json
skills/
workspace/AGENTS.md
obsidian-vault/
```

### 6.3 Expert Instance

专家实例。由某个 Expert Template 创建出来的运行中服务。

例如：

```text
writer 专家实例
finance 专家实例
purchase 专家实例
customer-service 专家实例
```

### 6.4 Expert Skill

专家技能。指放置在 Hermes 专家实例 `skills/` 目录下的可执行能力包。

技能包可以是：

```text
skills/<skill-name>/SKILL.md
skills/<skill-name>/scripts/
skills/<skill-name>/schemas/
skills/<skill-name>/examples/
```

---

## 7. 总体架构

```text
nodeskclaw Portal
  └─ AI 专家中心
      ├─ 专家实例管理
      ├─ 专家模板管理
      ├─ 专家技能管理
      ├─ 部署记录
      └─ 日志查看

nodeskclaw Backend
  ├─ RuntimeRegistry
  │   └─ hermes-webui-expert
  ├─ ComputeRegistry
  │   └─ docker
  ├─ HermesExpertService
  ├─ ExpertTemplateService
  ├─ ExpertSkillService
  ├─ HermesWebUIComposeBuilder
  └─ DeployRecord / SSE

Docker Host
  └─ hermes-<profile>
      ├─ Hermes WebUI :8787
      ├─ Hermes Agent runtime
      ├─ /data/hermes/config.yaml
      ├─ /data/hermes/SOUL.md
      ├─ /data/hermes/memories/
      ├─ /data/hermes/skills/
      ├─ /data/hermes/workspace/
      ├─ /data/hermes/obsidian-vault/
      ├─ /data/hermes/hindsight/
      └─ /data/hermes/webui/
```

---

## 8. Runtime 设计

### 8.1 新增 runtime id

```text
hermes-webui-expert
```

### 8.2 Runtime 定位

`hermes-webui-expert` 不是现有 `hermes` runtime 的替代品。

两者边界如下：

| Runtime             | 定位                               | 默认端口 | 是否带 WebUI | 用途              |
| ------------------- | -------------------------------- | ---: | --------- | --------------- |
| hermes              | Hermes Agent runtime             | 8642 | 否         | 纯 Agent Gateway |
| hermes-webui-expert | Hermes WebUI + Hermes Agent 专家容器 | 8787 | 是         | 专家服务后台管理        |

### 8.3 RuntimeSpec 要求

新增 RuntimeSpec：

```python
RuntimeSpec(
    runtime_id="hermes-webui-expert",
    display_name="Hermes 专家服务",
    display_description="Hermes WebUI + Hermes Agent + 专家模板 + 技能包",
    display_powered_by="Hermes Agent",
    gateway_port=8787,
    health_probe_path="/health",
    readiness_probe_path="/health",
    image_registry_key="image_registry_hermes_webui_expert",
    config_rel_path="config.yaml",
    config_format="yaml",
    channels_section_key="platforms",
    field_naming="snake_case",
    supports_channel_plugins=False,
    data_dir_container_path="/data/hermes",
    skills_dir_rel="skills",
    scripts_dir_rel="scripts",
    has_web_ui=True,
    has_init_script=False,
    available=True,
    backup_dirs=(
        "config.yaml",
        "SOUL.md",
        "memories",
        "hindsight",
        "skills",
        "workspace",
        "obsidian-vault",
        "sessions",
        "webui",
    ),
)
```

---

## 9. 资产包设计

### 9.1 资产包名称

```text
hermes-webui-expert-runtime-pack
```

### 9.2 目录结构

建议放在：

```text
nodeskclaw-backend/app/resources/hermes_webui_expert/
├── Dockerfile
├── docker-compose.template.yml
├── expert-templates/
│   ├── base/
│   │   ├── config.yaml
│   │   ├── SOUL.md
│   │   ├── memories/
│   │   │   ├── MEMORY.md
│   │   │   └── USER.md
│   │   ├── hindsight/
│   │   │   └── config.json
│   │   ├── workspace/
│   │   │   └── AGENTS.md
│   │   ├── obsidian-vault/
│   │   └── skills/
│   ├── writer/
│   └── finance/
└── skill-bundles/
    ├── default/
    ├── writer/
    └── finance/
```

### 9.3 私有 Git 构建要求

Dockerfile 不允许写死公开地址。

必须通过 build args 注入：

```dockerfile
ARG HERMES_WEBUI_BASE_IMAGE
ARG HERMES_AGENT_REPO
ARG HERMES_AGENT_REF
ARG HERMES_WEBUI_REPO
ARG HERMES_WEBUI_REF
```

后端生成构建参数时，从系统配置读取：

```text
settings.HERMES_AGENT_REPO
settings.HERMES_AGENT_REF
settings.HERMES_WEBUI_REPO
settings.HERMES_WEBUI_REF
settings.HERMES_WEBUI_BASE_IMAGE
```

私有 Git token 不写入 compose 文件明文，必须使用 Secret 或构建时临时注入。

---

## 10. 专家模板设计

### 10.1 内置模板

CE 版本内置三个模板：

```text
base
writer
finance
```

### 10.2 模板职责

#### base

基础 Hermes 专家模板，提供通用目录结构和默认行为边界。

#### writer

写作专家模板，面向文章创作、PRD、方案文档、报告、资料摘要。

#### finance

财务专家模板，面向财务分析、资金日报、账龄分析、订单回款状态、财务口径解释。

### 10.3 模板注入规则

注入流程：

```text
1. 检查模板存在
2. 创建实例数据目录
3. 备份已存在文件
4. 注入 base 模板
5. 注入专家模板
6. 替换占位符
7. 创建 workspace 目录
8. 创建 obsidian-vault 目录
9. 创建 skills 目录
10. 创建 sessions/logs/webui 目录
11. 写入注入记录
```

### 10.4 支持的占位符

```text
__PROFILE__
__EXPERT__
__INSTANCE_ID__
__INSTANCE_NAME__
__HINDSIGHT_API_URL__
__HINDSIGHT_BANK_ID__
__WORKSPACE_NAME__
__CREATED_AT__
```

---

## 11. 专家实例数据目录

每个实例独立目录：

```text
{DOCKER_HOST_DATA_DIR}/{instance_slug}/data/hermes/
├── .env
├── config.yaml
├── SOUL.md
├── memories/
│   ├── MEMORY.md
│   └── USER.md
├── hindsight/
│   └── config.json
├── skills/
├── workspace/
│   ├── AGENTS.md
│   ├── materials/
│   ├── references/
│   ├── drafts/
│   └── exports/
├── obsidian-vault/
│   ├── 00-Inbox/
│   ├── 10-Articles/
│   ├── 20-Research/
│   ├── 30-Templates/
│   ├── 40-Content-Calendar/
│   ├── 50-Policies/
│   ├── 60-Reports/
│   └── 90-Archive/
├── sessions/
├── logs/
└── webui/
```

---

## 12. Docker Compose 设计

### 12.1 服务名称

```text
hermes-webui
```

### 12.2 容器名称

```text
hermes-<profile>
```

### 12.3 Compose 生成规则

后端根据实例动态生成 compose，不再要求用户手工执行 `create-instance.sh`、`inject-expert.sh`、`up-instance.sh`。

### 12.4 Compose 样例

```yaml
services:
  hermes-webui:
    image: ${HERMES_EXPERT_IMAGE}
    container_name: hermes-${HERMES_PROFILE}
    restart: unless-stopped
    ports:
      - "${HERMES_WEBUI_BIND}:${HERMES_WEBUI_PORT}:8787"
    environment:
      HERMES_PROFILE: ${HERMES_PROFILE}
      HERMES_EXPERT: ${HERMES_EXPERT}
      HERMES_HOME: /data/hermes
      HERMES_CONFIG_PATH: /data/hermes/config.yaml
      HERMES_WEBUI_HOST: 0.0.0.0
      HERMES_WEBUI_PORT: 8787
      HERMES_WEBUI_STATE_DIR: /data/hermes/webui
      HERMES_WEBUI_DEFAULT_WORKSPACE: /data/hermes/workspace
      HERMES_WEBUI_AGENT_DIR: /opt/hermes-agent
      HERMES_WEBUI_AUTO_INSTALL: "1"
      HERMES_WEBUI_PASSWORD: ${HERMES_WEBUI_PASSWORD}
      HINDSIGHT_MODE: local_external
      HINDSIGHT_API_URL: ${HINDSIGHT_API_URL}
      HINDSIGHT_BANK_ID: ${HINDSIGHT_BANK_ID}
    volumes:
      - ${HOST_DATA_DIR}:/data/hermes
    shm_size: "1gb"
    healthcheck:
      test: ["CMD-SHELL", "curl -fsS http://127.0.0.1:8787/health || exit 1"]
      interval: 30s
      timeout: 5s
      retries: 5
      start_period: 60s
```

---

## 13. Hindsight 配置

### 13.1 本版本边界

本版本不部署 Hindsight 服务，只连接已有 Hindsight external API。

### 13.2 配置字段

```json
{
  "mode": "local_external",
  "api_url": "__HINDSIGHT_API_URL__",
  "bank_id": "__HINDSIGHT_BANK_ID__",
  "recall_budget": "mid",
  "recall_max_tokens": 4096,
  "auto_recall": true,
  "auto_retain": true,
  "retain_async": true,
  "retain_every_n_turns": 1,
  "memory_mode": "hybrid"
}
```

### 13.3 bank_id 规则

```text
hermes-<profile>
```

例如：

```text
hermes-writer
hermes-finance
```

---

## 14. 技能管理设计

### 14.1 管理对象

技能管理对象为 Hermes 专家实例下的 `skills/` 目录。

一个技能包结构：

```text
skills/<skill_slug>/
├── SKILL.md
├── README.md
├── scripts/
├── schemas/
├── examples/
└── manifest.json
```

### 14.2 技能 manifest

每个技能包建议包含：

```json
{
  "slug": "ic-datasheet-parser",
  "name": "IC Datasheet Parser",
  "version": "0.1.0",
  "description": "解析 IC 规格书并输出结构化摘要",
  "runtime": "hermes",
  "expert": ["writer", "finance"],
  "entry": "SKILL.md",
  "enabled": true,
  "requires_restart": false
}
```

### 14.3 技能来源

CE 版本支持三种来源：

```text
1. 内置 skill-bundles
2. 上传 zip 技能包
3. 从私有 Git 仓库拉取技能包
```

不支持公开市场。

### 14.4 技能操作

Portal 需要支持：

```text
查看技能列表
查看技能详情
安装技能
上传技能
启用技能
禁用技能
更新技能
删除技能
重新扫描技能目录
查看技能安装日志
```

### 14.5 技能状态

```text
installed
enabled
disabled
error
pending_restart
```

### 14.6 技能安装流程

```text
1. 校验实例存在
2. 校验实例 runtime=hermes-webui-expert
3. 校验技能包结构
4. 备份同名技能
5. 写入 skills/<skill_slug>
6. 写入 manifest.json
7. 更新 skill index
8. 如 requires_restart=true，提示重启实例
9. 记录操作结果
```

---

## 15. 后端服务设计

### 15.1 新增目录

```text
nodeskclaw-backend/app/services/hermes_expert/
├── __init__.py
├── expert_instance_service.py
├── expert_template_service.py
├── expert_skill_service.py
├── expert_compose_builder.py
├── expert_filesystem.py
├── expert_manifest.py
└── schemas.py
```

### 15.2 ExpertInstanceService

职责：

```text
创建专家实例
初始化实例目录
生成 WebUI 密码
生成 Hindsight bank_id
调用模板注入
生成 Docker Compose
触发部署流程
读取实例访问地址
读取实例运行状态
```

### 15.3 ExpertTemplateService

职责：

```text
列出内置模板
读取模板详情
注入模板
备份旧配置
替换模板占位符
生成 workspace/obsidian-vault 初始结构
```

### 15.4 ExpertSkillService

职责：

```text
列出实例技能
读取技能 manifest
安装技能
上传技能
启用技能
禁用技能
删除技能
扫描 skills 目录
生成技能索引
```

### 15.5 ExpertComposeBuilder

职责：

```text
根据 InstanceComputeConfig 生成 docker-compose.yml
写入 compose 文件
写入 .env 文件
处理私有镜像地址
处理端口映射
处理数据目录挂载
处理 healthcheck
```

---

## 16. API 设计

### 16.1 专家模板

```text
GET /api/hermes-experts/templates
GET /api/hermes-experts/templates/{template_slug}
```

返回字段：

```json
{
  "slug": "writer",
  "name": "写作专家",
  "description": "用于文章、PRD、方案、资料摘要",
  "version": "0.1.0",
  "files": [
    "SOUL.md",
    "memories/MEMORY.md",
    "skills/"
  ]
}
```

### 16.2 创建专家实例

```text
POST /api/hermes-experts/instances
```

请求：

```json
{
  "name": "writer",
  "profile": "writer",
  "expert_template": "writer",
  "cluster_id": "docker-local",
  "image_version": "latest",
  "webui_port": null,
  "hindsight_api_url": "http://hindsight.superic.com:8888",
  "env_vars": {},
  "llm_configs": []
}
```

返回：

```json
{
  "instance_id": "xxx",
  "deploy_id": "xxx",
  "profile": "writer",
  "webui_url": "http://localhost:8787",
  "status": "deploying"
}
```

### 16.3 专家实例列表

```text
GET /api/hermes-experts/instances
```

返回：

```json
[
  {
    "instance_id": "xxx",
    "name": "writer",
    "profile": "writer",
    "expert": "writer",
    "runtime": "hermes-webui-expert",
    "status": "running",
    "webui_url": "http://localhost:8787",
    "hindsight_bank_id": "hermes-writer",
    "created_at": "2026-06-07T00:00:00Z"
  }
]
```

### 16.4 实例操作

```text
POST /api/hermes-experts/instances/{instance_id}/restart
POST /api/hermes-experts/instances/{instance_id}/stop
POST /api/hermes-experts/instances/{instance_id}/start
DELETE /api/hermes-experts/instances/{instance_id}
GET /api/hermes-experts/instances/{instance_id}/logs
GET /api/hermes-experts/instances/{instance_id}/health
```

### 16.5 技能管理

```text
GET /api/hermes-experts/instances/{instance_id}/skills
GET /api/hermes-experts/instances/{instance_id}/skills/{skill_slug}
POST /api/hermes-experts/instances/{instance_id}/skills/install
POST /api/hermes-experts/instances/{instance_id}/skills/upload
POST /api/hermes-experts/instances/{instance_id}/skills/{skill_slug}/enable
POST /api/hermes-experts/instances/{instance_id}/skills/{skill_slug}/disable
DELETE /api/hermes-experts/instances/{instance_id}/skills/{skill_slug}
POST /api/hermes-experts/instances/{instance_id}/skills/rescan
```

---

## 17. Portal 页面设计

### 17.1 新增菜单

```text
AI 专家中心
├── 专家实例
├── 专家模板
├── 技能管理
└── 部署记录
```

### 17.2 专家实例列表

字段：

```text
实例名称
Profile
专家模板
Runtime
部署方式
状态
WebUI 地址
端口
Hindsight Bank
创建时间
操作
```

操作：

```text
打开 WebUI
查看日志
重启
停止
启动
管理技能
删除
```

### 17.3 创建专家实例页面

表单分区：

```text
基础信息
- 实例名称
- profile
- 专家模板

运行环境
- Docker Host / Cluster
- 镜像版本
- WebUI 端口：自动 / 手动

记忆配置
- Hindsight API URL
- Hindsight Bank ID：自动生成 / 手动

模型配置
- 主模型
- 抽取模型
- 压缩模型
- 本地模型

高级配置
- 环境变量
- 存储目录
- 是否初始化 Obsidian Vault
- 是否安装默认技能包
```

### 17.4 技能管理页面

功能：

```text
查看当前实例已安装技能
查看技能启用状态
安装内置技能包
上传 zip 技能包
从私有 Git 安装技能包
启用/禁用技能
删除技能
查看技能文件结构
查看 SKILL.md
```

---

## 18. 部署流程

### 18.1 创建流程

```text
1. 用户在 Portal 创建 Hermes 专家实例
2. Backend 校验 runtime 和 compute_provider
3. Backend 分配 profile、slug、端口、Hindsight bank_id
4. Backend 创建 Instance 记录
5. Backend 创建 DeployRecord
6. Backend 初始化实例数据目录
7. Backend 注入 base 模板
8. Backend 注入专家模板
9. Backend 安装默认技能包
10. Backend 生成 .env
11. Backend 生成 docker-compose.yml
12. DockerComputeProvider 执行 docker compose up -d
13. Backend 轮询 /health
14. Backend 更新 Instance.status=running
15. Backend 更新 DeployRecord.status=success
16. Portal 展示 WebUI 地址
```

### 18.2 部署进度步骤

```text
1. 环境预检查
2. 分配端口
3. 创建实例目录
4. 注入专家模板
5. 安装默认技能
6. 生成 Compose 配置
7. 启动容器
8. 等待 WebUI 就绪
9. 注册访问地址
10. 部署完成
```

---

## 19. 配置设计

### 19.1 后端 settings

新增：

```text
HERMES_EXPERT_DEFAULT_IMAGE
HERMES_AGENT_REPO
HERMES_AGENT_REF
HERMES_WEBUI_REPO
HERMES_WEBUI_REF
HERMES_WEBUI_BASE_IMAGE
HERMES_EXPERT_IMAGE_REGISTRY
HERMES_EXPERT_DEFAULT_HINDSIGHT_API_URL
HERMES_EXPERT_DEFAULT_BIND_HOST
HERMES_EXPERT_PORT_START
HERMES_EXPERT_PORT_END
HERMES_EXPERT_DATA_ROOT
```

### 19.2 默认端口池

```text
8787-8899
```

如与现有 Docker provider 端口池冲突，可以使用：

```text
16000-16999
```

最终端口池必须在 `.env` 可配置。

---

## 20. 数据模型设计

### 20.1 MVP 复用 Instance

本版本优先复用现有 Instance 表，不新增大规模表结构。

Instance 字段使用方式：

```text
runtime = hermes-webui-expert
compute_provider = docker
service_type = docker
ingress_domain = localhost:<port>
env_vars = Hermes 专家环境变量
advanced_config = Hermes 专家扩展配置
```

### 20.2 advanced_config 样例

```json
{
  "expert": {
    "profile": "writer",
    "template": "writer",
    "template_version": "0.1.0"
  },
  "webui": {
    "host": "0.0.0.0",
    "port": 8787,
    "container_port": 8787,
    "url": "http://localhost:8787"
  },
  "hindsight": {
    "mode": "local_external",
    "api_url": "http://hindsight.superic.com:8888",
    "bank_id": "hermes-writer"
  },
  "obsidian": {
    "enabled": true,
    "vault_path": "obsidian-vault"
  },
  "skills": {
    "default_bundle": "writer",
    "index_path": "skills/.index.json"
  },
  "compose": {
    "project_name": "hermes-writer",
    "compose_path": "/data/nodeskclaw/docker-instances/writer/docker-compose.yml"
  }
}
```

---

## 21. 安全要求

### 21.1 私有 Git 凭据

私有 Git token 不允许明文写入：

```text
docker-compose.yml
.env
config.yaml
日志
前端响应
```

必须通过 Secret 引用或后端加密存储处理。

### 21.2 WebUI 密码

每个实例必须自动生成独立 WebUI 密码。

密码只允许：

```text
创建成功时展示一次
实例详情中通过“重置密码”重新生成
后端加密保存或通过 Secret 保存
```

### 21.3 文件访问边界

Hermes 专家容器默认只挂载：

```text
/data/hermes
```

不得挂载宿主机根目录、用户 Home 目录、Docker socket。

### 21.4 Docker socket

CE MVP 可以由 backend 所在宿主机执行 Docker Compose。

但不得把 Docker socket 暴露给 Hermes 专家容器。

---

## 22. 验收标准

### 22.1 Runtime 验收

```text
1. Runtime 列表中出现 hermes-webui-expert。
2. 创建实例时可选择 Hermes 专家服务。
3. hermes-webui-expert 默认端口为 8787。
4. health_probe_path 为 /health。
5. has_web_ui=true。
```

### 22.2 专家实例验收

```text
1. 可以创建 writer 专家实例。
2. 可以创建 finance 专家实例。
3. 创建后自动生成实例数据目录。
4. 创建后自动注入 SOUL.md。
5. 创建后自动注入 MEMORY.md。
6. 创建后自动注入 hindsight/config.json。
7. 创建后自动生成 skills 目录。
8. 创建后自动生成 obsidian-vault 目录。
9. Docker 容器正常启动。
10. Portal 显示 WebUI 地址。
11. WebUI 可以打开并要求密码。
12. Instance.status=running。
13. DeployRecord.status=success。
```

### 22.3 技能管理验收

```text
1. 可以查看实例 skills 列表。
2. 可以安装内置技能包。
3. 可以上传 zip 技能包。
4. 可以启用技能。
5. 可以禁用技能。
6. 可以删除技能。
7. 可以重新扫描技能目录。
8. 技能 manifest 解析失败时有明确错误提示。
9. 禁用技能后 manifest.enabled=false。
10. 需要重启的技能安装后显示 pending_restart。
```

### 22.4 私有仓库验收

```text
1. Dockerfile 不出现公开 Hermes Agent GitHub 地址。
2. Dockerfile 不出现公开 Hermes WebUI GitHub 地址。
3. 构建时从 HERMES_AGENT_REPO 读取私有仓库。
4. 构建时从 HERMES_WEBUI_REPO 读取私有仓库。
5. Git token 不出现在 compose 文件中。
6. Git token 不出现在部署日志中。
```

---

## 23. Cursor 实施任务

### Task 1：新增 runtime

文件：

```text
nodeskclaw-backend/app/services/runtime/registries/runtime_registry.py
```

任务：

```text
新增 hermes-webui-expert RuntimeSpec
确保 runtime 列表可返回该 runtime
确保前端可选择该 runtime
```

### Task 2：新增 Hermes Expert 资源包

文件：

```text
nodeskclaw-backend/app/resources/hermes_webui_expert/
```

任务：

```text
迁移 base/writer/finance 模板
迁移默认 skill-bundles
新增 docker-compose.template.yml
新增私有 Git Dockerfile 模板
```

### Task 3：实现 ExpertTemplateService

文件：

```text
nodeskclaw-backend/app/services/hermes_expert/expert_template_service.py
```

任务：

```text
实现 list_templates
实现 get_template
实现 inject_template
实现 backup_existing_files
实现 render_placeholders
实现 ensure_default_layout
```

### Task 4：实现 ExpertSkillService

文件：

```text
nodeskclaw-backend/app/services/hermes_expert/expert_skill_service.py
```

任务：

```text
实现 list_skills
实现 install_builtin_bundle
实现 upload_skill_zip
实现 enable_skill
实现 disable_skill
实现 delete_skill
实现 rescan_skills
实现 read_skill_manifest
```

### Task 5：实现 Compose Builder

文件：

```text
nodeskclaw-backend/app/services/hermes_expert/expert_compose_builder.py
```

任务：

```text
根据实例生成 docker-compose.yml
生成 .env
写入 WebUI 端口
写入 Hindsight 配置
写入容器环境变量
写入数据目录挂载
```

### Task 6：扩展 DockerComputeProvider

文件：

```text
nodeskclaw-backend/app/services/runtime/compute/docker_provider.py
```

任务：

```text
当 config.runtime=hermes-webui-expert 时，走 ExpertComposeBuilder
保留现有 openclaw/hermes docker 部署逻辑
返回 endpoint=http://host:<port>
写入 compose_path
支持 logs/restart/stop/delete
```

### Task 7：新增 API Router

文件：

```text
nodeskclaw-backend/app/api/hermes_experts.py
```

任务：

```text
实现专家模板 API
实现专家实例 API
实现专家技能 API
接入权限校验
接入 DeployRecord
接入 SSE 部署进度
```

### Task 8：Portal 新增 AI 专家中心

文件：

```text
nodeskclaw-portal/src/pages/expert-center/
```

任务：

```text
新增专家实例列表页
新增创建专家实例页
新增专家详情页
新增技能管理页
新增日志抽屉
新增 WebUI 打开入口
```

---

## 24. 交付范围

本版本交付：

```text
1. hermes-webui-expert runtime
2. Hermes Expert Runtime Pack
3. base/writer/finance 专家模板
4. 默认技能包管理
5. Docker Compose 部署
6. 专家实例生命周期管理
7. 专家技能管理
8. Portal AI 专家中心
9. 私有 Git 仓库配置支持
10. 部署进度与日志查看
```

---

## 25. 里程碑

### M1：后端 Runtime 与模板注入

完成：

```text
hermes-webui-expert RuntimeSpec
ExpertTemplateService
实例目录初始化
模板注入
```

### M2：Docker 部署打通

完成：

```text
Compose Builder
DockerComputeProvider 适配
writer/finance 容器启动
健康检查
DeployRecord 成功
```

### M3：Portal 管理页面

完成：

```text
专家实例列表
创建专家实例
WebUI 入口
日志查看
启停重启
```

### M4：技能管理

完成：

```text
技能列表
安装内置技能
上传技能
启用/禁用
删除
重新扫描
```

---

## 26. 最终验收结论

当以下结果全部达成时，`team_v3.0_agent-expert` 视为完成：

```text
1. nodeskclaw CE 可以创建 hermes-webui-expert 实例。
2. writer 和 finance 专家可以从 Portal 一键部署。
3. Hermes Agent 与 Hermes WebUI 均来自私有 Git/私有镜像配置。
4. WebUI 可通过 Portal 打开。
5. Hindsight bank_id 按实例隔离。
6. 每个专家实例拥有独立 workspace、skills、memories、obsidian-vault。
7. Portal 可以管理专家技能。
8. 所有部署记录进入 nodeskclaw DeployRecord。
9. 部署进度通过现有 SSE 展示。
10. 不包含任何 EE 功能设计。
```
