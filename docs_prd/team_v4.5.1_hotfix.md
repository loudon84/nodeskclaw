# NoDeskClaw PRD v4.5.1：Hermes Docker Profile 管理稳定性修复

## 1. 版本信息

| 项目   | 内容                                                 |
| ---- | -------------------------------------------------- |
| 版本   | v4.5.1                                             |
| 类型   | Hotfix / 稳定性修复                                     |
| 基础版本 | v4.5                                               |
| 模块   | AI 员工 / Hermes Docker 绑定实例 / Profile 管理            |
| 目标   | 修复 v4.5 Profile 管理的状态识别、API 路径、路径安全、保存重启、审计和前端编辑保护 |
| 不包含  | 技能清单、文件管理、备份恢复、Profile 克隆导入导出、运行 Profile 切换        |

---

## 2. 当前状态

v4.5 已完成以下内容：

1. Docker Hermes 实例详情页。
2. Profile 列表扫描。
3. `default` Profile 管理。
4. `profiles/*` 扩展 Profile 扫描。
5. `.env / config.yaml / SOUL.md` 三个核心文件读取。
6. 核心文件校验、保存、备份。
7. 前端模型配置三页签。
8. Profile 选择器。
9. 创建 Profile API。
10. 删除 Profile API。

当前页面已经可以显示：

```text
default
writer-zh
```

并能读取：

```text
/data/copilot-docker/instances/common-writer/data/hermes/SOUL.md
```

但 v4.5 还存在以下问题：

1. `default` 显示为 `config_only`，未识别为当前运行 Profile。
2. 前端存在 `/hermes/agents/{profileName}` 与 `/instances/{instanceId}` 两套路由和 API 风格。
3. `.env` 校验过弱。
4. Profile 目录存在 symlink 逃逸风险。
5. 保存并重启后没有等待 Runtime 恢复。
6. 切换 Profile 或页签时，没有未保存内容保护。
7. 创建、删除、保存、重启等操作缺少审计记录。
8. 删除 Profile 保护不足。
9. 错误提示不够明确。

---

## 3. 目标

v4.5.1 目标：

1. 统一 Profile API 访问路径。
2. 正确识别 `active_runtime`。
3. 加强 `.env` 校验。
4. 加强路径安全和 symlink 防护。
5. 保存并重启后等待容器和 API Server 恢复。
6. 前端增加未保存变更保护。
7. 增加 Profile 操作审计。
8. 加强删除 Profile 的保护。
9. 修正页面状态显示和错误提示。

---

## 4. 非目标

v4.5.1 不做以下功能：

1. 不实现 Profile 技能清单。
2. 不实现 Profile 文件管理。
3. 不实现 Profile 备份恢复。
4. 不实现 Profile 克隆。
5. 不实现 Profile 导入导出。
6. 不实现运行 Profile 切换。
7. 不修改 copilot-docker 部署脚本。
8. 不改变 Docker 实例根 `.env` 的读取规则。

---

## 5. 核心规则

### 5.1 Docker 实例配置入口保持不变

NoDeskClaw 绑定 Docker Hermes 实例时，继续读取：

```text
/data/copilot-docker/instances/<instance>/.env
```

该文件继续作为容器绑定配置源，负责：

```text
容器名
WebUI 端口
Gateway 端口
WebUI 密码
Compose 文件
管理模式
HERMES_DATA_DIR
HERMES_INSTANCE_DIR
镜像与仓库参数
安装参数
```

v4.5.1 不允许模型配置页面写入该文件。

### 5.2 Hermes Runtime Profile 配置入口保持不变

`default` Profile：

```text
/data/copilot-docker/instances/<instance>/data/hermes/.env
/data/copilot-docker/instances/<instance>/data/hermes/config.yaml
/data/copilot-docker/instances/<instance>/data/hermes/SOUL.md
```

扩展 Profile：

```text
/data/copilot-docker/instances/<instance>/data/hermes/profiles/<profile>/.env
/data/copilot-docker/instances/<instance>/data/hermes/profiles/<profile>/config.yaml
/data/copilot-docker/instances/<instance>/data/hermes/profiles/<profile>/SOUL.md
```

---

## 6. 后端修复需求

## 6.1 统一 Profile API 路径

当前存在两种路径：

```text
/hermes/agents/{profileName}/profiles
/instances/{instanceId}/external-docker/profiles
```

v4.5.1 采用以下策略：

### 保留实例级 API

```http
GET    /api/instances/{instance_id}/external-docker/profiles
POST   /api/instances/{instance_id}/external-docker/profiles
DELETE /api/instances/{instance_id}/external-docker/profiles/{profile}
GET    /api/instances/{instance_id}/external-docker/profiles/{profile}/core-files/{kind}
POST   /api/instances/{instance_id}/external-docker/profiles/{profile}/core-files/{kind}/validate
PUT    /api/instances/{instance_id}/external-docker/profiles/{profile}/core-files/{kind}
```

### 新增 Agent profileName 代理 API

由于当前详情页路由是：

```text
/hermes/agents/common-writer
```

后端必须新增代理 API：

```http
GET    /api/hermes/agents/{agent_profile}/profiles
POST   /api/hermes/agents/{agent_profile}/profiles
DELETE /api/hermes/agents/{agent_profile}/profiles/{profile}
GET    /api/hermes/agents/{agent_profile}/profiles/{profile}/core-files/{kind}
POST   /api/hermes/agents/{agent_profile}/profiles/{profile}/core-files/{kind}/validate
PUT    /api/hermes/agents/{agent_profile}/profiles/{profile}/core-files/{kind}
```

代理逻辑：

```text
agent_profile
  -> 查询 Hermes Agent 绑定实例
  -> 获取 instance_id
  -> 调用实例级 Profile Service
```

若找不到实例，返回：

```json
{
  "error_code": "HERMES_AGENT_INSTANCE_NOT_FOUND",
  "message": "未找到已绑定的 Hermes Docker 实例"
}
```

---

## 6.2 active_runtime 状态识别

Profile 状态枚举调整为：

```text
active_runtime
config_only
missing_files
invalid
```

### 判断规则

输入来源：

```text
绑定实例记录 profile_name
根 .env: HERMES_PROFILE
根 .env: API_SERVER_MODEL_NAME
data/hermes/.env: HERMES_PROFILE
data/hermes/.env: API_SERVER_MODEL_NAME
/v1/models 返回的 model id
```

### MVP 判断规则

```text
1. default 对应 data/hermes 根目录。
2. 如果实例当前运行目录是 data/hermes，则 default = active_runtime。
3. 如果 API_SERVER_MODEL_NAME 等于实例 profile_name，且当前 Gateway 从 data/hermes/.env 读取，则 default = active_runtime。
4. 其他 profiles/* 默认为 config_only。
5. 缺少任一核心文件时为 missing_files。
6. 非法目录为 invalid。
```

返回示例：

```json
{
  "profile": "default",
  "profile_type": "default",
  "status": "active_runtime",
  "runtime_model_name": "common-writer",
  "env_exists": true,
  "config_exists": true,
  "soul_exists": true
}
```

扩展 Profile：

```json
{
  "profile": "writer-zh",
  "profile_type": "extended",
  "status": "missing_files",
  "env_exists": true,
  "config_exists": false,
  "soul_exists": true
}
```

---

## 6.3 `.env` 校验增强

当前校验只判断是否包含 `=`。v4.5.1 改为严格校验。

允许格式：

```env
KEY=value
KEY=
KEY="value"
KEY='value'
# comment
```

禁止格式：

```env
export KEY=value
A B=1
=value
KEY
../KEY=value
```

KEY 正则：

```regex
^[A-Z_][A-Z0-9_]*$
```

校验返回：

```json
{
  "valid": false,
  "message": "第 12 行 KEY 格式非法：A B"
}
```

注意：

1. 允许空值。
2. 允许注释。
3. 允许空行。
4. 不解析变量引用。
5. 不展开 `$VAR`。
6. 不在日志中记录完整内容。

---

## 6.4 路径安全增强

所有 Profile 路径读写前必须做路径归一化校验。

### 校验规则

```python
target_real = target_path.resolve()
profile_real = profile_dir.resolve()

if not target_real.is_relative_to(profile_real):
    raise BadRequest("路径越界")
```

### Profile 目录限制

扩展 Profile 必须位于：

```text
data/hermes/profiles/<profile>
```

禁止：

```text
../
绝对路径
软链接目录
空格路径
中文路径
嵌套路径
```

如果发现 `profiles/<profile>` 是 symlink，返回：

```json
{
  "error_code": "PROFILE_SYMLINK_NOT_ALLOWED",
  "message": "Profile 目录不允许使用软链接"
}
```

### 文件写入限制

只允许写入：

```text
.env
config.yaml
SOUL.md
```

不允许前端传任意文件名。

---

## 6.5 保存并重启后等待 Runtime 恢复

当前 `save_core_file(..., restart_after_save=true)` 保存后直接调用重启并返回。

v4.5.1 改为：

```text
1. 校验内容
2. 备份旧文件
3. 写入新文件
4. 重启容器
5. 等待 Docker 状态 running
6. 等待 /health 成功
7. 等待 /v1/models 成功
8. 刷新实例 Runtime 状态
9. 返回最终状态
```

### 超时配置

```env
HERMES_RESTART_WAIT_TIMEOUT_SECONDS=60
HERMES_RESTART_POLL_INTERVAL_SECONDS=3
```

### 返回示例

```json
{
  "success": true,
  "profile": "default",
  "kind": "env",
  "file_path": "/data/copilot-docker/instances/common-writer/data/hermes/.env",
  "backup_file": "/data/copilot-docker/instances/common-writer/data/hermes/backups/core-files/default/env-20260617-120000.bak",
  "restarted": true,
  "docker_status": "running",
  "api_server_status": "online",
  "agent_call_status": "callable",
  "runtime_status": "ready",
  "message": "保存成功，容器已重启，Runtime 已恢复"
}
```

失败示例：

```json
{
  "success": true,
  "restarted": true,
  "runtime_status": "degraded",
  "error_code": "HERMES_RUNTIME_RECOVERY_TIMEOUT",
  "message": "文件已保存，容器已重启，但 Runtime 未在 60 秒内恢复"
}
```

---

## 6.6 删除 Profile 安全保护

禁止删除：

```text
default
active_runtime
```

删除扩展 Profile 时：

```text
1. 检查 profile != default
2. 检查 profile.status != active_runtime
3. 自动创建删除前备份
4. 删除目录
5. 写审计记录
```

API 请求：

```http
DELETE /api/hermes/agents/{agent_profile}/profiles/{profile}
```

请求体：

```json
{
  "confirm_profile": "writer-zh"
}
```

如果 `confirm_profile` 不等于待删除 profile，返回：

```json
{
  "error_code": "PROFILE_DELETE_CONFIRM_MISMATCH",
  "message": "确认名称不匹配，已取消删除"
}
```

---

## 6.7 审计记录

新增 Profile 操作审计。

### 审计事件

```text
profile.list
profile.create
profile.delete
core_file.read
core_file.validate
core_file.save
core_file.save_and_restart
runtime.wait_after_restart
```

### 审计字段

```text
id
user_id
organization_id
instance_id
agent_profile
profile
operation
kind
file_path
result
error_code
error_message
created_at
```

### 禁止记录

```text
content
API_SERVER_KEY
HERMES_WEBUI_PASSWORD
*_API_KEY
PASSWORD
SECRET
TOKEN
```

---

## 7. 前端修复需求

## 7.1 API 调用统一

当前详情页路由：

```text
/hermes/agents/:profileName
```

前端详情页统一调用：

```text
/api/hermes/agents/{profileName}/profiles
/api/hermes/agents/{profileName}/profiles/{profile}/core-files/{kind}
```

保留 `instanceId` API 方法，但当前详情页不直接使用。

---

## 7.2 active_runtime 显示

Profile 下拉中显示状态：

```text
default        active_runtime
writer-zh      missing_files
researcher     config_only
```

颜色：

```text
active_runtime  绿色
config_only     灰色
missing_files   黄色
invalid         红色
```

当前运行 Profile 在详情页顶部显示：

```text
当前运行 Profile: default
Runtime Model: common-writer
```

---

## 7.3 未保存变更保护

增加 `dirty` 状态。

触发保护的操作：

```text
切换 Profile
切换环境变量 / 配置文件 / 角色定义页签
点击返回
切换左侧 Tab
刷新页面
关闭页面
```

提示：

```text
当前文件有未保存修改，是否放弃修改？
```

选项：

```text
取消
放弃修改
```

保存成功后：

```text
dirty = false
```

---

## 7.4 保存并重启交互

点击“保存并重启”时弹窗确认：

```text
该操作会保存当前文件并重启 Docker 容器。重启期间 WebUI 和 Gateway 会短暂不可用。
```

按钮：

```text
取消
确认保存并重启
```

执行中显示：

```text
正在保存...
正在重启容器...
正在等待 Runtime 恢复...
```

完成后显示：

```text
保存成功，Runtime 已恢复
```

失败后显示：

```text
文件已保存，但 Runtime 未恢复，请进入运行状态页查看日志
```

---

## 7.5 错误提示标准化

### 缺少文件

```text
当前 Profile 缺少 SOUL.md，可点击创建默认文件。
```

### Profile 非法

```text
Profile 名称非法，仅允许小写字母、数字、中划线和下划线。
```

### Runtime 未恢复

```text
容器已重启，但 Hermes API Server 未恢复。
```

### 权限不足

```text
当前账号没有编辑该 Profile 的权限。
```

---

## 8. 权限要求

| 操作            | 最低权限   |
| ------------- | ------ |
| 查看 Profile 列表 | viewer |
| 查看核心文件        | admin  |
| 校验核心文件        | admin  |
| 保存核心文件        | admin  |
| 保存并重启         | admin  |
| 创建 Profile    | admin  |
| 删除 Profile    | admin  |
| 查看审计          | admin  |

说明：

```text
.env / config.yaml / SOUL.md 可能包含密钥、模型配置和角色规则，raw 内容只允许 admin 读取。
```

---

## 9. 测试用例

### Case 1：default 识别为 active_runtime

前置：

```text
common-writer 使用 data/hermes/.env 启动 Gateway
```

预期：

```text
default.status = active_runtime
```

### Case 2：writer-zh 缺少 config.yaml

前置：

```text
data/hermes/profiles/writer-zh/.env 存在
data/hermes/profiles/writer-zh/SOUL.md 存在
data/hermes/profiles/writer-zh/config.yaml 不存在
```

预期：

```text
writer-zh.status = missing_files
```

### Case 3：非法 Profile 目录

前置：

```text
data/hermes/profiles/中文目录
```

预期：

```text
返回 invalid，不影响其他 Profile 列表
```

### Case 4：保存 env 并重启

操作：

```text
修改 data/hermes/.env
点击保存并重启
```

预期：

```text
自动备份旧文件
写入新文件
容器重启
/health 成功
/v1/models 成功
runtime_status = ready
```

### Case 5：切换页签时存在未保存内容

操作：

```text
编辑 SOUL.md
不保存
切换到 config.yaml
```

预期：

```text
弹出未保存修改确认
```

### Case 6：删除 default

操作：

```text
DELETE default
```

预期：

```text
返回错误：禁止删除 default
```

### Case 7：删除 active_runtime

操作：

```text
删除当前运行 Profile
```

预期：

```text
返回错误：禁止删除当前运行 Profile
```

### Case 8：symlink 逃逸

前置：

```text
profiles/bad -> /etc
```

预期：

```text
Profile 状态 invalid
禁止读取和写入
```

---

## 10. Cursor 实施任务

### Task 1：补充 Agent profileName 代理 API

修改：

```text
nodeskclaw-backend/app/api/hermes_agents.py
或新增 nodeskclaw-backend/app/api/hermes_agent_profiles.py
```

实现：

```text
/hermes/agents/{agent_profile}/profiles
/hermes/agents/{agent_profile}/profiles/{profile}/core-files/{kind}
```

验收：

```text
/hermes/agents/common-writer 页面所有 Profile API 都可访问。
```

---

### Task 2：实现 active_runtime 状态

修改：

```text
profile_service.py
path_resolver.py
```

实现：

```text
default / extended profile 状态识别
runtime_model_name 返回
active_runtime 返回
```

---

### Task 3：增强 `.env` 校验

修改：

```text
core_file_service.py
```

实现：

```text
KEY 正则校验
禁止 export
错误返回行号
```

---

### Task 4：增加路径安全防护

修改：

```text
path_resolver.py
profile_service.py
core_file_service.py
```

实现：

```text
resolve 后校验
禁止 symlink profile
禁止目标文件逃逸
```

---

### Task 5：保存并重启后等待恢复

修改：

```text
core_file_service.py
docker lifecycle service
Hermes probe service
```

实现：

```text
restart 后 wait running
wait /health
wait /v1/models
返回 runtime 状态
```

---

### Task 6：前端 dirty guard

修改：

```text
AgentProfileConfigView.vue
AgentDetailView.vue
```

实现：

```text
dirty 状态
切换确认
离开确认
保存后重置
```

---

### Task 7：删除 Profile 二次确认

修改：

```text
Profile 选择器组件
ProfileService
API Schema
```

实现：

```text
confirm_profile
禁止 default
禁止 active_runtime
删除前备份
```

---

### Task 8：审计记录

新增或接入：

```text
audit service
```

记录：

```text
profile.create
profile.delete
core_file.save
core_file.save_and_restart
```

---

## 11. 验收标准

v4.5.1 完成后必须满足：

1. `/hermes/agents/common-writer` 详情页无 404 API。
2. `default` 能显示为 `active_runtime`。
3. `writer-zh` 缺文件时显示 `missing_files`。
4. `.env` 非法格式能提示具体行号。
5. 保存并重启后能等待 Runtime 恢复。
6. 切换 Profile 或页签前能提示未保存修改。
7. 禁止删除 `default`。
8. 禁止删除当前运行 Profile。
9. Profile symlink 不可读写。
10. 保存、删除、创建、重启有审计记录。
