"""Task Orchestrator Constants - Table prefixes, timeouts, and status values."""

# Table name prefix for all task orchestrator tables
TABLE_PREFIX = "to_"

# Default timeout values (in seconds)
DEFAULT_NODE_TIMEOUT_SEC = 1800  # 30 minutes
DEFAULT_WORKFLOW_TIMEOUT_SEC = 86400  # 24 hours
DEFAULT_RETRY_MAX_ATTEMPTS = 2

# Callback modes
CALLBACK_MODE_POLL = "poll"
CALLBACK_MODE_WEBHOOK = "webhook"
CALLBACK_MODE_INTERRUPT = "interrupt"

# Workflow status values
WORKFLOW_STATUS_CREATED = "created"
WORKFLOW_STATUS_RUNNING = "running"
WORKFLOW_STATUS_PAUSED = "paused"
WORKFLOW_STATUS_WAITING_HUMAN = "waiting_human"
WORKFLOW_STATUS_BLOCKED = "blocked"
WORKFLOW_STATUS_COMPLETED = "completed"
WORKFLOW_STATUS_FAILED = "failed"
WORKFLOW_STATUS_CANCELLED = "cancelled"

# Node status values
NODE_STATUS_PENDING = "pending"
NODE_STATUS_RUNNING = "running"
NODE_STATUS_WAITING_HUMAN = "waiting_human"
NODE_STATUS_BLOCKED = "blocked"
NODE_STATUS_COMPLETED = "completed"
NODE_STATUS_FAILED = "failed"
NODE_STATUS_CANCELLED = "cancelled"
NODE_STATUS_TIMEOUT = "timeout"

# Node types
NODE_TYPE_ROLE_TASK = "role_task"
NODE_TYPE_SYSTEM_TASK = "system_task"
NODE_TYPE_HUMAN_REVIEW = "human_review"
NODE_TYPE_GATEWAY_TASK = "gateway_task"

# Executor types
EXECUTOR_TYPE_OPENCLAW = "openclaw"
EXECUTOR_TYPE_DIFY = "dify"
EXECUTOR_TYPE_DEERFLOW = "deerflow"
EXECUTOR_TYPE_HUMAN_REVIEW = "human_review"
EXECUTOR_TYPE_SYSTEM = "system"

# Intervention types
INTERVENTION_TYPE_APPROVE = "approve"
INTERVENTION_TYPE_REJECT = "reject"
INTERVENTION_TYPE_MODIFY = "modify"
INTERVENTION_TYPE_COMMENT = "comment"
INTERVENTION_TYPE_ESCALATE = "escalate"

# Intervention status values
INTERVENTION_STATUS_PENDING = "pending"
INTERVENTION_STATUS_RESOLVED = "resolved"
INTERVENTION_STATUS_CANCELLED = "cancelled"

# Source types
SOURCE_TYPE_PAPERCLIP_ISSUE = "paperclip_issue"
SOURCE_TYPE_PORTAL = "portal"
SOURCE_TYPE_API = "api"
SOURCE_TYPE_EVENT = "event"

# Template status values
TEMPLATE_STATUS_DRAFT = "draft"
TEMPLATE_STATUS_ACTIVE = "active"
TEMPLATE_STATUS_DEPRECATED = "deprecated"

# Edge condition types
EDGE_CONDITION_ALWAYS = "always"
EDGE_CONDITION_SUCCESS = "success"
EDGE_CONDITION_FAILURE = "failure"
EDGE_CONDITION_MANUAL_GATE = "manual_gate"
EDGE_CONDITION_EXPR = "expr"
