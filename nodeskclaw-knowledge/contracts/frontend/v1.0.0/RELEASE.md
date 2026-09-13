# KNOWLEDGE-FRONTEND-CONTRACT v1.0.0

First frozen public frontend contract for `nodeskclaw-knowledge`.

- Contract version: `1.0.0`
- Suggested tag: `knowledge-frontend-contract-v1.0.0`
- Source branch: `feat/knowledge-v2.0`
- Runtime baseline: RAGFlow v0.27.0
- Wire breaking: N/A (first release)
- Public identity: NodeSKClaw domain IDs + `evidence_id`
- Provider runtime IDs (`dataset_id`, `document_id`, `chunk_id`, non-metric `ragflow_*`) are not public frontend identity.
- Authentication: frontend reuses opaque Backend Bearer token; Knowledge does not provide a login endpoint.
- API path strategy: contract v1.0.0 spans `/api/v2` plus selected `/api/v1` compatibility endpoints.
- Check: `uv run python scripts/frontend_contract.py check`

Consumer must lock **tag name + tag commit SHA + SHA256SUMS**.

## Stability

`stable` endpoints/fields are frozen for the v1.x contract line. Removing or changing their meaning requires a new major contract version.

`stable-compat` is the same freeze as `stable`, but the HTTP path remains on `/api/v1` (ingestion jobs). The path may move to `/api/v2` only with an overlap window; field meaning must not change.

`compatibility` endpoints are required by the current frontend but remain on HTTP `/api/v1`; they may move to `/api/v2` in a later contract only with an overlap window.

`optional` endpoints are feature-flagged and must be capability-gated by the frontend.

## Excluded from frontend v1.0.0

The following are intentionally not part of the browser frontend contract:

- Runtime Admin / capability probe (super-admin diagnostics)
- Skill-run authorization proof APIs (service token)
- MCP transport APIs
- Agent tool transport APIs
- Internal RAGFlow resource IDs
- Translation UI (not frozen in this release)
- Query Intelligence debug internals (Playground `include_trace` / analysis fields are not frozen)
- Raw retrieval trace/audit internals
