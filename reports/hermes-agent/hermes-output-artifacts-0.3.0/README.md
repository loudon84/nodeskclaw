# Hermes Output Artifacts v0.3.0

该包把 Native Run 工作区内允许的输出文件上传到 MinIO，并在 Hermes 写入终态之前通过 Native finalizer 返回带签名下载地址、大小和 SHA-256 的 `output_refs`。

v0.3 只支持 MinIO S3 API。它不使用 HTTP 上传回退、不读取 `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD`，也不会 monkey-patch Hermes API Server。

## Core 前置条件

Hermes Core 必须提供 `ctx.register_native_run_finalizer(callback)`，并在 `post_tool_call` 的 payload 中显式提供 `native_run_id` 与 `workspace_root`。完整回调输入、返回值和调用顺序见 [NATIVE-FINALIZER-CONTRACT.md](NATIVE-FINALIZER-CONTRACT.md)。

缺少该 API 时，插件会在注册阶段报错并拒绝启用；这避免了把文件上传失败伪装成 run 成功。

## 安装

```powershell
<HERMES_PYTHON> -m pip install E:\path\to\hermes-output-artifacts-0.3.0
```

该包通过 `hermes_agent.plugins` entry point 注册为 `output_artifacts`。安装后须由 Hermes 的正常插件加载流程加载；本包不自行重启进程。

## 正式插件配置

所有非密钥配置经 `ctx.get_config()` 读取，即 `plugins.entries.output_artifacts.settings`。示例：

```yaml
plugins:
  entries:
    output_artifacts:
      settings:
        enabled: true
        s3_endpoint: https://minio.smc.lan:9000
        s3_bucket: agent-runtime-export
        s3_region: us-east-1
        s3_prefix: artifacts
        s3_addressing: path
        s3_presign_expires: 3600
        instance_id: hermes-lan-01
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

## 网络和权限

- Hermes 到 MinIO 必须能执行 `PutObject`。
- Agent 到 `s3_endpoint` 必须能使用 presigned GET 读取对象；S3 签名中的主机名必须就是 Agent 可访问的地址，不能上传后替换 URL 主机名。
- Agent 侧必须仅允许该精确 MinIO origin，例如 `https://minio.smc.lan:9000`；不能放行整个 `192.168.0.0/16`。
- 用于上传的 MinIO 身份需要 bucket 的 `s3:PutObject` 和 `s3:GetObject` 权限。bucket 不应匿名可写。

## 本地验证

```powershell
$env:PYTHONPATH = (Get-Location)
<PYTHON> -m unittest discover -s tests -t . -v
```

这些测试使用 S3 测试替身验证配置、对象键、签名引用、工作区边界和终态失败语义；不连接实际 MinIO。
