# Ownership-Aware Plan Slicing

## 核心问题

按“功能步骤”直接拆 Todo 容易产生：

- T1/T2 同时修改同一 function；
- 每个 Todo 重复创建 helper；
- shared registry 被多个 Todo 各追加一次；
- 同一 Capability 出现多个 implementation owner；
- 后一个 Todo 又重构前一个 Todo 刚写的代码。

因此 Todo 不能作为第一层拆分单位。

## 三个不变量

### Architecture invariant

```text
one Capability -> one Production Owner
```

继承自 APPROVED PRD。

### Plan invariant

```text
one production path#symbol -> one Todo WRITE_OWNER
```

### Change invariant

```text
one Change ID -> one Todo Owner
```

一个 Change ID 可以有多个 file/symbol 行，但它们必须归同一个 Todo。

## 正确拆分顺序

```text
PRD Change
  ↓
Implementation Grounding
  ↓
Atomic Change IDs
  ↓
Exact Write Set
  ↓
Read Set
  ↓
Conflict Normalization
  ↓
Dependency DAG
  ↓
Todo Slices
```

禁止：

```text
PRD section
  ↓
Todo list
  ↓
每个 Todo 自己找文件
```

## Write target 规范

优先使用 symbol-level：

```text
apps/work/src/task.ts#pollTask
services/task.py#normalize_state
```

以下情况使用 file-level：

- JSON/YAML/TOML config；
- package / build manifest；
- route / command registry；
- barrel export；
- migration registry；
- 共享 schema registry；
- 无稳定 symbol 的 declarative file。

file-level owner 意味着其它 Todo 不得写同一文件。

## 冲突规范化算法

发现两个候选 slice 写同一 target：

### Case A — 同一 Capability / 同一结果

合并 Todo。

```text
T1 writes X#f
T2 writes X#f
=> merge T1/T2
```

### Case B — 不同 Capability 依赖同一 shared foundation

提升 shared change：

```text
C01 shared foundation -> T1 writes X#f
C02 feature A        -> T2 reads X#f, depends T1
C03 feature B        -> T3 reads X#f, depends T1
```

T2/T3 不再写 X#f。

### Case C — Integration Hotspot

把整个 file 指定给一个 Todo：

```text
routes.ts -> Owner Todo T4
```

其它 Todo 只产生“需要注册”的前置结果，T4 统一集成。

### Case D — Generated output

只修改 generator / source-of-truth：

```text
generator.ts#emitSchema -> T1
```

生成的 `schema.generated.ts` 不作为人工 WRITE_OWNER。

## Reads 的含义

Ledger 的 `Reads` 不是“Agent 看过哪些文件”，而是：

> 当前 Todo 的实施结果依赖哪个由其它 Todo 可能改变的 symbol / file。

这样 Validator 才能识别 read-after-write hazard。

普通上下文浏览不需要全部写入 Ledger。

## Dependency 规则

如果：

```text
T1 writes X#f
T2 reads X#f
```

则 T1/T2 必须有明确顺序关系，通常：

```text
T2 Depends On T1
```

如果没有任何顺序边，Plan 存在：

```text
PLAN_READ_AFTER_WRITE_WITHOUT_DEPENDENCY
```

## Parallel Safe

`Parallel Safe = yes` 只在以下全部成立时允许：

- 无 Depends On；
- 没有其它 Todo 依赖它；
- 与其它 Todo 无 write/write overlap；
- 与其它 Todo 无 write/read overlap；
- 不与其它 Todo 同时写同一个 physical file。

不同 symbol 同文件可以顺序执行，但默认不标 parallel safe。

## Todo 的职责

Todo 只做三件事：

1. 实施它拥有的 Change IDs；
2. 只写 Ledger 中自己的 Writes；
3. 满足 Stop Conditions 后停止。

Todo 不再重新选择架构、不重新拆 owner、不创建未来抽象。
