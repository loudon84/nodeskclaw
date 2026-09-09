# RM-19 Verification Evidence

本文件记录 RM-19 Public Streaming Delta Contract `v1.5.0` 的验证状态。`commit_policy: post_review`。真实 `user_jwt` live 环境变量在本机会话中缺失，live 不得假绿。

## Implementation Scope (commit A candidate)

- Agent：`assistant_delta_coalescer.py` Unicode 64 KiB 切分；`native_event_normalizer.py` 消息段状态机（delta + snapshot）；`schemas.py` 校验；`hermes_engine.py` saw_assistant 含 delta
- Backend：`runs.py#_public_run_event` allowlist；`mcp_jsonrpc.py` V15 专用模型；`constants.py` / `scripts/contracts.py` 1.5.0 生成与两提交 release check
- LAT：`lat.md/architecture/skill-agent.md#RM-19 Public Streaming Delta`
- Live runner：`tools/acceptance/run_rm19_live_streaming_delta.py`
- Gene/Skill：无变更

## Automated Oracles

| ID | Command / Check | Result | Notes |
|---|---|---|---|
| A01 | `uv --directory nodeskclaw-agent run pytest tests/test_native_event_normalizer.py tests/test_assistant_delta_coalescer.py tests/test_hermes_engine.py` | PASS | 含边界、大小切分、工具段、latency flush |
| A02 | `uv --directory nodeskclaw-backend run pytest tests/hermes_skill/test_employee_runs_api.py -k public_run_event` | PASS | 含 delta/snapshot 投影与畸形拒绝 |
| A03 | `uv --directory nodeskclaw-backend run python scripts/contracts.py generate --family skill-run --version 1.5.0` 后 `check --version 1.5.0` | PASS | 生成后删除 Bundle，保留给 commit B |
| A04 | `uv --directory nodeskclaw-backend run python scripts/contracts.py check --family skill-run --version 1.4.0` | PASS | 旧目录零改写 |
| A05 | `lat check` | PREEXISTING_ERRORS | 本项新增 `@lat` 锚点可解析；仓库仍有 Credential Lease 等历史断链，非本项引入 |
| A06 | `python tools/acceptance/run_rm19_live_streaming_delta.py` | BLOCKED / MISSING | 缺少 RM13_* / user_jwt 等 live env；`SMC_ACCEPTANCE_RESULT` 全 MISSING |

## Claims

| Claim | Result | Evidence |
|---|---|---|
| CLM-01 schema/runtime | PASS (automated) | A01/A02/A03 |
| CLM-02 rebuild/snapshot | PASS (unit) / LIVE MISSING | A01；live A06 |
| CLM-03 projection/auth | PASS (unit) / LIVE MISSING | A02；live A06 |
| CLM-04 SSE dedupe | PARTIAL unit / LIVE MISSING | runner 具备去重断言；未实跑 |
| CLM-05 Bundle/tag | GENERATOR PASS / RELEASE BLOCKED | A03；无 live 前不打 tag、不标 DONE |
| CLM-06 mid-run delta | LIVE MISSING | A06 |

## Release Gate

- 两提交模型与 `check --release` 已写入生成链。
- **在 A06 PASS 之前**：禁止 annotated tag `skill-run-contract-v1.5.0`；禁止 Roadmap RM-19 `DONE`。
- 当前 Roadmap 状态应为 `BLOCKED`（等待 live 环境）或保持 `IMPLEMENTING` 直至 live PASS。

## Handoff

向 Work 交付的前提是本地可解析 tag + 完整 Bundle。当前仅完成行为实现与生成器；Bundle/tag 待 live PASS 后按 commit B 发布。
