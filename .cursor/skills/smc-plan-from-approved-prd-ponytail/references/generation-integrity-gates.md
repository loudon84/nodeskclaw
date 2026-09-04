# Plan Generation Integrity Gates

这些门禁包围 Ponytail 核心决策链，负责阻止误操作和不可执行计划，不改变最小实现梯子、root-cause 优先级或单写者规则。

## Mode Selection

模式必须在读取 PRD 或 Plan 前确定。

| Mode | Trigger | Allowed Inputs | Mutation |
|---|---|---|---|
| `CREATE` | 明确创建新 Plan | APPROVED PRD、源码、目标空路径 | 仅创建新 Plan |
| `REVISE` | 明确修订指定 Plan | APPROVED PRD、指定 Plan、源码 | 仅修改指定 Plan |
| `AUDIT` | 检查 Skill/规则/包，或禁止 Plan 操作 | Skill 包、直接治理依赖 | 禁止 Plan 读写与执行 |

目标已存在时，`CREATE` 返回 `PLAN_ALREADY_EXISTS`。`REVISE` 必须同时具有修订意图、指定目标和覆盖授权。不能从“继续”“按 PRD 做”推断覆盖授权。

## Grounding Evidence

Grounding 必须相对于 frontmatter 的 `grounded_commit`，并记录当前工作树是否含未提交差异。只有用户明确授权 working-tree grounding 时，未提交实现才能作为依据，并必须记录 fingerprint。

每个非 KEEP Change 证明：

1. target 在基线存在或确实不存在；
2. code symbol/entry 可定位；
3. direct caller/callee 支持选择该 root-cause owner；
4. 已搜索现有 helper/schema/type/fixture/shared path；
5. verification entry 和参数真实可运行，或目标被同一 Plan 明确创建。

静态文本相似不能替代 symbol resolution。不存在的 target、伪造的测试路径和未经 parser/`--help` 证实的参数都必须阻断。

## Boundary Closure

当一个 Change 的输入或输出跨越独立 owner、进程、网络、持久化或生成边界时，必须从 source 到 sink 逐字段证明：

```text
authoritative producer -> transport/schema -> consumer -> validation/failure mapping
```

幂等、重试或异步状态还必须证明 identity 的产生、传播、持久化和冲突行为。缺失 producer 不能由 consumer 默认值或占位值补齐。

## Concurrency Closure

出现状态转换、原子性、幂等、重试、lease、generation、并发、去重或单次消费语义时，Lifecycle Closure 必须写明：

- transaction boundary；
- CAS predicate、lock 或唯一约束；
- retry/idempotency identity；
- stale/conflict path；
- success、failure 与 cancel 的唯一 writer。

先查后写但没有原子条件不能宣称并发闭环。

## Verification Preflight

最终 Plan 写入前必须预检：

- existing test/script path 存在；
- existing test node 可被测试收集器识别；
- CLI flag 在 parser 或 `--help` 中存在；
- 新测试/脚本路径对应 Matrix 的 `ADD`；
- Evidence Output 由命令直接产生，或有明确采集步骤。

无法预检的外部环境验证必须明确标记环境依赖，不能伪装成已验证的本地命令。

## Generated Outputs

`Generated Outputs Ledger` 使用：

| Source Change | Generator Owner | Generated Outputs | Command | Drift Check |
|---|---|---|---|---|

生成产物不是人工 write target，但必须可追踪、可再生并有 drift check。

## Downstream Gate

固定顺序：

```text
Grounding/Closure -> Ponytail/Ownership -> Generation Integrity Validator -> SMC Plan Validator -> Review Assessor -> Conditional Semantic Review -> Execute
```

包内 Generation Integrity Validator 检查新增完整性表及基线 file/symbol。SMC Plan Validator 证明通用 v3.2 结构。Risk assessor 返回 `REQUIRED`，或 Contract / Data Flow Closure Matrix 非 `None` 时，独立 semantic review PASS 是执行前门禁。

## Error Codes

| Code | Meaning |
|---|---|
| `SKILL_MODE_UNCLEAR` | 无法确定 CREATE、REVISE 或 AUDIT |
| `PLAN_ALREADY_EXISTS` | CREATE 的目标已存在 |
| `PLAN_REVISION_NOT_AUTHORIZED` | 缺少明确修订或覆盖授权 |
| `GROUNDING_COMMIT_INVALID` | `grounded_commit` 不是可解析的 Git commit |
| `GROUNDING_SOURCE_INVALID` | grounding source 未明确或值非法 |
| `GROUNDING_WORKTREE_FINGERPRINT_INVALID` | working-tree grounding 缺少具体 fingerprint |
| `GROUNDING_TARGET_NOT_FOUND` | 既有 target 或 symbol 无法从基线解析 |
| `GROUNDING_SYMBOL_NOT_FOUND` | file 存在但声明的 symbol 无法从基线解析 |
| `PLAN_NEW_TARGET_ALREADY_EXISTS` | 声明为 ADD/new 的 target 在基线已经存在 |
| `VERIFICATION_COMMAND_INVALID` | 验证入口、参数或证据输出不可证明 |
| `CROSS_BOUNDARY_SOURCE_MISSING` | required field 缺少 producer/transport/consumer 闭环 |
| `CONCURRENCY_CLOSURE_MISSING` | 原子性、重试身份或状态 writer 未闭环 |
| `SEMANTIC_REVIEW_REQUIRED` | 风险判定要求 Plan semantic review |
