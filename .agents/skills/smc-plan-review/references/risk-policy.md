# Conditional Plan Review Risk Policy

Review is REQUIRED when deterministic Plan content indicates semantic risk that validator cannot prove by itself.

Triggers:

- any `NEW_DEPENDENCY` strategy;
- any `REPLACE` action;
- two or more `MINIMAL_NEW` decisions;
- two or more new PROD files;
- any declared Integration Hotspot;
- security/trust/auth/secret/permission keywords in PRD Capability or Target State;
- four or more Todos plus at least one cross-Todo read dependency.

A validator failure is not a reason to run semantic review. Fix validator errors first.
