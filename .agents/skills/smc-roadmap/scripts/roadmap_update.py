#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from datetime import datetime,timezone
from pathlib import Path

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('roadmap_validator',HERE/'validate_roadmap.py')
validator=importlib.util.module_from_spec(spec);assert spec and spec.loader;spec.loader.exec_module(validator)


def cells(line):return [x.strip() for x in line.strip().strip('|').split('|')]


def main():
    ap=argparse.ArgumentParser();ap.add_argument('roadmap',type=Path);ap.add_argument('item_id');ap.add_argument('--status',required=True)
    ap.add_argument('--prd');ap.add_argument('--plan');ap.add_argument('--implementation-commit');ap.add_argument('--verification');a=ap.parse_args()
    p=a.roadmap.resolve();original=p.read_text(encoding='utf-8');lines=original.splitlines();header=None;sep=None
    for i,line in enumerate(lines):
        if line.strip().startswith('|') and 'Item ID' in line and 'Verification Evidence' in line:
            header=cells(line);sep=i;break
    if header is None:print('ROADMAP_TABLE_MISSING',file=sys.stderr);return 1
    try:idx={k:header.index(k) for k in header}
    except ValueError as e:print(f'ROADMAP_COLUMN_MISSING: {e}',file=sys.stderr);return 1
    found=False
    for i in range(sep+2,len(lines)):
        if not lines[i].strip().startswith('|'):break
        vals=cells(lines[i])
        if len(vals)!=len(header):continue
        if vals[idx['Item ID']].strip()==a.item_id:
            found=True;vals[idx['Status']]=a.status.upper()
            for arg,col in ((a.prd,'PRD'),(a.plan,'Plan'),(a.implementation_commit,'Implementation Commit'),(a.verification,'Verification Evidence')):
                if arg is not None:vals[idx[col]]=arg
            lines[i]='| '+' | '.join(vals)+' |';break
    if not found:print(f'ROADMAP_ITEM_NOT_FOUND: {a.item_id}',file=sys.stderr);return 1
    now=datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
    for i,line in enumerate(lines[:30]):
        if line.startswith('updated_at:'):lines[i]=f'updated_at: {now}';break
    candidate='\n'.join(lines)+'\n';p.write_text(candidate,encoding='utf-8')

    errors=validator.validate(p,check_git=True,check_architecture=True)
    if errors:
        p.write_text(original,encoding='utf-8')
        print('ROADMAP_UPDATE_REJECTED',file=sys.stderr)
        print('\n'.join(errors),file=sys.stderr)
        return 1

    print(f'Roadmap updated: {a.item_id} -> {a.status.upper()}')
    print(f'Suggested commit: chore(roadmap): update {a.item_id} to {a.status.upper()}')
    return 0
if __name__=='__main__':raise SystemExit(main())
