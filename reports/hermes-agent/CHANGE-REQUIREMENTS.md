# 修改需求总表（给 Hermes 配置 / 配件 / 补丁负责人）

本文是 PRD 的执行清单，与 `INSTALL.md` 配套。

## A. Hermes 必须改 / 必须配

| # | 项 | 类型 | 交付位置 |
|---|----|------|----------|
| A1 | 安装 `hermes-output-artifacts` 插件 | 配件 | `plugin-output-artifacts/` |
| A2 | 配置 MinIO/S3（`agent-runtime-export`）或 HTTP 上传 | 配置 | `config/env.example` + `config.snippet.yaml` |
| A3 | 启用插件并重启 API Server | 配置 | `INSTALL.md` §2–3 |
| A4 | 终态 merge 绝对 URL `output_refs` | 代码（插件） | `plugin.py` monkeypatch |
| A5 | upload + refs 完成前禁止成功终态 | 代码（插件或补丁） | `plugin.py` + `patches/api_server_terminal_gate.md` |
| A6 | 产物收集（tool path / 手工 track） | 代码 + 运维 | `plugin.py` hooks + `patches/hook_track_example.sh` |

## B. 文件服务器必须提供

推荐 **已在使用的 MinIO**，独立 bucket `agent-runtime-export`（全体 agent runtime）。

| # | 项 |
|---|----|
| B1 | S3 PutObject（path-style）+ 可 GET 的绝对 URL（默认 presigned） |
| B2 | bucket 与 AK/SK 权限：`s3:PutObject`、`s3:GetObject` |
| B3 | Agent 主机网络可达该 URL（内网 MinIO 必须配 Agent origin allowlist） |
| B4 | 不复用 Backend 工作区/附件存储 bucket |

## C. NoDeskClaw Agent（本仓，另开实现）

| # | 项 | 何时必须 |
|---|----|----------|
| C1 | 公网绝对 URL ingest | 已 PASS（spike） |
| C2 | origin/host allowlist | 文件服务器为内网时 |
| C3 | 不对前端暴露文件服务器 URL | 始终 |

详见 `AGENT-SIDE-REQUIREMENTS.md`。

## D. 明确禁止

- 生产残留 spike 硬编码 RFC URL monkeypatch
- 相对路径当作正式 `output_refs.url`
- 未上传成功却 `completed`
- 把真实 API Key / upload token 写进本仓库

## E. 验收对照

见 PRD §7 AC-1～AC-6；spike 历史结果见 `TEST-RESULTS-SPIKE.md`。
