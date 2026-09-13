# knowledge-frontend-contract v1.0.0

Frozen contract between the Knowledge service and browser/frontend clients.

## Location

`nodeskclaw-knowledge/contracts/frontend/v1.0.0/`

Release tag:

`knowledge-frontend-contract-v1.0.0`

Consumer lock: **tag name + tag commit SHA + SHA256SUMS**. Do not pin `main` or only `manifest.source.commit`.

## Generate / check

```bash
cd nodeskclaw-knowledge
uv run python scripts/frontend_contract.py generate
uv run python scripts/frontend_contract.py check
```

Do not edit generated files by hand (`schemas/`, `http/endpoint-matrix.json`, `openapi.frontend.yaml`, `typescript/knowledge-contract.ts`, `manifest.json`, `SHA256SUMS`). Change `scripts/frontend_contract_spec.py` and regenerate.

## Files

- `RELEASE.md` — freeze statement and stability classes
- `FRONTEND-INTEGRATION.md` — end-to-end frontend flow
- `STATE-MACHINES.md` — states the UI must understand
- `http/endpoint-matrix.json` — complete frontend endpoint matrix
- `openapi.frontend.yaml` — curated public OpenAPI (all matrix operations)
- `schemas/*.json` — public DTO and request schemas
- `typescript/knowledge-contract.ts` — frontend type baseline
- `fixtures/*.json` — representative wire examples, plus one negative fixture
- `manifest.json` — metadata and per-file artifact hashes
- `SHA256SUMS` — package integrity

## Important

This is a frontend contract release, not a snapshot of every Knowledge API.
Internal/super-admin/service-token transports are intentionally excluded.
Provider runtime IDs (`dataset_id`, `document_id`, `chunk_id`, non-metric `ragflow_*`) are not public frontend identity.
