# DeskClaw 团队版 Skill Platform v1.5 API 验收与 Newman 运行指南

本文档说明如何使用 Postman 与 Newman 对 DeskClaw 团队版 Skill-first 平台的 API 进行完整性与安全性验收。

## 资产清单

- **主集合 (Collection)**: `tools/postman/nodeskclaw-skill-platform-v1.5.postman_collection.json`
- **本地环境示例 (Environment Example)**: `tools/postman/nodeskclaw-skill-platform-v1.5.local.postman_environment.example.json`

## 目录结构 (Folder 00–14)

| 目录编号 | 目录名称 | 验收目标 |
|---|---|---|
| 00 | 00 Environment | Backend/Agent 存活与就绪探针 (/health/live, /health/ready, /health) |
| 01 | 01 Authentication | 鉴权与组织隔离，跨租户访问 403 fail-closed |
| 02 | 02 Skill Lifecycle | Skill 发布生命周期 (Draft, Validate, Publish, Installation Desired) |
| 03 | 03 Connector and Edge Setup | 连接器中心、SecretRef 引用、Edge 节点心跳绑定 |
| 04 | 04 MCP Catalog | 员工公开 MCP 工具列表 (已发布过滤、剥离内部物理路由) |
| 05 | 05 Central Run | 中心 Run 提交、Session/Trace 关联、结果轮询与唯一终态 |
| 06 | 06 Event Replay | 事件增量拉取、序号单调递增、断线重放恢复 |
| 07 | 07 Approval and Resume | 高危 Run 的 WAITING_APPROVAL 状态与审批恢复防绕过 |
| 08 | 08 Cancel | 运行中 Run 的 CANCELLING/CANCELLED 三阶段中断流转 |
| 09 | 09 Artifact | 产物持久化描述符、SHA256 校验和与鉴权下载 |
| 10 | 10 Edge Run | 边缘节点 REST/MCP/DB 执行、租约续期、增量事件与代次隔离 |
| 11 | 11 Hybrid Run | 混合编排：中心步骤完成后真实派发 EdgeJob，等待边缘完成后统一终态 |
| 12 | 12 Security Negative | 安全负向门禁：SSRF 拦截、过期代次拒绝、明文 Token 拒绝、越权拦截 |
| 13 | 13 Compatibility Smoke | 旧版 Work Expert C2 兼容性冒烟（不计入新能力通过率） |
| 14 | 14 Logical Cleanup | 验收产生的资源通过正式 API 逻辑清理 |

## 环境准备与依赖

1. **Node.js**: >= 18.0.0
2. **Newman**: CLI 运行器

```bash
npm install -g newman
```

## 执行方式

### 1. 命令行直接执行

```bash
newman run tools/postman/nodeskclaw-skill-platform-v1.5.postman_collection.json \
  -e tools/postman/nodeskclaw-skill-platform-v1.5.local.postman_environment.example.json \
  --reporters cli,json \
  --reporter-json-export reports/postman/report.json
```

### 2. CI / Automated Pipeline 退出码与报告

- **退出码**:
  - `0`: 全量目录（00～14）断言全部通过。
  - 非 0: 存在断言失败、网络连接中断或协议未满足。
- **报告输出**: `reports/postman/report.json`
- **连续执行**: 集合内部使用动态生成的唯一后缀与幂等键，支持在同一环境下连续多次执行，无需人工重置数据库。
