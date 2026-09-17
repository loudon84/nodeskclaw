# PRD：Hermes 产物上传与 Native `output_refs`（v1.0）

| 字段 | 值 |
|------|-----|
| 文档 ID | PRD-HERMES-OUTPUT-ARTIFACTS-v1.0 |
| 状态 | DRAFT（供实例侧配置 / 插件 / 补丁验收） |
| 关联 | 独立于 RM-20；消费方为 NoDeskClaw Agent Native ingest |
| 目标 Runtime | Hermes Agent v0.21（v2026.8.31） |
| 日期 | 2026-09-12 |

## 1. 背景与问题

员工侧 skill-run 走 **MCP `tools/call` → Agent Native `POST /v1/runs` + SSE + `GET /v1/runs/{id}`**，不靠 chat completions，也不靠 Agent 扫描 Hermes workspace。

现状（V10 / live）：Hermes Native 终态常为 `completed`，但 **无结构化 `output_refs`**。Agent 只能落盘极小的 `result.txt`（约 27 字节文案），UI 侧可见的 workspace 文件无法作为正式产物入库。

Spike（已复原）证明：当终态 status 含 **公网绝对 URL** 的 `output_refs` 时，Agent ingest **PASS**（见 `TEST-RESULTS-SPIKE.md`）。

## 2. 目标

1. **Hermes**：把本 run 产物上传到配置的文件服务器（**MinIO/S3 为推荐主路径**；HTTP multipart 备选；MCP 可选）。
2. **Hermes**：终态 `GET /v1/runs/{id}` 的 status 合并 **绝对 URL** 的 `output_refs`（正式插件或镜像补丁，禁止再依赖临时 spike monkeypatch）。
3. **Agent**：公网 URL 已通；若文件服务器在内网，增加 **origin allowlist**（见 `AGENT-SIDE-REQUIREMENTS.md`）。
4. **终态门禁**：仅在 upload 成功且 refs 已写入后，才允许将 run 标为 `completed` / `succeeded`（修复 V10 过早 `completed`）。

## 3. 非目标

- 不新增 Hermes `GET /v1/runs/{id}/files` 作为主路径。
- 不让前端直接拿到文件服务器 URL；前端只消费 Agent 的 `artifact_id` + run 作用域下载。
- 不把相对路径 / workspace 扫描当作正式契约。
- 本 PRD 不替代 RM-20 的事件契约文档；只补 Hermes→Agent 产物桥。

## 4. 角色与边界

| 组件 | 职责 |
|------|------|
| Hermes Native API Server | 接受 `POST /v1/runs`，推 SSE，提供 `GET /v1/runs/{id}` |
| Hermes 插件 `hermes-output-artifacts` | 收集产物 → 上传文件服务器 → 注册绝对 URL refs → 门禁完成 |
| 文件服务器 | 存储字节；返回可被 Agent 拉取的 `http(s)://...` URL |
| NoDeskClaw Agent | 解析 `output_refs` → SSRF 策略校验 → `store_artifact_bytes` → 对外仅 `artifact_id` |
| Portal / 员工 UI | 只展示 Agent artifacts，不直连文件服务器 |

## 5. 功能需求

### FR-1 产物收集

- 插件须记录本 run 内产生的、应对外交付的文件（至少覆盖工具写入的常见路径：`write_file` / `bash` 落盘等到 workspace 的文件）。
- 必须绑定 `run_id`（Native run id），禁止串 run。
- 可配置：包含扩展名白名单、最大单文件大小、最大总大小、排除路径。

### FR-2 上传到文件服务器

- `HERMES_ARTIFACT_UPLOAD_MODE`：`s3`（与 `minio` 同义，推荐）| `http` | `mcp`（mcp 仍为后续）
- **S3 / MinIO**（专用 bucket `agent-runtime-export`，供全体 agent runtime，禁止复用工作区/附件 bucket）：
  - `HERMES_ARTIFACT_S3_ENDPOINT`（可回退 `MINIO_ENDPOINT_URL`）
  - `HERMES_ARTIFACT_S3_BUCKET`（可回退 `MINIO_BUCKET`，默认 `agent-runtime-export`）
  - `HERMES_ARTIFACT_S3_ACCESS_KEY` / `HERMES_ARTIFACT_S3_SECRET_KEY`（可回退 `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY`）
  - `HERMES_ARTIFACT_S3_REGION`（可回退 `MINIO_REGION`）
  - `HERMES_ARTIFACT_S3_PRESIGN`（默认 true，终态 `output_refs.url` 为 presigned GET）
  - IP 终点默认 path-style addressing
- **HTTP 备选**：
  - `HERMES_ARTIFACT_UPLOAD_URL`：multipart `file` + `run_id` + `name`
  - `HERMES_ARTIFACT_UPLOAD_TOKEN`：Bearer（可选）
- `HERMES_ARTIFACT_PUBLIC_BASE_URL`：unsigned GET 前缀；S3+presign 时仍可用于文档/回退拼装
- 上传成功后得到 **绝对 URL**（presigned GET，或 `PUBLIC_BASE_URL + object_key`）。
- 失败策略：
  - `required=true` 的产物失败 → **不得** `completed`，应 `failed` 并带错误信息。
  - 可选产物失败 → 可继续，但不得伪造 refs。

### FR-3 终态 `output_refs` 合并

`GET /v1/runs/{id}`（及内部 status 对象）在终态须包含：

```json
{
  "status": "completed",
  "output_refs": [
    {
      "name": "report.md",
      "content_type": "text/markdown",
      "url": "https://files.example.com/runs/<run_id>/report.md",
      "required": true
    }
  ]
}
```

约束：

- `url` 必须是绝对 `http:` 或 `https:` URL。
- `name` 非空；`content_type` 建议准确。
- 与既有 status 字段合并，不得覆盖掉 Agent 已依赖的其它字段。
- 实现形态：正式 **Hermes 插件**（推荐）或 **镜像内 api_server 补丁**；禁止生产环境留 spike 硬编码公网 RFC URL。

### FR-4 终态门禁（过早 completed 修复）

- 进入 `completed` / `succeeded` / `success` 之前必须：
  1. 完成本 run 的上传队列 flush；
  2. 将最终 `output_refs` 写入 status（可为空数组，但必须是「已决策」后的数组，不能是「还没写」）。
- 若仍有进行中的上传：保持 `running` / `uploading`（实现可选中间态），或延迟调用 `_set_run_status(..., completed)`。
- V10 回归验收：在人为延迟上传的情况下，不得先出现无 refs 的 `completed`。

### FR-5 Agent 消费（配套，本仓 Agent）

- 已支持：绝对 URL → 拉取 → 持久化 → SSE `artifact.persisted`（无长期公开 `download_url`）。
- 若 `HERMES_ARTIFACT_PUBLIC_BASE_URL` 指向**内网**，Agent 须增加 origin allowlist（见 `AGENT-SIDE-REQUIREMENTS.md`），默认拒绝私网 SSRF。

## 6. 非功能需求

- **安全**：上传 token 仅存实例环境 / Secret，不进 Git；日志脱敏。
- **隔离**：refs URL 不得泄漏到 Portal；仅 Agent 侧拉取。
- **可观测**：插件日志打印 `run_id`、上传对象数、失败原因；不打印完整 token。
- **兼容**：Hermes v0.21 API Server 路径 `gateway.platforms.api_server.APIServerAdapter`。

## 7. 验收标准

| ID | 标准 |
|----|------|
| AC-1 | 手工触发含写文件的 Native run；`GET /v1/runs/{id}` 终态含 ≥1 条绝对 URL `output_refs` |
| AC-2 | Agent 员工 run 出现对应 `artifact_id`，字节大小与文件服务器对象一致 |
| AC-3 | SSE `artifact.persisted` 无文件服务器 `download_url` |
| AC-4 | 上传失败（断网 / 401）时 run **不为**成功终态，或 `required` 失败显式 `failed` |
| AC-5 | 人为慢上传时，status 在 refs 就绪前不得 `completed` |
| AC-6 | 禁用插件后，新 run 不再出现本插件注入的 refs |

## 8. 配置面（实例）

见 `config/config.snippet.yaml` 与 `config/env.example`。

局域网 API 访问（由你在实例侧配置，文档仅占位）：

```text
API SERVER URL = http://<LAN-HOST>:29401
API SERVER KEY = <API_SERVER_KEY>
```

## 9. 交付物映射

| 交付物 | 路径 |
|--------|------|
| 本 PRD | `reports/hermes-agent/PRD-hermes-output-artifacts-v1.0.md` |
| 安装手册 | `reports/hermes-agent/INSTALL.md` |
| 插件包 | `reports/hermes-agent/plugin-output-artifacts/` |
| 可选补丁 | `reports/hermes-agent/patches/` |
| Spike 结果 | `reports/hermes-agent/TEST-RESULTS-SPIKE.md` |
| Agent 配套 | `reports/hermes-agent/AGENT-SIDE-REQUIREMENTS.md` |

## 10. 风险与开放问题

1. 文件服务器尚未就绪：可先用「仅 merge refs、上传 mock」模式做联调，但 AC-2 需真实字节。
2. 终态门禁若仅插件 monkeypatch `_set_run_status`，在部分升级路径可能被覆盖 → 镜像补丁作兜底。
3. 工具未走 `write_file` 而直接 bash 写盘时，收集策略需配置「workspace 扫描白名单」——v1 建议显式声明路径模式。
