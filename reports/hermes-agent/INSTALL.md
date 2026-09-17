# 安装与配置手册（Hermes 实例手工操作）

适用：Hermes Agent Runtime **v0.21（v2026.8.31）**。  
本手册由你在实例上执行；

## 0. 安全提醒

- 对话中若暴露过真实 `API_SERVER_KEY`，建议在实例侧**轮换** Key。
- 本仓库文档一律使用 `<API_SERVER_KEY>` 等占位符，**禁止**把真实 Key 提交进 Git。

## 1. 前置条件

| 项 | 说明 |
|----|------|
| Native API Server 可访问 | 例：`http://<LAN-HOST>:29401` |
| 鉴权 | `Authorization: Bearer <API_SERVER_KEY>`（以你实例实际为准） |
| 文件服务器 | 可上传 + 返回/可拼绝对 URL；Agent 主机须能 GET 该 URL |
| 插件落盘位置 | 与现有 Hermes 插件一致（`plugins/` 目录或 pip entry-point） |

健康检查（在你能访问 API 的机器上）：

```bash
curl -sS "http://<LAN-HOST>:29401/health"
# 或
curl -sS -H "Authorization: Bearer <API_SERVER_KEY>" \
  "http://<LAN-HOST>:29401/v1/runs"
```

## 2. 安装插件包

本包路径（从本仓库拷贝到实例）：

```text
reports/hermes-agent/plugin-output-artifacts/
```

### 方式 A：plugins 目录（推荐手工）

1. 将整个目录拷到实例数据盘，例如：

```text
<HERMES_DATA>/plugins/hermes-output-artifacts/
  pyproject.toml
  hermes_output_artifacts/
    __init__.py
    plugin.py
    upload.py
    refs.py
```

2. 确保包可被 Hermes 加载（与现有 `nodeskclaw` 等插件同级规则一致）。若运行时用 entry-point，见方式 B。

3. 在 `config.yaml` 启用插件（见第 3 节）。

### 方式 B：pip 可编辑安装（容器内）

```bash
# 在 hermes 容器 / venv 内
pip install -e /path/to/hermes-output-artifacts
```

`pyproject.toml` 已声明：

```toml
[project.entry-points."hermes_agent.plugins"]
output_artifacts = "hermes_output_artifacts.plugin"
```

安装后重启 Hermes / API Server 进程或容器，使插件 `register()` 执行。

## 3. 配置

### 3.1 推荐：MinIO / S3（`agent-runtime-export`）

`agent-runtime-export` 是 **全体 agent runtime 专用 bucket**，不要复用 Backend 工作区/附件的 `S3_BUCKET`。

插件 `upload_mode=s3`（`minio` 同义）走 S3 PutObject + SigV4；默认 **path-style** + **presigned GET**。

若 Hermes 容器里已经有正在使用的 `MINIO_ENDPOINT_URL` / `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` / `MINIO_BUCKET` / `MINIO_REGION`，插件会在 `HERMES_ARTIFACT_S3_*` 为空时回读这些变量。仍建议显式写：

```bash
HERMES_ARTIFACT_UPLOAD_MODE=s3
HERMES_ARTIFACT_S3_ENDPOINT=http://<MINIO-HOST>:9010
HERMES_ARTIFACT_S3_BUCKET=agent-runtime-export
HERMES_ARTIFACT_S3_REGION=us-east-1
HERMES_ARTIFACT_S3_ACCESS_KEY=<MINIO_ACCESS_KEY>
HERMES_ARTIFACT_S3_SECRET_KEY=<MINIO_SECRET_KEY>
HERMES_ARTIFACT_S3_ADDRESSING=path
HERMES_ARTIFACT_S3_PRESIGN=true
HERMES_ARTIFACT_S3_PRESIGN_EXPIRES=3600
HERMES_ARTIFACT_PUBLIC_BASE_URL=http://<MINIO-HOST>:9010/agent-runtime-export
HERMES_ARTIFACT_MAX_BYTES=10485760
HERMES_ARTIFACT_REQUIRED_DEFAULT=true
HERMES_ARTIFACT_EXT_ALLOW=.md,.txt,.json,.png,.pdf,.csv,.docx,.pptx,.xlsx
```

对象 key：`[<prefix>/]<run_id>/<filename>`。  
`output_refs.url`：默认是 MinIO **presigned GET**（带签名查询串，有效期 `PRESIGN_EXPIRES` 秒）。Agent 必须在过期前 ingest（通常在终态立即拉取）。

MinIO 侧确认：

1. bucket `agent-runtime-export` 已存在
2. 所用 AK/SK 对该 bucket 有 `s3:PutObject`；presign GET 需要 `s3:GetObject`
3. **不要**把整个 bucket 匿名可写
4. Hermes 主机能访问 `<MINIO-HOST>:9010`（同机可用 `http://127.0.0.1:9010`，但 `output_refs` 必须填 **Agent 能访问的地址**，通常是局域网 IP/主机名，不能用 Hermes 容器内部的 `localhost`）

依赖：容器内 `pip install boto3`（`pyproject.toml` 已声明）。

### 3.2 HTTP 备选（非 MinIO）

仅当不用 S3 时：

```bash
HERMES_ARTIFACT_UPLOAD_MODE=http
HERMES_ARTIFACT_UPLOAD_URL=https://files.example.com/api/v1/upload
HERMES_ARTIFACT_PUBLIC_BASE_URL=https://files.example.com/objects
HERMES_ARTIFACT_UPLOAD_TOKEN=<UPLOAD_TOKEN>
```

### 3.3 config.yaml 片段

合并 `config/config.snippet.yaml`。密钥不要写进 yaml。备份现有 `config.yaml` 后再改。

Agent 若要从内网 MinIO 拉对象，还须按 `AGENT-SIDE-REQUIREMENTS.md` 配置 origin allowlist；**只装 Hermes 插件不够**。

## 4. 可选：终态门禁镜像补丁

若仅靠插件 monkeypatch 在你环境不稳定，应用 `patches/` 中说明：

- `patches/README.md` — 改哪些函数、为何改
- `patches/api_server_terminal_gate.md` — 补丁片段与手工合并步骤

原则：在真正写入 `completed` 之前 `await` / 同步 flush 上传队列，并 merge `output_refs`。

## 5. 验证步骤（手工）

### 5.1 插件已加载

重启后看 Hermes 日志应出现类似：

```text
[output-artifacts] registered; mode=s3; s3_endpoint='http://<MINIO-HOST>:9010'; s3_bucket='agent-runtime-export'; ...
```

### 5.2 Native run + status

用短 prompt 让模型写一个文件（或你已知会落盘的工具），然后：

```bash
# 创建 run（按你实例实际 API 调整）
curl -sS -X POST "http://<LAN-HOST>:29401/v1/runs" \
  -H "Authorization: Bearer <API_SERVER_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Write hello to out/hello.txt then stop."}'

# 轮询
curl -sS -H "Authorization: Bearer <API_SERVER_KEY>" \
  "http://<LAN-HOST>:29401/v1/runs/<run_id>"
```

期望终态 JSON 含：

```json
"output_refs": [
  {
    "name": "hello.txt",
    "url": "http://<MINIO-HOST>:9010/agent-runtime-export/<run_id>/hello.txt?X-Amz-Algorithm=...",
    "required": true
  }
]
```

且 `url` 为绝对地址；`status` 为成功仅当上传完成。

### 5.3 Agent 端

走员工 MCP `tools/call` → Native：期望出现对应 artifact，大小与对象一致；SSE 无文件服务器直链。

### 5.4 回滚

1. `plugins.output_artifacts.enabled: false` 或卸载包  
2. 若打了镜像补丁：按 `patches/` 回滚备份的 `api_server.py`  
3. 重启；新 run 不应再带本插件 refs

## 6. 与 spike 的差异

| | Spike | 本包 |
|--|-------|------|
| refs URL | 硬编码公网 RFC | MinIO `agent-runtime-export` presigned GET（或 HTTP 文件服务器 URL） |
| 用途 | 证明 Agent ingest | 生产可配置交付 |
| 终态门禁 | 无 | 有（插件 + 可选补丁） |
| 残留 | 已复原 | 由你控制启停 |
