# Remote Expert Catalog Contract v1.1.0

Employee-facing catalog for Remote ACP v2. Requires `expert:invoke`. Identity is `expert_slug` as `agent_ref`. Unpublished or disabled experts are not listed. Unknown detail lookups return 404. Runtime not ready remains listed as `unavailable`.

Catalog items MUST include nested `capabilities.acp.protocol_version=1` and `capabilities.acp.remote_transport`, plus `session_resume`, `attachments`, `artifacts`, and `permissions`. Implementation MAY also emit the v1.0 flat fields as a superset. MUST NOT expose Agent or Hermes internal addresses, `runtime_run_id`, or internal tokens.

Consumer pin is sha256 of SHA256SUMS.
