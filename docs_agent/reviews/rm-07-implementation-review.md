# RM-07 Implementation Review

**Verdict**: PASS  
**Reviewer**: code-review-and-quality（五轴）  
**Scope**: Plan-owned delta in implementation commit `c29411e54d8357e6976cfc89f4bbee03498ea7ec`（仅审查 RM-07 路径；同 commit 内 RM-18 夹杂物不在本审查验收范围）  
**Plan**: `.cursor/plans/rm-07_edge_control_channel_601b46f4.plan.md`（`plan_id: RM-07`）  
**PRD**: `docs_agent/prd-v1.6.8-edge-control-channel-security-closure.md`

## Scope Reviewed

- Backend：`internal_edge.py#edge_heartbeat`、`COMMAND_PURPOSES` + `node.heartbeat`、`EdgeNodeRead.identity_rotation_expires_at`
- Agent：`EdgeWorker#_heartbeat` / `_maybe_complete_rotation`、`generate_rotation_keypair` / `apply_rotation_response`
- Portal：`EdgeNodesView` rotating 待定态、`connectors.ts`、`hermes.edgeNodes.*` i18n
- Tests：backend/agent edge control channel + worker oracles
- `lat.md/` Edge Control Channel / Edge Worker / Portal / decisions / core-concepts

## Five-Axis Summary

| Axis | Result | Notes |
|---|---|---|
| Correctness | PASS | 心跳验签后才读轮换窗；窗口内用当前身份 POST `/rotate` 并落盘；Portal 仅开窗展示，不收集私钥 |
| Readability | PASS | `_maybe_complete_rotation` 从心跳路径抽出；purpose 集合两边对称 |
| Architecture | PASS | 不引入无封套 `rotation_required` 状态机；不改 Public Skill Run；Delivery Generation 未触碰 |
| Security | PASS | 未签名 heartbeat 不推进轮换；unsigned cancel 仍不得置位（既有 + 回归）；无私钥进 Backend/Portal |
| Performance | PASS | 仅窗口有效时额外一次 rotate；无热路径放大 |

## Observations（非阻断）

- Implementation commit `c29411e5` 同时混入 RM-18 fixture / `test_skill_release.py` / PRD 文稿；历史已在 `origin/main`，本项不以 rewrite 收口，在 Verification Evidence 标注 contamination。
- 心跳验签失败仅 warning 返回（不 fail heartbeat HTTP）；与「软提示轮换窗」一致，轮换副作用仍 fail-closed。

## Blocking Findings

无。
