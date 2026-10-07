# REMOTE-EXPERT-FRONTEND-CONTRACT v2.1.0

Aggregate Consumer pin for Remote ACP fidelity, rich tools, terminal exactly-once, and Hermes session continuity.

## Components

- remote-expert-catalog v1.1.0 (unchanged)
- remote-acp-gateway v1.1.0
- acp-runtime-gateway v1.1.0 (internal; not directly pinable by SMC)

## Compatibility

- v2.0.0 remains frozen and historically verifiable.
- Discovery reports a single current aggregate digest. Consumers that still pin v2.0.0 become INCOMPATIBLE after freeze, even though wire fields are additive.
- To consume v2.1 semantics, SMC MUST update its pin to this aggregate digest.

## Gates

- Provider READY: G1-G4 in nodeskclaw
- EXT-G5 SMC Golden: external Desktop gate; does not block Provider freeze
