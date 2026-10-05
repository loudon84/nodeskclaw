# Hermes Output Artifacts Package

该候选插件把 Native Hermes Run 工作区文件上传到 MinIO/HTTP，并在成功终态前合并绝对 URL `output_refs`。Hermes v0.21 走 `_set_run_status` 门禁；若 Core 提供 Native finalizer 则同时注册。

## Configuration And Object Scope

[[reports/hermes-agent/hermes-output-artifacts-0.3.0/hermes_output_artifacts/config.py#ArtifactSettings#from_context]] 读取 `ctx.get_config()` 与 `HERMES_ARTIFACT_*` 环境，密钥只来自非 root MinIO 凭据。[[reports/hermes-agent/hermes-output-artifacts-0.3.0/hermes_output_artifacts/upload.py#build_object_key]] 用实例、run、SHA-256 和安全文件名构造对象键。

## Workspace And Finalizer Boundary

[[reports/hermes-agent/hermes-output-artifacts-0.3.0/hermes_output_artifacts/collector.py#ArtifactCollector#collect]] 只接受工作区内、非链接且满足扩展名/排除规则的普通文件。[[reports/hermes-agent/hermes-output-artifacts-0.3.0/hermes_output_artifacts/refs.py#ArtifactRegistry#finalize]] 在不持有全局锁的情况下上传，必需上传失败则禁止成功终态。

## Core Integration Prerequisite

[[reports/hermes-agent/hermes-output-artifacts-0.3.0/hermes_output_artifacts/plugin.py#register]] 在 v0.21 包装 `APIServerAdapter._set_run_status`；若存在则同时注册 `register_native_run_finalizer`。两者都缺失时拒绝启用。`post_tool_call` 回退 `session_id`/`session`，工作区回退 hook `cwd` 或 `/data/hermes/workspace`；register/skip/track/upload 打 INFO。契约见 [NATIVE-FINALIZER-CONTRACT.md](../../reports/hermes-agent/hermes-output-artifacts-0.3.0/NATIVE-FINALIZER-CONTRACT.md)。
