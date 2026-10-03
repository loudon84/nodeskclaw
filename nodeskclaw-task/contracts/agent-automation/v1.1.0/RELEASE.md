# AGENT-AUTOMATION-CONTRACT v1.1.0

This bundle freezes Shared IntegrationAccount selector semantics for AutoTask AgentAutomation.

`integration_account_refs` wire shape is unchanged. Owners may reference personal accounts and shared accounts they currently can USE. Enable and integration_account_refs updates call Backend internal validate with `X-Autotask-Internal-Token`; user JWTs are never stored. Dispatch and execute revalidate again.

Work Shared Integrations, Grant UI, and Selector are outside this repository. Consumers must configure Shared accounts and USE Grants before selecting them in Work. This release only documents the consumer contract.

MCP automation tools remain deferred. production_gate: unpassed
