# PRD v5.0：nodeskclaw Hermes Insight 运行统计能力（裁剪版）

## 1. 文档信息

**文档名称**：nodeskclaw Hermes Insight 运行统计能力 PRD
**版本**：v5.0
**版本类型**：功能裁剪版
**适用模块**：nodeskclaw-backend / hermes 模块、nodeskclaw 前端 `/hermes/agents/:instanceId` 页面
**目标页面**：Hermes Agent 详情页 →【运行状态】
**核心目标**：在 nodeskclaw 中实现 Hermes Agent 使用统计与运行状态查看能力，并适配一个 Hermes Docker 实例内多个独立 profiles 的部署模式。
**统计口径**：Hermes Instance + Hermes Profile 双层统计。
**默认统计周期**：最近 30 天，前端不提供时间范围切换。
**数据来源**：每个 profile 独立 `HERMES_HOME` 下的 `state.db`、`webui/sessions/_index.json`、`config.yaml`、Docker runtime 状态。
**重要结论**：Insight 统计不通过 Hermes API Server 8642 获取；API Server 只作为 agent 调用入口，不作为统计数据源。

---

## 2. 本版裁剪范围

相对上一版 v5.0 完整方案，本版删除以下功能：

```text id="wwu6tg"
1. 删除 LLM Wiki 状态统计
2. 删除时间范围过滤，固定统计最近 30 天
3. 删除按时活动统计，包括 activityByHour / activityByDay
```

本版保留以下核心能力：

```text id="2y1y27"
1. Container Runtime
2. Profile Runtime
3. Profile Selector
4. 最近 30 天 usage 统计
5. Instance all profiles 汇总统计
6. Sessions / Messages / Tokens / Cost
7. Daily Token Trend，固定最近 30 天
8. Model Usage
9. Profile Usage
10. Token Breakdown
11. 基础降级与安全保护
```

---

## 3. 背景

当前 nodeskclaw 的 Hermes Agent 页面已经具备 Docker 容器级运行状态查看能力，可以展示：

```text id="se2vk2"
Docker 状态
Health 状态
端口
最后探活
启动 / 停止 / 重启操作
```

但目前缺少 Hermes Agent 使用统计能力，无法直接看到：

```text id="vm3xae"
每个 profile 近 30 天使用了多少 sessions
产生了多少 messages
消耗了多少 input/output tokens
大概产生了多少 estimated cost
主要使用了哪些模型
不同 profile 的使用量差异
```

经过验证，当前 Hermes Agent 容器中每个 profile 已经具备独立 profile home。因此本方案以 profile 独立 `HERMES_HOME` 作为统计边界，再在 nodeskclaw 中做 instance 级汇总。

---

## 4. 目标

## 4.1 产品目标

在 nodeskclaw 的 Hermes Agent 详情页【运行状态】中新增 Insight 区块，实现：

```text id="z93109"
1. 支持按 profile 查看最近 30 天统计。
2. 支持查看整个 Hermes instance 下所有 profiles 的汇总统计。
3. 支持展示 Docker container 运行状态。
4. 支持展示 profile runtime 状态。
5. 支持展示 sessions / messages / tokens / cost。
6. 支持展示最近 30 天每日 token 趋势。
7. 支持展示 model usage。
8. 支持展示 profile usage 对比。
9. 支持展示 token breakdown。
10. 支持 state.db 缺失、profile 未运行、Docker stats 不可用等场景的安全降级。
11. 不依赖 hermes-webui 服务是否启动。
12. 不依赖 Hermes API Server 8642 获取统计数据。
```

## 4.2 工程目标

```text id="fqaa2m"
1. 在 nodeskclaw-backend Hermes 模块新增 insight 子模块。
2. 建立 HermesProfileResolver，统一解析 profile 的 host/container 路径。
3. 建立 HermesInsightCollector，按 profile 读取 state.db 与 _index.json。
4. 建立 instance-level aggregate 统计。
5. 所有统计读取必须只读、可降级、不可泄漏密钥。
6. API 输出结构稳定，可供前端长期使用。
7. 前端 Insight UI 与现有 nodeskclaw 页面风格一致。
```

---

## 5. 非目标

本版本不做以下事情：

```text id="v2besr"
1. 不通过 Hermes API Server 8642 获取 Insight 统计。
2. 不调用 LLM。
3. 不触发 Hermes Agent 对话。
4. 不修改 Hermes Agent 源码。
5. 不修改 profile 的 config.yaml、.env、state.db。
6. 不重算历史消息 token。
7. 不扫描完整 session message 内容。
8. 不做 LLM Wiki 状态统计。
9. 不做时间范围选择。
10. 不做 activityByHour / activityByDay。
11. 不展示 .env 中的 API key。
12. 不替代 hermes-webui。
13. 不做多租户权限系统重构。
14. 不做真实账单对账，只展示 Hermes 已记录的 estimated cost。
15. 不在 v5.0 实现 Skill Usage，预留后续扩展。
```

---

## 6. 核心概念定义

## 6.1 Hermes Instance

一个 nodeskclaw 管理的 Hermes Docker 实例，例如：

```text id="q5c24g"
common-writer
finance
researcher
coding-agent
```

典型宿主机目录：

```text id="f34qzj"
/data/copilot-docker/instances/common-writer
```

一个 Hermes Instance 通常对应一个 Docker container。

## 6.2 Hermes Profile

一个 Hermes Instance 内部的独立 agent profile，例如：

```text id="ne499v"
default
writer-zh
researcher
finance
```

每个 profile 有独立 `HERMES_HOME`，并拥有自己的：

```text id="m2z20c"
state.db
config.yaml
.env
webui/sessions/_index.json
memory
sessions
gateway pid
logs
```

## 6.3 Profile Insight

单个 profile 的最近 30 天统计信息。

## 6.4 Instance Insight

一个 Hermes Instance 下所有 profiles 的最近 30 天汇总统计。

## 6.5 Container Runtime

Docker container 级运行状态，例如：

```text id="efnrxf"
running
healthy
cpu
memory
disk
ports
lastProbeAt
```

## 6.6 Profile Runtime

profile 级运行状态，例如：

```text id="q595iy"
profileName
apiServerEnabled
apiServerPort
gatewayPid
stateDbExists
lastStateWriteAt
lastSessionAt
```

---

## 7. 总体方案

## 7.1 统计层级

nodeskclaw 需要支持三层数据：

```text id="m6nu2c"
Container Runtime
  common-writer 容器状态、CPU、RAM、Disk、端口、最后探活

Profile Insight
  default / writer-zh / researcher / finance 各自独立统计

Instance Aggregate
  common-writer 下全部 profiles 汇总统计
```

## 7.2 页面入口

现有页面：

```text id="rozk9v"
/hermes/agents/:instanceId
```

在【运行状态】tab 内增加：

```text id="av40fd"
Profile Selector:
  全部 profiles
  default
  writer-zh
  researcher
  finance

Refresh Button:
  刷新状态
```

默认：

```text id="t0e8fx"
profile=all
periodDays=30
```

前端不提供 days selector。

## 7.3 统计数据流

```text id="u6xi8u"
前端运行状态页
  ↓
GET /api/hermes/instances/:instanceId/insight?profile=all
  ↓
HermesInsightController
  ↓
HermesProfileResolver
  ↓
HermesInsightService
  ├─ ContainerHealthCollector
  ├─ ProfileRuntimeCollector
  ├─ UsageCollector
  └─ WebUISessionIndexCollector
  ↓
InsightResponse
```

---

## 8. Profile Home 解析方案

## 8.1 解析原则

不要在 Insight Collector 中硬编码 profile 路径。

必须通过统一 resolver 得到：

```text id="dgs7tt"
instanceRoot
containerName
profileName
hostHermesHome
containerHermesHome
stateDbPath
configPath
envPath
webuiIndexPath
```

## 8.2 推荐落地文件

新增或复用：

```text id="j5acqj"
/data/copilot-docker/instances/common-writer/profiles.manifest.json
```

结构：

```json id="i3g59v"
{
  "instanceId": "common-writer",
  "containerName": "hermes-common-writer",
  "instanceRoot": "/data/copilot-docker/instances/common-writer",
  "profiles": [
    {
      "name": "default",
      "containerHermesHome": "/home/hermes/.hermes/profiles/default",
      "hostHermesHome": "/data/copilot-docker/instances/common-writer/data/hermes/profiles/default",
      "apiServerEnabled": true,
      "apiServerPort": 8642,
      "webuiPort": 8787
    },
    {
      "name": "writer-zh",
      "containerHermesHome": "/home/hermes/.hermes/profiles/writer-zh",
      "hostHermesHome": "/data/copilot-docker/instances/common-writer/data/hermes/profiles/writer-zh",
      "apiServerEnabled": true,
      "apiServerPort": 8643,
      "webuiPort": 8788
    }
  ]
}
```

## 8.3 Resolver 优先级

`HermesProfileResolver` 按以下顺序解析：

```text id="c4zz8p"
P0: nodeskclaw 数据库中已登记的 profile manifest
P1: instanceRoot/profiles.manifest.json
P2: docker exec hermes profile list / hermes profile show <profile>
P3: 扫描 instanceRoot/data/hermes/profiles/*
P4: fallback 到 instanceRoot/data/hermes 作为 default profile
```

## 8.4 路径安全规则

```text id="khfsix"
1. 前端不得传入任何路径。
2. 后端只接受 instanceId 与 profileName。
3. instanceId 必须来自 nodeskclaw 已登记 Hermes 实例。
4. profileName 必须来自 manifest 或 resolver。
5. 所有 host 路径必须落在 instanceRoot 允许范围内。
6. 禁止 ../ path traversal。
7. 禁止符号链接逃逸。
8. SQLite 只读打开。
9. .env 不参与本版统计读取，不返回任何 .env 内容。
```

---

## 9. 后端模块设计

## 9.1 目录建议

TypeScript / Nest 风格：

```text id="qaay0d"
src/modules/hermes/
  hermes.module.ts
  instances/
  profiles/
  insight/
    hermes-insight.controller.ts
    hermes-insight.service.ts
    hermes-insight.types.ts
    hermes-profile-resolver.ts
    collectors/
      container-health.collector.ts
      profile-runtime.collector.ts
      usage.collector.ts
      webui-index.collector.ts
    utils/
      sqlite-readonly.ts
      safe-path.ts
      yaml-safe-reader.ts
```

Python / FastAPI 风格：

```text id="rqgtd7"
nodeskclaw_backend/modules/hermes/
  insight/
    router.py
    service.py
    schemas.py
    profile_resolver.py
    collectors/
      container_health.py
      profile_runtime.py
      usage.py
      webui_index.py
    utils/
      sqlite_readonly.py
      safe_path.py
      yaml_safe_reader.py
```

## 9.2 核心服务

```text id="q3qg9t"
HermesInsightService
  getInstanceInsight(instanceId, profile)
  getProfiles(instanceId)
  getProfileInsight(instanceId, profileName)
  aggregateProfileInsights(profileInsights)
```

```text id="yyp50h"
HermesProfileResolver
  resolveInstance(instanceId)
  resolveProfiles(instanceId)
  resolveProfile(instanceId, profileName)
  mapContainerPathToHostPath(instanceId, containerPath)
  validateProfileHome(profileHome)
```

```text id="dxry4n"
HermesUsageCollector
  collectFromStateDb(profileHome)
  collectFromWebUIIndex(profileHome)
  mergeUsageRecords(records)
  aggregate(records)
```

```text id="ji4mu7"
HermesContainerHealthCollector
  collectDockerStatus(instance)
  collectDockerStats(instance)
  collectDiskUsage(instanceRoot)
```

```text id="lnl0xv"
HermesProfileRuntimeCollector
  collectProfileRuntime(profile)
  checkApiServerPort(profile)
  checkGatewayPid(profile)
  checkStateDbMtime(profile)
```

---

## 10. API 设计

## 10.1 获取 instance profiles

```http id="wbwqxy"
GET /api/hermes/instances/:instanceId/profiles
```

返回：

```json id="bd8jh6"
{
  "instanceId": "common-writer",
  "containerName": "hermes-common-writer",
  "profiles": [
    {
      "profileName": "default",
      "status": "running",
      "apiServerEnabled": true,
      "apiServerPort": 8642,
      "webuiPort": 8787,
      "stateDbExists": true,
      "configExists": true,
      "webuiIndexExists": true,
      "lastStateWriteAt": "2026-06-17T07:31:20Z"
    },
    {
      "profileName": "writer-zh",
      "status": "idle",
      "apiServerEnabled": true,
      "apiServerPort": 8643,
      "webuiPort": 8788,
      "stateDbExists": true,
      "configExists": true,
      "webuiIndexExists": true,
      "lastStateWriteAt": "2026-06-17T07:33:41Z"
    }
  ]
}
```

## 10.2 获取 Insight

```http id="g8l6nn"
GET /api/hermes/instances/:instanceId/insight?profile=all
```

参数：

```text id="fopxbg"
profile:
  all
  default
  writer-zh
  researcher
  finance
```

说明：

```text id="lz3z41"
1. 不提供 days 参数。
2. 后端固定统计最近 30 天。
3. 响应中返回 periodDays=30。
4. 如果前端传入 days 参数，后端忽略或返回参数不支持错误，建议忽略并记录 warning。
```

返回：

```json id="i9gkay"
{
  "scope": "instance",
  "instanceId": "common-writer",
  "profileName": "all",
  "periodDays": 30,
  "generatedAt": "2026-06-17T07:40:00Z",
  "container": {
    "containerName": "hermes-common-writer",
    "dockerStatus": "running",
    "health": "healthy",
    "cpuPercent": 18.2,
    "memoryUsedBytes": 4294967296,
    "memoryLimitBytes": 17179869184,
    "memoryPercent": 25,
    "diskUsedBytes": 91268055040,
    "diskTotalBytes": 214748364800,
    "diskPercent": 42.5,
    "lastProbeAt": "2026-06-17T07:39:55Z"
  },
  "profiles": [
    {
      "profileName": "default",
      "runtime": {
        "status": "running",
        "apiServerEnabled": true,
        "apiServerPort": 8642,
        "webuiPort": 8787,
        "stateDbExists": true,
        "configExists": true,
        "webuiIndexExists": true,
        "lastStateWriteAt": "2026-06-17T07:31:20Z",
        "lastSessionAt": "2026-06-17T07:20:10Z"
      },
      "usage": {
        "totalSessions": 12,
        "totalMessages": 642,
        "totalInputTokens": 2200000,
        "totalOutputTokens": 780000,
        "totalTokens": 2980000,
        "totalCost": 0.22
      }
    }
  ],
  "usage": {
    "totalSessions": 98,
    "totalMessages": 5133,
    "totalInputTokens": 65100000,
    "totalOutputTokens": 35400000,
    "totalTokens": 100500000,
    "totalCost": 1.29
  },
  "dailyTokens": [
    {
      "date": "2026-06-17",
      "profileName": "all",
      "sessions": 7,
      "messages": 355,
      "inputTokens": 1200000,
      "outputTokens": 480000,
      "totalTokens": 1680000,
      "cost": 0.07
    }
  ],
  "models": [
    {
      "profileName": "writer-zh",
      "model": "doubao/seed-2-0-pro",
      "sessions": 18,
      "messages": 1330,
      "inputTokens": 9200000,
      "outputTokens": 3100000,
      "totalTokens": 12300000,
      "cost": 0.42,
      "sessionShare": 18.3,
      "tokenShare": 35.2,
      "costShare": 40.1
    }
  ],
  "tokenBreakdown": {
    "inputTokens": 65100000,
    "outputTokens": 35400000,
    "cacheReadTokens": 0,
    "cacheWriteTokens": 0
  },
  "warnings": []
}
```

## 10.3 单 profile 返回

```http id="bdx2uw"
GET /api/hermes/instances/common-writer/insight?profile=writer-zh
```

返回：

```json id="y41rbj"
{
  "scope": "profile",
  "instanceId": "common-writer",
  "profileName": "writer-zh",
  "periodDays": 30,
  "generatedAt": "2026-06-17T07:40:00Z",
  "container": {
    "containerName": "hermes-common-writer",
    "dockerStatus": "running",
    "health": "healthy"
  },
  "profile": {
    "profileName": "writer-zh",
    "runtime": {
      "status": "running",
      "apiServerEnabled": true,
      "apiServerPort": 8643,
      "webuiPort": 8788,
      "stateDbExists": true,
      "configExists": true,
      "webuiIndexExists": true,
      "lastStateWriteAt": "2026-06-17T07:31:20Z",
      "lastSessionAt": "2026-06-17T07:20:10Z"
    }
  },
  "usage": {
    "totalSessions": 30,
    "totalMessages": 1220,
    "totalInputTokens": 9000000,
    "totalOutputTokens": 3100000,
    "totalTokens": 12100000,
    "totalCost": 0.41
  },
  "dailyTokens": [],
  "models": [],
  "tokenBreakdown": {
    "inputTokens": 9000000,
    "outputTokens": 3100000,
    "cacheReadTokens": 0,
    "cacheWriteTokens": 0
  },
  "warnings": []
}
```

## 10.4 错误返回

instance 不存在：

```json id="tj947i"
{
  "error": {
    "code": "HERMES_INSTANCE_NOT_FOUND",
    "message": "Hermes instance not found: common-writer"
  }
}
```

profile 不存在：

```json id="cv8ve3"
{
  "error": {
    "code": "HERMES_PROFILE_NOT_FOUND",
    "message": "Profile not found in instance common-writer: writer-zh"
  }
}
```

state.db 缺失时不返回 500，而是：

```json id="cncxkj"
{
  "profileName": "writer-zh",
  "usage": {
    "totalSessions": 0,
    "totalMessages": 0,
    "totalInputTokens": 0,
    "totalOutputTokens": 0,
    "totalTokens": 0,
    "totalCost": 0
  },
  "warnings": [
    {
      "code": "STATE_DB_NOT_FOUND",
      "message": "state.db not found for profile writer-zh"
    }
  ]
}
```

---

## 11. Usage 统计规则

## 11.1 固定统计窗口

本版本固定统计最近 30 天。

后端常量：

```text id="vry3y8"
INSIGHT_WINDOW_DAYS = 30
```

cutoff 计算：

```text id="pbo73e"
cutoff = now - 30 days
```

前端不展示时间范围选择器。

## 11.2 数据来源优先级

单 profile 的 usage collector 按以下顺序读取：

```text id="yrilss"
P0: {profileHome}/state.db
P1: {profileHome}/webui/sessions/_index.json
P2: 无数据时返回空统计，不报错
```

`state.db` 是主数据源。`_index.json` 是补充数据源。

## 11.3 SQLite 查询

只读打开：

```text id="wcszh1"
file:/path/to/state.db?mode=ro
```

查询前需要检查：

```text id="hf37e2"
sessions 表是否存在
字段是否存在
字段类型是否可解析
```

推荐字段：

```text id="xa2j6g"
id
model
message_count
input_tokens
output_tokens
cache_read_tokens
cache_write_tokens
estimated_cost_usd
started_at
ended_at
source
platform
```

如果某些字段不存在，collector 自动降级。

推荐 SQL：

```sql id="vichzm"
SELECT
  id,
  model,
  message_count,
  input_tokens,
  output_tokens,
  cache_read_tokens,
  cache_write_tokens,
  estimated_cost_usd,
  started_at,
  ended_at,
  source,
  platform
FROM sessions
WHERE
  started_at >= :cutoff
  OR ended_at >= :cutoff;
```

## 11.4 WebUI Index 补充

读取：

```text id="zl6ts1"
{profileHome}/webui/sessions/_index.json
```

可用字段：

```text id="amcax1"
session_id
model
message_count
created_at
updated_at
input_tokens
output_tokens
cache_read_tokens
cache_write_tokens
estimated_cost
```

如果 `_index.json` 缺失，返回 warning，不影响主统计。

## 11.5 去重规则

必须带 profile，避免不同 profile 的 session id 冲突：

```text id="xuoy72"
dedupeKey = instanceId + ":" + profileName + ":" + source + ":" + sessionId
```

如果 `state.db` 与 `_index.json` 中存在同一个 session：

```text id="rw58h7"
优先保留 state.db
_index.json 只补充 state.db 不存在的记录
```

## 11.6 汇总规则

单 profile：

```text id="vlpz4e"
totalSessions      = session count
totalMessages      = sum(message_count)
totalInputTokens   = sum(input_tokens)
totalOutputTokens  = sum(output_tokens)
totalTokens        = totalInputTokens + totalOutputTokens
totalCost          = sum(estimated_cost_usd)
```

instance aggregate：

```text id="u23klh"
totalSessions      = sum(profile.totalSessions)
totalMessages      = sum(profile.totalMessages)
totalInputTokens   = sum(profile.totalInputTokens)
totalOutputTokens  = sum(profile.totalOutputTokens)
totalTokens        = totalInputTokens + totalOutputTokens
totalCost          = sum(profile.totalCost)
```

daily tokens：

```text id="u83rlu"
固定最近 30 天
group by date
sum sessions
sum messages
sum inputTokens
sum outputTokens
sum totalTokens
sum cost
```

models：

```text id="s7scap"
group by profileName + model
sum sessions
sum messages
sum inputTokens
sum outputTokens
sum cost
calculate sessionShare / tokenShare / costShare
```

---

## 12. Container 与 Profile Runtime 规则

## 12.1 Container Runtime

container runtime 来自 Docker：

```text id="f9qxeb"
docker inspect
docker stats --no-stream
port bindings
healthcheck
```

展示字段：

```text id="jhz9cz"
Docker Status
Health
CPU
Memory
Disk
Ports
Last Probe
```

container runtime 是 instance 级状态。

## 12.2 Profile Runtime

profile runtime 是 profile 级状态，不等同于 container running。

判断优先级：

```text id="l23n9p"
P0: profile API Server 端口是否监听
P1: profile gateway PID 是否存在
P2: state.db 是否存在
P3: state.db 最近写入时间
P4: webui/sessions/_index.json 是否存在
P5: config.yaml 是否存在
```

状态枚举：

```text id="m773ob"
running
idle
configured
missing
error
unknown
```

建议判定：

```text id="go6fdl"
running:
  api server 端口监听，或 gateway pid 存活

idle:
  profile home 存在，state.db 存在，但当前无 API Server / gateway

configured:
  profile home 与 config.yaml 存在，但无 state.db

missing:
  manifest 有 profile，但 profile home 不存在

error:
  读取 profile home / config / db 报错

unknown:
  信息不足
```

---

## 13. 前端页面设计

## 13.1 页面位置

```text id="xdu8cc"
/hermes/agents/:instanceId
  Tab: 运行状态
```

在现有 Docker runtime 状态下新增 Insight 区域。

## 13.2 页面结构

```text id="ra2lh5"
运行状态
  ├─ Container Runtime
  │   ├─ Docker running
  │   ├─ Health healthy
  │   ├─ CPU / RAM / Disk
  │   └─ Last Probe

  ├─ Profile Runtime
  │   ├─ Profile selector
  │   ├─ default status
  │   ├─ writer-zh status
  │   └─ researcher status

  ├─ Insight Controls
  │   ├─ Profile: all / default / writer-zh / researcher
  │   ├─ Period: 固定最近 30 天
  │   └─ Refresh

  ├─ Overview Cards
  │   ├─ Sessions
  │   ├─ Messages
  │   ├─ Tokens
  │   └─ Estimated Cost

  ├─ Charts
  │   ├─ Daily Token Trend
  │   └─ Token Breakdown

  └─ Tables
      ├─ Model Usage
      └─ Profile Usage
```

## 13.3 删除的页面元素

本版本前端不得出现：

```text id="sbyqmy"
1. LLM Wiki 卡片
2. Time Range Selector
3. Activity by Day
4. Activity by Hour
5. Skill Usage 卡片
```

## 13.4 UI 风格

按 nodeskclaw 现有暗色后台风格：

```text id="gqwuxz"
深色背景
圆角卡片
轻边框
状态 pill
小型图表
表格密度适中
不引入过重图表库
```

图表第一版建议使用 CSS bar chart，不强依赖 ECharts / Chart.js。

## 13.5 前端组件建议

```text id="e1985i"
HermesRunStatusPage
  ├─ ContainerRuntimeCard
  ├─ ProfileRuntimeGrid
  ├─ HermesInsightPanel
      ├─ InsightToolbar
      ├─ InsightOverviewCards
      ├─ DailyTokensChart
      ├─ TokenBreakdownCard
      ├─ ModelUsageTable
      └─ ProfileUsageTable
```

## 13.6 Hook 建议

```text id="vx9k3p"
useHermesProfiles(instanceId)
useHermesInsight(instanceId, profile)
useHermesRuntime(instanceId)
```

`useHermesInsight` 需要支持：

```text id="d7cb6f"
loading
error
data
refetch
isStale
```

---

## 14. 缓存与刷新

## 14.1 后端缓存

Insight 统计可以短缓存：

```text id="ltd1qu"
profile insight cache TTL: 15 秒
container stats cache TTL: 5 秒
profiles cache TTL: 30 秒
```

手动刷新时支持 bypass cache：

```http id="k3bu1a"
GET /api/hermes/instances/common-writer/insight?profile=all&refresh=true
```

## 14.2 前端刷新

页面提供：

```text id="f6cdd6"
刷新状态
```

点击后同时刷新：

```text id="koj5rv"
container runtime
profile runtime
insight
```

自动刷新建议：

```text id="u8a5ut"
运行状态 tab 激活时，每 30 秒刷新一次 runtime
Insight 不自动频繁刷新，除非用户点击刷新
```

---

## 15. 安全要求

## 15.1 路径安全

```text id="c6hdsx"
1. 禁止前端传入文件路径。
2. 后端根据 instance/profile resolver 得到路径。
3. 所有路径必须验证在 instance allowlist 内。
4. 禁止符号链接逃逸。
5. 禁止 ../。
6. 禁止读取非 profile home 下的任意文件。
```

## 15.2 数据安全

```text id="n0rgqi"
1. 不返回 .env 内容。
2. 不返回 API key。
3. 不返回 API_SERVER_KEY。
4. 不返回模型供应商 key。
5. 不返回 session 完整 message 内容。
6. 不返回用户附件内容。
7. 不返回 terminal 输出详情。
8. 不返回本地绝对路径给普通前端用户；如需展示路径，只展示 masked path。
```

## 15.3 SQLite 安全

```text id="sf0o3r"
1. 只读模式打开。
2. 查询参数化。
3. 不执行写 SQL。
4. 不执行 PRAGMA 修改。
5. 单次查询超时限制。
6. 大库限制返回行数。
7. 异常降级，不阻塞页面。
```

---

## 16. 降级策略

## 16.1 state.db 缺失

展示：

```text id="gss1xl"
No usage data
```

返回 warning：

```text id="i6f6wb"
STATE_DB_NOT_FOUND
```

## 16.2 _index.json 缺失

不影响主统计。

返回 warning：

```text id="m0hzgf"
WEBUI_INDEX_NOT_FOUND
```

## 16.3 config.yaml 缺失

profile runtime 显示：

```text id="pjyybr"
configured=false
```

## 16.4 Docker stats 不可用

Container Runtime 显示：

```text id="g5isw1"
Docker stats unavailable
```

Usage 统计仍可展示。

## 16.5 profile home 缺失

Profile Runtime 显示：

```text id="jegmds"
missing
```

该 profile usage 归零。

## 16.6 SQLite schema 不兼容

返回 warning：

```text id="oj5e06"
STATE_DB_SCHEMA_UNSUPPORTED
```

该 profile 使用 `_index.json` 补充统计。

---

## 17. 验收标准

## 17.1 功能验收

```text id="e7w7m8"
1. 打开 /hermes/agents/common-writer 的【运行状态】页面，可以看到 Insight 区块。
2. 默认显示 profile=all、periodDays=30 的汇总统计。
3. 页面不显示时间范围选择器。
4. 切换到 writer-zh 后，只显示该 profile 的最近 30 天统计。
5. Container Runtime 与 Profile Runtime 分开展示。
6. 单 profile 可以看到：
   - sessions
   - messages
   - input tokens
   - output tokens
   - total tokens
   - estimated cost
   - daily tokens
   - model usage
7. all profiles 模式可以看到 instance aggregate。
8. Model Usage 表在 all 模式下必须显示 profileName 列。
9. Profile Usage 表显示每个 profile 的 sessions/messages/tokens/cost。
10. state.db 缺失时页面不报错。
11. Docker stats 不可用时页面不报错。
12. 不启动 hermes-webui 时，Insight 仍可用。
13. 不启动 Hermes API Server 8642 时，Insight 仍可用。
14. 页面不显示 LLM Wiki。
15. 页面不显示 activityByDay。
16. 页面不显示 activityByHour。
17. 页面不显示 Skill Usage。
```

## 17.2 安全验收

```text id="f2nllf"
1. 前端无法通过 API 读取任意路径。
2. API 不返回 .env 原文。
3. API 不返回 API key。
4. API 不返回 API_SERVER_KEY。
5. API 不返回 session message 正文。
6. SQLite 只读打开。
7. 无 path traversal。
8. 不同 instance/profile 的统计不会串数据。
```

## 17.3 性能验收

```text id="epgfrd"
1. 单 profile 最近 30 天统计响应时间小于 500ms。
2. all profiles 最近 30 天统计响应时间小于 1000ms。
3. 页面首次加载不阻塞现有运行状态展示。
4. 大 _index.json 读取失败时自动跳过。
5. 不扫描完整 session message 文件。
```

---

## 18. 测试计划

## 18.1 Unit Tests

```text id="i1bata"
HermesProfileResolver
  - manifest 解析
  - docker mount path 映射
  - profile home 验证
  - path traversal 拦截

UsageCollector
  - state.db 正常聚合
  - schema 缺字段降级
  - _index.json fallback
  - state.db + _index.json 去重
  - 固定 30 天 cutoff 过滤
  - model group by
  - daily token group by date

ContainerHealthCollector
  - docker running
  - docker stopped
  - docker stats unavailable

ProfileRuntimeCollector
  - running
  - idle
  - configured
  - missing
  - error
```

## 18.2 Integration Tests

```text id="uq8ydx"
GET /api/hermes/instances/:id/profiles
GET /api/hermes/instances/:id/insight?profile=all
GET /api/hermes/instances/:id/insight?profile=writer-zh
profile 不存在
instance 不存在
state.db 缺失
days 参数被忽略或返回 warning
```

## 18.3 E2E Tests

```text id="se9ybo"
打开运行状态页
切换 profile
点击刷新
all profiles model table 显示 profileName
profile usage table 正常展示
缺失 state.db 时显示 No usage data
页面没有 LLM Wiki
页面没有时间范围选择器
页面没有 activity by hour/day
```

---

## 19. 实施任务拆分

## Phase 1：Profile Resolver

```text id="xpdle3"
1. 新增 HermesProfileResolver。
2. 支持读取 profiles.manifest.json。
3. 支持列出 instance 下所有 profiles。
4. 支持校验 hostHermesHome。
5. 支持输出 stateDbPath、configPath、webuiIndexPath。
6. 新增 GET /api/hermes/instances/:instanceId/profiles。
```

## Phase 2：Usage Collector

```text id="vvs8h9"
1. 新增 SQLite 只读工具。
2. 新增 UsageCollector.collectFromStateDb()。
3. 新增 _index.json fallback。
4. 新增去重逻辑。
5. 新增单 profile aggregate。
6. 新增 all profiles aggregate。
7. 固定最近 30 天 cutoff。
8. 新增 warning 结构。
```

## Phase 3：Runtime Collector

```text id="r7d2q6"
1. 新增 Docker inspect 读取。
2. 新增 Docker stats 读取。
3. 新增 disk usage 读取。
4. 新增 profile runtime 状态判断。
5. 拆分 container runtime 与 profile runtime。
```

## Phase 4：Insight API

```text id="jprqpt"
1. 新增 GET /api/hermes/instances/:instanceId/insight。
2. 支持 profile 参数。
3. 不支持前端时间范围过滤。
4. 固定返回 periodDays=30。
5. 支持 refresh=true。
6. 输出统一 InsightResponse。
7. 错误与 warning 标准化。
```

## Phase 5：Frontend UI

```text id="fvwwhc"
1. 运行状态页新增 HermesInsightPanel。
2. 新增 profile selector。
3. 新增 overview cards。
4. 新增 daily token chart。
5. 新增 token breakdown。
6. 新增 model usage table。
7. 新增 profile usage table。
8. 新增 loading / empty / error 状态。
9. 确认不出现 LLM Wiki、时间范围选择器、activity charts。
```

## Phase 6：Tests

```text id="j7ldfx"
1. 补齐 resolver unit tests。
2. 补齐 usage collector unit tests。
3. 补齐 runtime collector unit tests。
4. 补齐 API integration tests。
5. 补齐前端组件测试。
6. 补齐基础 E2E。
```

---

## 20. Cursor Spec 执行建议

## 20.1 后端 Cursor Prompt

```text id="a7mdvk"
请在 nodeskclaw-backend 的 hermes 模块中实现 Hermes Insight v5.0 裁剪版。

要求：
1. 新增 profile-level insight 能力。
2. 一个 Hermes instance 下有多个 profiles。
3. 每个 profile 有独立 hostHermesHome。
4. 统计数据从 profileHome/state.db 和 profileHome/webui/sessions/_index.json 读取。
5. 不通过 Hermes API Server 8642 获取统计。
6. 固定统计最近 30 天。
7. 不实现时间范围过滤。
8. 不实现 LLM Wiki。
9. 不实现 activityByHour / activityByDay。
10. 不实现 Skill Usage。
11. 新增 GET /api/hermes/instances/:instanceId/profiles。
12. 新增 GET /api/hermes/instances/:instanceId/insight?profile=all。
13. SQLite 只读打开。
14. 不返回 .env、API key、session message 正文。
15. 支持 state.db 缺失、schema 不兼容、Docker stats 不可用等降级。
16. 返回结构按 PRD v5.0 裁剪版的 InsightResponse。
17. 增加单元测试与集成测试。
```

## 20.2 前端 Cursor Prompt

```text id="ywphtp"
请在 nodeskclaw 的 /hermes/agents/:instanceId 详情页【运行状态】tab 中新增 Hermes Insight Panel。

要求：
1. 保留现有 Docker 状态展示。
2. 新增 Profile Selector，默认 all。
3. 不增加 Days Selector。
4. 调用 GET /api/hermes/instances/:instanceId/insight?profile=all。
5. 展示 overview cards：sessions/messages/tokens/cost。
6. 展示 daily token chart，固定最近 30 天。
7. 展示 token breakdown。
8. 展示 model usage table，all 模式下显示 profileName。
9. 展示 profile usage table。
10. loading/error/empty 状态完整。
11. UI 风格保持 nodeskclaw 现有暗色后台风格。
12. 不引入大型图表库，第一版使用 CSS bar chart。
13. 页面不得出现 LLM Wiki。
14. 页面不得出现时间范围选择器。
15. 页面不得出现 activity by hour/day。
16. 页面不得出现 Skill Usage。
```

---

## 21. 风险与处理

## 21.1 state.db schema 差异

风险：不同 Hermes 版本的 `sessions` 表字段不一致。

处理：

```text id="p67i2u"
查询前 introspect table schema
字段不存在则默认 0/null
schema 不支持时 fallback 到 _index.json
```

## 21.2 profile path 不统一

风险：不同实例 profile home 路径不同。

处理：

```text id="uo8khg"
以 profiles.manifest.json 为准
docker exec hermes profile show 作为补充
禁止 collector 猜路径
```

## 21.3 数据重复

风险：state.db 与 webui _index.json 同一 session 重复统计。

处理：

```text id="vpao3o"
state.db 优先
dedupeKey 带 instanceId + profileName + source + sessionId
```

## 21.4 密钥泄露

风险：误读 `.env` 并返回敏感信息。

处理：

```text id="ck632n"
本版 insight 不读取 .env
后端响应永不返回 .env 原始内容
```

## 21.5 大文件性能

风险：_index.json 过大导致接口慢。

处理：

```text id="gec4br"
state.db 优先
_index.json 设置文件大小上限
读取失败自动跳过
添加短缓存
```

---

## 22. 版本边界

v5.0 必须完成：

```text id="wmx2gm"
profile resolver
profiles API
insight API
profile/all 统计
固定最近 30 天
state.db usage collector
webui _index fallback
container runtime
profile runtime
前端运行状态页 Insight Panel
基础测试
```

v5.0 明确不做：

```text id="lekvxc"
LLM Wiki
时间范围过滤
Activity by Day
Activity by Hour
Skill Usage
真实账单对账
完整 session message 解析
```

v5.1 可增强：

```text id="w2vfrn"
skill usage
cache read/write token 更细粒度展示
cost by provider
profile 对比图
异常告警
预算阈值
多 instance 总览页
```

v5.2 可增强：

```text id="k2xiyv"
趋势历史落库
Prometheus metrics
token 成本预算策略
团队/用户维度统计
agent 任务成功率
tool call latency
approval count
```

---

## 23. 最终结论

nodeskclaw Hermes Insight v5.0 裁剪版的核心实现原则是：

```text id="rtxi8e"
以 Hermes Profile 的独立 HERMES_HOME 为统计边界；
以 Hermes Instance 为聚合边界；
以 state.db 为主数据源；
以 webui/sessions/_index.json 为补充数据源；
以 Docker runtime 为运行状态数据源；
固定统计最近 30 天；
不通过 Hermes API Server 8642 获取统计；
不依赖 hermes-webui 服务运行；
不读取敏感内容；
不修改 Hermes Agent 状态。
```

该方案可以满足：

```text id="mgjh9l"
单 profile 精准统计
多 profile 汇总统计
容器运行状态查看
profile runtime 状态查看
Hermes 使用成本与 token 趋势观察
nodeskclaw 后续多实例管理扩展
```
