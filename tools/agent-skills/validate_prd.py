#!/usr/bin/env python3
from __future__ import annotations
import argparse,re,subprocess,sys
from datetime import datetime
from pathlib import Path
STATUSES={'DRAFT','REVIEW_REQUIRED','APPROVED','SUPERSEDED'}
FIELDS={'work_item_id','version','status','target_branch','review_verdict','approved_at'}
SECTIONS=('Current Capability Inventory','Target End-State Inventory','Change Classification','Acceptance Criteria')
ACTIONS={'KEEP','MODIFY','ADD','REPLACE','REMOVE'}
SHA=re.compile(r'^[0-9a-fA-F]{7,40}$')
CHANGE_ID=re.compile(r'^C\d{2,}(?:\.\d+)?$')

def fm(text):
    lines=text.splitlines()
    if not lines or lines[0].strip()!='---':raise ValueError('frontmatter missing')
    try:end=next(i for i,x in enumerate(lines[1:],1) if x.strip()=='---')
    except StopIteration:raise ValueError('frontmatter not closed')
    out={}
    for line in lines[1:end]:
        if ':' in line:
            k,v=line.split(':',1);out[k.strip()]=v.strip().strip('"\'')
    return out

def section(text,name):
    m=re.search(rf'^##\s+{re.escape(name)}\s*$\n?(.*?)(?=^##\s+|\Z)',text,re.M|re.S);return m.group(1).strip() if m else None

def iso(v):
    try:datetime.fromisoformat(v.replace('Z','+00:00'));return True
    except Exception:return False

def cells(line):return [x.strip() for x in line.strip().strip('|').split('|')]
def table(body):
    if not body:return [],[]
    lines=[x.strip() for x in body.splitlines() if x.strip().startswith('|')]
    for i in range(len(lines)-1):
        h=cells(lines[i]);s=cells(lines[i+1])
        if len(h)==len(s) and all(re.fullmatch(r':?-{3,}:?',x.replace(' ','')) for x in s):
            rows=[]
            for raw in lines[i+2:]:
                v=cells(raw)
                if len(v)!=len(h):break
                rows.append(dict(zip(h,v)))
            return h,rows
    return [],[]


def git_root(path):
    try:
        out=subprocess.check_output(["git","-C",str(path.resolve().parent),"rev-parse","--show-toplevel"],text=True,stderr=subprocess.DEVNULL).strip()
        return Path(out)
    except Exception:return None

def commit_exists(root,sha):
    if not root:return True  # standalone fixture/package validation: format check only
    return subprocess.run(["git","-C",str(root),"cat-file","-e",f"{sha}^{{commit}}"],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0

def validate(path,require_approved=False,require_evidence=False):
    text=path.read_text(encoding='utf-8');errors=[]
    try:f=fm(text)
    except ValueError as e:return [f'PRD_INVALID: {e}']
    for k in sorted(FIELDS-set(f)):errors.append(f'PRD_INVALID: missing {k}')
    for k in ('work_item_id','version','target_branch'):
        if k in f and not f[k]:errors.append(f'PRD_INVALID: {k} must not be empty')
    st=f.get('status','')
    if st not in STATUSES:errors.append('PRD_STATE_INVALID: invalid status')
    if st in {'DRAFT','REVIEW_REQUIRED'}:
        if f.get('review_verdict'):errors.append(f'PRD_STATE_INVALID: {st} review_verdict must be empty')
        if f.get('approved_at'):errors.append(f'PRD_STATE_INVALID: {st} approved_at must be empty')
    if st=='APPROVED':
        if f.get('review_verdict')!='PASS':errors.append('PRD_STATE_INVALID: APPROVED review_verdict must be PASS')
        if not iso(f.get('approved_at','')):errors.append('PRD_STATE_INVALID: APPROVED approved_at must be ISO-8601')
        if path.name.endswith('-DRAFT.md'):errors.append('PRD_APPROVED_FILENAME_HAS_DRAFT')
    if require_approved and st!='APPROVED':errors.append('PRD_NOT_APPROVED')
    for s in SECTIONS:
        b=section(text,s)
        if b is None:errors.append(f'PRD_INVALID: missing section {s}')
        elif not b:errors.append(f'PRD_INVALID: empty section {s}')
    change=section(text,'Change Classification')
    actions=re.findall(r'\|\s*(KEEP|MODIFY|ADD|REPLACE|REMOVE)\s*\|',change or '')
    if not actions:errors.append('PRD_INVALID: Change Classification has no action')
    if 'REPLACE' in actions:
        rep=section(text,'Replacement / Removal Matrix')
        if not rep or not re.search(r'\bREMOVE\b|removal',rep,re.I):errors.append('PRD_REPLACEMENT_WITHOUT_REMOVAL')
    if require_evidence:
        if not f.get('source_revision'):errors.append('PRD_EVIDENCE_INVALID: source_revision required')
        if not SHA.fullmatch(f.get('grounded_commit','')):errors.append('PRD_EVIDENCE_INVALID: grounded_commit must be git SHA')
        elif not commit_exists(git_root(path),f.get('grounded_commit','')):errors.append('PRD_EVIDENCE_INVALID: grounded_commit does not resolve to a git commit')
        if not section(text,'Evidence Baseline'):errors.append('PRD_EVIDENCE_INVALID: Evidence Baseline section required')
        h,rows=table(change)
        if 'Change ID' not in h:errors.append('PRD_CHANGE_ID_REQUIRED: Change Classification missing Change ID column')
        else:
            for i,r in enumerate(rows,1):
                action=next((r.get(c,'').strip().upper() for c in h if r.get(c,'').strip().upper() in ACTIONS),'')
                if action and action!='KEEP' and not CHANGE_ID.fullmatch(r.get('Change ID','').strip().upper()):errors.append(f'PRD_CHANGE_ID_INVALID: row {i}')
    return errors

def main():
    ap=argparse.ArgumentParser();ap.add_argument('prd',type=Path);ap.add_argument('--require-approved',action='store_true');ap.add_argument('--require-evidence',action='store_true');a=ap.parse_args()
    e=validate(a.prd.resolve(),a.require_approved,a.require_evidence)
    if e:print('\n'.join(e),file=sys.stderr);return 1
    print('PRD validation passed');return 0
if __name__=='__main__':raise SystemExit(main())
