# INTEGRATION-ACCOUNT-CONTRACT v1.1.0

This bundle adds Organization Shared IntegrationAccount ownership and NodeSkClaw USE Grant ACL.

Connect accepts optional `ownership=PERSONAL|ORGANIZATION`. Missing ownership remains PERSONAL for v1.0 compatibility. Shared connect requires `integration:shared:manage` and uses provider principal `nodeskclaw:<org_id>:shared`.

Public account DTOs add `ownership`, `can_use`, and `can_manage`. `can_manage` is not USE. List supports `scope=all|personal|shared`. Ungranted shared account ID lookups return not-found to consumers.

Grant APIs:

```text
GET /integrations/accounts/{id}/grants
PUT /integrations/accounts/{id}/grants
```

PUT is desired-state soft-delete replacement. Personal accounts reject Grant APIs.

Work Shared Integrations UI, Grant UI, and Selector live outside this repository in `smc-copilot/apps/work`. Consumers must configure Shared accounts and USE Grants before selecting them in Work. This bundle freezes the consumer contract only; Work UI is not implemented here.

The v1.0.0 bundle stays byte-immutable. production_gate: unpassed
