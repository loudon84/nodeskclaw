# Hermes Output Artifacts v0.3.0

该包把 Native Run 工作区内允许的输出文件上传到 MinIO 或 HTTP 文件服务器，并在写入成功终态之前合并绝对 URL `output_refs`。

针对 **Hermes Agent v0.21**：在 `APIServerAdapter._set_run_status` 上安装终态门禁。若 Core 已提供 `ctx.register_native_run_finalizer()`，则同时注册 Native finalizer。两者都没有时拒绝启用。

v0.3 不读取 `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD`。

## Core / v0.21 前置条件

优先顺序：

1. 包装 `gateway.platforms.api_server.APIServerAdapter._set_run_status`（v0.21 正式路径，见仓库 `patches/api_server_terminal_gate.md`）。
2. 或 Core 提供 `ctx.register_native_run_finalizer(callback)`，且 `post_tool_call` 带 `native_run_id` / `workspace_root`（见 [NATIVE-FINALIZER-CONTRACT.md](NATIVE-FINALIZER-CONTRACT.md)）。

`post_tool_call` 在缺少 `native_run_id` 时回退 `run_id` / `task_id` / `session_id`，工作区回退 `workspace` / `cwd`。手工登记：`track_workspace_file(run_id, path)`。

缺少门禁与 finalizer 时，插件在注册阶段报错并拒绝启用，避免未上传却 `completed`。

## 安装

```powershell
<HERMES_PYTHON> -m pip install E:\path\to\hermes-output-artifacts-0.3.0
```

该包通过 `hermes_agent.plugins` entry point 注册为 `output_artifacts`。安装后须由 Hermes 的正常插件加载流程加载。

## 正式插件配置

非密钥配置经 `ctx.get_config()` 读取，也可被 `HERMES_ARTIFACT_*` / `HERMES_OUTPUT_ARTIFACTS_ENABLED` 覆盖。示例：

```yaml
plugins:
  output_artifacts:
    enabled: true
    upload_mode: s3
    s3_endpoint: http://127.0.0.1:9010
    s3_bucket: agent-runtime-export
    s3_region: us-east-1
    s3_addressing: path
    s3_presign: true
    s3_presign_expires: 3600
    instance_id: hermes-lan-01
    public_base_url: http://127.0.0.1:9010/agent-runtime-export
    ext_allow: [".md", ".txt", ".json", ".csv", ".pdf", ".png", ".docx", ".pptx", ".xlsx"]
    exclude_patterns: [".git/*", ".env", "private/*"]
    max_single_bytes: 10485760
    max_total_bytes: 52428800
    max_files: 20
    required_default: true
```

`instance_id` 必须是单个安全对象键段，只允许字母、数字、`.`、`_`、`-`。对象键格式为：

```text
<s3_prefix>/instances/<instance_id>/runs/<run_id>/<sha256>-<filename>
```

密钥仅从运行时环境读取，推荐：

```powershell
$env:HERMES_ARTIFACT_S3_ACCESS_KEY = '<MINIO_ACCESS_KEY>'
$env:HERMES_ARTIFACT_S3_SECRET_KEY = '<MINIO_SECRET_KEY>'
```

为兼容既有非 root MinIO 部署，也接受 `MINIO_ACCESS_KEY` 与 `MINIO_SECRET_KEY`。禁止配置或回退到 MinIO root 凭据。

`s3_presign: false` 时，`output_refs.url` 使用 `public_base_url` + object key，不再改写 presigned 主机名。

## 网络和权限

- Hermes 到 MinIO 必须能执行 `PutObject`。
- Agent 必须能 GET `output_refs.url`：公网 HTTPS，或与 Hermes `gateway_url` 同源，或 Agent origin allowlist（见 `../AGENT-SIDE-REQUIREMENTS.md`）。内网 MinIO 默认会被 Agent SSRF 策略拒绝。
- 用于上传的 MinIO 身份需要 bucket 的 `s3:PutObject` 和 `s3:GetObject` 权限。bucket 不应匿名可写。

## 本地验证

```powershell
$env:PYTHONPATH = (Get-Location)
<PYTHON> -m unittest discover -s tests -t . -v
```

这些测试使用 S3 测试替身验证配置、对象键、签名引用、工作区边界、v0.21 终态门禁和终态失败语义；不连接实际 MinIO。
