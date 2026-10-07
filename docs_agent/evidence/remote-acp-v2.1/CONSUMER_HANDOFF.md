# Remote ACP v2.1 Consumer Handoff

## Pin

- Aggregate: `contracts/remote-expert-frontend/v2.1.0/`
- Status: `FROZEN` / `frontendContractGate=passed`
- Implementation SHA (G3 PASS): `3205fdcac003fc91d5a04349c2813b815bc0342b`
- Aggregate consumer digest: `b25a9edbf2fa5afd6f15cb1cc1f8b17d6cb63b613bf18a2212e75002c61b4aba`
- Remote ACP gateway digest: `86668a0a013ca3aef08f11611c6c32cb7643918caf21f5d530049b0d0a1a28be`
- Runtime gateway digest: `0c796f63391a5585f7a57318d7b202eb57a65039ee27555adabefce53287e17a`
- Catalog digest (unchanged): `d51d27a33e6776be780bf3556ffa4ef4f6dab7f731c0a48421683708364efd2c`
- Discovery exact-match fail-closed remains. Additive fields do not keep a v2.0 pin valid.
- Backend discovery must advertise `frontendContractVersion=2.1.0` and digests above after the same closure deploy.

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
