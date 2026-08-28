# 设计输入审查提示模板

此 prompt 只用于 brainstorming 输出的设计输入自检，不再把设计直接判定为“ready for generic plan”。

检查：

- 完整性：目标、约束、成功标准是否足够进入下一 governed Artifact；
- 一致性：是否存在相互冲突的需求/边界；
- 范围：是否需要 Architecture Decision，还是仅属于既有架构内 Stage PRD；
- YAGNI：是否包含未请求的未来扩展；
- Evidence：事实、假设、未知是否区分；
- Ownership：是否存在 Production Owner 可能改变但未进入 architecture mode。

返回：

- `FEATURE_READY` → `smc-prd-grounding`；
- `ARCHITECTURE_REQUIRED` → `smc-architecture-decision` draft；
- `NEEDS_CLARIFICATION` → 只列答案会改变下一决策的问题。
