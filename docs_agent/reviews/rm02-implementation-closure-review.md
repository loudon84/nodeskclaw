# RM-02 Implementation Closure Review

**Scope:** `b8d69828` 的结构化语义事件实现，以及随后完成的 ingest 边界修复。  
**Verdict:** PASS

## Review Findings And Resolution

| Finding | Severity | Resolution |
|---|---|---|
| Internal ingest 仅按 `artifact_id` 和 PERSISTED 状态接受 `artifact.persisted`，允许名称、大小、内容类型或校验和伪造。 | Required | 对已持久化的 `ArtifactDescriptor` 逐字段核对公开 payload；不一致时记录 `artifact_descriptor_mismatch`，不调用 `append_event`。 |
| 语义 payload 只使用敏感字段黑名单，`headers` 等额外字段可穿透到 Event SoT 和 SSE。 | Required | 六类语义事件改用类别允许字段集合；已知敏感字段保留稳定 rejection 原因，其余额外字段以 `unexpected_semantic_payload_field` fail-closed。控制事件不受影响。 |
| Cursor Plan 含重复 frontmatter，且 PRD DoD 未带可追踪 ID，无法通过确定性 Plan 校验。 | Required | Plan 保留单一 SMC v3.2 frontmatter；PRD 仅补 DOD-01 至 DOD-04 标识，不改任何义务、范围或 Owner。 |

## Five-Axis Review

- **Correctness**：Hermes 只规范化显式结构化字段；Worker 和 ingest 的语义分支只 append，不迁移 Step 或聚合终态；Artifact 投影必须来自匹配的 PERSISTED 描述符。
- **Readability**：事件类别、允许字段、拒绝原因和 Artifact 公开字段在现有 schema 与 ingest 边界集中表达，无额外服务或二次转换层。
- **Architecture**：Agent 继续拥有 Run/Event/Artifact 事实与终态裁决；Backend 只生成 v1.2.0 合同并代理 SSE；控制事件仍复用既有路径。
- **Security**：内部 Token 边界继续存在；语义 payload fail-closed，拒绝详情仅包含事件类别与 Artifact ID，不存储原始 payload、认证头或存储引用。
- **Performance**：Artifact 比对复用同次 ingest 的 `list_artifacts` 结果，不引入新的持久化模型、队列或网络调用。

## Verification Review

V01 Hermes、V02 Event SoT/Worker、V03 Internal ingest、V04 Skill Run contract、V05 Backend SSE 和 V06 `lat check` 的新鲜执行结果记录在 `docs_agent/evidence/rm02-verification.md`。V02 的 AsyncMock 警告与 V03 的 TestClient 弃用警告来自既有测试辅助代码，目标命令均以退出码 0 完成。

## Conclusion

Required findings 已关闭；RM-02 可进入实施提交、合同产物提交和 Roadmap `DONE` 的最终闭环。
