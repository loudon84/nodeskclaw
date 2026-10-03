---
name: plan-post-review-commit
description: >
  Creates the single post_review implementation commit after a Cursor/SMC .plan.md
  finishes Review PASS and Verification PASS. Stages explicit files only, uses
  git commit-tree plumbing so Cursor cannot inject Co-authored-by, sets Author to
  SMC-Copilot, and verifies UTF-8 Conventional Commits Chinese subjects. Use when
  finishing a plan implementation commit, post_review commit, plan commit after
  verification, or when ordinary git commit keeps adding Co-authored-by.
---

# Plan Post-Review Commit

Plan 执行顺序是 `Execute -> Review -> Verification -> Commit Implementation`。
本 Skill 只负责最后一步。Todo 完成过程中禁止调用。

## When to use

- `.plan.md`（或缺 `commit_policy` 被推断为 `post_review`）的全部 Todo 已完成
- Review PASS + Verification PASS 已有证据
- 需要一次 implementation commit，且 Author 必须是 SMC-Copilot
- 普通 `git commit` 会被 Cursor 追加 `Co-authored-by: Cursor <cursoragent@cursor.com>`

## Preconditions checklist

Copy and keep until done:

```text
- [ ] Plan Todo 全部完成（含 deferred/skip 已标明）
- [ ] Review PASS（含必须修复项已处理）
- [ ] Verification PASS（刚跑过的命令输出，不是口头“应该过了”）
- [ ] 已列出本次 Agent 改动文件；未混入其他 Agent / 无关 untracked
- [ ] 不包含 .plan.md、未 APPROVED 的 PRD/Architecture、Roadmap status
- [ ] 不包含 .env / 密钥 / production env
```

任一未勾选：停止，不要提交。

## Do not commit in the same commit

- `.cursor/plans/**` 与任意 `*.plan.md`
- `status` 不是 `APPROVED` / `APPROVED_FOR_PLAN` 后独立 docs 流程之外的 PRD / Architecture
- Roadmap status 变更
- `.env*`、密钥、证书、kubeconfig
- 其他 Agent 正在改的无关文件

Artifact 与 implementation 必须分 commit。

## Commit procedure

1. Inspect isolation:

```bash
git status --short
git diff --stat
git log -5 --oneline
```

2. Draft message: `type(scope): 中文说明`（subject 一行；必要时空一行再写 body）。

3. **Run the script**（不要手写临时 Python，不要用会注入 trailer 的 `git commit`）:

```bash
python .agents/skills/plan-post-review-commit/scripts/commit_plan_implementation.py \
  --message "feat(scope): 中文说明" \
  -- path/to/file1 path/to/file2
```

Windows PowerShell 同样用上面命令；路径用仓库相对 POSIX 或本机路径均可。

4. Confirm script output contains:

- `AUTHOR SMC-Copilot <smc-copilot@smart-core.com>`
- `SUBJECT` 为预期中文 subject
- 无 `Co-authored-by`

5. Double-check:

```bash
git log -1 --format="%H%n%an <%ae>%n%B"
git status -sb
```

## If HEAD already has Co-authored-by (unpushed)

```bash
python .agents/skills/plan-post-review-commit/scripts/commit_plan_implementation.py \
  --rewrite-clean-head
```

仅当 `git status -sb` 显示 ahead、且未 push 到共享分支时使用。已 push 的 `main` / `release-*` 禁止 rewrite / force push。

## Dry run

```bash
python .agents/skills/plan-post-review-commit/scripts/commit_plan_implementation.py \
  --dry-run \
  --message "feat(scope): 中文说明" \
  -- path/to/file1
```

## Script behavior (source of truth)

[`scripts/commit_plan_implementation.py`](scripts/commit_plan_implementation.py):

- `git add -- <explicit files only>`，禁止等价于 `git add -A`
- 拒绝 `.cursor/plans/`、`*.plan.md`、`.env*`
- `git write-tree` + `git commit-tree` + `git update-ref HEAD`
- Author/Committer 固定 `SMC-Copilot <smc-copilot@smart-core.com>`
- message UTF-8；拒绝已含 `Co-authored-by` 的 message
- 提交后校验 Author 与 message

## Forbidden

- `git commit` / `git commit --amend` 作为本流程主路径（易被注入 trailer）
- `git add -A` / `git add .`
- `git config user.name` / `user.email`
- 把 Plan 文件或未核准 artifact 打进 implementation commit
- Review/Verification 未 PASS 就提交
- 已 push 共享分支上 force push 清 trailer

## Mirror

本 Skill 规范源在 `.agents/skills/plan-post-review-commit/`。
变更后必须同步到 `.cursor/skills/plan-post-review-commit/`，避免 mirror drift。
