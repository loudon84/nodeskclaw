# Plan Semantic Review

**Artifact:** `.cursor/plans/rm-18_skill-run-v140-public-attachment-input.plan.md`
**Plan ID:** RM-18
**Mode:** actual semantic review after router REQUIRED
**Verdict:** PASS

## Router

`assess_plan_review.py` returned REQUIRED because:

- MULTIPLE_MINIMAL_NEW
- MULTIPLE_NEW_PROD_FILES
- INTEGRATION_HOTSPOT
- COMPLEX_CROSS_TODO_DEPENDENCY

REQUIRED is not PASS. Plan declares `acceptance_contract: smc.acceptance.v1`, so Actual Semantic Review is mandatory.

## Findings

1. Grounding at `26e1cb5aa2aebbb4bdc1a8e1c65617aaa6b6c948` matches APPROVED PRD: `_build_authorized_execution_context` still raises `errors.run.attachment_workspace_required` when refs exist without `workspace_id`; `_assert_attachment_proofs` always calls workspace ACL; `WorkspaceFile.workspace_id` is non-null FK; `_build_client_context` builds only from headers and drops `params.client_context.attachment_refs`; `supportsAttachments` is copied from Release extra; `scripts/contracts.py` generate/check stop at `1.3.0`. Static validator and generation integrity both PASS.

2. Ponytail minimality is real, not table-only: Public upload cannot reuse `workspaces.py#upload_workspace_file` (workspace FK + Portal envelope) or `GET .../artifacts/.../download` (output). MINIMAL_NEW router/service/metadata table stay in the same Attachment 授权域. C04/C06/C07/C08/C09/C10/C11 are MODIFY_EXISTING. No NEW_DEPENDENCY. No rewrite of frozen `v1.2.1/` or `v1.3.0/`. Agent byte ingest and Hermes inject remain OUT.

3. Single writer holds: T1 owns upload+metadata; T2 owns Runtime proof/revalidate/accepted refs; T3 owns Gateway copy + Catalog honesty + JSON-RPC nest; T4 owns generator/bundle/schema constants; T5 owns live runner. Hotspots `runtime_skill_run_service.py`, `handler.py`, `mcp_tool_mapper.py`, `contracts.py` each have one owner Todo.

4. Requirement coverage maps AC-01..AC-14 and DOD-01..DOD-14 to Change/Todo/Verification. KEEP C01/C05/C13/C14 have no writer Todo. AC-07 REST 4xx vs `tools/call` JSON-RPC nesting is a Plan-level freeze of transport, not a PRD owner/boundary change. `ATTACHMENT_WORKSPACE_MISMATCH` is forbidden. CLM-04 Prior Result FAILED correctly uses NEW_EVIDENCE, not REUSE_EVIDENCE.

5. Lifecycle writers are unique: Public attachment service writes metadata+bytes; Runtime is the only proof/fail-closed writer; Gateway copies frozen snake_case field only. TTL expiry rejects at proof, not by creating a Run.

6. LIVE SCN-01 binds V10 to ENV-01 with COMMAND candidate probe, not LOCAL_WORKTREE against a pre-deployed SUT. Required capabilities (user_jwt upload, tools/call refs, accepted refs, fail-closed, leak scan) match the single fixture. Missing `supportsAttachments=true` Skill is VERIFICATION_BLOCKED, not a guessed PASS. Cross-tenant uses unknown/other-user ref, not fake `X-Org-Id`.

7. Cursor todos `t1-...` through `t5-...` project Markdown headings plus owned Change IDs. No second `.plan.md`.

8. Post-static REVISE before workspace freeze: C13 KEEP 不再把 `docs_agent/roadmaps/ROADMAP-SKILL-AGENT-V16.md` 列入 Change Matrix 路径。该文件启动前已是 ambient dirty（RM-18 `IN_PRD` 未提交），列入 write set 会 `DELIVERY_TARGET_CONFLICT`。RM-09 边界仍由 blocking V12 只读证明；Roadmap DONE 仍走 Delivery Phase 9 独立 commit。这不是 PRD owner/boundary 变更。

No RETURN_PRD. Execute may proceed after workspace freeze.
