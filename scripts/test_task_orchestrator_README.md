# Task Orchestrator 测试脚本

## 概述

本测试脚本用于验证 Task Orchestrator 模块的功能完整性,覆盖 Phase 1 的所有核心功能:

- ✅ 模板管理 (CRUD)
- ✅ 工作流实例创建和执行
- ✅ 人工介入 (Human-in-the-loop)
- ✅ 完整链路验证

## 前置条件

1. **数据库已启动并迁移完成**
   ```bash
   # 启动 PostgreSQL
   docker-compose up -d postgres

   # 运行数据库迁移
   alembic upgrade head
   ```

2. **应用已启动**
   ```bash
   uv run uvicorn app.main:app --reload --port 4510 --timeout-graceful-shutdown 3
   ```

3. **获取认证令牌**
   ```bash
   # 方式 1: 通过登录 API 获取
   curl -X POST http://localhost:4510/api/v1/auth/login \
     -H "Content-Type: application/json" \
     -d '{"email": "admin@example.com", "password": "password"}' \
     | jq -r '.access_token'

   # 方式 2: 如果有测试用户,可以直接使用测试令牌
   ```

## 使用方法

### 完整测试 (推荐)

运行所有测试,验证完整生命周期:

```bash
python scripts/test_task_orchestrator.py \
  --base-url http://localhost:4510 \
  --token <YOUR_JWT_TOKEN>
```

### 分步测试

如果需要单独测试某个功能模块:

```bash
# 仅测试模板管理
python scripts/test_task_orchestrator.py --test template --token <TOKEN>

# 测试模板 + 工作流实例
python scripts/test_task_orchestrator.py --test workflow --token <TOKEN>

# 完整测试 (默认)
python scripts/test_task_orchestrator.py --test full --token <TOKEN>
```

## 测试流程

### Phase 1: 模板管理

1. **创建模板** - 创建包含人工审批节点的工作流模板
2. **查询模板列表** - 验证模板已创建
3. **查询模板详情** - 验证模板内容正确
4. **激活模板** - 将模板状态设置为 active

### Phase 2: 工作流实例

1. **创建工作流实例** - 基于模板创建新的工作流实例
2. **查询工作流详情** - 验证实例已创建并开始执行
3. **查询时间线** - 验证事件记录正确
4. **测试暂停/恢复** - 验证生命周期控制功能

### Phase 3: 人工介入

1. **等待人工审批节点** - 轮询工作流状态直到进入 `waiting_human`
2. **提交人工审批** - 通过 intervention API 提交审批结果
3. **等待工作流完成** - 验证工作流继续执行并完成
4. **查询最终时间线** - 验证完整事件链

## 预期结果

### 成功输出示例

```
============================================================
Task Orchestrator 功能完整性测试
============================================================
API 地址: http://localhost:4510
测试类型: full

============================================================
📋 测试模板管理功能
============================================================

1️⃣ 创建工作流模板...

✅ 模板创建成功:
{
  "id": "uuid-here",
  "template_key": "test_approval_workflow",
  "name": "测试审批工作流",
  "status": "draft",
  ...
}

2️⃣ 查询模板列表...
✅ 模板列表:
...

============================================================
✅ 所有测试通过!
============================================================
```

### 失败情况

如果测试失败,脚本会输出详细的错误信息:

```
❌ 请求失败: POST http://localhost:4510/api/v1/admin/task-orchestrator/templates
   状态码: 401
   响应: {"detail": "Could not validate credentials"}
```

## 常见问题

### 1. 认证失败 (401)

**原因**: JWT 令牌无效或过期

**解决**: 重新获取有效的认证令牌

### 2. 连接失败

**原因**: 应用未启动或端口错误

**解决**: 确认应用已启动在正确的端口

### 3. 数据库错误

**原因**: 数据库未启动或迁移未完成

**解决**:
```bash
docker-compose up -d postgres
alembic upgrade head
```

### 4. 工作流未进入人工审批节点

**原因**: LangGraph 执行异常或节点配置错误

**解决**: 检查应用日志,确认 LangGraph 正常执行

## 测试数据

测试脚本使用以下测试数据:

- **模板 Key**: `test_approval_workflow`
- **工作流输入**: `{"applicant": "张三", "reason": "测试申请"}`
- **审批结果**: `{"approved": true, "approver": "管理员", "comment": "同意申请"}`

测试完成后,这些数据会保留在数据库中,可以用于后续的手动验证。

## 扩展测试

如需测试更多场景,可以修改测试脚本中的测试数据:

- **多节点工作流**: 在 `definition.nodes` 中添加更多节点
- **条件分支**: 在 `definition.edges` 中添加条件边
- **不同执行器**: 修改 `executor_type` 测试不同执行器
- **超时场景**: 设置较短的 `timeout_seconds` 测试超时处理

## 集成到 CI/CD

可以将测试脚本集成到 CI/CD 流程:

```yaml
# .github/workflows/test-task-orchestrator.yml
name: Test Task Orchestrator

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_DB: nodeskclaw
          POSTGRES_PASSWORD: password
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v3
      - name: Install dependencies
        run: uv sync
      - name: Run migrations
        run: alembic upgrade head
      - name: Start server
        run: uv run uvicorn app.main:app --port 4510 &
      - name: Run tests
        run: |
          TOKEN=$(curl -X POST http://localhost:4510/api/v1/auth/login \
            -H "Content-Type: application/json" \
            -d '{"email": "test@example.com", "password": "test"}' \
            | jq -r '.access_token')
          python scripts/test_task_orchestrator.py --token $TOKEN
```

## 相关文档

- [PRD 文档](../../docs_prd/task_orchestrivate_arch.md)
- [执行计划](../../.cursor/plans/task_orchestrator_执行计划_f50368b9.plan.md)
- [API 文档](http://localhost:4510/docs) - 启动应用后访问
