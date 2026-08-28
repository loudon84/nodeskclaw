# Source Basis

Prepared: 2026-08-28

The new validator replaces the rule coverage of:

- `loudon84/nodeskclaw/tools/agent-skills/validate_plan.py`
  - main blob: `2c19e3283b69c471ba0ebfec074e26540198000f`

The previous validator already covered:

- required sections;
- Approved PRD link + project PRD validation;
- Change Matrix columns;
- legal actions;
- REPLACE requires REMOVE at a global level;
- New File? yes/no;
- New File Justification when new files exist.

It did not parse or validate:

- Todo sections;
- Change ID ownership;
- Todo write ownership;
- duplicate symbol writers;
- integration hotspots;
- read/write ordering;
- dependency cycles;
- parallel safety;
- implementation minimality evidence;
- unresolved planning placeholders.
- PRD Acceptance Criteria / Definition of Done coverage;
- lifecycle success, failure and cancel closure;
- requirement-to-blocking-verification evidence mapping.

`smc-plan-validator v1.2.0` is the only Plan v3.2 validation implementation. It keeps source inspection out of the deterministic gate, while requiring every PRD obligation (numbered list or explicit-id bullet) to map to a blocking verification contract.
