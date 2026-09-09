# LIVE_RUNNING_TOOL_NAME is not an RM-16 live exit fixture.
# Stage PRD v1.6.15 forbids --scenario pc05 / pc08 (Worker kill / Hermes restart).
$env:LIVE_PLAIN_TOOL_NAME = "hermes_marketing__live-plain-response"
$env:LIVE_TOOL_CALL_TOOL_NAME = "hermes_marketing__live-tool-call"
$env:LIVE_APPROVAL_TOOL_NAME = "hermes_marketing__live-approval-park"
$env:LIVE_SUBAGENT_TOOL_NAME = "hermes_marketing__live-subagent-delegation"
$env:LIVE_OLD_RUNTIME_TOOL_NAME = "hermes_marketing__live-old-runtime-probe"

$env:RM16_PLAIN_TOOL_NAME = $env:LIVE_PLAIN_TOOL_NAME
$env:RM16_TOOL_NAME = $env:LIVE_TOOL_CALL_TOOL_NAME
$env:RM15_TOOL_NAME = $env:LIVE_APPROVAL_TOOL_NAME
$env:RM16_SUBAGENT_TOOL_NAME = $env:LIVE_SUBAGENT_TOOL_NAME
$env:RM16_OLD_RUNTIME_TOOL_NAME = $env:LIVE_OLD_RUNTIME_TOOL_NAME
