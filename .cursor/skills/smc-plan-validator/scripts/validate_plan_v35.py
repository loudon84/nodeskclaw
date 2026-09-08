#!/usr/bin/env python3
"""SMC Plan v3.5 validator: v3.4 governance plus Domain Pack contract."""
from __future__ import annotations
import argparse, importlib.util, json, sys
from pathlib import Path

HERE=Path(__file__).resolve().parent
DELIVERY=HERE.parents[1]/'smc-plan-delivery'/'scripts'
sys.path.insert(0,str(DELIVERY))
from acceptance import validate_contract as validate_acceptance  # type: ignore
from validate_plan_v33 import validate_plan  # type: ignore

def repo_root(plan:Path)->Path:
    p=plan.resolve().parent
    for c in (p,*p.parents):
        if (c/'.agents').is_dir() or (c/'.git').exists(): return c
    raise ValueError('DOMAIN_REPO_ROOT_NOT_FOUND')

def domain_module(plan:Path):
    repo=repo_root(plan);target=repo/'.agents/ges/domain-runtime/domain_runtime.py'
    if not target.is_file(): raise ValueError(f'DOMAIN_RUNTIME_MISSING: {target}')
    spec=importlib.util.spec_from_file_location('ges_domain_runtime_validate',target)
    if spec is None or spec.loader is None: raise ValueError('DOMAIN_RUNTIME_IMPORT_FAILED')
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod

def main()->int:
    ap=argparse.ArgumentParser();ap.add_argument('plan',type=Path);ap.add_argument('--json',action='store_true');a=ap.parse_args();plan=a.plan.resolve()
    if not plan.is_file():
        payload={'valid':False,'plan':str(plan),'errors':[{'code':'PLAN_NOT_FOUND','detail':str(plan)}]};print(json.dumps(payload,ensure_ascii=False,indent=2) if a.json else f'PLAN_NOT_FOUND: {plan}');return 2
    errors=validate_plan(plan,'smc.plan.v3.5');errors.extend(validate_acceptance(plan))
    try: errors.extend(domain_module(plan).validate_plan(plan))
    except ValueError as exc: errors.append({'code':str(exc).split(':',1)[0],'detail':str(exc)})
    if a.json: print(json.dumps({'valid':not errors,'plan':str(plan),'errors':errors},ensure_ascii=False,indent=2))
    elif errors: print('\n'.join(f"{e['code']}: {e['detail']}".rstrip(': ') for e in errors),file=sys.stderr)
    else: print('Plan v3.5 validation passed')
    return 1 if errors else 0
if __name__=='__main__': raise SystemExit(main())
