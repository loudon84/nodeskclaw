# Hermes Output Artifacts Package

该候选插件包为 Native Hermes Run 提供工作区受限的 MinIO 工件上传和失败关闭的 finalizer 结果，尚需 Hermes Core 和 Agent 的配套变更后才能投入运行。

## Configuration And Object Scope

[[reports/hermes-agent/hermes-output-artifacts-0.3.0/hermes_output_artifacts/config.py#ArtifactSettings#from_context]] 只通过正式 `ctx.get_config()` 读取非密钥设置，并从环境读取非 root MinIO 凭据。[[reports/hermes-agent/hermes-output-artifacts-0.3.0/hermes_output_artifacts/upload.py#build_object_key]] 用实例、run、SHA-256 和安全文件名构造对象键，避免同 run 同名文件覆盖。

## Workspace And Finalizer Boundary

[[reports/hermes-agent/hermes-output-artifacts-0.3.0/hermes_output_artifacts/collector.py#ArtifactCollector#collect]] 只接受工作区内、非链接且满足扩展名/排除规则的普通文件。[[reports/hermes-agent/hermes-output-artifacts-0.3.0/hermes_output_artifacts/refs.py#ArtifactRegistry#finalize]] 在不持有全局锁的情况下上传，并将必需上传失败返回为 `failed` finalizer 结果。

## Core Integration Prerequisite

[[reports/hermes-agent/hermes-output-artifacts-0.3.0/hermes_output_artifacts/plugin.py#register]] 要求 Core 提供 `register_native_run_finalizer`，并只注册正式 `post_tool_call` hook；不具备该能力的运行时会拒绝加载。具体 Core 契约见 [NATIVE-FINALIZER-CONTRACT.md](../../reports/hermes-agent/hermes-output-artifacts-0.3.0/NATIVE-FINALIZER-CONTRACT.md)。
