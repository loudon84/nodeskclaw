# nodeskclaw-knowledge plugins

Agent 产品侧 Hermes / 其它运行时插件统一放在本目录。

## 约定

- 每个插件一个子目录，例如 `hermes-plugin-nodeskclaw-knowledge/`
- 插件源码在本仓维护；运行时由运维拷贝或链接到目标 Agent 的 plugins 目录（Hermes: `~/.hermes/plugins/`）
- 本目录不负责写入目标机的 `.env`；密钥与 URL 由运维按各插件 README 配置

## 已有插件

| 目录 | 说明 |
|------|------|
| `hermes-plugin-nodeskclaw-knowledge/` | Hermes v0.21 `knowledge.retrieve` → nodeskclaw-knowledge API |
