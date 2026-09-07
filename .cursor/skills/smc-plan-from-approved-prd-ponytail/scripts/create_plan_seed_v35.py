#!/usr/bin/env python3
"""Create smc.plan.v3.5 seed with deterministic Domain Activation binding."""
from __future__ import annotations
import argparse, importlib.util, os, sys, tempfile
from pathlib import Path

HERE=Path(__file__).resolve().parent
V34=HERE/'create_plan_seed.py'

def load_v34():
    spec=importlib.util.spec_from_file_location('ges_v34_seed',V34)
    if spec is None or spec.loader is None: raise RuntimeError('PLAN_V34_GENERATOR_NOT_FOUND')
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod

def find_repo(path:Path)->Path:
    p=path.resolve();p=p.parent if p.suffix else p
    for c in (p,*p.parents):
        if (c/'.agents').is_dir() or (c/'.git').exists(): return c
    raise ValueError('PLAN_REPO_ROOT_NOT_FOUND')

def load_domain(repo:Path):
    target=repo/'.agents/ges/domain-runtime/domain_runtime.py'
    if not target.is_file(): raise ValueError(f'DOMAIN_RUNTIME_MISSING: {target}')
    spec=importlib.util.spec_from_file_location('ges_domain_runtime',target)
    if spec is None or spec.loader is None: raise ValueError('DOMAIN_RUNTIME_IMPORT_FAILED')
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod

def inject_before(text:str, marker:str, block:str)->str:
    if marker not in text: raise ValueError(f'PLAN_SEED_MARKER_MISSING: {marker}')
    return text.replace(marker,block+'\n\n'+marker,1)

def main()->int:
    ap=argparse.ArgumentParser();ap.add_argument('prd',type=Path);ap.add_argument('output',type=Path);ap.add_argument('--plan-id',required=True);a=ap.parse_args()
    prd=a.prd.resolve();out=a.output.resolve()
    if not prd.is_file(): print(f'PRD_NOT_FOUND: {prd}',file=sys.stderr);return 2
    if out.exists(): print(f'PLAN_ALREADY_EXISTS: {out}',file=sys.stderr);return 2
    v34=load_v34();text=prd.read_text(encoding='utf-8')
    try:
        meta=v34.fm(text)
        if meta.get('status')!='APPROVED': raise ValueError('PRD_NOT_APPROVED')
        if meta.get('review_verdict')!='PASS': raise ValueError('PRD_REVIEW_NOT_PASS')
        if not meta.get('approved_at'): raise ValueError('PRD_APPROVED_AT_MISSING')
        chs=v34.changes(text); reqs=v34.requirements(text)
        base=v34.render(prd,out,meta,a.plan_id,chs,reqs).replace('plan_contract: smc.plan.v3.4','plan_contract: smc.plan.v3.5',1)
        repo=find_repo(out); domain=load_domain(repo)
        out.parent.mkdir(parents=True,exist_ok=True)
        with tempfile.NamedTemporaryFile('w',encoding='utf-8',suffix='.plan.md',prefix='.ges-domain-',dir=out.parent,delete=False) as fh:
            fh.write(base); temp=Path(fh.name)
        try:
            activation=domain.resolve(temp)
            profile_line=f"consumer_profile: {activation['profile']}"
            contract_lines='\n'.join([
                'domain_contract: smc.ges.domain-activation.v1',
                profile_line,
                f"domain_policy_digest: {activation['policy_digest']}",
            ])
            base=base.replace(f'plan_id: {a.plan_id}',f'plan_id: {a.plan_id}\n{contract_lines}',1)
            ledger=domain.activation_ledger(activation)
            extensions=domain.render_extensions(temp,activation)
            block=ledger + ('\n\n'+extensions if extensions else '')
            base=inject_before(base,'## Implementation Decisions',block)
        finally:
            temp.unlink(missing_ok=True)
    except (ValueError,RuntimeError) as exc:
        print(str(exc),file=sys.stderr);return 1
    out.write_text(base,encoding='utf-8')
    print(f"Plan v3.5 seed created: {out}\nPlan ID: {a.plan_id}\nTodos: {len(chs)}\nRequirements: {len(reqs)}\nDomain binding embedded; seed remains non-executable until placeholders are grounded and all gates pass.")
    return 0
if __name__=='__main__': raise SystemExit(main())
