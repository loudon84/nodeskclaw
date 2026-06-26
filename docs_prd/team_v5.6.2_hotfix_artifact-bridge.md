# NoDeskClaw Hermes MCP Artifact Bridge PRD

## 版本

v5.6.2

## 标题

Runtime Skill 真实导出产物优先入库，修复 unknown 物化副本与 KB 入库对象错误问题

## 模块

nodeskclaw-backend
nodeskclaw-portal
Hermes MCP Skill Gateway
Hermes Artifact Bridge
KB Ingestion Queue

## 一、背景

v5.6 已经完成 MCP Artifact Bridge Pull-only 能力：

1. MCP Runtime Skill 执行完成后，Gateway 可生成 `server_artifacts`。
2. 产物保存到 nodeskclaw 中心 Artifact Store。
3. 产物提供 preview / download / suggested_workspace_path。
4. 可创建 KB ingestion job，进入知识库审核流程。
5. Gateway 不直接写调用方 Hermes workspace。

当前实际运行中已经能生成 artifact，并能在：

```text
/hermes/artifacts
/hermes/kb-ingestion
```

看到相关产物和入库任务。

但当前存在一个关键偏差：

同一个 MCP Runtime Skill 任务会出现两份文档：

```text
1. unknown_客户画像_20260626_1108.md
   - 来源：nodeskclaw 根据 runtime 返回文本 content_text 物化生成
   - 存储：nodeskclaw object_store
   - 路径：workspace/drafts/customer/unknown_客户画像_20260626_1108.md
   - 会进入 KB ingestion

2. 陕西天基通信科技有限责任公司_客户画像报告.md
   - 来源：Hermes runtime skill 实际导出的 workspace 文件
   - 存储：Hermes 实例 workspace / exports
   - 路径：exports/陕西天基通信科技有限责任公司_客户画像报告.md
   - 当前不会进入 KB ingestion
```

这导致 `/hermes/artifacts` 能看到两份产物，但 `/hermes/kb-ingestion` 只看到 `unknown_客户画像...`，而不是业务真正需要入库的完整报告文件。

## 二、问题定义

### 2.1 当前问题

当前 v5.6 的 Worker 流程是：

```text
Runtime Skill 执行完成
  ↓
拿到 content_text
  ↓
ServerArtifactService.create_from_task_result()
  ↓
基于 content_text 物化 unknown_客户画像_xxx.md
  ↓
创建 KB ingestion job
  ↓
ArtifactDiscoveryService.discover_and_register_for_task()
  ↓
发现 Hermes workspace 中真实报告文件
```

这个顺序导致：

```text
KB ingestion job 绑定的是 content_text 物化产物
不是 Runtime Skill 真实导出的报告文件
```

### 2.2 直接表现

在 `/hermes/artifacts` 中，每个任务会出现两份文档：

```text
unknown_客户画像_20260626_1108.md
陕西天基通信科技有限责任公司_客户画像报告.md
```

在 `/hermes/kb-ingestion` 中，只出现：

```text
unknown_客户画像_20260626_1108.md
```

没有出现：

```text
陕西天基通信科技有限责任公司_客户画像报告.md
```

### 2.3 根因

根因分为三层：

#### 第一层：Worker 顺序错误

当前先执行 `create_from_task_result()`，再执行 `ArtifactDiscoveryService`。

因此系统还没发现真实导出文件时，就已经根据 `content_text` 生成了中心产物并创建了 KB job。

#### 第二层：content_text 不一定是报告全文

Runtime Skill 的返回文本可能只是：

```text
报告已生成：
/data/hermes/workspace/exports/陕西天基通信科技有限责任公司_客户画像报告.md
```

或者是简短摘要。

此时基于 content_text 物化出来的 Markdown 不是完整报告，只是提示文本或摘要。

#### 第三层：文件名缺少结构化参数

`customer-profiling` 的默认文件名模板是：

```text
{company}_客户画像_{date}.md
```

但 `task.arguments` 里可能只有：

```json
{
  "prompt": "请为陕西天基通信科技有限责任公司做客户画像"
}
```

没有：

```json
{
  "company": "陕西天基通信科技有限责任公司"
}
```

导致 fallback 成：

```text
unknown_客户画像_20260626_1108.md
```

## 三、目标

v5.6.2 的目标是修复 v5.6 的产物优先级问题：

```text
真实导出文件优先。
content_text 物化只作为 fallback。
KB ingestion job 必须绑定真实报告产物。
```

### 3.1 功能目标

1. Runtime Skill 如果生成真实 workspace 文件，则优先使用真实文件作为 `server_artifacts`。
2. 真实文件被提升为中心产物，进入 nodeskclaw Artifact Store。
3. KB ingestion job 绑定真实报告文件，而不是 unknown 物化副本。
4. 如果没有发现真实文件，再 fallback 到 `content_text` 物化。
5. 新任务不再重复生成 unknown 副本文档。
6. 历史任务提供数据修复方式。
7. `/hermes/artifacts` 与 `/hermes/kb-ingestion` 对入库对象保持一致。
8. `task.server_artifacts` 只记录最终被中心化治理的产物。

### 3.2 用户体验目标

修复前：

```text
Artifact 列表：
- unknown_客户画像_20260626_1108.md
- 陕西天基通信科技有限责任公司_客户画像报告.md

KB 入库：
- unknown_客户画像_20260626_1108.md
```

修复后：

```text
Artifact 列表：
- 陕西天基通信科技有限责任公司_客户画像报告.md

KB 入库：
- 陕西天基通信科技有限责任公司_客户画像报告.md
```

任务详情中的中心产物库显示：

```text
陕西天基通信科技有限责任公司_客户画像报告.md
markdown · 27.4 KB
workspace/exports/陕西天基通信科技有限责任公司_客户画像报告.md
预览
下载
KB 状态：待审核
```

## 四、非目标

v5.6.2 不做以下事情：

1. 不改变 v5.6 的 Pull-only 原则。
2. 不直接写入调用方 Hermes workspace。
3. 不修改 hermes-agent 核心源码。
4. 不修改 runtime skill 的执行协议。
5. 不强制要求所有 runtime skill 必须写文件。
6. 不删除 `/hermes/artifacts` 中已有历史 unknown 产物。
7. 不默认自动入库知识库。
8. 不实现真正的向量库索引执行器。
9. 不重构整个 Artifact 权限体系。
10. 不改变 MCP tools/call 的 queued 返回机制。

## 五、设计原则

### 5.1 真实文件优先

Runtime Skill 如果已经生成真实报告文件，系统不应再基于简短返回文本生成第二份报告。

优先级固定为：

```text
Hermes workspace 真实导出文件
  >
Runtime Skill 返回的全文 content_text
  >
Runtime Skill 返回的摘要或路径提示
```

### 5.2 content_text 只做 fallback

只有在以下情况下，才允许基于 `content_text` 物化中心产物：

```text
1. 没有发现任何真实导出文件。
2. 真实导出文件不可读。
3. 真实导出文件不满足安全校验。
4. Artifact Discovery 被关闭。
```

### 5.3 KB job 绑定最终 server_artifact

KB ingestion job 必须绑定最终进入中心产物库的 artifact。

不能绑定：

```text
临时摘要
路径提示文本
unknown 文件名副本
非最终报告
```

### 5.4 不重复注册同一业务文档

同一个任务内，真实报告文件和 content_text fallback 不能同时作为 server_artifacts。

### 5.5 Artifact Discovery 不等于 KB 入库

Artifact Discovery 只负责发现 Hermes workspace 文件。

是否进入 KB ingestion，由 v5.6.2 的 ServerArtifactService 根据 output_policy 决定。

## 六、总体方案

v5.6.2 调整 Worker 完成路径：

### 6.1 当前流程

```text
Runtime Skill 执行完成
  ↓
mark_completed(content_text[:500])
  ↓
ServerArtifactService.create_from_task_result(content_text)
  ↓
生成 unknown_*.md
  ↓
创建 KB job
  ↓
ArtifactDiscoveryService 发现真实文件
```

### 6.2 目标流程

```text
Runtime Skill 执行完成
  ↓
mark_completed(content_text[:500])
  ↓
ArtifactDiscoveryService 先发现真实 workspace 文件
  ↓
ServerArtifactService.create_from_discovered_artifacts()
  ↓
如果发现真实报告：
      真实报告提升为中心 server_artifact
      创建 KB ingestion job
      跳过 content_text 物化
  ↓
如果没有发现真实报告：
      fallback 到 create_from_task_result(content_text)
```

### 6.3 新链路图

```text
Hermes WebUI
  ↓
nodeskclaw-skill-router
  ↓
MCP tools/call
  ↓
HermesTask queued
  ↓
Worker 调用 Docker Hermes Agent API_SERVER
  ↓
Runtime Skill 执行
  ↓
Runtime Skill 写入 workspace/exports/xxx.md
  ↓
Runtime Skill 返回报告路径或摘要
  ↓
ArtifactDiscoveryService 发现真实 xxx.md
  ↓
ServerArtifactService promote 真实 xxx.md 到中心 Artifact Store
  ↓
HermesArtifact 更新为 object_store
  ↓
创建 KB ingestion job
  ↓
task.server_artifacts 指向真实 xxx.md
  ↓
Portal 任务详情和 KB 审核页展示真实报告
```

## 七、后端详细设计

## 7.1 Worker 顺序调整

修改文件：

```text
nodeskclaw-backend/app/services/hermes_skill/hermes_task_worker.py
```

### 当前逻辑

```python
await task_service.mark_completed(task, result_summary=content_text[:500])

output_policy = task.routing_metadata.get("output_policy")

if output_policy:
    server_artifacts = await ServerArtifactService(db).create_from_task_result(
        task=task,
        full_result_text=content_text,
        output_policy=output_policy,
    )

if settings.HERMES_ARTIFACT_DISCOVERY_ENABLED:
    await ArtifactDiscoveryService(db).discover_and_register_for_task(...)
```

### 目标逻辑

```python
await task_service.mark_completed(task, result_summary=content_text[:500])

output_policy = resolve_output_policy_from_task(task)

discovered_artifacts = []

if settings.HERMES_ARTIFACT_DISCOVERY_ENABLED:
    try:
        discovered_artifacts = await ArtifactDiscoveryService(db).discover_and_register_for_task(
            task=task,
            result_text=content_text,
            force_rescan=False,
        )
    except Exception as exc:
        log discovery failed
        discovered_artifacts = []

server_artifacts = []

if output_policy and discovered_artifacts:
    try:
        server_artifacts = await ServerArtifactService(db).create_from_discovered_artifacts(
            task=task,
            artifacts=discovered_artifacts,
            output_policy=output_policy,
        )
    except Exception as exc:
        log promote failed
        server_artifacts = []

if output_policy and not server_artifacts:
    try:
        server_artifacts = await ServerArtifactService(db).create_from_task_result(
            task=task,
            full_result_text=content_text,
            output_policy=output_policy,
        )
    except Exception as exc:
        log materialize fallback failed

if server_artifacts:
    task.server_artifacts = server_artifacts
    task.artifact_status = "stored"
    task.kb_status = ServerArtifactService.resolve_task_kb_status(server_artifacts)
    task.result_summary = ServerArtifactService.append_artifact_links(
        task.result_summary or content_text[:500],
        server_artifacts,
    )

await db.flush()
```

### 关键规则

```text
1. Discovery 先于 materialize。
2. Promote 成功后不再 fallback materialize。
3. Discovery 失败不影响任务完成。
4. Promote 失败时允许 fallback content_text。
5. task.server_artifacts 只写最终中心产物。
```

## 7.2 新增 ServerArtifactService.create_from_discovered_artifacts

修改文件：

```text
nodeskclaw-backend/app/services/mcp_skill_gateway/server_artifact_service.py
```

新增方法：

```python
async def create_from_discovered_artifacts(
    self,
    task: HermesTask,
    artifacts: list[HermesArtifact],
    output_policy: dict[str, Any],
) -> list[dict[str, Any]]:
    ...
```

### 7.2.1 方法职责

该方法负责把 ArtifactDiscoveryService 发现的真实文件提升为 v5.6 server_artifacts。

职责包括：

```text
1. 过滤可提升的 discovered artifacts。
2. 读取真实文件内容。
3. 上传到中心 Artifact Store。
4. 更新 HermesArtifact 为 object_store 中心产物。
5. 保留原始 workspace 文件路径到 metadata_json。
6. 设置 suggested_workspace_path。
7. 设置 kb_status。
8. 调用 KbIngestionService.create_job。
9. 返回 server_artifacts。
```

### 7.2.2 可提升 artifact 条件

只有满足以下条件的 artifact 才允许 promote：

```text
artifact.deleted_at is None
artifact.task_id == task.id
artifact.org_id == task.org_id
artifact.storage_type != object_store 或 object_key 为空
artifact.file_path 指向真实本地文件
文件存在
文件大小 > 0
文件通过 PathGuard 校验
content_type 属于 text/* 或 application/json
文件扩展名属于 .md / .txt / .json / .csv
```

第一版建议优先支持：

```text
.md
.txt
.json
.csv
```

PDF / DOCX 后续版本再处理。

### 7.2.3 Promote 后字段更新

对于真实报告 artifact：

```python
artifact.storage_type = "object_store"
artifact.object_key = stored.object_key
artifact.file_path = stored.object_key
artifact.size_bytes = stored.size_bytes
artifact.sha256 = stored.sha256
artifact.source = "materialized"
artifact.kb_status = kb_status
artifact.workspace_saved = False
artifact.format = resolved_format
artifact.suggested_workspace_dir = resolved_dir
artifact.suggested_workspace_path = resolved_path
artifact.metadata_json = {
    **old_metadata,
    "source": "hermes_api_server_workspace_promoted",
    "original_storage_type": "local_fs",
    "original_file_path": original_file_path,
    "original_relative_path": original_relative_path,
    "artifact_mode": "pull_only",
    "tool_name": task.tool_name,
}
```

### 7.2.4 suggested_workspace_path 规则

如果 discovered artifact 的 `relative_path` 是：

```text
exports/陕西天基通信科技有限责任公司_客户画像报告.md
```

则 `suggested_workspace_path` 生成：

```text
workspace/exports/陕西天基通信科技有限责任公司_客户画像报告.md
```

如果 relative_path 已经是：

```text
workspace/exports/xxx.md
```

则不重复加 `workspace/`。

建议实现：

```python
def build_suggested_path_from_relative_path(relative_path: str) -> str:
    rel = relative_path.strip("/")
    if rel.startswith("workspace/"):
        return rel
    return f"workspace/{rel}"
```

### 7.2.5 多文件处理规则

一个任务可能发现多个文件。

优先级：

```text
1. result_text 中明确出现的路径
2. 文件名包含 报告 / 客户画像 / 风险评估 / 联系窗口 / 推广文案
3. Markdown 文件
4. 文件较大者
5. 创建时间较晚者
```

v5.6.2 第一版可以 promote 所有符合条件的 `.md/.txt/.json/.csv` 文件。

如果要避免多文件噪音，可以只 promote Top 1：

```text
默认 promote 所有 eligible documents。
如果 output_policy.promote_mode = "primary_only"，只 promote 主文档。
```

建议默认：

```json
{
  "promote_mode": "all_documents"
}
```

## 7.3 保留 fallback create_from_task_result

`create_from_task_result()` 继续保留，作为 fallback。

触发条件：

```text
1. Artifact Discovery 没发现真实文件。
2. Artifact Discovery 被关闭。
3. promote 真实文件失败。
4. Runtime Skill 本身不写 workspace 文件，只返回正文。
```

fallback 文件名仍走 output_policy：

```text
{company}_客户画像_{date}.md
```

但 v5.6.2 会增强 company 提取，减少 unknown。

## 7.4 增强 ArtifactMaterializer 文件名提取

修改文件：

```text
nodeskclaw-backend/app/services/mcp_skill_gateway/artifact_materializer.py
```

### 当前逻辑

```python
company = args.get("company") or args.get("company_name") or args.get("name") or "unknown"
```

### 目标逻辑

新增函数：

```python
def extract_company_from_task(task: HermesTask) -> str:
    args = task.arguments or {}

    for key in (
        "company",
        "company_name",
        "customer",
        "customer_name",
        "enterprise",
        "enterprise_name",
        "name",
    ):
        value = args.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    context = args.get("context")
    if isinstance(context, dict):
        for key in (
            "company",
            "company_name",
            "customer",
            "customer_name",
            "enterprise",
            "enterprise_name",
            "name",
        ):
            value = context.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

    prompt = str(args.get("prompt") or task.request_summary or "")
    patterns = [
        r"为(.+?)做客户画像",
        r"分析(.+?)的客户画像",
        r"(.+?)客户画像",
        r"公司[：:]\s*(.+)",
        r"企业[：:]\s*(.+)",
        r"客户[：:]\s*(.+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, prompt)
        if match:
            value = match.group(1)
            value = value.strip(" ，。,.：:；;")
            if value:
                return value

    return "unknown"
```

`render_filename()` 中：

```python
"company": _sanitize_filename_part(extract_company_from_task(task))
```

### 目标效果

即使 Router Skill 只传：

```json
{
  "prompt": "请为陕西天基通信科技有限责任公司做客户画像"
}
```

fallback 文件名也能生成：

```text
陕西天基通信科技有限责任公司_客户画像_20260626_1108.md
```

而不是：

```text
unknown_客户画像_20260626_1108.md
```

## 7.5 Router Skill 参数增强

修改文件：

```text
nodeskclaw-backend/app/services/hermes_agents/router_skill_template_service.py
```

目标：

当用户意图包含公司、客户、品牌、产品、主题时，Router Skill 调用 MCP tool 时尽量传结构化参数。

### customer-profiling 示例

当前可能只传：

```json
{
  "prompt": "请为陕西天基通信科技有限责任公司做客户画像"
}
```

目标：

```json
{
  "company": "陕西天基通信科技有限责任公司",
  "prompt": "请为陕西天基通信科技有限责任公司做客户画像"
}
```

### marketing-copy 示例

```json
{
  "topic": "TI 音频芯片",
  "prompt": "帮我写一篇 TI 音频芯片的推广文案"
}
```

### b2b-contact-finder 示例

```json
{
  "company": "研华科技",
  "prompt": "帮我找研华科技的采购或商务联系窗口"
}
```

### 模板新增规则

```markdown
## MCP 参数提取规则

调用远程 MCP skill 时，除 prompt 外，应尽量提取结构化参数：

- 公司/客户/企业名称 → company
- 品牌/产品/主题 → topic
- 风险对象 → company
- 联系窗口目标公司 → company

不要只把所有信息塞进 prompt。
```

## 八、KB Ingestion 逻辑调整

## 8.1 当前逻辑

当前 `KbIngestionService.create_job()` 只在 `ServerArtifactService.create_from_task_result()` 中被调用。

结果：

```text
content_text 物化产物会创建 KB job
discovery 真实文件不会创建 KB job
```

## 8.2 目标逻辑

`KbIngestionService.create_job()` 应该在两种场景被调用：

```text
1. promote discovery artifact 成功后
2. fallback materialize content_text 成功后
```

但同一个任务内，如果 promote 成功，则不再 fallback。

## 8.3 去重策略

继续使用 sha256 去重。

如果发现同 org 下同 sha256 已经有 job：

```text
不重复创建 job。
artifact.kb_status 建议设置为 duplicate 或 indexed。
```

v5.6.2 建议先使用：

```text
artifact.kb_status = "indexed" if existing job indexed
artifact.kb_status = existing_job.status if existing job exists
```

如果不做这一步，则至少不要让 artifact 显示 `pending_review` 但 job 不存在。

建议改造 `create_job()` 返回结构：

```python
@dataclass
class KbJobCreateResult:
    job: HermesArtifactKbIngestionJob | None
    status: str
    reason: str | None = None
```

如果为了控制 hotfix 范围，也可以暂时保留原返回值，但在 `create_from_discovered_artifacts()` 中只依赖 artifact.kb_status，不强依赖 job 一定创建成功。

## 九、API 行为

## 9.1 `/api/v1/hermes/tasks/{task_id}/artifacts`

保持原有行为：

```text
展示该任务全部 artifacts。
```

但建议增加 source 字段，方便前端区分：

```json
{
  "id": "...",
  "file_name": "陕西天基通信科技有限责任公司_客户画像报告.md",
  "source": "materialized",
  "metadata_json": {
    "source": "hermes_api_server_workspace_promoted"
  }
}
```

## 9.2 `/api/v1/hermes/tasks/{task_id}/result`

返回最终 server_artifacts：

```json
{
  "task_id": "...",
  "status": "completed",
  "artifact_mode": "pull_only",
  "server_artifacts": [
    {
      "artifact_id": "...",
      "name": "陕西天基通信科技有限责任公司_客户画像报告.md",
      "type": "markdown",
      "mime_type": "text/markdown",
      "stored": true,
      "store": "nodeskclaw_artifact_store",
      "download_url": "/api/v1/hermes/artifacts/{artifact_id}/download",
      "preview_url": "/api/v1/hermes/artifacts/{artifact_id}/preview",
      "suggested_workspace_path": "workspace/exports/陕西天基通信科技有限责任公司_客户画像报告.md",
      "workspace_saved": false,
      "kb_status": "pending_review"
    }
  ]
}
```

## 9.3 `/api/v1/hermes/artifacts/kb-ingestion-jobs`

返回真实报告对应的入库任务：

```json
{
  "items": [
    {
      "artifact_id": "...",
      "task_id": "...",
      "knowledge_base": "general",
      "status": "pending_review",
      "tags": ["customer", "sales"],
      "metadata_json": {
        "artifact_name": "陕西天基通信科技有限责任公司_客户画像报告.md",
        "tool_name": "hermes_xieyi__customer-profiling"
      }
    }
  ]
}
```

不再优先出现：

```text
unknown_客户画像_20260626_1108.md
```

## 十、前端调整

## 10.1 `/hermes/artifacts`

当前可以继续显示全部 artifact。

建议增加：

```text
source badge
kb_status badge
server_artifact badge
```

显示示例：

```text
陕西天基通信科技有限责任公司_客户画像报告.md
markdown · 27.4 KB
source: server_artifact / promoted
kb: pending_review
```

对于历史 unknown 产物，可以显示：

```text
source: materialized_fallback
```

## 10.2 `/hermes/kb-ingestion`

无需大改。

修复后该页面自然显示真实报告 artifact 对应的 job。

建议显示：

```text
文件名
KB
tags
来源 Tool
状态
artifact_id
task_id
```

## 10.3 任务详情中心产物卡片

任务详情只展示：

```text
task.server_artifacts
```

不直接把所有 discovery artifacts 都当成中心产物。

如果 `server_artifacts` 为空，但 `data` 里有普通 artifacts，则展示：

```text
本任务有 workspace 导出文件，但尚未进入中心产物库。
```

## 十一、历史数据修复

v5.6.2 发布后，新任务会自动修复。

历史任务中已经产生的 unknown 产物需要一次性清理。

## 11.1 找出同任务重复产物

```sql
select
  task_id,
  count(*) as artifact_count
from hermes_artifacts
where deleted_at is null
group by task_id
having count(*) > 1
order by artifact_count desc;
```

## 11.2 查找 unknown 物化产物

```sql
select
  id,
  task_id,
  file_name,
  relative_path,
  storage_type,
  object_key,
  source,
  kb_status,
  size_bytes,
  created_at
from hermes_artifacts
where deleted_at is null
  and file_name like 'unknown_%'
order by created_at desc;
```

## 11.3 查找同 task 下真实报告

```sql
select
  id,
  task_id,
  file_name,
  relative_path,
  storage_type,
  object_key,
  source,
  kb_status,
  size_bytes,
  created_at
from hermes_artifacts
where deleted_at is null
  and task_id = '<task_id>'
order by size_bytes desc;
```

## 11.4 拒绝 unknown 的 KB job

```sql
update hermes_artifact_kb_ingestion_jobs
set
  status = 'rejected',
  review_comment = 'replaced by original exported report artifact',
  reviewed_at = now()
where artifact_id = '<unknown_artifact_id>'
  and status = 'pending_review';

update hermes_artifacts
set kb_status = 'rejected'
where id = '<unknown_artifact_id>';
```

## 11.5 给真实报告创建 KB job

推荐走 API：

```bash
curl -X POST \
  "http://192.168.102.247:4517/api/v1/hermes/artifacts/<real_report_artifact_id>/kb-ingest" \
  -H "Authorization: Bearer <portal_user_jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "knowledge_base": "general",
    "tags": ["customer", "sales"]
  }'
```

## 11.6 可选：软删除 unknown 产物

如果确认 unknown 产物没有业务价值，可以软删除：

```sql
update hermes_artifacts
set deleted_at = now()
where id = '<unknown_artifact_id>';
```

不建议物理删除 object_store 文件，除非同时清理对象存储。

## 十二、配置项

v5.6.2 建议新增配置：

```env
HERMES_ARTIFACT_PROMOTE_DISCOVERED_ENABLED=true
HERMES_ARTIFACT_MATERIALIZE_FALLBACK_ENABLED=true
HERMES_ARTIFACT_PROMOTE_MODE=all_documents
```

说明：

| 配置                                             |           默认值 | 说明                                   |
| ---------------------------------------------- | ------------: | ------------------------------------ |
| `HERMES_ARTIFACT_PROMOTE_DISCOVERED_ENABLED`   |          true | 是否优先提升 discovery 真实文件                |
| `HERMES_ARTIFACT_MATERIALIZE_FALLBACK_ENABLED` |          true | 没有真实文件时是否 fallback 到 content_text 物化 |
| `HERMES_ARTIFACT_PROMOTE_MODE`                 | all_documents | `all_documents` 或 `primary_only`     |

如果不想新增配置，也可以先硬编码启用，作为 hotfix 行为。

## 十三、安全要求

### 13.1 文件读取安全

promote discovery artifact 时必须继续使用现有 PathGuard / Discovery 校验结果。

不得读取：

```text
workspace 根目录外文件
系统敏感路径
token 文件
.env
config.yaml
私钥文件
```

### 13.2 内容脱敏

promote 真实文件时，原则上不修改正文内容。

但以下字段不得写入 metadata_json：

```text
Authorization
Bearer token
NODESKCLAW_MCP_TOKEN
ndsk_mcp_*
API_SERVER_KEY
```

### 13.3 权限

preview / download 继续走现有 Artifact 权限链：

```text
hermes_artifact:view
hermes_artifact:download
PermissionChecker.can_view_artifact
PermissionChecker.can_download_artifact
```

### 13.4 object_key 不暴露本地路径

返回给前端的 `server_artifacts` 只暴露：

```text
artifact_id
preview_url
download_url
suggested_workspace_path
```

不暴露：

```text
object_key
original_file_path
host_workspace_root
```

原始路径只允许在后端 metadata_json 中审计使用。

## 十四、审计日志

新增或复用审计事件：

```text
mcp_artifact.discovery.promote.started
mcp_artifact.discovery.promote.completed
mcp_artifact.discovery.promote.failed
mcp_artifact.materialize.fallback.started
mcp_artifact.materialize.fallback.completed
mcp_artifact.materialize.fallback.skipped
mcp_artifact.kb_job.created
```

promote completed 示例：

```json
{
  "action": "mcp_artifact.discovery.promote.completed",
  "task_id": "...",
  "artifact_id": "...",
  "artifact_name": "陕西天基通信科技有限责任公司_客户画像报告.md",
  "original_relative_path": "exports/陕西天基通信科技有限责任公司_客户画像报告.md",
  "suggested_workspace_path": "workspace/exports/陕西天基通信科技有限责任公司_客户画像报告.md",
  "kb_status": "pending_review",
  "tool_name": "hermes_xieyi__customer-profiling"
}
```

## 十五、实施任务拆分

### Task 1：调整 Worker 完成路径

文件：

```text
nodeskclaw-backend/app/services/hermes_skill/hermes_task_worker.py
```

任务：

```text
1. mark_completed 后先执行 ArtifactDiscoveryService。
2. 收集 discovered_artifacts。
3. 有 output_policy 时先 promote discovered artifacts。
4. promote 成功则跳过 create_from_task_result。
5. promote 失败或无 discovered artifacts 时 fallback materialize。
6. 更新 task.server_artifacts / artifact_status / kb_status。
```

### Task 2：实现 create_from_discovered_artifacts

文件：

```text
nodeskclaw-backend/app/services/mcp_skill_gateway/server_artifact_service.py
```

任务：

```text
1. 新增 create_from_discovered_artifacts。
2. 新增 eligible artifact 过滤。
3. 新增读取真实文件并上传 object_store。
4. 更新 HermesArtifact 为中心产物。
5. 创建 KB ingestion job。
6. 返回 server_artifacts。
```

### Task 3：增强文件名提取

文件：

```text
nodeskclaw-backend/app/services/mcp_skill_gateway/artifact_materializer.py
```

任务：

```text
1. 新增 extract_company_from_task。
2. 从 args/context/prompt/request_summary 提取 company。
3. 增加 customer/customer_name/enterprise 等字段。
4. fallback 文件名减少 unknown。
```

### Task 4：更新 Router Skill 模板

文件：

```text
nodeskclaw-backend/app/services/hermes_agents/router_skill_template_service.py
```

任务：

```text
1. 增加 MCP 参数提取规则。
2. 调 customer-profiling 时尽量传 company。
3. 调 marketing-copy 时尽量传 topic。
4. 调 b2b-contact-finder 时尽量传 company。
```

### Task 5：前端 source 展示增强

文件：

```text
nodeskclaw-portal/src/views/hermes/ArtifactsView.vue
nodeskclaw-portal/src/views/hermes/TasksView.vue
```

任务：

```text
1. artifacts 列表显示 source/kb_status。
2. 任务详情中心产物卡片只展示 server_artifacts。
3. 历史 unknown fallback 产物可显示为 fallback。
```

### Task 6：历史数据修复脚本

新增脚本：

```text
nodeskclaw-backend/scripts/fix_v5_6_unknown_artifacts.py
```

功能：

```text
1. 查找 unknown_* materialized artifacts。
2. 查找同 task 下更大的真实报告 artifact。
3. 拒绝 unknown KB job。
4. 给真实报告创建 KB job。
5. 可选软删除 unknown artifact。
```

第一版可以只提供 dry-run：

```bash
python scripts/fix_v5_6_unknown_artifacts.py --dry-run
```

执行模式：

```bash
python scripts/fix_v5_6_unknown_artifacts.py --apply
```

## 十六、测试方案

## 16.1 单元测试

### Case 1：有真实报告文件时优先 promote

输入：

```text
task 有 output_policy
ArtifactDiscoveryService 返回 陕西天基通信科技有限责任公司_客户画像报告.md
content_text 非完整报告
```

期望：

```text
create_from_discovered_artifacts 被调用
create_from_task_result 不被调用
task.server_artifacts[0].name = 陕西天基通信科技有限责任公司_客户画像报告.md
```

### Case 2：没有真实文件时 fallback

输入：

```text
ArtifactDiscoveryService 返回 []
content_text = 完整报告正文
```

期望：

```text
create_from_task_result 被调用
生成 markdown object_store artifact
```

### Case 3：promote 失败时 fallback

输入：

```text
ArtifactDiscoveryService 返回 artifact
但真实文件丢失或读取失败
```

期望：

```text
promote 失败被日志记录
create_from_task_result fallback 成功
任务状态仍 completed
```

### Case 4：KB job 绑定真实 artifact

输入：

```text
promote artifact 成功
output_policy.kb_ingest.enabled=true
```

期望：

```text
hermes_artifact_kb_ingestion_jobs.artifact_id = real_report_artifact_id
不是 unknown artifact id
```

### Case 5：文件名提取

输入：

```json
{
  "prompt": "请为陕西天基通信科技有限责任公司做客户画像"
}
```

期望：

```text
render_filename 生成 陕西天基通信科技有限责任公司_客户画像_xxx.md
```

### Case 6：结构化参数优先

输入：

```json
{
  "company": "研华科技",
  "prompt": "请为其他公司做客户画像"
}
```

期望：

```text
company 使用 研华科技
```

## 16.2 集成测试

### Case 1：customer-profiling 端到端

步骤：

```text
1. Hermes WebUI 输入：请为陕西天基通信科技有限责任公司做客户画像。
2. Router Skill 调用 hermes_xieyi__customer-profiling。
3. Runtime Skill 生成 exports/陕西天基通信科技有限责任公司_客户画像报告.md。
4. Worker discovery 发现文件。
5. ServerArtifactService promote 文件。
6. KB job 创建。
```

期望：

```text
/hermes/artifacts 看到真实报告。
/hermes/kb-ingestion 看到真实报告。
task.result_url.server_artifacts[0].name 是真实报告文件名。
不再生成 unknown_客户画像_xxx.md。
```

### Case 2：不写文件的 Runtime Skill

步骤：

```text
Runtime Skill 只返回正文，不写 workspace 文件。
```

期望：

```text
fallback materialize 生效。
仍生成 server_artifacts。
KB job 正常创建。
```

### Case 3：Artifact Preview / Download

期望：

```text
preview_url 可预览真实报告。
download_url 可下载真实报告。
权限不足返回 403。
```

## 十七、验收标准

### 17.1 新任务验收

1. 每个 customer-profiling 任务不再出现 `unknown_客户画像_xxx.md` 副本。
2. 如果 Runtime Skill 写出真实报告，`server_artifacts` 指向真实报告。
3. `/hermes/kb-ingestion` 显示真实报告文件名。
4. KB job 的 `artifact_id` 等于真实报告 artifact id。
5. `task.server_artifacts[0].name` 等于真实报告文件名。
6. preview / download 正常。
7. suggested_workspace_path 正常。
8. task 状态仍然 completed。
9. Discovery 失败时不影响任务完成。
10. fallback 场景仍可生成中心产物。

### 17.2 历史数据验收

1. 已有 unknown KB job 可被拒绝或软删除。
2. 真实报告可手动创建 KB job。
3. KB 审核页不再混淆 unknown 与真实报告。
4. 已下载链接不受影响。

### 17.3 安全验收

1. 不读取 workspace 外文件。
2. 不暴露 host_workspace_root。
3. 不把 token 写入 metadata_json。
4. preview/download 权限不降低。
5. object_key 不直接暴露给普通前端。

## 十八、上线步骤

### 18.1 开发环境

```bash
cd /data/nodeskclaw

# 后端单测
cd nodeskclaw-backend
pytest tests/services/mcp_skill_gateway/test_server_artifact_service.py -q
pytest tests/services/mcp_skill_gateway/test_artifact_materializer.py -q
pytest tests/services/hermes_skill/test_hermes_task_worker_artifacts.py -q

# 前端构建
cd ../nodeskclaw-portal
pnpm build
```

### 18.2 部署

```bash
cd /data/nodeskclaw

git pull

# 如使用 docker compose
docker compose build nodeskclaw-backend nodeskclaw-portal
docker compose up -d nodeskclaw-backend nodeskclaw-portal

# 重启 worker
docker compose restart nodeskclaw-worker
```

### 18.3 验证

新建一个 customer-profiling 任务：

```text
请为陕西天基通信科技有限责任公司做客户画像
```

检查：

```sql
select
  id,
  task_id,
  file_name,
  relative_path,
  storage_type,
  object_key,
  source,
  kb_status,
  size_bytes
from hermes_artifacts
where task_id = '<task_id>'
order by created_at;
```

期望：

```text
真实报告 artifact 存在
storage_type = object_store
object_key 不为空
kb_status = pending_review
没有 unknown_客户画像_xxx.md
```

检查 KB job：

```sql
select
  id,
  artifact_id,
  task_id,
  status,
  knowledge_base,
  tags,
  metadata_json
from hermes_artifact_kb_ingestion_jobs
where task_id = '<task_id>';
```

期望：

```text
artifact_id 指向真实报告 artifact
status = pending_review
```

## 十九、回滚方案

如果 v5.6.2 发布后出现问题：

1. 回滚 `hermes_task_worker.py`。
2. 回滚 `server_artifact_service.py`。
3. 回滚 `artifact_materializer.py`。
4. 回滚 Router Skill 模板修改。
5. 重启 backend 与 worker。

因为 v5.6.2 默认不需要新增数据库字段，所以回滚不需要 migration downgrade。

如果已经 promote 了一批 discovery artifacts 到 object_store：

```text
可以保留，不影响旧逻辑。
```

## 二十、风险与处理

### 风险 1：真实文件发现失败

原因：

```text
runtime skill 没返回路径
mtime fallback 未命中
workspace 映射不正确
```

处理：

```text
fallback 到 content_text 物化。
任务仍 completed。
日志记录 discovery failed。
```

### 风险 2：promote 后原始 file_path 被替换

处理：

```text
把 original_file_path / original_relative_path 保存到 metadata_json。
download/preview 走 object_store。
```

### 风险 3：一个任务发现多个文件

处理：

```text
v5.6.2 默认 promote 所有符合条件的文档文件。
后续可通过 output_policy.promote_mode=primary_only 控制。
```

### 风险 4：历史 unknown 产物仍存在

处理：

```text
提供修复脚本。
新任务不再产生。
历史数据不强制自动删除。
```

### 风险 5：KB job sha256 去重导致 job 未创建

处理：

```text
如果已有相同 sha256 job，则 artifact.kb_status 同步为已有 job 状态。
避免 artifact 显示 pending_review 但 KB 页查不到。
```

## 二十一、Cursor 实施提示词

```text
请在 nodeskclaw 中实现 PRD v5.6.2：Runtime Skill 真实导出产物优先入库。

背景：
当前 v5.6 在 hermes_task_worker 中先调用 ServerArtifactService.create_from_task_result(content_text)，再调用 ArtifactDiscoveryService.discover_and_register_for_task，导致每个任务生成两份文档：
1. unknown_客户画像_xxx.md：由 content_text 物化生成，并创建 KB ingestion job。
2. 真实报告文件：由 Runtime Skill 写入 workspace/exports，被 ArtifactDiscovery 发现，但没有创建 KB ingestion job。

目标：
1. Worker 完成路径改成先 ArtifactDiscovery，再 promote discovered artifacts。
2. 如果 promote 成功，不再调用 create_from_task_result。
3. 只有没有真实文件或 promote 失败时，才 fallback 到 content_text 物化。
4. 新增 ServerArtifactService.create_from_discovered_artifacts。
5. promote 真实文件时，将原 discovery artifact 更新为 object_store server_artifact，不新建第三条 artifact。
6. KB ingestion job 必须绑定真实报告 artifact。
7. 增强 ArtifactMaterializer 的 company/topic 提取，减少 unknown 文件名。
8. Router Skill 模板增加结构化参数提取规则，例如 customer-profiling 应传 company。
9. 不新增数据库 migration。
10. 保持 Pull-only，不直接写 caller workspace。
11. preview/download 权限不降低。
12. 增加单测和端到端测试。

验收：
- customer-profiling 新任务只生成真实报告 server_artifact。
- /hermes/kb-ingestion 显示真实报告文件名，不显示 unknown_客户画像_xxx.md。
- task.result_url.server_artifacts 指向真实报告。
- 如果 Runtime Skill 不写文件，fallback materialize 仍可用。
```

## 二十二、最终结论

v5.6.2 的核心修复是：

```text
先发现真实文件，再决定是否物化。
```

最终产物规则固定为：

```text
Runtime Skill 真实导出文件优先进入中心产物库和 KB 入库审核。
content_text 物化只作为 fallback。
unknown_*.md 不再作为首选知识库文档。
```

修复后，NoDeskClaw 的 MCP Artifact Bridge 才符合 v5.6 的产品目标：把真正有业务价值的报告、文档、清单类产物中心化保存、预览、下载、审核和沉淀到通用知识库。
