# Ponytail Minimality — SMC Plan Adaptation

## 目的

把 Ponytail 的“lazy senior developer”思想用于 **APPROVED PRD → Plan**，但不破坏 SMC 的架构审批边界。

Ponytail 原始核心：

- 先理解问题与真实调用流；
- 查现有代码再写新代码；
- root-cause fix 优先于 caller-by-caller patch；
- stdlib / native / installed dependency 优先于 custom code；
- fewest files / shortest correct diff；
- 不做未请求抽象、scaffolding 和 future-proofing；
- 安全、数据完整性、信任边界、明确需求与必要验证不能被“精简”。

## SMC 阶段改写

APPROVED PRD 已经冻结产品行为，所以 Plan 不能再问：

> 这个 Capability 要不要做？

Plan 应问：

> 为满足这个 Capability，这个新增实现实体是否真的需要存在？

“实体”包括：

- 新 production file；
- 新 service / store / client；
- 新 adapter / mapper / codec；
- 新 public interface；
- 新 dependency；
- 新 config surface；
- 新 retry / compatibility wrapper；
- 新 test harness。

## Minimality Ladder

理解真实调用流后，停在第一种能正确满足 AC 的方案：

| 顺序 | Strategy | 判定 |
|---|---|---|
| 1 | `REUSE_EXISTING` | 当前 codebase 已有能力可复用，不需要新增实现实体 |
| 2 | `STDLIB` | 标准库可以正确完成 |
| 3 | `NATIVE` | framework / platform / DB / runtime 原生能力可以完成 |
| 4 | `INSTALLED_DEP` | 已安装依赖可以完成 |
| 5 | `MODIFY_EXISTING` | 在现有 Owner / function / mapping 中做最小变更 |
| 6 | `MINIMAL_NEW` | 前述均不成立，增加最小新实现 |
| 7 | `NEW_DEPENDENCY` | 例外；必须证明现有/stdlib/native/installed/custom-minimal 都不合适 |
| - | `REMOVE_ONLY` | 删除被替代实现 |
| - | `GENERATED_ENTRYPOINT` | 只改生成入口，不手工写生成产物 |

## Root-Cause Rule

如果多个调用方出现相同问题：

1. 找它们的最近共享 owner / shared function；
2. 判断 shared location 是否是行为真正应该成立的位置；
3. 是 → 在 shared location 修一次；
4. 否 → 才允许各入口有不同策略。

错误模式：

```text
T1: caller A 加 guard
T2: caller B 加 guard
T3: caller C 加 guard
```

优先模式：

```text
T1: shared normalizer 修根因
T2/T3: 只消费修复后的行为
```

## Minimum ≠ Fewest Tokens

Plan 可以少写代码，但不能少理解：

- 不得跳过真实 owner；
- 不得只看 ticket 点名文件；
- 不得为了少文件把职责塞进错误 owner；
- 不得为了少代码降低 correctness。

## Minimum Correct Includes Proof

Ponytail 最小化只约束实现实体与写入面，不允许削弱验收闭环。Requirement Coverage Ledger、Lifecycle Closure Matrix 与 Verification Ledger 是追踪和证据合同，不是新增 production abstraction，也不要求每个 requirement 新建 Todo。

正确的最小 Plan 可以让多个 AC/DoD 共享一个 root-cause Change、一个 Todo 或一个验证；但每条 requirement 仍必须保留独立映射和阻断证据。`IMPLEMENTED_NOT_PROVEN` 是诚实状态，不是可以被“最小化”省略的工作。

## 新文件规则

默认：`New File? = no`。

`yes` 仅在以下事实成立时允许：

- 当前 Owner 的现有文件承载会形成明显错误职责；或
- 项目既有结构明确要求独立 artifact；或
- 当前 change 本身是新的 production owner，且 PRD 已批准这个 owner；或
- 测试没有可合理扩展的现有承载点。

“更干净”“未来扩展”“更模块化”不能单独成为新文件理由。

## 新依赖规则

`NEW_DEPENDENCY` 是例外，不是默认梯子的一部分。

必须说明：

1. 现有 codebase 无等价能力；
2. stdlib 不满足；
3. platform/framework native 不满足；
4. 已安装依赖不满足；
5. 自己写最小实现会更高风险、更难正确维护。

## 不准懒

以下项目没有 minimality 豁免：

- input validation at trust boundary；
- authentication / authorization；
- secret protection；
- 防止数据丢失的 error handling；
- transaction / money correctness；
- accessibility basics；
- APPROVED Behaviour；
- AC 指定验证；
- migration/removal condition；
- 实机或外部系统校准。

## Plan 中的证据格式

每个 Change ID 的 `Root-Cause / Reuse Evidence` 应尽量是可定位事实：

```text
path/to/file.ts#symbol
```

或：

```text
A,B,C callers converge at path/to/shared.py#normalize
```

`Why This Is Minimum` 只说明为什么更高 rung 不需要，不写大段设计辩护。
