# GES Domain Runtime

Stdlib-only generic runtime for `smc.ges.domain-pack.v1`.

It deliberately has no branches for concrete domain ids. The runtime loads Consumer Profile, registry, pack manifest, activation policy and optional pack validator dynamically.

Commands after installation:

```bash
python .agents/ges/domain-runtime/domain_runtime.py resolve <plan> --json
python .agents/ges/domain-runtime/domain_runtime.py validate-plan <plan> --json
python .agents/ges/domain-runtime/domain_runtime.py providers <plan> --phase engineering --json
python .agents/ges/domain-runtime/domain_runtime.py assert-policy <plan>
```
