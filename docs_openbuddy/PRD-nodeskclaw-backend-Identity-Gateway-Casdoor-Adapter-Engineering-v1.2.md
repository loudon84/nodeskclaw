---
title: "nodeskclaw-backend Identity Gateway + Casdoor Adapter Engineering PRD"
prd_id: "SMC-IDG-NODESKCLAW-001"
version: "v1.2"
status: "APPROVED_FOR_PLAN"
project: "smc-copilot Enterprise Agent OS"
repository: "loudon84/nodeskclaw/nodeskclaw-backend"
priority: "P0"
updated_at: "2026-10-12"
---

# nodeskclaw-backend Identity Gateway + Casdoor Adapter Engineering PRD v1.2

## 0. 文档定位

本文是 nodeskclaw-backend 内 Casdoor 桌面登录的实现契约。SMC Identity Gateway（统一身份入口）是该后端里的逻辑边界，不是新进程。

`PRD-SMC-Identity-Gateway-Casdoor-Provider-Adapter-v1.1.md` 状态为 CANCELLED，不进入 Plan，不作为实现依据。本文第 0.5 节吸收了该文第 4–9 节在取消前已确认的行为，并写上 grilling Q1–Q23。

`PRD-SMC-Identity-Gateway-Identity-Provider-Adapter-v1.2.md` 与 `PRD-nodeskclaw-backend-Identity-Gateway-Casdoor-Adapter-文件级改造方案-v1.0.md` 不是本 Plan 的契约。

## 0.5 Grilling Decisions

grilling Q1–Q23 全选「是」。后文与本节冲突时，以本节为准。

```text
D-001 桌面登录是系统浏览器 + 本机 return_to + 兑换。GET /api/v1/auth/casdoor/login 校验 return_to 后创建 10 分钟事务并 302 到 Casdoor。GET /api/v1/auth/casdoor/callback 不返回 LoginResponse。成功时 302 到 return_to?code=。OpenBuddy POST /api/v1/auth/casdoor/exchange 才得到与邮箱登录相同的 ApiResponse，data 为 LoginResponse。发给 Casdoor 的 redirect_uri 只有后端 callback。
D-002 member_user 就是现有 users 行。identity_binding.member_user_id 外键指向 users.id，不级联删除。首次匹配对邮箱去首尾空白并转小写，只匹配未删除、is_active 为 true、邮箱非空的行。不新建 member_user 表。工号登录 account-login 行为不变。
D-003 配置一套 Casdoor 应用：CASDOOR_ISSUER、CASDOOR_CLIENT_ID、CASDOOR_CLIENT_SECRET、CASDOOR_REDIRECT_URI。端点只从 {issuer}/.well-known/openid-configuration 发现。新建 identity_binding，不复用 user_oauth_connections。软删除。未删除记录上 (provider, provider_org, provider_user_id) 唯一，且同一 users.id 同时只有一条 provider=casdoor 的绑定。登录事务放 PostgreSQL。唯一约束使用 deleted_at IS NULL 的部分唯一索引。
D-004 路由在 app/api/casdoor_auth.py，只挂到 api_router 的 /auth，不挂 admin_router。Casdoor HTTP 在 app/services/identity/casdoor_client.py。绑定与登录事务在 app/services/identity/binding_service.py。JWT 仍走现有 auth_service 发牌函数。模型是 app/models/identity_binding.py 与 app/models/oauth_login_transaction.py。不建 app/routers、app/auth，也不建第二份 identity_service。
D-005 provider 固定为 casdoor。provider_org 取 userinfo.owner。provider_user_id 取 userinfo.sub，且 sub 去空白后不得含「/」、不得为空。含「/」或为空则本次登录失败，机器码 idp_failed，不写绑定。owner 只进绑定键，不改 users.current_org_id。owner 去空白后为空则 org_missing。
D-006 本轮只做 Casdoor 适配器。不建 IdentityProvider 接口，不做 Local、LDAP、企业微信、Azure AD Provider。JWT 载荷保持 sub、exp、type。门户不加 Casdoor 登录按钮，也不新增门户词条。工号登录继续直接进入 auth_service。本轮不做过期事务清理任务，不加登录频率限制。
D-007 四项配置任一为空：不发起发现、换票或 userinfo。login 与 exchange 返回 API 错误 errors.auth.casdoor_not_configured。callback 若能认出 return_to，则 302 到 return_to?error=idp_failed，否则不重定向。.env.example 这四项留空。
D-008 API 失败使用 BadRequestError，HTTP 400，error_code 40000。message_key 为：非法 return_to 用 errors.auth.casdoor_return_to_invalid；兑换失败用 errors.auth.casdoor_login_expired；未配置用 errors.auth.casdoor_not_configured；无密码解绑用 errors.auth.casdoor_password_required。浏览器跳转只使用第 8 节机器码。测试用假的发现文档、换票和 userinfo，覆盖拒绝场景和工号登录回归，不连接真实 Casdoor。
D-009 字符串长度：provider 32；provider_org、provider_user_id、state、code_verifier 128；email 与 return_to 256；exchange_code_hash 64。主键与 deleted_at 使用 BaseModel。
D-010 授权请求固定 response_type=code、code_challenge_method=S256、scope=openid profile email，不带 prompt。邮箱只读 userinfo.email，不从 id_token 补。
D-011 callback 认出 state 后，若查询串有 error 或没有 code，立即把该事务标成 state 已使用，并 302 到 return_to?error=idp_failed。认不出 state 时不重定向。不回传 Casdoor 的 error_description。
D-012 已有绑定指向的 users 行已软删除或不存在时，拒绝登录，机器码 account_disabled，不更新 last_login_at，不用当前邮箱改绑到另一个用户。首次绑定匹配时排除停用用户，结果是 member_not_found。已绑定用户后来被停用，结果是 account_disabled。
D-013 首次绑定只把 userinfo 中 JSON 布尔值 true 当作 email_verified。缺字段、false 或字符串 "true" 均为 email_unverified。不验证 id_token 签名。身份只采用令牌端点换到的 access token 去读 userinfo。
D-014 未删除记录上，state 唯一。exchange_code_hash 在非空且未删除时唯一。发现、换票、userinfo 每次登录重新请求，单次超时 10 秒，超时按 idp_failed。进程内不缓存发现文档。
D-015 POST /api/v1/auth/casdoor/exchange 的 JSON 只有 code。成功响应与 POST /api/v1/auth/login 相同：ApiResponse，code 为 0，data 为 LoginResponse。
D-016 令牌端点使用 application/x-www-form-urlencoded，字段为 grant_type=authorization_code、code、redirect_uri、client_id、client_secret、code_verifier。不使用 Authorization: Basic。redirect_uri 与 CASDOOR_REDIRECT_URI 完全一致。
D-017 Casdoor 路由只注册在 api_router 的 /auth。管理端不提供这组接口。
D-018 登录事务列名为 state、code_verifier、return_to、expires_at（10 分钟）、exchange_code_hash、exchange_expires_at（60 秒）、used_at，另加 D-019 的 exchange_used_at 与 D-022 的 member_user_id，以及 BaseModel 的 id、created_at、updated_at、deleted_at。绑定表邮箱快照列名是 email，不是 email_snapshot，且没有 status 列。API message 为：回调地址无效；登录已失效，请重新发起登录；企业单点登录未配置；请先设置密码后再解除绑定。
D-019 used_at 表示 callback 已认出 state 并立即作废，更新条件是 used_at 仍为空。exchange_used_at 表示兑换码已使用。exchange 仅当 used_at 已写入、exchange_used_at 仍为空、兑换未过 60 秒、事务未过期时签发 LoginResponse，成功后立即写入 exchange_used_at。再次兑换返回 errors.auth.casdoor_login_expired。重复 callback 在仍能认出 return_to 时使用机器码 login_expired。
D-020 return_to 必须同时满足：协议正好是 http；主机正好是小写的 127.0.0.1 或 localhost；端口必须出现且为 1 到 65535 的整数；路径正好是 /callback；不能带用户名、密码、查询串、片段或结尾斜杠。否则 login 返回 errors.auth.casdoor_return_to_invalid，不建事务、不重定向。跳到 Casdoor 和跳回 return_to 的响应都带 Cache-Control: no-store 与 Referrer-Policy: no-referrer。
D-021 DELETE /api/v1/auth/casdoor/binding 只处理已登录用户自己的绑定。password_hash 为空时返回 errors.auth.casdoor_password_required，绑定保持不动。没有未删除绑定时也返回成功的 ApiResponse，code 为 0，data 为空。有绑定且已有密码时软删除后返回同一成功体。不提供管理员解除他人绑定。解除后，同一 Casdoor 主体再次登录按首次绑定处理。
D-022 oauth_login_transaction.member_user_id 可空，外键指向 users.id，不级联删除。只在绑定成功、准备 302 回桌面端时写入。兑换码原文做 SHA-256 十六进制哈希写入 exchange_code_hash。Casdoor 换票一旦结束（成功或失败），立刻清空 code_verifier。exchange 用哈希找到该行后，再检查用户未软删除、is_active 为 true、当前 users.email 仍通过 LOGIN_EMAIL_WHITELIST、对应 Casdoor 绑定仍在。任一失败返回 errors.auth.casdoor_login_expired，不发 JWT。通过后才写 exchange_used_at 并返回 LoginResponse。事务不保存 Casdoor 令牌。
D-023 callback 里绑定判断通过后，立刻写入或更新 identity_binding（含 email 快照），并把 member_user_id 与兑换码哈希写入登录事务，提交数据库，再 302。此时不改 users.last_login_at，也不写 auth.login 审计。exchange 校验通过并签发 JWT 之后，才同时更新 users.last_login_at 与 identity_binding.last_login_at，审计 details.method 为 casdoor。桌面端未兑换或兑换失败时，绑定可以已经存在，但不算成功登录。同一时刻两条首次绑定撞上唯一索引时，失败的那次使用 binding_conflict。日志不记录授权码、code_verifier、Casdoor 令牌和 client secret。Casdoor 登录不清除 must_change_password。
```

# 1. Executive Summary

## 1.1 Background

当前 nodeskclaw-backend 已具备企业用户体系：

- `users`（本文沿用「成员」称呼；不存在单独的 member_user 表）
- 工号登录 `/auth/account-login`
- `auth_service`
- JWT 认证
- Workspace Member
- Role / Permission

OpenBuddy 桌面端需要通过 Casdoor 登录，并拿到与邮箱登录相同的 `LoginResponse`。

## 1.2 Design Principle

1. 成员事实源是 `users`。
2. Casdoor 不是用户中心，只作为 OIDC Identity Provider（身份提供者）。
3. 不要求员工在 Casdoor 注册，也不把员工同步到 Casdoor。
4. 不新增独立 Identity 服务。
5. Identity Gateway 位于 nodeskclaw-backend 内部。

# 2. Current System Analysis

工号登录保持：

```text
Employee
    |
account-login
    |
auth_service
    |
users
    |
JWT
```

邮箱登录成功体是 `ApiResponse`，`data` 为 `LoginResponse`（`access_token`、`refresh_token`、`user` 等）。Casdoor 兑换成功时使用同一形态。刷新仍走 `POST /api/v1/auth/refresh`。

# 3. Scope

## 3.1 In Scope

- Casdoor OIDC 适配器
- `identity_binding`
- `oauth_login_transaction`
- `GET /api/v1/auth/casdoor/login`
- `GET /api/v1/auth/casdoor/callback`
- `POST /api/v1/auth/casdoor/exchange`
- `DELETE /api/v1/auth/casdoor/binding`
- OpenBuddy 桌面端系统浏览器登录

## 3.2 Out Of Scope

- 替换 `users`、workspace、role、permission
- 创建 Casdoor 账号或同步员工
- LDAP、Azure AD、企业微信、Local Provider、`IdentityProvider` 接口
- 修改 JWT 载荷
- 门户 Casdoor 按钮与门户词条
- Hermes Skill 权限
- 管理员解除他人绑定
- 过期事务清理任务与新的登录频率限制
- 连接真实 Casdoor 的自动化测试

# 4. Target Architecture

```text
OpenBuddy Desktop
        |
系统浏览器 GET /api/v1/auth/casdoor/login
        |
nodeskclaw-backend
        |
Casdoor（发现、授权、换票、userinfo）
        |
identity_binding -> users
        |
302 return_to?code=
        |
POST /api/v1/auth/casdoor/exchange
        |
现有 auth_service 发牌
```

# 5. Source Of Truth

| Domain | Source |
| --- | --- |
| Employee Account | `users` |
| Password | `auth_service` / `users.password_hash` |
| Permission | existing permission tables |
| Workspace | workspace member |
| External Identity | `identity_binding` |
| SSO Identity | Casdoor userinfo |

# 6. Business Rules

## BR-001 User Ownership

SMC 用户必须已存在于 `users`。Casdoor 用户不等于 SMC 用户。禁止创建 User、Workspace、Role。

## BR-002 First Binding

没有未删除绑定时：

1. userinfo 含 `email`
2. `email_verified` 为 JSON 布尔值 `true`
3. `owner` 去空白后非空
4. `sub` 去空白后非空且不含 `/`
5. 邮箱标准化后匹配未删除、`is_active`、邮箱非空的 `users`
6. 该用户还没有另一条 `provider=casdoor` 的未删除绑定
7. 当前 `users.email` 通过与邮箱登录相同的 `LOGIN_EMAIL_WHITELIST` 检查；邮箱为空同样拒绝

callback 在写入绑定和兑换码之前做第 7 步。失败时 302 到 `error=domain_not_allowed`，不写兑换码，不更新 `last_login_at`，也不在这次失败里改邮箱快照。exchange 按 D-022 再查一次；这 60 秒内白名单或成员状态变化导致的失败，返回 `errors.auth.casdoor_login_expired`。

## BR-003 Binding Sticky

绑定键是 `provider` + `provider_org` + `provider_user_id`。绑定后不因 Casdoor 邮箱变化修改 `member_user_id`。再次登录不再检查 `email_verified`，但仍在写兑换码前执行 BR-002 第 7 步的白名单检查。解除绑定后，同一主体再次登录按首次绑定处理。

## BR-004 Login Success Timing

绑定行在 callback 提交。`users.last_login_at`、`identity_binding.last_login_at` 和 `auth.login`（`details.method=casdoor`）只在 exchange 成功签发 JWT 后写入。

# 7. Domain Model

## identity_binding

| 字段 | 说明 |
| --- | --- |
| id | BaseModel 主键 |
| member_user_id | `users.id`，不级联删除 |
| provider | `casdoor`，长度 32 |
| provider_org | userinfo.owner，长度 128 |
| provider_user_id | userinfo.sub，长度 128 |
| email | Casdoor 邮箱快照，长度 256，不是匹配键 |
| last_login_at | 仅 exchange 成功时更新 |
| created_at / updated_at / deleted_at | BaseModel |

未删除记录上：

- `(provider, provider_org, provider_user_id)` 唯一
- `member_user_id` 在 `provider=casdoor` 时唯一

没有 `status` 列。

## oauth_login_transaction

| 字段 | 说明 |
| --- | --- |
| id / created_at / updated_at / deleted_at | BaseModel |
| state | 长度 128，未删除记录上唯一 |
| code_verifier | 长度 128，换票结束后清空 |
| return_to | 长度 256 |
| expires_at | 创建后 10 分钟 |
| exchange_code_hash | SHA-256 十六进制，长度 64；非空且未删除时唯一 |
| exchange_expires_at | 兑换码 60 秒 |
| used_at | callback 认出 state 时写入 |
| exchange_used_at | exchange 成功时写入 |
| member_user_id | 可空，绑定成功时写入，外键 `users.id`，不级联删除 |

过期或已使用的记录标记失效，不物理删除。

# 8. API Contract

浏览器失败只带机器码，不带令牌，不带 Casdoor 原文：

| 机器码 | 条件 |
| --- | --- |
| `email_missing` | userinfo 没有邮箱 |
| `email_unverified` | 首次绑定且 `email_verified` 不是 JSON `true` |
| `member_not_found` | 没有匹配的可用成员 |
| `binding_conflict` | 成员已有另一条 Casdoor 绑定，或唯一索引冲突 |
| `org_missing` | 没有 `owner` |
| `account_disabled` | 已绑定用户停用，或绑定指向的用户已软删除、不存在 |
| `domain_not_allowed` | 当前成员邮箱不在白名单，或邮箱为空 |
| `login_expired` | 事务过期、state 已使用，或兑换码无效、过期、已使用 |
| `idp_failed` | 未配置、发现、换票、userinfo 失败，Casdoor 返回 error，缺少 code，或 `sub` 不是不可变用户 id |

## GET /api/v1/auth/casdoor/login

查询参数 `return_to`。符合 D-020 才创建事务并 302 到 Casdoor。否则返回 `errors.auth.casdoor_return_to_invalid`，message 为「回调地址无效」。

## GET /api/v1/auth/casdoor/callback

1. 认不出 `state`：不重定向。
2. 事务已过期，或 `used_at` 已经有值：在仍能认出 `return_to` 时 302 到 `error=login_expired`，不再换票。过期且 `used_at` 仍为空时，先写入 `used_at` 再跳转。
3. 本次请求成功把空的 `used_at` 写成当前时间后，若查询串有 `error` 或没有 `code`：302 到 `error=idp_failed`。
4. 按 D-016 换票，读 userinfo，执行第 6 节。换票结束清空 `code_verifier`。
5. 绑定判断通过：写入或更新 `identity_binding`，写入 `member_user_id` 与兑换码哈希，提交后 302 到 `return_to?code={原文}`。
6. 绑定或身份源失败：302 到 `return_to?error={机器码}`，不写兑换码。

本接口不生成 `LoginResponse`。

## POST /api/v1/auth/casdoor/exchange

请求体只有 `{ "code": "..." }`。按 D-022 校验。成功返回 `ApiResponse` + `LoginResponse`，并写入登录时间与审计。失败返回 `errors.auth.casdoor_login_expired`，message 为「登录已失效，请重新发起登录」。

## DELETE /api/v1/auth/casdoor/binding

已登录用户软删除自己的 Casdoor 绑定。无密码时 message 为「请先设置密码后再解除绑定」。没有绑定也返回 `code=0`、`data` 为空的成功体。

未配置时的 message 为「企业单点登录未配置」。

# 9. Security Design

- Authorization Code Flow（授权码流程）
- PKCE S256。`code_verifier` 可回读，直到换票结束
- `state` 放在 PostgreSQL，认出来即作废
- `return_to` 按 D-020 限制为本机回调
- 重定向响应 `Cache-Control: no-store`、`Referrer-Policy: no-referrer`
- client secret 只出现在发往 Casdoor 的表单正文和环境配置
- Casdoor access token 与 refresh token 不入库、不返回桌面端、不作业务令牌
- 兑换码原文只出现在跳回桌面端的查询串中，库中只存 SHA-256

# 10. File Level Change Plan

新增：

```text
app/api/casdoor_auth.py
app/services/identity/casdoor_client.py
app/services/identity/binding_service.py
app/models/identity_binding.py
app/models/oauth_login_transaction.py
```

修改：

```text
app/api/router.py          只在 api_router 注册 /auth
app/core/config.py         四项 CASDOOR_* 配置
.env.example               四项留空
alembic migration
tests                      假 Casdoor HTTP
```

`app/api/auth.py` 的 `account_login` 不改行为。发牌继续调用现有 `auth_service`。

# 11. Test Plan

使用假的发现文档、令牌端点和 userinfo。覆盖：

- 合法 `return_to` 得到 Casdoor 302，非法地址得到 `casdoor_return_to_invalid` 且不建事务
- callback 成功只 302 带 `code`，exchange 返回与邮箱登录相同的 `ApiResponse`
- 邮箱未验证、用户不存在、组织缺失、`sub` 含 `/`、重复绑定、停用、软删除用户、域名不允许
- state 过期、重复 callback、兑换码重放、未配置不访问网络
- 无密码拒绝解绑，无绑定解绑仍成功
- 绑定写在 callback，登录审计只出现在 exchange 成功之后
- 工号登录回归

# 12. Acceptance Criteria

- AC-001：已有匹配成员可以完成 Casdoor 登录，并得到现有 `LoginResponse`。
- AC-002：不存在匹配成员时拒绝，不创建用户、workspace 或角色。
- AC-003：工号登录、邮箱登录、短信登录、刷新、`/me`、`/logout` 保持可用。
- AC-004：OpenBuddy 只配置 backend 根地址；`LoginResponse` 只从 exchange 获得。
- AC-005：callback 的浏览器响应是 302，不包含 JWT 或 Casdoor 令牌。
- AC-006：无密码成员不能解绑；有密码成员可以软删除自己的绑定。

# 13. Release Gate

- Migration 成功
- 第 11 节测试通过
- 安全检查确认 Casdoor 令牌与 client secret 不进入桌面端、日志和业务表
- 工号登录回归通过

# 14. Implementation Plan

1. 数据库迁移：两张表、部分唯一索引、外键。
2. 绑定与登录事务服务。
3. Casdoor 发现、换票、userinfo 客户端。
4. 四个认证接口，只挂在 `api_router`。
5. 假 Casdoor 的接口测试与工号登录回归。

当前状态是 `APPROVED_FOR_PLAN`。可以按第 0.5 节生成本仓 Plan。
