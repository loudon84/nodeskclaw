---
name: smc-prd-converge
description: 将已经获得 PASS 的 NoDeskClaw PRD 收敛为最终 APPROVED 文档；只做确定性清理与状态转换，不重新分析源码或架构。
version: 2.3.0
disable-model-invocation: true
---

# SMC PRD Converge

## 前置条件

必须同时满足：

1. 最新 `smc-prd-review` Verdict=`PASS`；
2. 无 OPEN BLOCKER / MAJOR；
3. 必须的人类决策已完成；
4. 当前 PRD 为 `DRAFT` 或 `REVIEW_REQUIRED`；
5. `python tools/agent-skills/validate_prd.py <prd>` 通过。

否则停止，不设置 APPROVED。

使用：

- [`../../references/prd-contract.md`](../../references/prd-contract.md)
- [`../../references/architecture-convergence.md`](../../references/architecture-convergence.md)

## 只做确定性收敛

删除：

- Grounding Closure Table；
- Review History / Required Revisions；
- rejected alternatives；
- exploration notes；
- temporary workaround；
- 已废弃算法；
- “上一轮 / 本轮”等过程描述。

保留：

- Current Capability Inventory；
- Target End-State Inventory；
- Change Classification；
- 必要 Replacement / Removal Matrix；
- 必要 Compatibility Contract；
- 最终 Behaviour / Boundary；
- Acceptance Criteria；
- 最小 Source Anchors。

最终 PRD 只表达一个 Target Architecture。

## 禁止重新推理

禁止：

- 重新扫描源码；
- 新增 Architecture Finding；
- 改 Production Owner；
- 改 Change Classification；
- 新增 implementation design；
- 搜索 Provider 最新状态；
- 再运行 Grounding / Review。

若收敛时发现必须改变架构，停止并返回 Grounding。

## 状态转换

仅在前置条件成立后设置：

```yaml
status: APPROVED
review_verdict: PASS
approved_at: <current ISO-8601 timestamp>
```

保持：

- `work_item_id`
- `version`
- `target_branch`

除非用户明确要求版本升级。

PRD Review 的 REVISE/BLOCKED 不写入 frontmatter；只有 Converge 写 `PASS`。

## 文件名

`status: APPROVED` 写入后，必须去掉文件名中的 `-DRAFT` 后缀，只保留一份最终文件：

- `PRD-WORK-v3.0.1-foo-DRAFT.md` → `PRD-WORK-v3.0.1-foo.md`
- 已跟踪文件用 `git mv`；未跟踪文件直接重命名
- 禁止 `*-DRAFT.md` 与去后缀文件并存
- 最终校验必须针对**新路径**运行

未以 `-DRAFT.md` 结尾的路径不要改名。

## 最终校验

执行：

```bash
python tools/agent-skills/validate_prd.py <prd> --require-approved
```

Validator 负责确定性检查：

- frontmatter 状态一致性；
- APPROVED 文件名不得保留 `-DRAFT` 后缀；
- required sections；
- Change Classification；
- REPLACE / Removal Matrix；
- 显式 Compatibility Contract 字段；
- APPROVED 文档是否仍残留已知 process-only section。

失败则不得交付 APPROVED。

## 输出

只输出：

1. 最终 APPROVED PRD；
2. `APPROVED → ready for smc-plan-from-approved-prd`

不再次输出 Review 报告。

## Exit

`PASS Review → deterministic converge → APPROVED PRD（文件名去掉 -DRAFT）→ Plan`
