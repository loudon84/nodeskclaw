# Remote ACP v2.1 G4 Freeze

- Status: PASS
- Implementation SHA (G3 live): `3205fdcac003fc91d5a04349c2813b815bc0342b`
- Tool: `python tools/contracts/freeze_remote_acp_v21.py --implementation-sha <sha>`
- Aggregate digest: `b25a9edbf2fa5afd6f15cb1cc1f8b17d6cb63b613bf18a2212e75002c61b4aba`
- Remote ACP gateway digest: `86668a0a013ca3aef08f11611c6c32cb7643918caf21f5d530049b0d0a1a28be`
- Runtime gateway digest: `0c796f63391a5585f7a57318d7b202eb57a65039ee27555adabefce53287e17a`
- Backend constants: `FRONTEND_CONTRACT_VERSION=2.1.0`, `REMOTE_ACP_CONTRACT_VERSION=1.1.0`
- v2.0.0 aggregate digest unchanged: `22ad68dd1132a073f6df5d2bf9f219b683c73ebb7ea1fa48933c9b92a744ecd5`
- Verifier: `tools/contracts/verify_remote_expert_frontend_contract_v21.py` → ok / status FROZEN / frontendContractGate=passed
- Live evidence: `A-NACP-007.json`, `g3-live-latest.json`
- EXT-G5: still external (SMC Golden)
