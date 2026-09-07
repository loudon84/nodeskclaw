#!/usr/bin/env python3
"""Generic smc-plan-delivery bridge to installed Domain Pack providers.

This module deliberately contains no domain ids. It binds the Plan to the installed
Domain Contract and reports provider skills for engineering/review/verification.
"""
from __future__ import annotations
import argparse, importlib.util, json, sys
from pathlib import Path

def root(plan:Path)->Path:
    p=plan.resolve().parent
    for c in (p,*p.parents):
        if (c/'.agents/ges/domain-runtime/domain_runtime.py').is_file(): return c
    raise ValueError('DOMAIN_RUNTIME_MISSING')

def runtime(plan:Path):
    target=root(plan)/'.agents/ges/domain-runtime/domain_runtime.py';spec=importlib.util.spec_from_file_location('ges_domain_runtime_delivery',target)
    if spec is None or spec.loader is None: raise ValueError('DOMAIN_RUNTIME_IMPORT_FAILED')
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod

def main()->int:
    ap=argparse.ArgumentParser();sub=ap.add_subparsers(dest='cmd',required=True)
    for name in ('validate','assert-policy'):
        p=sub.add_parser(name);p.add_argument('plan',type=Path);p.add_argument('--json',action='store_true')
    p=sub.add_parser('providers');p.add_argument('plan',type=Path);p.add_argument('--phase',choices=('engineering','review','verification'),required=True);p.add_argument('--json',action='store_true')
    a=ap.parse_args();plan=a.plan.resolve()
    try:
        mod=runtime(plan)
        if a.cmd=='validate':
            errors=mod.validate_plan(plan);payload={'valid':not errors,'errors':errors};rc=1 if errors else 0
        elif a.cmd=='assert-policy':
            payload=mod.assert_policy(plan);rc=0
        else:
            payload=mod.providers(plan,a.phase);rc=0
        print(json.dumps(payload,ensure_ascii=False,indent=2) if a.json else (('\n'.join(x['skill'] for x in payload)) if isinstance(payload,list) else ('Domain contract PASS' if rc==0 else str(payload))))
        return rc
    except ValueError as exc:
        print(json.dumps({'valid':False,'error':str(exc)},ensure_ascii=False,indent=2) if a.json else str(exc),file=sys.stdout if a.json else sys.stderr);return 2
if __name__=='__main__': raise SystemExit(main())
