# RM-03 Implementation Closure Review

**Scope:** `d6e7cb8` 的 Edge Published Bundle（边缘已发布技能包）生命周期实现。
**Verdict:** PASS

## Review Findings And Resolution

| Finding | Severity | Resolution |
|---|---|---|
| Installer（安装器）用 `Path.name` 静默净化 Skill ID（技能标识）和版本，`..` 可映射到托管根之外；路径包含判断还存在同前缀目录绕过。 | Required | 标识改为拒绝绝对路径、分隔符、`.` 与 `..`；目标路径统一用 `Path.relative_to` 做根目录约束，并拒绝托管 Skill/版本目录符号链接。 |
| Current（当前版本）指针直接覆盖，切换失败可能留下损坏指针；重试同代安装会先删除当前版本。 | Required | 指针改为临时文件加 `os.replace` 原子切换；同版本升级先移动到备份目录，任何切换失败均恢复旧目录并清理未激活版本。 |
| Worker（工作进程）把卸载 Desired Generation（期望代次）当作已安装版本删除，旧代请求还会移除当前指针。 | Required | Worker 卸载当前受管版本；Installer 对显式非当前版本执行无副作用拒绝，保持 Current 可用。 |
| Bundle reference（技能包引用）、节点绑定与 Actual status（实际状态）未完全 fail-closed（失败即关闭）。 | Required | Backend 仅接受规范 UUID（通用唯一标识符）引用、精确 `edge_node_id`、Edge 目标和合法状态；活动态拒绝 `uninstalled/removed`，卸载态拒绝 `ready`。 |
| Agent 对缺失 SHA-256（安全散列）的 Bundle 描述符会退化为不校验摘要。 | Required | Worker 在下载前完整校验 release ID、bundle reference、版本、64 位十六进制 SHA-256 与非负 size；描述符不完整时同代报告稳定错误且不执行安装。 |

## Five-Axis Review

- **Correctness**：发布时冻结独立 Bundle 摘要和大小；Desired 按代钉包；只有本地激活成功后报告 `ready`，失败 Actual 不推进 `actual_generation`。
- **Readability**：Bundle 描述符、钉包、下载、安装和 Actual 分支保留在既有 Owner 内，辅助函数职责单一。
- **Architecture**：Backend 继续拥有 Release 与 Installation 事实，Agent 继续唯一拥有 Edge 文件副作用；没有新增服务或第二状态机。
- **Security**：下载强制 Edge Token、精确组织/节点和代次；本地安装拒绝路径逃逸、ZIP 符号链接、重复条目、托管根符号链接与非法标识；元数据不含存储路径或凭据。
- **Performance**：Bundle 只在发布时打包，下载采用流式响应；调谐复用现有轮询，不增加队列或跨服务调用。

## Verification Review

V01–V06、Alembic（数据库迁移）单 head 和目标 lint 的新鲜执行结果记录在 `docs_agent/evidence/rm03-verification.md`。V02 的 AsyncMock（异步模拟）警告来自既有测试辅助代码，不影响目标命令退出码。

## Conclusion

所有 Required finding（必须关闭项）均已关闭，RM-03 满足 PRD v1.6.2 的 AC-01 至 AC-10 和 DOD-01 至 DOD-04，可更新 Roadmap（路线图）为 `DONE`。
