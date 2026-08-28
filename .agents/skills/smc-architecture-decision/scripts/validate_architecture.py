#!/usr/bin/env python3
from __future__ import annotations
import argparse, re, subprocess, sys
from datetime import datetime
from pathlib import Path

STATUSES={"DRAFT","REVIEW_REQUIRED","APPROVED","SUPERSEDED"}
FIELDS={"decision_id","version","status","target_branch","review_verdict","approved_at","source_revision","grounded_commit"}
SECTIONS=("Problem","Decision Drivers","Evidence Baseline","Current Capability","Options Considered","Decision","Target Architecture","Ownership & Boundaries","Dependencies & Cascading Effects","Risks & Kill Criteria","Rejected Alternatives","Roadmap Boundaries")
SHA=re.compile(r"^[0-9a-fA-F]{7,40}$")

def fm(text):
    lines=text.splitlines()
    if not lines or lines[0].strip()!='---': raise ValueError('frontmatter missing')
    try: end=next(i for i,x in enumerate(lines[1:],1) if x.strip()=='---')
    except StopIteration: raise ValueError('frontmatter not closed')
    out={}
    for line in lines[1:end]:
        if ':' in line:
            k,v=line.split(':',1); out[k.strip()]=v.strip().strip('"\'')
    return out

def section(text,name):
    m=re.search(rf"^##\s+{re.escape(name)}\s*$\n?(.*?)(?=^##\s+|\Z)",text,re.M|re.S)
    return m.group(1).strip() if m else None

def iso(v):
    try: datetime.fromisoformat(v.replace('Z','+00:00')); return True
    except Exception: return False


def git_root(path):
    try:
        out=subprocess.check_output(["git","-C",str(path.resolve().parent),"rev-parse","--show-toplevel"],text=True,stderr=subprocess.DEVNULL).strip()
        return Path(out)
    except Exception:return None

def commit_exists(root,sha):
    if not root:return True
    return subprocess.run(["git","-C",str(root),"cat-file","-e",f"{sha}^{{commit}}"],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0

def validate(path, require_approved=False):
    text=path.read_text(encoding='utf-8'); errors=[]
    try: fields=fm(text)
    except ValueError as e: return [f"ARCH_INVALID: {e}"]
    for k in sorted(FIELDS-set(fields)): errors.append(f"ARCH_INVALID: missing {k}")
    for k in ('decision_id','version','target_branch','source_revision'):
        if k in fields and not fields[k]: errors.append(f"ARCH_INVALID: {k} must not be empty")
    status=fields.get('status','')
    if status not in STATUSES: errors.append('ARCH_STATE_INVALID: invalid status')
    if status in {'DRAFT','REVIEW_REQUIRED'}:
        if fields.get('review_verdict'): errors.append(f'ARCH_STATE_INVALID: {status} review_verdict must be empty')
        if fields.get('approved_at'): errors.append(f'ARCH_STATE_INVALID: {status} approved_at must be empty')
    if status=='APPROVED':
        if fields.get('review_verdict')!='PASS': errors.append('ARCH_STATE_INVALID: APPROVED review_verdict must be PASS')
        if not iso(fields.get('approved_at','')): errors.append('ARCH_STATE_INVALID: APPROVED approved_at must be ISO-8601')
        if path.name.endswith('-DRAFT.md'): errors.append('ARCH_APPROVED_FILENAME_HAS_DRAFT')
    if require_approved and status!='APPROVED': errors.append('ARCH_NOT_APPROVED')
    grounded=fields.get('grounded_commit','')
    if status in {'REVIEW_REQUIRED','APPROVED'} and not SHA.fullmatch(grounded):
        errors.append('ARCH_EVIDENCE_INVALID: grounded_commit must be a git SHA')
    elif status in {'REVIEW_REQUIRED','APPROVED'} and not commit_exists(git_root(path),grounded):
        errors.append('ARCH_EVIDENCE_INVALID: grounded_commit does not resolve to a git commit')
    for name in SECTIONS:
        body=section(text,name)
        if body is None: errors.append(f'ARCH_INVALID: missing section {name}')
        elif not body: errors.append(f'ARCH_INVALID: empty section {name}')
    return errors

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('architecture',type=Path); ap.add_argument('--require-approved',action='store_true'); a=ap.parse_args()
    errs=validate(a.architecture.resolve(),a.require_approved)
    if errs: print('\n'.join(errs),file=sys.stderr); return 1
    print('Architecture validation passed'); return 0
if __name__=='__main__': raise SystemExit(main())
