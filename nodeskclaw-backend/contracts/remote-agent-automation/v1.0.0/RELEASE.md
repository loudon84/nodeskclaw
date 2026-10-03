# REMOTE-AGENT-AUTOMATION-CONTRACT v1.0.0

This bundle freezes the Backend internal dispatch surface used by nodeskclaw-task AutoTask Automation.

Service authentication uses `X-Autotask-Internal-Token` with optional previous-token rotation. The token only proves the caller is nodeskclaw-task; business authorization still revalidates owner membership and `expert:invoke`.

Consumers must configure an AgentAutomation definition in nodeskclaw-task before triggering Manual, Cron, Webhook, or RPA Successor paths. Work UI is not implemented by this bundle. MCP automation tools are deferred.

`client_request_id` for dispatched runs is `autotask:<invocation_id>`. User JWTs must not be persisted by AutoTask.

ACP is unsupported. The sibling `remote-agent/v1.3.0` public provider bundle remains unchanged.

production_gate: unpassed
