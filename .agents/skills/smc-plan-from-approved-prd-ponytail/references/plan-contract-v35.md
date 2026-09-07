# SMC Cursor Plan Contract v3.5 — Domain Binding Extension

Plan v3.5 inherits all v3.4 requirements and adds deterministic Domain Pack binding.

## Required Frontmatter

```yaml
plan_contract: smc.plan.v3.5
plan_id: <stable-id>
commit_policy: post_review

domain_contract: smc.ges.domain-activation.v1
consumer_profile: <profile-id>@<profile-version>
domain_policy_digest: sha256:<digest>
```

The digest is generated from the installed Consumer Profile and all Domain policy inputs selected by that profile. Delivery MUST fail `DOMAIN_POLICY_STALE` when the current digest differs.

## Domain Activation Ledger

Every v3.5 Plan includes exactly one:

```markdown
## Domain Activation Ledger

| Domain | Pack Version | Trigger Changes | Capabilities | Status |
|---|---:|---|---|---|
| example | 1.0.0 | C01,C03 | engineering,review | REQUIRED |
```

The ledger is deterministic projection, not a second SOT. The resolver recomputes it from Consumer Profile + Change Matrix.

A profile-enabled domain that does not match current Change Scope is recorded `NOT_REQUIRED`; it must not run its providers for that Plan.

## Domain Extension Sections

An active pack may declare one Plan extension section. The pack manifest owns its columns/defaults and optional validator. Core Plan Validator dynamically delegates to the pack; Core cannot contain domain-specific field rules.

The Frontend v1 reference pack declares `## Frontend Quality Ledger`.

## Delivery

At phase boundaries `smc-plan-delivery/scripts/domain_hooks.py` is the generic bridge:

```bash
python .agents/skills/smc-plan-delivery/scripts/domain_hooks.py assert-policy "$PLAN_PATH"
python .agents/skills/smc-plan-delivery/scripts/domain_hooks.py providers "$PLAN_PATH" --phase engineering
python .agents/skills/smc-plan-delivery/scripts/domain_hooks.py providers "$PLAN_PATH" --phase review
python .agents/skills/smc-plan-delivery/scripts/domain_hooks.py providers "$PLAN_PATH" --phase verification
```

Providers do not own delivery state or evidence freshness.
