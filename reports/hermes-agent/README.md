# Hermes Agent — 产物上传 + `output_refs` 交付包

本目录独立于 RM-20 实现 Plan，供你在 **Hermes 实例上手工安装 / 配置 / 补丁**。

**约束（执行方已遵守）：**

- 不连接、不修改你的 live 实例（含 `192.168.102.247:29401`）
- 不依赖 spike monkeypatch 作为正式方案；本包提供可安装插件 + 可选镜像补丁
- 文档中的 API Key / 内网地址一律用占位符；请勿把真实 Key 写进仓库

## 目录结构

| 路径 | 说明 |
|------|------|
| [`PRD-hermes-output-artifacts-v1.0.md`](./PRD-hermes-output-artifacts-v1.0.md) | 需求 PRD（上传、refs、终态门禁、Agent allowlist） |
| [`INSTALL.md`](./INSTALL.md) | 实例侧配置 + 插件安装 + 验证步骤 |
| [`AGENT-SIDE-REQUIREMENTS.md`](./AGENT-SIDE-REQUIREMENTS.md) | NoDeskClaw Agent 侧配套改动清单（公网已通 / 内网需 allowlist） |
| [`TEST-RESULTS-SPIKE.md`](./TEST-RESULTS-SPIKE.md) | 局域网 spike 验证结果（ingest 已 PASS） |
| [`config/`](./config/) | `config.yaml` / 环境变量示例 |
| [`plugin-output-artifacts/`](./plugin-output-artifacts/) | 正式插件源码包（可 `pip install` 或拷进 plugins 目录） |
| [`hermes-output-artifacts-0.2.0.zip`](./hermes-output-artifacts-0.2.0.zip) | 插件压缩包（含 MinIO/S3 模式），便于拷贝到实例 |
| [`patches/`](./patches/) | 可选：`api_server` 终态门禁补丁说明与片段 |
| [`tests/`](./tests/) | 本地单元自检脚本（不连实例） |

## 目标 runtime

- Hermes Agent Runtime：**v0.21（v2026.8.31）**
- Native API Server（局域网对外访问示例，请按你的环境替换）：
  - `API_SERVER_URL=http://<LAN-HOST>:29401`
  - `API_SERVER_KEY=<your-key>`（勿提交到 Git）

## 一句话方案

Hermes 在 run 结束前把产物上传到 **MinIO bucket `agent-runtime-export`（全体 agent runtime 专用）** 或 HTTP 文件服务器，在 `GET /v1/runs/{id}` 终态里合并 **绝对 URL** 的 `output_refs`；Agent 拉取字节入库后只暴露 `artifact_id`；**upload + refs 写完后再 `completed`**。
