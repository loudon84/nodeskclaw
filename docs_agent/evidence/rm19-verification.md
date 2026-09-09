# RM-19 Verification Evidence

本文件记录 RM-19 Public Streaming Delta Contract `v1.5.0` 的可复现验证证据。`commit_policy: post_review`。

## Implementation Scope

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
| A03 | `uv --directory nodeskclaw-backend run python scripts/contracts.py generate --family skill-run --version 1.5.0` 后 `check --version 1.5.0` | PASS | Bundle 仅在 commit B 提交 |
| A04 | `uv --directory nodeskclaw-backend run python scripts/contracts.py check --family skill-run --version 1.4.0` | PASS | 旧目录零改写 |
| A05 | `lat check` | PASS | Credential Lease / Attempt Binding 章节层级已纠正 |
| A06 | `python tools/acceptance/run_rm19_live_streaming_delta.py` | PASS | `auth_type=user_jwt`；`SMC_ACCEPTANCE_RESULT` 全 PASS；`delta_count>=1` 且 first delta 早于 terminal |

## Claims

| Claim | Result | Evidence |
|---|---|---|
| CLM-01 schema/runtime | PASS | A01/A02/A03 |
| CLM-02 rebuild/snapshot | PASS | A01；live A06 snapshot 拼接对账 |
| CLM-03 projection/auth | PASS | A02；live A06 `auth_type=user_jwt` |
| CLM-04 SSE dedupe | PASS | live A06：`Last-Event-ID` 只重放 after_seq；客户端按 `event_id` 去重无冲突 |
| CLM-05 Bundle/tag | PASS | commit B `3a7fa5ac`；tag `skill-run-contract-v1.5.0` → `3a7fa5ac`；`check --release` PASS；`releaseCommit`/`backendCommit`=`e83e39a0` |
| CLM-06 mid-run delta | PASS | live A06：terminal 前至少一条 public `assistant.delta` |

## Live Notes

- ENV-01：`RM13_*` + `SKILL_AGENT_INTERNAL_TOKEN`；工具 `hermes_marketing__customer-profiling`
- 候选记录：`.smc/runs/RM-19/verification-candidate.json`
- 不在证据中写入 JWT / API key / 数据库口令

## Release Gate

- 两提交模型：`releaseCommit`/`backendCommit` = `e83e39a0883545c35f4c99ba5bbef004c9ffd150`；annotated tag `skill-run-contract-v1.5.0` → Bundle-only `3a7fa5ac32017d41f7191b8221c861b93d7e7f32`。
- live A06 PASS；tag tree `check --release` PASS；Roadmap RM-19 → DONE（独立 status commit）。

## Handoff

向 Work 交付：本地可解析 tag `skill-run-contract-v1.5.0` + 完整 Bundle `nodeskclaw-backend/contracts/skill-run/v1.5.0/`。不含 Work UI / consumer-lock。
