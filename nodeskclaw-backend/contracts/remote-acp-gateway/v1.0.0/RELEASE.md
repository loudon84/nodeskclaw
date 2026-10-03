# Remote ACP Gateway Contract v1.0.0

Public Remote ACP transport for SMC Copilot. SMC connects only to Backend WSS `/api/v1/remote-experts/{agent_ref}/acp` with subprotocol `nodeskclaw.remote-acp.v1`. Credentials MUST be Bearer headers. Query credentials are forbidden.

Backend owns authentication, org membership, Expert ACL, runtime placement, Execution Capability minting, and transparent proxying. Backend MUST NOT become Run SOT and MUST NOT write HermesTask or RunDispatchOutbox for this path.

Artifact ResourceLinks resolve to `/api/v1/remote-experts/{agent_ref}/acp/runs/{run_id}/artifacts/{artifact_id}`.
