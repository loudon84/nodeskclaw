#!/usr/bin/env python3
from __future__ import annotations
import importlib.util,json,tempfile
from pathlib import Path

HERE=Path(__file__).resolve().parent

def load():
    spec=importlib.util.spec_from_file_location('domain_runtime_tests',HERE/'domain_runtime.py');assert spec and spec.loader
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod

def test_fixture_pack():
    mod=load()
    with tempfile.TemporaryDirectory() as td:
        repo=Path(td);(repo/'.git').mkdir();ges=repo/'.agents/ges';packs=ges/'domain-packs/fixture';packs.mkdir(parents=True);(ges/'domain-packs/registry.json').write_text(json.dumps({'schema':'smc.ges.domain-registry.v1','packs':{'fixture':{'path':'fixture/pack.json'}}}),encoding='utf-8');(packs/'pack.json').write_text(json.dumps({'schema':'smc.ges.domain-pack.v1','id':'fixture','version':'1.0.0','activation_rules':'activation.json','capabilities':{'engineering':{'skill':'fixture-engineering'}}}),encoding='utf-8');(packs/'activation.json').write_text(json.dumps({'schema':'smc.ges.domain-activation-rules.v1','extensions':['.fixture']}),encoding='utf-8');(ges/'profile.json').write_text(json.dumps({'schema':'smc.ges.consumer-profile.v2','id':'x','version':'1.0.0','domains':{'fixture':{'activation':'auto'}}}),encoding='utf-8');plan=repo/'x.plan.md';plan.write_text('''---\nplan_contract: smc.plan.v3.5\n---\n## Change Matrix\n\n| Change ID | File / Symbol | Kind | Action | Existing Owner | Todo Owner | Target State | PRD Capability | New File? |\n|---|---|---|---|---|---|---|---|---|\n| C01 | `src/a.fixture#x` | PROD | MODIFY | x | T1 | x | x | no |\n''',encoding='utf-8');r=mod.resolve(plan);assert r['domains'][0]['status']=='REQUIRED';assert mod.providers(plan,'engineering')[0]['skill']=='fixture-engineering'

if __name__=='__main__':
    test_fixture_pack();print('DOMAIN RUNTIME SELFTEST PASS')
