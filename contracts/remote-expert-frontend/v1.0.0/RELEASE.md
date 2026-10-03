# REMOTE-EXPERT-FRONTEND-CONTRACT v1.0.0

1. This aggregate is the cross-repository frontend handoff for `smc-copilot/apps/work`.
2. Remote Expert must integrate through ACP v1; it MUST NOT depend on `WORK-EXPERT-CONTRACT`.
3. Remote Expert MUST NOT use Skill Run execution paths.
4. Component contracts remain pinned by `sha256(raw SHA256SUMS bytes)` as SOT.
5. The annotated Git tag `remote-expert-frontend-contract-v1.0.0` is a discovery/freeze handle; it does not replace digest validation.
6. `productionGate` remains `unpassed` until real LIVE evidence exists.
7. Frontend development on Original Chat / Compose / ACP may proceed against this freeze.
8. Production rollout must wait for separate live gates (Windows clean-machine, managed auth, attachments, approvals, Zed regression).
