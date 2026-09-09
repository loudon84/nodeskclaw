# RM-04 Plan Initial Review

**Plan:** `.cursor/plans/rm-04_strict_readiness_7c349609.plan.md`  
**Approved PRD:** `docs_agent/prd-v1.6.3-strict-readiness-production-acceptance.md`（v1.6.3.1）  
**Router:** `assess_plan_review.py` → `REQUIRED`（`INTEGRATION_HOTSPOT`、`SECURITY_OR_TRUST_BOUNDARY`）  
**Mode:** actual semantic review（`acceptance_contract: smc.acceptance.v1`）  
**Verdict:** REVISE

## Findings

### MAJOR

1. LOCAL `REUSE_EVIDENCE` 无法交付。`acceptance.py inherit` 需要既有 durable manifest 且源 Verification PASS。仓内 `RM-12/13/14/15-evidence.json` 的 V01 命令与 Claim 与本项不同；无 `RM-04-evidence.json`。源码 SHA 不是 inherit 输入。KEEP 生产路径应改为 NEW_EVIDENCE 现跑 pytest/checker。
2. V04 为 `FAULT_INJECTION` + `NEW_EVIDENCE`，`evidence.py` 要求恰好一行 `SMC_ACCEPTANCE_RESULT`。现有 `harness.py run` 只打印 JSON 报告，进程 0 不能单独结项。须在同一 Harness Owner 打印该协议。
3. Verification 命令含 `cd ...;` 复合 shell。`evidence.py` 用 `Popen(command)` 无 shell，命令必须是可 `shlex.split` 的 argv。Secret scan 与 `contracts.py check` 不得挤在同一 Verification 行。

### MINOR

1. `Fault Driver Env=SKILL_AGENT_LEASE_SECONDS` 是租约窗口，真正注入是 Compose kill/pause。Preflight 只检查变量存在，可接受，但不要写成独立 chaos driver。
2. `LOCAL_WORKTREE` 合法：Harness 从当前 worktree 起 Compose，不是预部署旧 SUT。

## Disposition

只改 Plan（Evidence Action、命令切分、T3 打印 `SMC_ACCEPTANCE_RESULT`）。不改 APPROVED PRD Capability/Owner/Boundary。
