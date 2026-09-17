# NoDeskClaw Agent 侧配套需求

本文件描述 **Agent**（非 Hermes）为消费 Hermes 绝对 URL `output_refs` 所需改动。  
Hermes 插件可先独立交付；若文件服务器对 Agent 主机是**公网可达 HTTPS**，现有 ingest 路径在 spike 中已验证 PASS。

## 已验证（无需再改即可用公网 refs）

- Agent 从 Native `GET /v1/runs/{id}` 读取 `output_refs`
- 对绝对 `http(s)` URL 拉取字节 → `store_artifact_bytes`
- 员工侧产物以 `artifact_id` 暴露；SSE `artifact.persisted` 不带长期公开 `download_url`

依据：`TEST-RESULTS-SPIKE.md`（run `4542c3ab-...`，artifact 3215 bytes）。

## 当文件服务器在内网时（必须做）

当前 Agent SSRF 策略通常：**拒绝私网 / 非网关私有 IP**，仅放行公网 HTTPS。  
MinIO 若只在局域网（例如 `http://<LAN-HOST>:9010`），**必须** allowlist 该 origin，否则 Hermes 已上传成功、Agent ingest 仍会被拦住。

若 `output_refs.url` / `HERMES_ARTIFACT_PUBLIC_BASE_URL` 形如：

```text
http://10.x.x.x/...
http://192.168.x.x/...
http://172.16-31.x.x/...
```

则需增加 **origin allowlist**，例如：

| 配置项（建议名） | 含义 |
|------------------|------|
| `ARTIFACT_FETCH_ORIGIN_ALLOWLIST` | 逗号分隔 origin，如 `http://10.0.0.5:8080,https://files.internal.example.com` |
| 或 `ARTIFACT_FETCH_HOST_ALLOWLIST` | 主机名/IP 白名单 |

行为：

1. URL 解析后的 origin/host **命中 allowlist** → 允许 GET（仍建议限制 method/redirect、限制最大字节）。
2. 未命中且属私网 → **拒绝**（保持默认拒绝）。
3. 未命中但为公网 → 维持现有公网策略。
4. allowlist **不得** 被前端/用户输入覆盖；仅运维配置。

## 终态竞态（Agent 侧注意）

即使 Hermes 修好「上传完成后再 completed」，Agent 仍应：

- 以终态 status 中的 `output_refs` 为准做 ingest；
- 若 `completed` 且 `output_refs` 为空：记可观测日志，不要静默当作「无产物成功」掩盖 Hermes 配置错误（产品策略可选：标记 warning artifact）。

## 明确不做

- 不把文件服务器 URL 回传 Portal。
- 不把相对 Hermes workspace 路径当作正式契约。
- 不新增对 Hermes `/files` 的依赖作为主路径。

## 验收（Agent）

| ID | 标准 |
|----|------|
| A-AC-1 | 公网绝对 URL refs → ingest PASS（已有 spike） |
| A-AC-2 | 内网 URL + allowlist → ingest PASS |
| A-AC-3 | 内网 URL 无 allowlist → 拒绝，无 SSRF 穿透 |
| A-AC-4 | 前端/API 响应无文件服务器原始 URL |
