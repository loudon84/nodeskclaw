# Error Contract

失败响应必须同时提供 `error_code`、`message_key` 与 `message`；前端以 `message_key` 做 i18n，缺失时回退 `message`。

只要出现 `error_code` 即视为失败。禁止再把 `detail` 当作前端主展示路径。

## Message Key Shape

`message_key` 使用小写点分层：`<domain>.<module>.<action_or_reason>`（如 `errors.auth.token_invalid`）。

插值一律命名参数。Portal 请求带 `Accept-Language`。该契约连接 [[architecture/backend]] 与 [[architecture/portal]]。

## Why

统一契约让 CE/EE 多语言与多端（Portal / Admin）共享同一错误语义，避免后端中文硬编码泄漏到 UI。
