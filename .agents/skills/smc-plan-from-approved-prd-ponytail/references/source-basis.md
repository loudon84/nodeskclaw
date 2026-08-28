# Source Basis

Prepared: 2026-08-28

## SMC current sources reviewed

- `loudon84/nodeskclaw/.agents/skills/smc-plan-from-approved-prd/SKILL.md`
  - main blob: `2371a3584b06c98340a333f4a502ad6e6f4cb340`
  - prior version: `2.2.0`
- `loudon84/nodeskclaw/.cursor/rules/plan-codegen-minimal.mdc`
  - main blob: `1e7b3e157163f65e900bee58f6279a19205d86a2`
- `loudon84/nodeskclaw/tools/agent-skills/validate_plan.py`
  - main blob: `2c19e3283b69c471ba0ebfec074e26540198000f`
- `loudon84/nodeskclaw/tools/agent-skills/validate_prd.py`
  - main blob: `4b9dccf6ab910a92ec3ec0e843a1383fd74b8a88`
- `loudon84/nodeskclaw/.agents/references/architecture-convergence.md`
  - main blob: `b2dcf147ae470213711099d22831272423c13dd6`

## Ponytail source reviewed

- `DietrichGebert/ponytail/skills/ponytail/SKILL.md`
  - main blob: `02c0712c86277d49d18a77da3a2b825657bf02d1`

Adapted concepts:

- understand the real flow before minimizing;
- reuse codebase before writing new code;
- stdlib/native/installed dependency before custom implementation;
- root-cause fix rather than caller-by-caller patches;
- fewest files / shortest correct diff;
- YAGNI for unrequested abstractions and future scaffolding;
- safety, validation, data integrity and explicit requirements are not simplification targets.

SMC-specific adaptation:

- an APPROVED PRD capability cannot be removed by Ponytail at Plan stage;
- “does this need to exist?” applies to the implementation entity, not the approved product behavior;
- minimality is combined with Change IDs and Todo write ownership so it prevents duplicate Plan slices, not only bloated code during execution.
