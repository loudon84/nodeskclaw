# SMC Acceptance Governance Contract v1

## Purpose

This contract closes the gap between implementation proof and live acceptance proof.

It is orthogonal to `smc.plan.v3.4`. A governed Plan that performs LIVE,
FAULT_INJECTION, or EXTERNAL verification declares:

```yaml
acceptance_contract: smc.acceptance.v1
```

The contract adds five non-negotiable gates:

1. Blocking Failure Integrity
2. Acceptance Scenario Binding
3. Evidence Inheritance
4. Live Environment Preflight
5. Verification Candidate Provenance

## Acceptance Claim

An Acceptance Claim is the smallest observable statement that may close an
AC/DoD requirement.

Required Plan table:

```markdown
## Acceptance Claim Ledger

| Claim ID | Requirement | Observable Fact | Blocking | Prior Evidence | Prior Result | Evidence Action | Invalidation Reason | Verification IDs |
```

Rules:

- every blocking Requirement Coverage row has at least one blocking Claim;
- `Prior Result=FAIL` on a blocking Claim can never use `REUSE_EVIDENCE`;
- `REUSE_EVIDENCE` requires prior PASS + durable source evidence;
- `TARGETED_RERUN` requires a concrete invalidation reason;
- a known blocking failure cannot be downgraded to an observation at delivery
  time; changing blocking semantics requires PRD revision.

Allowed Evidence Actions:

```text
NEW_EVIDENCE
TARGETED_RERUN
REUSE_EVIDENCE
```

## Scenario Binding

LIVE/FAULT_INJECTION/EXTERNAL verification is not capability discovery.
Before execution it binds exactly one scenario:

```markdown
## Live Scenario Matrix

| Scenario ID | Claim IDs | Verification IDs | Subject / Fixture | Required Capabilities | Preconditions | Stimulus | Oracle | Environment ID |
```

A fixture/tool may be reused only when the semantic Plan Review explicitly
proves it satisfies every scenario's Required Capabilities. Execute-time tool
search/substitution/prompt fishing is forbidden.

`Subject / Fixture` may be `None` when the scenario is endpoint/runtime-level
(e.g. a version-floor endpoint) rather than a business tool.

## Live Environment

```markdown
## Live Environment Matrix

| Environment ID | Required Env Vars | Preflight Command | Fault Driver Env | Candidate Mode | Candidate Probe |
```

No secret values belong in the Plan; only variable names and safe probe
commands are recorded.

For FAULT_INJECTION, `Fault Driver Env` is mandatory.

Allowed Candidate Modes:

```text
LOCAL_WORKTREE
ENV_TOKEN
COMMAND
RECEIPT
```

`LOCAL_WORKTREE` is only valid when the verification command starts/uses the
SUT directly from the current governed worktree. A long-running pre-deployed
Backend/Agent/Runtime must use ENV_TOKEN, COMMAND, or RECEIPT.

## Verification Ledger Extension

Acceptance-enabled Plans extend the existing Verification Ledger:

```markdown
| Verification ID | Claim IDs | Level | Acceptance Mode | Entry Point / Command | Oracle | Negative / Regression | Evidence Policy | Environment | Evidence Action | Blocking |
```

Allowed Acceptance Modes:

```text
LOCAL
LIVE
FAULT_INJECTION
EXTERNAL
```

`Evidence Policy` remains retention/storage policy. It must not be overloaded
with meanings such as REAL_PROCESS or REAL_RUNTIME.

## Blocking Failure Integrity Protocol

For LIVE / FAULT_INJECTION / EXTERNAL verification with a non-reuse action,
the exact verification command must emit exactly one machine-readable line:

```text
SMC_ACCEPTANCE_RESULT {"claims":{"CLM-01":{"result":"PASS"}}}
```

Every Claim ID bound to the Verification must be present and PASS.

Therefore:

```text
process exit 0 + HTTP 500 observed
```

cannot become proof. Missing/FAIL claim results force verification FAIL even
when the wrapper process itself exits 0.

## Evidence Inheritance

Evidence reuse is explicit, never implicit.

Use:

```bash
python .agents/skills/smc-plan-delivery/scripts/acceptance.py inherit \
  --plan "$PLAN_PATH" \
  --verification V03 \
  --from-manifest docs_agent/evidence/RM-15-evidence.json \
  --from-verification V13
```

This creates a current-scope inherited evidence record only when:

- current Claim action is `REUSE_EVIDENCE`;
- current Claim declares Prior Result PASS;
- source durable manifest is integrity-valid;
- source verification is PASS.

A prior failed claim can only be `TARGETED_RERUN` or `NEW_EVIDENCE`.

## Candidate Provenance

`post_review` remains unchanged: the final implementation commit does not yet
exist at live verification time.

After Implementation Review and before live verification, capture a
working-tree candidate:

```bash
python .agents/skills/smc-plan-delivery/scripts/acceptance.py capture \
  --plan "$PLAN_PATH"
```

The candidate ID is content-bound to the current Plan scope fingerprint.

A live environment must prove it is running that candidate through its
declared Candidate Mode. A mismatch returns:

```text
LIVE_SUT_MISMATCH
```

This prevents "fixed A, tested old B" without weakening `post_review`.

The later commit guard still proves the post-review implementation commit
contains exactly the verified Plan-owned content.

## Preflight

Before any live command:

```bash
python .agents/skills/smc-plan-delivery/scripts/acceptance.py preflight \
  --plan "$PLAN_PATH" --verification V01
```

Missing fixture dependencies, environment variables, fault drivers, or
candidate provenance return a preflight blocker. They do not create false
product FAIL evidence.

## Completion

For acceptance-enabled Plans:

```text
all blocking Verification FRESH PASS
AND
all blocking Acceptance Claims PASS
AND
all non-reuse live evidence carries the captured candidate ID
```

is required before `IMPLEMENTED_AND_PROVEN`.
