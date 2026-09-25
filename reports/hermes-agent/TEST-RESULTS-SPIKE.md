# Spike 测试结果（output_refs 绝对 URL → Agent ingest）

| 项 | 值 |
|----|-----|
| 日期 | 2026-09-12 |
| 目的 | 证明 Agent 在 Native 终态含**公网绝对 URL** `output_refs` 时可 ingest |
| 实例改动 | 临时插件 monkeypatch（**已全部复原**） |
| 正式方案 | 见本目录 PRD + `plugin-output-artifacts`（勿再依赖本 spike） |

## 结论

**ingest = PASS**

| 字段 | 值 |
|------|-----|
| 员工 / Native 关联 run_id | `4542c3ab-db2e-4cfd-9dcc-77f42e44ff18` |
| spike artifact_id | `42b56c2a-5878-4602-ba6f-7073f10f4a22` |
| spike 产物大小 | `3215` bytes（RFC 1149 文本） |
| 同时存在 | `result.txt`（约 27 bytes 文案）仍可能出现 |
| SSE | `artifact.persisted` 出现；无长期公开 `download_url` |
| 复原后 | 新 completed run **不再**带 spike `output_refs` |

## 注入形态（仅历史说明）

临时将 `APIServerAdapter._set_run_status` 在 `completed`/`succeeded`/`success` 时注入：

```json
{
  "name": "spike-output-ref.txt",
  "content_type": "text/plain",
  "url": "https://www.rfc-editor.org/rfc/rfc1149.txt",
  "required": true
}
```

## 对正式方案的含义

1. **Agent 拉取绝对 URL 路径可用** — 方案 B（文件服务器 + 绝对 URL refs）在消费侧已打通。
2. **仍缺**：真实上传、按 run 动态 refs、终态门禁（避免无 refs 的过早 `completed`）。
3. **相对 URL / workspace 扫描** — 本次未作为主路径验证；正式契约不依赖它们。

## 证据落盘（仓库内）

- `.smc/runs/RM-20/spike-output-refs/verify-summary.txt`
- `.smc/runs/RM-20/spike-output-refs/plugin_init.py`（历史 spike，非生产）
- 计划笔记：`.cursor/plans/hermes_output_refs_spike_c9aeb213.plan.md`

## 安全

本结果文档**不含** API Server Key、上传 token 或内网密码。
