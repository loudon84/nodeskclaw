#!/usr/bin/env python3
from __future__ import annotations
import argparse,re
from pathlib import Path

def section(text,name):
    m=re.search(rf"^##\s+{re.escape(name)}\s*$\n?(.*?)(?=^##\s+|\Z)",text,re.M|re.S)
    return m.group(1).strip() if m else ''
def cells(line): return [x.strip() for x in line.strip().strip('|').split('|')]
def table(body):
    lines=[x.strip() for x in body.splitlines() if x.strip().startswith('|')]
    for i in range(len(lines)-1):
        h=cells(lines[i]); s=cells(lines[i+1])
        if len(h)==len(s) and all(re.fullmatch(r':?-{3,}:?',x.replace(' ','')) for x in s):
            rows=[]
            for raw in lines[i+2:]:
                v=cells(raw)
                if len(v)!=len(h): break
                rows.append(dict(zip(h,v)))
            return rows
    return []
def assess(text):
    reasons=[]
    matrix=table(section(text,'Change Matrix'))
    decisions=table(section(text,'Implementation Decisions'))
    ledger=table(section(text,'Write Ownership Ledger'))
    if any(r.get('Strategy','').strip().upper()=='NEW_DEPENDENCY' for r in decisions): reasons.append('NEW_DEPENDENCY')
    if any(r.get('Action','').strip().upper()=='REPLACE' for r in matrix): reasons.append('REPLACE')
    if sum(r.get('Strategy','').strip().upper()=='MINIMAL_NEW' for r in decisions)>=2: reasons.append('MULTIPLE_MINIMAL_NEW')
    if sum(r.get('Kind','').strip().upper()=='PROD' and r.get('New File?','').strip().lower()=='yes' for r in matrix)>=2: reasons.append('MULTIPLE_NEW_PROD_FILES')
    hot=section(text,'Integration Hotspots')
    if hot and hot.strip().lower() not in {'none','-','n/a'}: reasons.append('INTEGRATION_HOTSPOT')
    joined=' '.join((r.get('PRD Capability','')+' '+r.get('Target State','')) for r in matrix)
    if re.search(r'\b(auth|security|secret|permission|trust|authorization|credential)\b|鉴权|认证|授权|权限|安全|密钥|凭据|信任边界',joined,re.I): reasons.append('SECURITY_OR_TRUST_BOUNDARY')
    todo_count=len(re.findall(r'^##\s+Todo\s+T\d+\b',text,re.M))
    cross_read=sum(bool(r.get('Reads','').strip() not in {'','-','none','None'} and r.get('Depends On','').strip() not in {'','-','none','None'}) for r in ledger)
    if todo_count>=4 and cross_read: reasons.append('COMPLEX_CROSS_TODO_DEPENDENCY')
    return reasons
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('plan',type=Path); a=ap.parse_args()
    reasons=assess(a.plan.read_text(encoding='utf-8'))
    if reasons:
        print('REQUIRED')
        for x in reasons: print(f'- {x}')
        return 2
    print('NOT_REQUIRED'); return 0
if __name__=='__main__': raise SystemExit(main())
