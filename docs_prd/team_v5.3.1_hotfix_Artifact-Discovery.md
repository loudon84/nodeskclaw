# nodeskclaw Hermes Skill Gateway PRD v5.3.1_hotfix

## 1. 文档信息

**PRD 名称**：Hermes API_SERVER Route 任务完成后的 Artifact Discovery + Register
**PRD 版本**：v5.3.1_hotfix
**关联版本**：v5.3 Runtime Skill 注册到组织级 MCP
**适用项目**：nodeskclaw
**实施范围**：nodeskclaw-backend、nodeskclaw-portal
**不实施范围**：hermes-agent、hermes-webui、copilot-docker、第三方 MCP Client
**修复目标**：组织级 MCP 调用注册后的 Hermes runtime skill，任务完成后自动发现 Hermes Agent 实例生成的文件，并写入 `hermes_artifacts`，使 `/hermes/tasks/{task_id}/artifacts` 和 `/hermes/artifacts?task_id=...` 能返回产物清单。

---

## 2. 当前现象

### 2.1 已完成能力

PRD v5.3 已完成：

```text
1. common-writer runtime skill 可快速注册到组织级 MCP
2. POST /api/v1/hermes/mcp tools/list 可看到注册后的 tool
3. POST /api/v1/hermes/mcp tools/call 可创建 HermesTask
4. Task 能进入队列
5. 指定 Hermes Agent 实例 common-writer 能完成任务
6. /hermes/tasks/{task_id} 能看到 completed 状态和 result_summary
```

### 2.2 当前问题

任务：

```text
871dac86-ba18-434a-9a90-0a2a7e3933fa
```

任务详情结果中显示报告已保存到：

```text
/data/hermes/workspace/reports/sale/芯智科技有限公司-客户画像.md
```

宿主机也能查到文件：

```text
/data/copilot-docker/instances/common-writer/data/hermes/workspace/reports/sale/芯智科技有限公司-客户画像.md
```

但数据库查询为空：

```sql
select *
from hermes_artifacts
where task_id = '871dac86-ba18-434a-9a90-0a2a7e3933fa';
```

导致以下接口返回空数据集：

```http
GET /api/v1/hermes/tasks/871dac86-ba18-434a-9a90-0a2a7e3933fa/artifacts
GET /api/v1/hermes/artifacts?task_id=871dac86-ba18-434a-9a90-0a2a7e3933fa&page=1&page_size=20
```

---

## 3. 根因分析

v5.3 已打通的是：

```text
组织级 MCP
  → HermesTask
  → hermes_task_worker
  → 指定 Hermes Agent 实例 API_SERVER
  → 任务完成
  → result_summary 写入
```

但未打通：

```text
任务完成
  → 从 result_summary / final_response 中发现文件路径
  → 将容器路径映射为宿主机路径
  → 检查文件存在
  → 计算文件元数据
  → 写入 hermes_artifacts
  → artifacts API 返回文件清单
```

因此当前属于：

```text
文件已生成
任务已完成
但 Artifact 未入库
```

不是：

```text
文件没有生成
任务没有完成
MCP 调用失败
队列执行失败
指定实例执行失败
```

---

## 4. 修复目标

v5.3.1_hotfix 必须完成：

```text
1. Hermes API_SERVER route 任务完成后自动发现生成文件
2. 支持从 result_summary / final_response 中提取 /data/hermes/workspace/... 文件路径
3. 支持将容器路径映射为宿主机路径
4. 支持检查文件存在、读取 size、mime、sha256
5. 支持 upsert hermes_artifacts
6. 支持写入 task event
7. 支持历史 completed 任务手动重新扫描 artifacts
8. 支持任务详情页触发 rescan
9. Artifact 扫描失败不得影响主任务 completed 状态
10. 新任务完成后无需人工 rescan，自动登记 artifacts
```

---

## 5. 非目标

v5.3.1_hotfix 不做：

```text
1. 不修改 hermes-agent
2. 不修改 hermes-webui
3. 不要求 Hermes API_SERVER 返回结构化 artifacts
4. 不实现复杂文件全文索引
5. 不实现 artifact 权限 EE 扩展
6. 不实现对象存储上传
7. 不改变现有任务 result_summary 结构
8. 不改变 v5.3 的组织级 MCP 注册流程
9. 不新增 POST /api/v1/hermes/tasks 创建任务接口
10. 不做跨实例 artifact 聚合
```

---

## 6. 总体方案

新增一条任务完成后的产物登记链路：

```text
hermes_task_worker
  → execute_hermes_api_server_skill()
  → task completed
  → ArtifactDiscoveryService.discover_and_register_for_task()
  → extract artifact paths
  → map container path to host path
  → validate file
  → upsert HermesArtifact
  → write task event
```

同时新增手动重扫接口：

```http
POST /api/v1/hermes/tasks/{task_id}/artifacts/rescan
```

用于修复历史已完成任务。

---

## 7. Artifact Discovery 数据来源

v5.3.1 支持三类来源，按优先级执行。

### 7.1 结构化 artifacts 来源，预留

如果未来 Hermes API_SERVER 结果包含：

```json
{
  "artifacts": [
    {
      "path": "/data/hermes/workspace/reports/sale/xxx.md",
      "type": "markdown"
    }
  ]
}
```

优先使用。

v5.3.1 先预留解析能力，不依赖 Hermes Agent 修改。

---

### 7.2 result_summary / final_response 路径提取，必须支持

当前必须支持从文本中提取：

```text
/data/hermes/workspace/...
```

示例：

```text
客户画像报告已完成并保存到 `/data/hermes/workspace/reports/sale/芯智科技有限公司-客户画像.md`
```

提取结果：

```text
/data/hermes/workspace/reports/sale/芯智科技有限公司-客户画像.md
```

---

### 7.3 workspace 增量扫描，兜底支持

如果文本中没有路径，但任务完成时间附近 workspace 有新增文件，可做兜底扫描。

v5.3.1 建议默认关闭或低优先级启用，避免误关联其他任务文件。

兜底规则：

```text
mtime >= task.created_at - 60 seconds
mtime <= task.completed_at + 60 seconds
extension in .md, .pdf, .docx, .xlsx, .pptx, .json, .csv, .txt
path contains reports / output / outputs / artifacts / export
```

---

## 8. 路径映射规则

### 8.1 容器路径

Hermes Agent 实例内部路径：

```text
/data/hermes/workspace/reports/sale/芯智科技有限公司-客户画像.md
```

容器 workspace root：

```text
/data/hermes/workspace
```

---

### 8.2 宿主机路径

common-writer 宿主机路径：

```text
/data/copilot-docker/instances/common-writer/data/hermes/workspace/reports/sale/芯智科技有限公司-客户画像.md
```

宿主机 workspace root：

```text
/data/copilot-docker/instances/common-writer/data/hermes/workspace
```

---

### 8.3 映射算法

```python
container_root = Path("/data/hermes/workspace")
host_root = Path("/data/copilot-docker/instances/common-writer/data/hermes/workspace")

container_path = Path("/data/hermes/workspace/reports/sale/芯智科技有限公司-客户画像.md")
relative_path = container_path.relative_to(container_root)

host_path = host_root / relative_path
```

得到：

```text
reports/sale/芯智科技有限公司-客户画像.md
```

和：

```text
/data/copilot-docker/instances/common-writer/data/hermes/workspace/reports/sale/芯智科技有限公司-客户画像.md
```

---

## 9. Hermes 实例绑定要求

Artifact Discovery 必须从 `task.payload.route_snapshot` 或 Task 关联的 installation 中获取指定实例信息。

必须包含：

```json
{
  "route_type": "hermes_api_server",
  "force_instance": true,
  "hermes_instance_name": "common-writer",
  "hermes_agent_instance_id": "uuid-of-common-writer",
  "agent_profile": "common-writer",
  "profile_id": "default",
  "workspace_id": "default",
  "runtime_skill_id": "customer-profiling"
}
```

如果 `route_snapshot` 缺失，需要 fallback 到：

```text
task.installation_id
  → SkillInstallation.route_config
  → hermes_agent_instance_id
```

禁止前端传入 host path。

host path 必须来自：

```text
HermesAgentInstance 绑定记录
或后端已有 _host_dir_from_agent(record)
或绑定记录 host_data_dir 推导
```

---

## 10. 后端新增 Service

新增文件：

```text
nodeskclaw-backend/app/services/hermes_skill/artifact_discovery_service.py
```

核心类：

```python
class ArtifactDiscoveryService:
    async def discover_and_register_for_task(
        self,
        db: AsyncSession,
        task: HermesTask,
        result_text: str | None = None,
        force_rescan: bool = False,
    ) -> list[HermesArtifact]:
        ...
```

---

## 11. ArtifactDiscoveryService 职责

### 11.1 输入

```text
task
result_text
force_rescan
```

其中 `result_text` 来源按顺序取：

```text
1. 显式传入 result_text
2. task.result_summary
3. task.result.text / task.result.raw_result
4. task.error_message 不参与 artifact 提取
```

---

### 11.2 输出

```python
list[HermesArtifact]
```

如果未发现产物，返回空列表，不抛异常。

---

### 11.3 内部流程

```text
1. 读取 task.payload.route_snapshot
2. 判断 route_type 是否为 hermes_api_server
3. 读取 hermes_instance_name / hermes_agent_instance_id / runtime_skill_id
4. 查询 HermesAgentInstance
5. 解析 container_workspace_root
6. 解析 host_workspace_root
7. 从 result_text 提取 container paths
8. 将 container path 映射到 host path
9. 校验 host path 存在且是文件
10. 校验 host path 位于 host_workspace_root 内
11. 计算 file metadata
12. upsert HermesArtifact
13. 写 task event
14. 返回 artifacts
```

---

## 12. 文件路径提取规则

### 12.1 必须支持的路径格式

Markdown code path：

```text
`/data/hermes/workspace/reports/sale/a.md`
```

普通文本 path：

```text
保存到 /data/hermes/workspace/reports/sale/a.md
```

带引号 path：

```text
"/data/hermes/workspace/reports/sale/a.md"
'/data/hermes/workspace/reports/sale/a.md'
```

---

### 12.2 正则建议

```python
CONTAINER_WORKSPACE_PATH_RE = re.compile(
    r"[`\"']?(?P<path>/data/hermes/workspace/[^\n`\"']+?)(?=[`\"']|\\s|$)"
)
```

处理后需要：

```text
strip 空白
strip 句号、逗号、中文句号、右括号等尾部符号
URL decode 不需要
保留中文文件名
```

---

### 12.3 安全限制

只接受以下前缀：

```text
/data/hermes/workspace/
```

不接受：

```text
/etc/passwd
/root/.ssh
/data/hermes/config.yaml
/data/hermes/.env
```

---

## 13. Host Path 解析

### 13.1 推荐字段

如果 HermesAgentInstance 已有字段：

```text
host_data_dir
```

则：

```python
host_workspace_root = Path(host_data_dir) / "hermes" / "workspace"
```

对于 common-writer：

```text
host_data_dir = /data/copilot-docker/instances/common-writer/data
host_workspace_root = /data/copilot-docker/instances/common-writer/data/hermes/workspace
```

---

### 13.2 兼容字段

如果已有字段名不同，按现有项目字段适配，例如：

```text
host_dir
host_data_path
data_dir
workspace_host_path
```

PRD 不强制新增字段，优先复用已有 Agent 绑定记录字段。

---

### 13.3 路径安全校验

必须校验：

```python
resolved_host_path.is_relative_to(resolved_host_workspace_root)
```

Python 低版本兼容：

```python
try:
    resolved_host_path.relative_to(resolved_host_workspace_root)
except ValueError:
    raise SecurityError
```

防止 result_summary 注入：

```text
/data/hermes/workspace/../../.env
```

---

## 14. HermesArtifact 入库设计

### 14.1 必须写入字段

根据现有 `hermes_artifacts` 模型字段适配，至少要保证查询接口能按 `task_id` 查到。

建议字段：

```json
{
  "org_id": "2be7c618-326d-4a73-91ea-1cfda10f7073",
  "task_id": "871dac86-ba18-434a-9a90-0a2a7e3933fa",
  "skill_id": "hermes_common_writer__customer-profiling",
  "tool_name": "hermes_common_writer__customer-profiling",
  "agent_id": "eb237392-ab8c-4e85-bf04-4357297f7e55",
  "profile_id": "default",
  "workspace_id": "default",
  "filename": "芯智科技有限公司-客户画像.md",
  "artifact_type": "markdown",
  "mime_type": "text/markdown",
  "file_path": "/data/copilot-docker/instances/common-writer/data/hermes/workspace/reports/sale/芯智科技有限公司-客户画像.md",
  "container_path": "/data/hermes/workspace/reports/sale/芯智科技有限公司-客户画像.md",
  "relative_path": "reports/sale/芯智科技有限公司-客户画像.md",
  "size_bytes": 12345,
  "sha256": "sha256",
  "source": "hermes_api_server_workspace",
  "metadata": {
    "hermes_instance_name": "common-writer",
    "hermes_agent_instance_id": "uuid-of-common-writer",
    "runtime_skill_id": "customer-profiling",
    "discovered_from": "result_summary"
  }
}
```

---

### 14.2 如果现有表缺少字段

如果 `hermes_artifacts` 已有字段较少，v5.3.1 采用兼容策略：

```text
1. 现有字段能写则写
2. 缺少的新字段写入 metadata JSON
3. 不强制大规模重构 artifact 表
```

例如缺少 `container_path` 时：

```json
{
  "metadata": {
    "container_path": "/data/hermes/workspace/reports/sale/xxx.md",
    "relative_path": "reports/sale/xxx.md",
    "hermes_instance_name": "common-writer"
  }
}
```

如果缺少 `metadata` 字段，则需要 Alembic 增加 `metadata_json` 或项目当前约定的 JSON 字段。

---

### 14.3 Artifact 类型推断

```text
.md       → markdown, text/markdown
.pdf      → pdf, application/pdf
.docx     → word, application/vnd.openxmlformats-officedocument.wordprocessingml.document
.xlsx     → excel, application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
.pptx     → powerpoint, application/vnd.openxmlformats-officedocument.presentationml.presentation
.json     → json, application/json
.csv      → csv, text/csv
.txt      → text, text/plain
.html     → html, text/html
其他      → file, application/octet-stream
```

---

### 14.4 Upsert 唯一键

避免重复 rescan 产生重复记录。

推荐唯一约束：

```text
org_id + task_id + relative_path
```

如果不能新增唯一约束，则 service 层先查：

```sql
where org_id = :org_id
  and task_id = :task_id
  and relative_path = :relative_path
```

没有 `relative_path` 字段时，使用：

```text
task_id + file_path
```

---

## 15. Task Event 设计

新增事件类型：

```text
TASK_ARTIFACT_SCAN_STARTED
TASK_ARTIFACT_REGISTERED
TASK_ARTIFACT_SCAN_COMPLETED
TASK_ARTIFACT_SCAN_EMPTY
TASK_ARTIFACT_SCAN_FAILED
```

### 15.1 成功事件

```json
{
  "event_type": "TASK_ARTIFACT_REGISTERED",
  "detail": {
    "artifact_id": "uuid",
    "filename": "芯智科技有限公司-客户画像.md",
    "relative_path": "reports/sale/芯智科技有限公司-客户画像.md",
    "hermes_instance_name": "common-writer",
    "runtime_skill_id": "customer-profiling"
  }
}
```

### 15.2 空结果事件

```json
{
  "event_type": "TASK_ARTIFACT_SCAN_EMPTY",
  "detail": {
    "reason": "no_artifact_path_found",
    "hermes_instance_name": "common-writer",
    "runtime_skill_id": "customer-profiling"
  }
}
```

### 15.3 失败事件

```json
{
  "event_type": "TASK_ARTIFACT_SCAN_FAILED",
  "detail": {
    "error_code": "host_file_not_found",
    "container_path": "/data/hermes/workspace/reports/sale/xxx.md",
    "mapped_host_path": "/data/copilot-docker/instances/common-writer/data/hermes/workspace/reports/sale/xxx.md"
  }
}
```

---

## 16. Worker 集成

### 16.1 当前 worker 成功路径

当前 v5.3 已实现：

```text
1. 领取任务
2. 读取 route_snapshot
3. 指定 common-writer 实例
4. 调用 Hermes API_SERVER
5. 写 result_summary
6. 标记 completed
```

### 16.2 v5.3.1 新增步骤

在任务成功完成后追加：

```python
try:
    artifacts = await ArtifactDiscoveryService(db).discover_and_register_for_task(
        task=task,
        result_text=result_summary,
        force_rescan=False,
    )
except Exception as exc:
    await task_event_service.append_event(
        task_id=task.id,
        event_type="TASK_ARTIFACT_SCAN_FAILED",
        detail={"error": str(exc)},
    )
```

### 16.3 失败隔离原则

Artifact Discovery 失败不得影响主任务状态。

正确行为：

```text
任务执行成功 → completed
Artifact 扫描失败 → 写 TASK_ARTIFACT_SCAN_FAILED event
任务仍保持 completed
```

禁止行为：

```text
Artifact 扫描失败 → task failed
```

---

## 17. 手动 Rescan API

新增接口：

```http
POST /api/v1/hermes/tasks/{task_id}/artifacts/rescan
```

鉴权：

```text
require_org_member + hermes_task:view
```

建议只有以下角色可触发：

```text
任务创建者
admin/operator
具备 hermes_task:manage 权限的用户
```

### 17.1 请求

```http
POST /api/v1/hermes/tasks/871dac86-ba18-434a-9a90-0a2a7e3933fa/artifacts/rescan
Authorization: Bearer <token>
Content-Type: application/json
```

可选 body：

```json
{
  "force": true
}
```

### 17.2 响应

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "task_id": "871dac86-ba18-434a-9a90-0a2a7e3933fa",
    "artifact_count": 1,
    "artifacts": [
      {
        "id": "uuid",
        "filename": "芯智科技有限公司-客户画像.md",
        "artifact_type": "markdown",
        "mime_type": "text/markdown",
        "relative_path": "reports/sale/芯智科技有限公司-客户画像.md",
        "size_bytes": 12345
      }
    ]
  }
}
```

### 17.3 空结果响应

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "task_id": "871dac86-ba18-434a-9a90-0a2a7e3933fa",
    "artifact_count": 0,
    "artifacts": [],
    "warning": "No artifact path found in task result_summary."
  }
}
```

---

## 18. Artifacts 查询接口兼容

现有接口保持不变：

```http
GET /api/v1/hermes/tasks/{task_id}/artifacts
GET /api/v1/hermes/artifacts?task_id={task_id}&page=1&page_size=20
```

v5.3.1 不改变接口语义，只保证扫描入库后能查到数据。

---

## 19. Download / Preview 兼容要求

Artifact 入库后，已有下载/预览接口必须能使用 `file_path` 或项目当前 artifact path 字段读取宿主机文件。

要求：

```text
1. 下载接口从 hermes_artifacts 查 artifact
2. 校验 org_id / permission
3. 校验 file_path 在允许的 workspace root 内
4. 读取文件并返回
```

如果现有下载接口只支持某种固定存储路径，需要在 ArtifactService 中兼容 `source=hermes_api_server_workspace`。

---

## 20. Portal 前端改动

## 20.1 任务详情页 Artifacts 区域

在：

```text
nodeskclaw-portal
/hermes/tasks/{task_id}
```

增加或完善 Artifacts 区域。

状态：

```text
加载中
已发现 N 个产物
未发现产物
扫描失败
```

---

## 20.2 空 artifacts 但 result_summary 包含路径

如果 artifacts 为空，同时 result_summary 包含：

```text
/data/hermes/workspace/
```

显示提示：

```text
任务结果中包含生成文件路径，但尚未登记为产物。可点击“重新扫描产物”补录。
```

按钮：

```text
[重新扫描产物]
```

---

## 20.3 Rescan 成功后刷新

点击 rescan 后：

```text
1. 调 POST /api/v1/hermes/tasks/{task_id}/artifacts/rescan
2. 显示扫描中状态
3. 成功后刷新 artifacts 列表
4. 如果 artifact_count > 0，显示文件卡片
5. 如果 artifact_count = 0，显示空状态
```

---

## 20.4 Artifact 文件卡片字段

展示：

```text
文件名
文件类型
文件大小
相对路径
来源 Hermes 实例
下载按钮
预览按钮
```

示例：

```text
芯智科技有限公司-客户画像.md
markdown · 32 KB
reports/sale/芯智科技有限公司-客户画像.md
来源：common-writer
[预览] [下载]
```

---

## 21. 后端文件改动清单

### 21.1 新增

```text
nodeskclaw-backend/app/services/hermes_skill/artifact_discovery_service.py
nodeskclaw-backend/app/schemas/hermes_skill/artifact_rescan.py
```

### 21.2 修改

```text
nodeskclaw-backend/app/services/hermes_skill/hermes_task_worker.py
nodeskclaw-backend/app/services/hermes_skill/artifact_service.py
nodeskclaw-backend/app/api/hermes_skill/artifacts_router.py
nodeskclaw-backend/app/api/hermes_skill/tasks_router.py 或 task_result_router.py
nodeskclaw-backend/app/api/hermes_skill/router.py
```

### 21.3 可选迁移

如果 `hermes_artifacts` 缺少必要字段，新增 Alembic：

```text
alembic/versions/xxxx_v5_3_1_artifact_metadata.py
```

建议优先复用现有字段，减少迁移风险。

---

## 22. 前端文件改动清单

### 22.1 修改

```text
nodeskclaw-portal/src/api/hermes/tasks.ts
nodeskclaw-portal/src/api/hermes/artifacts.ts
nodeskclaw-portal/src/views/hermes/HermesTaskDetailView.vue
nodeskclaw-portal/src/i18n/locales/zh-CN.ts
nodeskclaw-portal/src/i18n/locales/en-US.ts
```

### 22.2 可选新增组件

```text
nodeskclaw-portal/src/views/hermes/TaskArtifactsPanel.vue
nodeskclaw-portal/src/views/hermes/ArtifactCard.vue
```

---

## 23. ArtifactDiscoveryService 伪代码

```python
class ArtifactDiscoveryService:
    CONTAINER_WORKSPACE_ROOT = "/data/hermes/workspace"

    async def discover_and_register_for_task(
        self,
        db: AsyncSession,
        task: HermesTask,
        result_text: str | None = None,
        force_rescan: bool = False,
    ) -> list[HermesArtifact]:
        route_snapshot = self._get_route_snapshot(task)

        if route_snapshot.get("route_type") != "hermes_api_server":
            return []

        instance = await self._load_hermes_instance(
            db,
            task.org_id,
            route_snapshot.get("hermes_agent_instance_id"),
        )

        host_workspace_root = self._resolve_host_workspace_root(instance)
        container_workspace_root = route_snapshot.get(
            "container_workspace_root",
            self.CONTAINER_WORKSPACE_ROOT,
        )

        text = result_text or task.result_summary or self._extract_text_from_task_result(task)

        container_paths = self._extract_container_paths(
            text,
            container_workspace_root,
        )

        artifacts = []

        for container_path in container_paths:
            relative_path = self._to_relative_path(
                container_path,
                container_workspace_root,
            )
            host_path = host_workspace_root / relative_path

            self._assert_safe_path(host_path, host_workspace_root)

            if not host_path.exists() or not host_path.is_file():
                await self._append_scan_failed_event(...)
                continue

            artifact = await self._upsert_artifact(
                db=db,
                task=task,
                host_path=host_path,
                container_path=container_path,
                relative_path=relative_path,
                route_snapshot=route_snapshot,
            )

            artifacts.append(artifact)

        await self._append_scan_completed_event(task, len(artifacts))

        return artifacts
```

---

## 24. 文件元数据计算

```python
def build_file_metadata(host_path: Path) -> dict:
    stat = host_path.stat()
    sha256 = hashlib.sha256()

    with host_path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            sha256.update(chunk)

    return {
        "filename": host_path.name,
        "size_bytes": stat.st_size,
        "sha256": sha256.hexdigest(),
        "mime_type": guess_mime_type(host_path),
        "artifact_type": guess_artifact_type(host_path),
    }
```

---

## 25. 安全要求

### 25.1 禁止扫描非 workspace 路径

只允许：

```text
/data/hermes/workspace/
```

映射到：

```text
host_workspace_root
```

### 25.2 禁止路径穿越

拒绝：

```text
/data/hermes/workspace/../../.env
/data/hermes/workspace/reports/../../../config.yaml
```

### 25.3 禁止暴露 API key

事件、日志、artifact metadata 不得包含：

```text
api_server_key
authorization header
.env 内容
```

### 25.4 文件大小限制

建议配置：

```text
HERMES_ARTIFACT_DISCOVERY_MAX_FILE_SIZE_MB=200
```

超过限制：

```text
不入库或标记为 oversized
写 TASK_ARTIFACT_SCAN_FAILED event
不影响主任务
```

---

## 26. 配置项

新增可选配置：

```text
HERMES_ARTIFACT_DISCOVERY_ENABLED=true
HERMES_ARTIFACT_DISCOVERY_CONTAINER_WORKSPACE_ROOT=/data/hermes/workspace
HERMES_ARTIFACT_DISCOVERY_MAX_FILE_SIZE_MB=200
HERMES_ARTIFACT_DISCOVERY_ENABLE_MTIME_FALLBACK=false
HERMES_ARTIFACT_DISCOVERY_MTIME_WINDOW_SECONDS=60
```

默认：

```text
enabled = true
container_workspace_root = /data/hermes/workspace
max_file_size = 200MB
mtime fallback = false
```

---

## 27. 历史任务补录

v5.3.1 必须支持对历史任务补录。

方式一：单任务接口：

```http
POST /api/v1/hermes/tasks/{task_id}/artifacts/rescan
```

方式二：可选管理脚本：

```bash
python -m app.scripts.rescan_hermes_task_artifacts \
  --task-id 871dac86-ba18-434a-9a90-0a2a7e3933fa
```

方式三：可选批量接口，v5.3.1 不强制：

```http
POST /api/v1/hermes/artifacts/rescan-completed-tasks
```

v5.3.1 必须完成方式一。

---

## 28. 针对当前任务的验收示例

### 28.1 调用 rescan

```http
POST /api/v1/hermes/tasks/871dac86-ba18-434a-9a90-0a2a7e3933fa/artifacts/rescan
```

期望返回：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "task_id": "871dac86-ba18-434a-9a90-0a2a7e3933fa",
    "artifact_count": 1,
    "artifacts": [
      {
        "filename": "芯智科技有限公司-客户画像.md",
        "artifact_type": "markdown",
        "relative_path": "reports/sale/芯智科技有限公司-客户画像.md"
      }
    ]
  }
}
```

### 28.2 查询 task artifacts

```http
GET /api/v1/hermes/tasks/871dac86-ba18-434a-9a90-0a2a7e3933fa/artifacts
```

期望返回 1 条记录。

### 28.3 查询 global artifacts

```http
GET /api/v1/hermes/artifacts?task_id=871dac86-ba18-434a-9a90-0a2a7e3933fa&page=1&page_size=20
```

期望返回 1 条记录。

### 28.4 SQL 验证

```sql
select id, task_id, filename, artifact_type, file_path, created_at
from hermes_artifacts
where task_id = '871dac86-ba18-434a-9a90-0a2a7e3933fa';
```

期望返回：

```text
芯智科技有限公司-客户画像.md
```

---

## 29. 自动登记新任务验收

重新通过组织级 MCP 调用：

```text
hermes_common_writer__customer-profiling
```

任务完成后，不手动 rescan，直接查询：

```http
GET /api/v1/hermes/tasks/{new_task_id}/artifacts
```

期望 artifact 自动存在。

---

## 30. 测试计划

### 30.1 后端单元测试

新增：

```text
tests/hermes_skill/test_artifact_discovery_service.py
```

测试用例：

```text
test_extract_markdown_code_path
test_extract_plain_workspace_path
test_ignore_non_workspace_path
test_map_container_path_to_host_path
test_reject_path_traversal
test_register_markdown_artifact
test_upsert_artifact_idempotent
test_no_artifact_path_returns_empty
test_missing_host_file_writes_failed_event
test_scan_failure_does_not_fail_task
```

---

### 30.2 Worker 集成测试

```text
test_hermes_api_server_route_completed_registers_artifact
test_worker_completed_even_when_artifact_scan_failed
test_worker_records_task_artifact_registered_event
test_worker_uses_route_snapshot_instance_for_artifact_path
```

---

### 30.3 API 测试

```text
test_rescan_artifacts_for_completed_task
test_rescan_requires_task_permission
test_task_artifacts_returns_registered_artifact
test_artifacts_list_by_task_id_returns_registered_artifact
```

---

### 30.4 前端测试

```text
Task detail shows empty artifact warning when result_summary contains workspace path
Click rescan calls artifacts rescan API
Rescan success refreshes artifact list
Artifact card shows filename, type, size, relative path
```

---

## 31. 日志要求

新增日志：

```text
artifact_discovery.start
artifact_discovery.path_extracted
artifact_discovery.path_mapped
artifact_discovery.file_missing
artifact_discovery.artifact_registered
artifact_discovery.completed
artifact_discovery.failed
```

日志字段：

```json
{
  "task_id": "871dac86-ba18-434a-9a90-0a2a7e3933fa",
  "hermes_instance_name": "common-writer",
  "runtime_skill_id": "customer-profiling",
  "container_path": "/data/hermes/workspace/reports/sale/芯智科技有限公司-客户画像.md",
  "relative_path": "reports/sale/芯智科技有限公司-客户画像.md"
}
```

不得输出：

```text
api_server_key
Authorization
.env 内容
```

---

## 32. 上线步骤

### Step 1：实现后端 ArtifactDiscoveryService

```text
新增路径提取
新增 path mapping
新增 file metadata
新增 artifact upsert
新增 task event
```

### Step 2：接入 worker

```text
Hermes API_SERVER route task completed 后自动调用 discovery
扫描失败不影响 task completed
```

### Step 3：新增 rescan API

```text
POST /tasks/{task_id}/artifacts/rescan
```

### Step 4：前端任务详情页增加 rescan

```text
空 artifacts + result_summary 含路径时显示提示
支持点击 rescan
刷新 artifacts 列表
```

### Step 5：历史任务验证

```text
对 871dac86-ba18-434a-9a90-0a2a7e3933fa 执行 rescan
确认 hermes_artifacts 入库
确认 artifacts 接口返回
```

### Step 6：新任务验证

```text
重新调用 customer-profiling
任务完成后自动出现 artifact
```

---

## 33. 回滚方案

如果上线后 artifact discovery 出现异常：

```text
1. 设置 HERMES_ARTIFACT_DISCOVERY_ENABLED=false
2. worker 不再自动扫描 artifacts
3. 已完成任务状态不受影响
4. rescan API 可临时隐藏或返回 disabled
```

回滚不会影响：

```text
组织级 MCP
任务队列
指定 Hermes 实例执行
任务结果 result_summary
```

---

## 34. 风险与处理

### 风险 1：result_summary 中路径格式变化

处理：

```text
支持多种路径提取格式
后续鼓励 skill 输出固定 “保存到 `path`” 格式
```

### 风险 2：host_data_dir 字段不统一

处理：

```text
优先复用已有 _host_dir_from_agent(record)
或封装统一 resolve_host_workspace_root(record)
```

### 风险 3：误登记其他任务文件

处理：

```text
v5.3.1 优先只解析 result_summary 显式路径
mtime fallback 默认关闭
```

### 风险 4：扫描失败影响主任务

处理：

```text
扫描失败只写 event，不改变 task completed
```

### 风险 5：路径穿越安全风险

处理：

```text
只允许 /data/hermes/workspace 前缀
host path 必须在 host_workspace_root 内
```

---

## 35. Cursor 实施指令

```text
请实现 PRD v5.3.1_hotfix：Hermes API_SERVER route 任务完成后的 artifact discovery + register。

背景：
PRD v5.3 已完成 runtime skill 注册到组织级 MCP、tools/call 入队、指定 Hermes 实例执行。当前任务能完成，result_summary 中有生成文件路径，宿主机也能查到文件，但 hermes_artifacts 表没有记录，导致 /tasks/{task_id}/artifacts 和 /artifacts?task_id=xxx 返回空。

实施范围：
- nodeskclaw-backend
- nodeskclaw-portal

禁止修改：
- hermes-agent
- hermes-webui
- copilot-docker

后端要求：
1. 新增 app/services/hermes_skill/artifact_discovery_service.py
2. ArtifactDiscoveryService 支持：
   - 从 task.result_summary / result_text 提取 /data/hermes/workspace/... 路径
   - 从 task.payload.route_snapshot 获取 hermes_instance_name / hermes_agent_instance_id / runtime_skill_id
   - 查询 HermesAgentInstance 绑定记录
   - 将 container path 映射到 host workspace path
   - 校验 host path 存在且在 workspace root 内
   - 计算 filename / extension / mime_type / artifact_type / size_bytes / sha256
   - upsert HermesArtifact
   - 写 TASK_ARTIFACT_REGISTERED / TASK_ARTIFACT_SCAN_COMPLETED / TASK_ARTIFACT_SCAN_FAILED event

3. 修改 hermes_task_worker：
   - 当 route_type == hermes_api_server 且任务成功完成后，自动调用 ArtifactDiscoveryService.discover_and_register_for_task()
   - artifact 扫描失败不得导致主任务 failed，只写 warning event

4. 新增 API：
   POST /api/v1/hermes/tasks/{task_id}/artifacts/rescan
   - 从历史 completed task 的 result_summary 重新扫描 artifacts
   - 返回 artifact_count 和 artifacts

5. 修改 artifact_service / artifacts_router：
   - 确保 newly registered HermesArtifact 能被以下接口查到：
     GET /api/v1/hermes/tasks/{task_id}/artifacts
     GET /api/v1/hermes/artifacts?task_id={task_id}&page=1&page_size=20

6. 前端：
   - 在任务详情页 Artifacts 区域增加空状态提示
   - 如果 artifacts 为空但 result_summary 包含 /data/hermes/workspace/，显示“重新扫描产物”
   - 点击后调用 rescan API
   - rescan 成功后刷新 artifact list
   - artifact card 显示 filename / type / size / relative_path / source instance

验收：
1. 宿主机存在：
   /data/copilot-docker/instances/common-writer/data/hermes/workspace/reports/sale/芯智科技有限公司-客户画像.md

2. 对任务执行：
   POST /api/v1/hermes/tasks/871dac86-ba18-434a-9a90-0a2a7e3933fa/artifacts/rescan

3. 期望返回 artifact_count=1。

4. SQL 查询：
   select * from hermes_artifacts
   where task_id = '871dac86-ba18-434a-9a90-0a2a7e3933fa';
   应返回 芯智科技有限公司-客户画像.md。

5. GET /api/v1/hermes/tasks/871dac86-ba18-434a-9a90-0a2a7e3933fa/artifacts 应返回该文件。

6. GET /api/v1/hermes/artifacts?task_id=871dac86-ba18-434a-9a90-0a2a7e3933fa&page=1&page_size=20 应返回该文件。

7. 新的 customer-profiling 任务完成后，无需手动 rescan，自动登记 artifact。
```

---

## 36. 最终结论

v5.3.1_hotfix 的本质是补齐这一步：

```text
Hermes Agent 已生成文件
  → nodeskclaw 发现文件
  → 映射宿主机路径
  → 写入 hermes_artifacts
  → artifacts API 可查询
```

对当前任务：

```text
871dac86-ba18-434a-9a90-0a2a7e3933fa
```

修复完成后，应能将：

```text
/data/copilot-docker/instances/common-writer/data/hermes/workspace/reports/sale/芯智科技有限公司-客户画像.md
```

登记为任务产物，并通过：

```text
/hermes/tasks/871dac86-ba18-434a-9a90-0a2a7e3933fa/artifacts
/hermes/artifacts?task_id=871dac86-ba18-434a-9a90-0a2a7e3933fa
```

正常返回。
