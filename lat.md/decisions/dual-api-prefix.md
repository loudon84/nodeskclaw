# Dual API Prefix

Portal 与管理后台共享路由处理函数，但挂载在 `/api/v1` 与 `/api/v1/admin` 两套前缀下，成员体系分离。

Portal 使用 `org_memberships`；Admin 使用 `admin_memberships`。统计 Portal 用户时必须排除 admin-only 成员。

## Why

双前缀避免复制整套 handler，同时强制管理端与租户端鉴权表隔离，降低「管理员身份串到组织成员」的风险。

新增需管理端暴露的 API 时，确认前缀挂载与角色校验成对出现，而不是只挂一边。
