# hermes-plugin-nodeskclaw-knowledge

Hermes Agent v0.21 目录插件：通过 `knowledge.retrieve` 调用 nodeskclaw-knowledge 已有 Retrieval API。

本 README **只提供运维操作说明**。插件与本需求 **不负责** 创建/写入/轮换 `~/.hermes/.env`，不签发 JWT，不向 Session 写入 `knowledge_set_id`。

## 安装

将本目录拷贝或符号链接到：

```text
~/.hermes/plugins/hermes-plugin-nodeskclaw-knowledge/
```

## 配置 ~/.hermes/.env（运维自行维护）

```bash
SMC_KB_API_URL=http://nodeskclaw-knowledge:4530
SMC_KB_API_TOKEN=<backend登录后的用户JWT>
```

- `SMC_KB_API_URL` 仅为 origin（scheme://host:port），不要带 `/api/v2`
- `SMC_KB_API_TOKEN` 为 nodeskclaw-backend（默认 4510）登录后的用户 JWT
- Token 过期后：更新 `.env` 并执行 `hermes gateway restart`

## 可选：~/.hermes/config.yaml

```yaml
plugins:
  enabled:
    - nodeskclaw-knowledge
  nodeskclaw-knowledge:
    enabled: true
    config:
      url: ${SMC_KB_API_URL}
      token: ${SMC_KB_API_TOKEN}
```

插件读取顺序：`config.url` / `config.token` 优先，缺省回退环境变量 `SMC_KB_*`。

## 启用与检查

```bash
hermes gateway restart
hermes tools list
```

应能看到 `knowledge.retrieve`。

## Tool 参数

| 参数 | 说明 |
|------|------|
| `query` | 必填 |
| `knowledge_set_id` | 可选；缺省回退 Session `knowledge_context.knowledge_set_id`（由应用注入） |
| `top_k` | 可选，默认 10 |

鉴权：请求头 `Authorization: Bearer <SMC_KB_API_TOKEN>`，Knowledge 侧走 `get_member_context`（与 Desktop/Portal 相同）。
