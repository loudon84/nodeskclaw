# Architecture Convergence Checklist

这是 PRD、Plan、staged review 共用的**最小架构不变量**。各阶段只检查属于自己的层级，不重复做上一阶段工作。

## Core Invariants

- [ ] 一个 Capability 只有一个 Production Owner。
- [ ] 每个 REPLACE 都有对应 REMOVE 和明确 removal condition。
- [ ] 没有无期限 Legacy。
- [ ] Compat / adapter / fallback / alias 有真实 Current Consumer、Reason、Removal Condition、Removal Version。
- [ ] 历史 Bug 只保存在 tests / fixtures / golden evidence。
- [ ] 没有 duplicate parser、serializer、adapter 或 lifecycle owner。
- [ ] 新增生产文件不会形成第二 Production Owner。

## PRD Gate

PRD / Review 负责确认：

- Capability 与 Scope；
- Existing / Target Owner；
- KEEP / MODIFY / ADD / REPLACE / REMOVE；
- API / IPC / Auth / Contract / Security Boundary；
- 关键 Behaviour 与 Acceptance Criteria。

PRD Gate 默认不决定 exact 私有函数、hook、fetch option、test file、mock 或其它施工技术。

## Plan Gate

Plan 继承 APPROVED PRD，不重新决定架构。

Plan 负责确认：

- exact file / symbol；
- 最小调用链；
- 当前实施 slice；
- 新增生产文件的必要性；
- REPLACE 对应 REMOVE 未丢失；
- 没有因实现方便新增平行 Owner。

## Staged Review Gate

代码 Review 验证：

- 实际 diff 与 APPROVED PRD / Plan 一致；
- 没有未计划的 Owner 转移或 scope expansion；
- removal 已真实发生；
- 必要测试证明目标行为。

任何阶段发现必须改变上游架构决定时，应返回对应上游阶段，而不是在当前阶段静默改写。
