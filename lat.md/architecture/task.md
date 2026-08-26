# Task Architecture

`nodeskclaw-task` 是 monorepo 内独立 AutoTask FastAPI 服务：自动化任务、工作流模板/绑定、RPA 调度与制品；与 Backend 并列，自有 PostgreSQL 与 Alembic。

技术栈对齐 Knowledge：Python 3.12、SQLAlchemy asyncio、错误契约 `error_code` + `message_key` + `message`、软删除 `BaseModel`（[[soft-delete]]、[[error-contract]]）。入口：[[nodeskclaw-task/app/main.py]]。Knowledge 脚手架对齐见 [[knowledge#Package Placement]]。

## Package Placement

Task 落在仓库根 `nodeskclaw-task/`，与 Backend / Knowledge / LLM Proxy 并列，不并入 Backend 进程。

目录约定：`app/api`（`router.py` 聚合）、`schemas`、`services`、`models`、`core`、自管 `alembic/`、本地 `storage/`（制品落盘，不是可分发 Python 包）、独立 `DATABASE_URL`。本地与镜像安装优先 `uv sync`（Dockerfile 同路径）。根目录 `dev.sh` 不启动本服务，本地需单独 `uv run uvicorn`（默认 4520）。启动可用 `SKIP_AUTO_MIGRATE=1` 跳过自动迁移，`SEED_DATA_ENABLED=false` 跳过种子。

## Packaging Constraint

flat-layout 下 `app/`、`alembic/`、`storage/` 会被 setuptools 误判为多个顶层包，导致 `pip install -e .` 失败。

`pyproject.toml` 必须声明 `[build-system]`（setuptools）与 `[tool.setuptools.packages.find]`：`include = ["app*"]`，`exclude = ["alembic*", "storage*", "tests*"]`。推荐 `uv sync` / `uv pip install -e .`；uv 管理的 `.venv` 默认无 pip，勿误用系统 pip 装进全局 site-packages。同布局兄弟服务（如 Knowledge）若做 editable 安装，也应显式 `include = ["app*"]`。

## Successor Jobs

源任务 Run 成功后按 Binding `config.successor` 异步派生后继任务；作业表幂等排队，默认关闭，迁移完成后再开。

配置写入 Workflow Binding：`successor.on=SUCCESS`、`targetWorkflowBindingId`、`inputMapper`。创建/更新/启用 Binding 时校验目标存在、同 Portal、已启用、有 Flow 版本快照、模板 code 匹配，且禁止自引用：[[nodeskclaw-task/app/services/task_successor_service.py#validate_successor_binding_config]]。

Worker `finish_run` 在 `SUCCESS` 时写入 `run.output` 并调用 [[nodeskclaw-task/app/services/task_successor_service.py#enqueue_successor_job]]（[[nodeskclaw-task/app/services/dispatch_service.py#finish_run]]）。`RunFinishRequest.output` 仅允许 `status=SUCCESS`。

模型：[[nodeskclaw-task/app/models/task_successor_job.py#TaskSuccessorJob]]。幂等键 `source_run_id` + `target_workflow_binding_id`（Partial Unique）。状态 PENDING / PROCESSING / RETRYING / SUCCEEDED / FAILED（[[nodeskclaw-task/app/models/enums.py#SuccessorJobStatus]]）。子任务在 [[nodeskclaw-task/app/models/automation_task.py#AutomationTask]] 记录 `source_task_id` / `source_run_id`。

支持的 mapper：`ORDER_DELIVERY_CONFIRMATION_V1`（源输出 `ORDER_DOWNLOAD_PUSH_OUTPUT_V1` → 模板 `srm_update_expected_delivery_dates`，子任务 DRAFT）与 `ORDER_ATTACHMENT_UPLOAD_V1`（源 `ORDER_DELIVERY_CONFIRMATION_OUTPUT_V1` 且已回签 → `srm_upload_order_attachment`，子任务直接 QUEUED）。

后台 [[nodeskclaw-task/app/services/task_successor_service.py#SuccessorJobProcessor]] 轮询 `PENDING`/`RETRYING`（`FOR UPDATE SKIP LOCKED`），可重试错误按退避延迟，超过 `SUCCESSOR_JOB_MAX_ATTEMPTS` 标 FAILED。开关与调参见 `.env.example`：`SUCCESSOR_JOB_ENABLED`（默认 false）、poll / batch / max_attempts。查询与人工重试（仅 FAILED→PENDING）：[[nodeskclaw-task/app/api/tasks.py#list_task_successors]]、[[nodeskclaw-task/app/api/tasks.py#retry_task_successor]]。

执行侧约束：任务进入队列后禁止改 `input`；启动/重试交货日期模板时校验 `order_lines`（[[nodeskclaw-task/app/services/automation_task_service.py#start_task]]）。领域对象见 [[autotask-objects]]。

## Schema Migration Successor

启用后继作业前必须先应用 Alembic revision `7c1f4d8e2a90`，再将 `SUCCESSOR_JOB_ENABLED` 设为 true。

该迁移：为 `rpa_runs` 增加 JSONB `output`；为 `automation_tasks` 增加 `source_task_id` / `source_run_id` 及索引；新建 `task_successor_jobs`（含就绪索引与 `source_run_id`+`target_workflow_binding_id` 的 Partial Unique）。实现文件：[[nodeskclaw-task/alembic/versions/7c1f4d8e2a90_task_successor_jobs_and_run_output.py]]。

## Workflow Template Delete

模板删除是软删除，且仅 DRAFT/DISABLED 可删；有活跃 Binding 或历史任务引用时拒绝，只能禁用。

实现：[[nodeskclaw-task/app/services/workflow_template_service.py#delete_workflow_template]]；API `DELETE /workflow-templates/{id}`。成功后写审计 `workflow_template.deleted`。启用中模板必须先 disable。

## Artifact URL Bases

本地制品上传/下载 URL 可分别覆盖公网基址，避免 Worker 与浏览器走同一入口。

`ARTIFACT_UPLOAD_BASE_URL` / `ARTIFACT_DOWNLOAD_BASE_URL` 为空时回退 `PUBLIC_BASE_URL`（[[nodeskclaw-task/app/services/s3_storage.py#local_upload_url]]、[[nodeskclaw-task/app/services/s3_storage.py#local_download_url]]）。出站调用 Backend / RPA Engine 的 `httpx` 使用 `trust_env=False`，避免误走 HTTP 代理。
