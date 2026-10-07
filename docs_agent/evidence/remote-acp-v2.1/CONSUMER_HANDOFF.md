# Remote ACP v2.1 Consumer Handoff

## Pin

- Aggregate: `contracts/remote-expert-frontend/v2.1.0/`
- Consumer digest (sha256 of SHA256SUMS): see sealed `SHA256SUMS` / verifier output `aggregateConsumerDigest`
- Discovery exact-match fail-closed remains. Additive fields do not keep a v2.0 pin valid.

## Behavior changes for SMC

1. Assistant deltas + matching snapshot must not double-append.
2. Tool frames may include `rawInput`, `content`, `structuredContent`, `errorCode`, `errorMessage`, `redacted`, `truncated`. Status `started` maps to `in_progress`.
3. `seq` is Turn/Run scoped. New Prompt after terminal uses `after_seq=0`.
4. Continuity: same ACP Formal Session reuses Hermes runtime session when bound; never-bound allows first-turn retry; once-bound-then-missing returns `ACP_RUNTIME_SESSION_CONTINUITY_LOST`.
5. Failed runs are JSON-RPC errors (`ACP_REMOTE_RUN_FAILED` / binding codes), not successful `stopReason` results.
6. `clarify.requested` remains unique `end_turn`.

## EXT-G5

SMC Golden Consumer remains external. Provider READY is G1-G4 only.

## Deploy train (Provider)

Agent behavior and Backend `FRONTEND_CONTRACT_DIGEST` / remote-acp constants MUST ship on the same closure commit after freeze. Do not roll one without the other.
