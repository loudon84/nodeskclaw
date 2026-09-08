# SMC Plan-Scoped Delivery Workspace Contract v1

## Goal

让一个明确指定的 canonical Plan 成为 delivery mutation/audit/review/verification/commit 的唯一 scope owner，同时保护同一 Git worktree 中启动前已经存在的其它任务 dirty state。

## Classification

| Class | Meaning | Action |
|---|---|---|
| `PLAN_OWNED` | canonical Plan、Change Matrix implementation paths、durable evidence manifest | allowed |
| `AMBIENT_PREEXISTING` | delivery 启动前已 dirty 且不属于本 Plan | allowed only while unchanged and still ambient |
| `TARGET_CONFLICT` | Plan write set 在 baseline 前已经 dirty | fail closed |
| `TOOLING_BLOCKED` | 非本 Plan 的 governance tooling 在 baseline 前 dirty | fail closed |
| `AMBIENT_MUTATED` | pre-existing ambient content/state changed during delivery | fail closed |
| `SCOPE_DRIFT` | delivery 后新出现的 non-Plan dirty | fail closed |
| `TOOLING_MUTATION` | delivery 中新增非 Plan governance tooling mutation | fail closed |

## Baseline

`.smc/runs/<plan_id>/workspace-baseline.json` records:

- frozen HEAD/base commit;
- canonical Plan path;
- Change Matrix planned files;
- planned-file baseline content states;
- pre-existing ambient path/content states;
- ambient baseline fingerprint;
- Plan semantic hash.

Do not refresh baseline after implementation begins to hide conflicts.

## Scope Fingerprint

`scope_fingerprint` = SHA256 of:

```text
semantic Plan hash
+ every declared planned implementation path
+ current content state of each planned path
```

Cursor todo `status` and deterministic `content` projection are normalized by semantic Plan hashing. `.smc/` and durable Evidence Manifest are not implementation scope.

## Ambient Integrity

Ambient paths must preserve both working-tree bytes and their dirty existence. Committing, cleaning, overwriting or deleting a pre-existing ambient path is a mutation even when unrelated to current Plan semantics.

## Commit Rule

Implementation commit may contain only:

```text
Plan-owned implementation delta
canonical Plan
Durable Evidence Manifest
```

Repository-wide clean worktree is NOT required after commit. Original ambient dirty may remain, but must match baseline.

## HEAD Stability

Before implementation commit, repository `HEAD` must remain equal to the frozen workspace `base_commit`. Unrelated dirty files may coexist, but unrelated commits/rebases in the same worktree are not ambient state and return `DELIVERY_HEAD_DRIFT`. After the guarded implementation commit, verification of the commit may allow the expected HEAD change only to that verified commit.

## Dirty-state Identity

Ambient stability covers both file content identity and Git dirty class (`worktree`, `index`, `untracked`). Staging/unstaging, cleaning, committing, deleting, or rewriting an ambient path therefore counts as mutation even if its visible bytes are unchanged.

## Deterministic Error Mapping

- pre-existing Plan target dirty -> `DELIVERY_TARGET_CONFLICT`;
- pre-existing unrelated governance tooling dirty -> `DELIVERY_TOOLING_BLOCKED`;
- ambient mutation -> `DELIVERY_AMBIENT_MUTATED`;
- new non-Plan mutation -> `DELIVERY_SCOPE_DRIFT`;
- governance tooling mutation -> `DELIVERY_TOOLING_MUTATION`.

The runtime persists and compares both `scope_fingerprint` and `ambient_fingerprint`; neither may be silently rebased to make a failed run pass.

## Baseline Refresh Guard

`workspace.py init --refresh` is permitted only before implementation mutation. If the frozen Plan scope already has an implementation delta, ambient drift, scope drift or HEAD drift, refresh returns `DELIVERY_WORKSPACE_REFRESH_AFTER_MUTATION` rather than rebasing evidence onto a dirty run.
