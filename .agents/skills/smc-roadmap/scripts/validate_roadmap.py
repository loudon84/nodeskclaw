#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

STATUSES={"BACKLOG","READY","IN_PRD","PLANNED","IMPLEMENTING","REVIEW","BLOCKED","DONE","SUPERSEDED"}
ROADMAP_STATUSES={"ACTIVE","SUPERSEDED"}
COLS=("Item ID","Outcome","Depends On","Status","Exit Criteria","PRD","Plan","Implementation Commit","Verification Evidence")
ID=re.compile(r"^RM-\d{2,}$")
SHA=re.compile(r"^[0-9a-fA-F]{7,40}$")
EMPTY={"","-","none","n/a","na"}
FM_FIELDS=("roadmap_id","version","status","architecture_decision","source_revision","updated_at")


def frontmatter(text: str) -> dict[str,str]:
    lines=text.splitlines()
    if not lines or lines[0].strip()!="---": return {}
    try:end=next(i for i,x in enumerate(lines[1:],1) if x.strip()=="---")
    except StopIteration:return {}
    out={}
    for line in lines[1:end]:
        if ":" in line:
            k,v=line.split(":",1);out[k.strip()]=v.strip().strip('"\'')
    return out


def iso(v: str) -> bool:
    try: datetime.fromisoformat(v.replace("Z","+00:00")); return True
    except Exception: return False


def section(text,name):
    m=re.search(rf"^##\s+{re.escape(name)}\s*$\n?(.*?)(?=^##\s+|\Z)",text,re.M|re.S); return m.group(1).strip() if m else None

def cells(line): return [x.strip() for x in line.strip().strip('|').split('|')]
def table(body):
    if not body:return [],[]
    lines=[x.strip() for x in body.splitlines() if x.strip().startswith('|')]
    for i in range(len(lines)-1):
        h=cells(lines[i]); s=cells(lines[i+1])
        if len(h)==len(s) and all(re.fullmatch(r':?-{3,}:?',x.replace(' ','')) for x in s):
            rows=[]
            for raw in lines[i+2:]:
                v=cells(raw)
                if len(v)!=len(h):break
                rows.append(dict(zip(h,v)))
            return h,rows
    return [],[]
def empty(v): return v.strip().strip('`').lower() in EMPTY
def split(v):
    if empty(v):return []
    return [x.strip().strip('`') for x in re.split(r'<br\s*/?>|[,;\n]+',v,flags=re.I) if x.strip() and not empty(x)]
def cycle(deps):
    state={k:0 for k in deps}; stack=[]
    def dfs(n):
        state[n]=1; stack.append(n)
        for d in deps.get(n,set()):
            if d not in state:continue
            if state[d]==0:
                r=dfs(d)
                if r:return r
            elif state[d]==1:return stack[stack.index(d):]+[d]
        stack.pop();state[n]=2
    for n in deps:
        if state[n]==0:
            r=dfs(n)
            if r:return r
    return None


def git_root(path: Path) -> Path | None:
    start=path.resolve().parent
    try:
        out=subprocess.check_output(["git","-C",str(start),"rev-parse","--show-toplevel"],text=True,stderr=subprocess.DEVNULL).strip()
        return Path(out)
    except Exception:return None


def commit_exists(root: Path | None, sha: str) -> bool:
    if root is None:return False
    return subprocess.run(["git","-C",str(root),"cat-file","-e",f"{sha}^{{commit}}"],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0

def resolve_repo_path(roadmap: Path, raw: str, root: Path | None) -> Path | None:
    value=raw.strip().strip('`')
    if not value:return None
    candidate=Path(value)
    options=[candidate] if candidate.is_absolute() else [roadmap.parent/candidate]
    if root and not candidate.is_absolute():options.append(root/candidate)
    for option in options:
        if option.resolve().is_file():return option.resolve()
    return None

def architecture_is_approved(path: Path) -> bool:
    text=path.read_text(encoding='utf-8')
    fm=frontmatter(text)
    return fm.get('status')=='APPROVED' and fm.get('review_verdict')=='PASS' and bool(fm.get('approved_at'))

def validate(path, check_git=True, check_architecture=True):
    text=path.read_text(encoding='utf-8'); errors=[]
    fm=frontmatter(text)
    if not fm: errors.append('ROADMAP_FRONTMATTER_MISSING')
    else:
        for field in FM_FIELDS:
            if not fm.get(field):errors.append(f'ROADMAP_FRONTMATTER_FIELD_REQUIRED: {field}')
        if fm.get('status') and fm['status'].upper() not in ROADMAP_STATUSES:errors.append(f"ROADMAP_STATE_INVALID: {fm['status']}")
        if fm.get('updated_at') and not iso(fm['updated_at']):errors.append('ROADMAP_UPDATED_AT_INVALID')
        if check_architecture and fm.get('architecture_decision'):
            root=git_root(path)
            arch=resolve_repo_path(path,fm['architecture_decision'],root)
            if arch is None:errors.append(f"ROADMAP_ARCHITECTURE_UNRESOLVED: {fm['architecture_decision']}")
            elif not architecture_is_approved(arch):errors.append(f"ROADMAP_ARCHITECTURE_NOT_APPROVED: {arch}")

    body=section(text,'Roadmap Items'); h,rows=table(body)
    if not h:return errors+['ROADMAP_TABLE_MISSING']
    for c in COLS:
        if c not in h:errors.append(f'ROADMAP_COLUMN_MISSING: {c}')
    if any(c not in h for c in COLS):return errors

    seen=set(); statuses={}; deps={}; prd_owner={}; plan_owner={}; root=git_root(path) if check_git else None
    for i,r in enumerate(rows,1):
        iid=r['Item ID'].strip(); st=r['Status'].strip().upper(); ds=set(split(r['Depends On']))
        if not ID.fullmatch(iid):errors.append(f'ROADMAP_ITEM_ID_INVALID: row {i}: {iid}')
        if iid in seen:errors.append(f'ROADMAP_ITEM_DUPLICATE: {iid}')
        seen.add(iid); statuses[iid]=st; deps[iid]=ds
        if st not in STATUSES:errors.append(f'ROADMAP_STATUS_INVALID: {iid}: {st}')
        if empty(r['Outcome']):errors.append(f'ROADMAP_OUTCOME_EMPTY: {iid}')
        if empty(r['Exit Criteria']):errors.append(f'ROADMAP_EXIT_CRITERIA_EMPTY: {iid}')

        prd=r['PRD'].strip().strip('`'); plan=r['Plan'].strip().strip('`')
        if not empty(prd):
            previous=prd_owner.setdefault(prd,iid)
            if previous!=iid:errors.append(f'ROADMAP_STAGE_PRD_REUSED: {prd}: {previous},{iid}')
        if not empty(plan):
            previous=plan_owner.setdefault(plan,iid)
            if previous!=iid:errors.append(f'ROADMAP_PLAN_REUSED: {plan}: {previous},{iid}')

        if st in {'IN_PRD','PLANNED','IMPLEMENTING','REVIEW','DONE'} and empty(r['PRD']):errors.append(f'ROADMAP_PRD_REQUIRED: {iid}')
        if st in {'PLANNED','IMPLEMENTING','REVIEW','DONE'} and empty(r['Plan']):errors.append(f'ROADMAP_PLAN_REQUIRED: {iid}')
        if st=='DONE':
            sha=r['Implementation Commit'].strip().strip('`')
            if not SHA.fullmatch(sha):errors.append(f'ROADMAP_IMPLEMENTATION_COMMIT_REQUIRED: {iid}')
            elif check_git and not commit_exists(root,sha):errors.append(f'ROADMAP_IMPLEMENTATION_COMMIT_NOT_FOUND: {iid}: {sha}')
            if empty(r['Verification Evidence']):errors.append(f'ROADMAP_VERIFICATION_REQUIRED: {iid}')
    for iid,ds in deps.items():
        for d in ds:
            if d not in seen:errors.append(f'ROADMAP_DEPENDENCY_UNKNOWN: {iid}->{d}')
        if statuses.get(iid)=='READY':
            for d in ds:
                if statuses.get(d)!='DONE':errors.append(f'ROADMAP_READY_DEPENDENCY_NOT_DONE: {iid}->{d}')
    c=cycle(deps)
    if c:errors.append('ROADMAP_DEPENDENCY_CYCLE: '+' -> '.join(c))
    return errors


def main():
    ap=argparse.ArgumentParser();ap.add_argument('roadmap',type=Path);ap.add_argument('--no-git-check',action='store_true',help='test/migration escape hatch; production check should keep git validation on');ap.add_argument('--no-architecture-check',action='store_true',help='test/migration escape hatch')
    a=ap.parse_args();e=validate(a.roadmap.resolve(),check_git=not a.no_git_check,check_architecture=not a.no_architecture_check)
    if e:print('\n'.join(e),file=sys.stderr);return 1
    print('Roadmap validation passed');return 0
if __name__=='__main__':raise SystemExit(main())
