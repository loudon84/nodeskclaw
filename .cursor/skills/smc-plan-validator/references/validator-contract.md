# SMC Plan Validator Contract

## 原则

Validator 是静态 gate，不是 Agent reviewer。

输入：

```text
one .plan.md
```

输出：

```text
PASS
```

或稳定 error codes。

## 为什么不扫描源码

源码真实性已经由 `smc-plan-from-approved-prd-ponytail` 的 implementation grounding 负责。

Validator 再扫描源码会：

- 重复消耗上下文；
- 引入模型主观判断；
- 让同一个 Plan 在不同运行中产生不同 verdict；
- 混淆 Plan 与 Review 的职责。

因此 Validator 只证明“Plan 自身是否自洽、可执行、无确定性冲突”，以及 PRD 的 AC/DoD（有序列表或显式编号 bullet）是否完整映射到阻断验证。

它不执行验证命令，也不把声明的 evidence output 伪装成真实证据；这仍是 Execute/Verification 的职责。

## Canonical Validator

唯一规则实现：

```text
.agents/skills/smc-plan-validator/scripts/validate_plan.py
```

旧调用点如果必须兼容，使用 wrapper：

```python
#!/usr/bin/env python3
import runpy
from pathlib import Path

script = (
    Path(__file__).resolve().parents[2]
    / ".agents/skills/smc-plan-validator/scripts/validate_plan.py"
)
runpy.run_path(str(script), run_name="__main__")
```

不要复制 validator 代码到：

- `.cursor/rules`；
- `tools/agent-skills`；
- CI script；
- 其它 Skill。

## Return Codes

```text
0 = PASS
1 = Plan/PRD validation failure
2 = invocation/file error
```

## JSON Contract

`--json`：

```json
{
  "valid": false,
  "plan": "...",
  "errors": [
    {
      "code": "PLAN_WRITE_CONFLICT",
      "detail": "T1 and T2 both write path#symbol"
    }
  ]
}
```

error code 稳定，detail 可演进。

## Project PRD Validator Integration

若可以在 Plan 所在 repository 向上找到：

```text
tools/agent-skills/validate_prd.py
```

则在内建 APPROVED/PASS 状态检查之后额外执行：

```bash
python validate_prd.py <prd> --require-approved
```

这样 Plan Validator 保持自包含，同时继续尊重项目现有 PRD contract。

## Fail Closed

任何结构不确定、需求/验证映射矛盾、生命周期缺闭环或 unresolved placeholder 都 FAIL。

Validator 不“猜测”作者意图。
