# RM-12 Implementation Review

**Scope:** C11–C15 working-tree implementation vs Plan RM-12  
**Reviewer:** code-review-and-quality  
**Verdict:** PASS

## Axes

1. **Correctness** — Default Runtime Skill + SSE + `async_event` no longer splits `user_jwt` to `queued`. Employee `tools/call` returns KEEP C07 structured content when Skill Agent is enabled. Catalog calls the same resolver. SSE yields a contract terminal event before close for four Agent statuses. Projection maps `run.timed_out` and logs `PROJECTION_SYNC_FAILED`.
2. **Tests** — Resolver, mapper, projection, SSE four-terminal, and PC-10–PC-14 conformance module all pass. Conformance records `auth_type=user_jwt` and does not skip.
3. **Architecture** — No new Control Plane, Event Store, or Idempotency Service. HermesTaskWorker not deleted. Expert `_build_task_response` remains for non-employee paths.
4. **Security** — Employee merge strips forbidden HermesTask keys. Public GET/SSE still authorize via existing Run ACL. No secrets added.
5. **Performance** — SSE still polls on 1s timeout; synthesize-on-terminal avoids hang and extra loops after Agent terminal.
6. **Scope** — Unrelated dirty plans/env files are not part of this implementation. `test_run_projection_updater.py` extras are C13 evidence. `lat.md` documents the new Backend fact.

No must-fix findings.
