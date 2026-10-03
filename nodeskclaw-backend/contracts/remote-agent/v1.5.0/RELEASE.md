# REMOTE-AGENT-PROVIDER-CONTRACT v1.5.0

This bundle freezes Shared IntegrationAccount USE semantics for Remote Agent create and execute.

`integration_account_refs` may reference the caller's PERSONAL accounts and ORGANIZATION shared accounts with an effective USE grant. Create-time authorization and execute-time revalidation both require USE, ACTIVE status, and Expert External Action Policy coverage. Idempotent digest replay still revalidates Shared USE before returning the existing run.

Provider sessions are principal-scoped through `routing_metadata.provider_execution_session_set`. One session contains accounts for exactly one `provider_user_id`. Mixed personal and shared principals use separate sessions. Same-toolkit multi-account collisions remain denied. Legacy `provider_execution_session_ref` stays read-compatible.

Request shape remains compatible with v1.3.0. ACP is unsupported. Work UI is not implemented by this bundle. Consumers should configure Shared accounts and USE Grants before selecting them.

Sibling bundles v1.0.0 through v1.3.0 stay byte-immutable. production_gate: unpassed
