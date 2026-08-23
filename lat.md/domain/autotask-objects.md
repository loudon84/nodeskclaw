# AutoTask Objects

AutoTask 领域对象描述独立服务 `nodeskclaw-task` 中的任务、工作流、Binding、Run 与后继作业语义，供改码前对齐产品语言。

架构与打包约束见 [[task]]；软删除不变量见 [[soft-delete]]。

## Automation Task

自动化任务是租户内一次可执行工作单元，绑定 Portal 账号与 Workflow Binding，并携带业务 `input`。

状态机驱动排队与执行；进入队列后 `input` 不可变。后继创建的子任务通过 `source_task_id` / `source_run_id` 追溯来源。模型：[[nodeskclaw-task/app/models/automation_task.py#AutomationTask]]。

## Workflow Template And Binding

模板定义可启用的流程类型（`code`）；Binding 把模板钉到具体 Portal 与 RPA Flow 版本快照。

Binding `config.successor` 可声明成功后继目标。删除模板必须软删，且仅 DRAFT/DISABLED、无活跃 Binding、无历史任务引用时可删（见 [[task#Workflow Template Delete]]）。

## Rpa Run And Output

RpaRun 是任务的一次 Worker 执行；成功结束时可携带结构化 `output`（JSONB），失败不得带 output。

`finish_run` 在 SUCCESS 时落库 `output` 并可能入队后继作业。迁移 `7c1f4d8e2a90` 增加 `rpa_runs.output`。契约：[[nodeskclaw-task/app/schemas/dispatch.py#RunFinishRequest]]。

## Task Successor Job

后继作业是「源 Run → 目标 Binding」的可靠创建队列，幂等于 `source_run_id` + `target_workflow_binding_id`。

状态 PENDING / PROCESSING / RETRYING / SUCCEEDED / FAILED。仅支持白名单 `inputMapper` 与对应模板 code。领域行为与处理器见 [[task#Successor Jobs]]；模型：[[nodeskclaw-task/app/models/task_successor_job.py#TaskSuccessorJob]]。
