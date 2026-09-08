---
name: smc-external-dependency-check
version: 1.0.0
description: 在本地 PRD/Plan 前读取中央 Repo Work Package 与 External Dependency，按成熟度决定可继续、Dark Implementation 或局部 Block。
---
# SMC External Dependency Check
禁止把“外部项目未全部完成”直接转换为整个 Stage BLOCKED。

输入：`.agents/governance/work-packages/<feature>.yaml` 与 `.agents/governance/contracts/*`。

- UNDEFINED：仅允许不依赖 wire semantics 的本地工作。
- CANDIDATE：允许 parser / DTO / fixture / dark implementation。
- RELEASED：允许 production integration。
- CONSUMED：Consumer Lock 已完成。
- CONFORMANCE_PASS：允许进入 integration/promotion gate。

输出必须区分 `allowed_changes` 与 `blocked_changes`，只 Block 依赖未成熟的 Global Change。
