#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,re,subprocess,sys
from pathlib import Path

def frontmatter(text):
    lines=text.splitlines()
    if not lines or lines[0].strip()!='---': return {}
    try:end=next(i for i,x in enumerate(lines[1:],1) if x.strip()=='---')
    except StopIteration:return {}
    out={}
    for line in lines[1:end]:
        if ':' in line:
            k,v=line.split(':',1);out[k.strip()]=v.strip().strip('"\'')
    return out

def repo_root(path):
    p=path.resolve().parent
    for c in (p,*p.parents):
        if (c/'.git').exists(): return c
    return None

def git(root,*args):
    return subprocess.check_output(['git','-C',str(root),*args],text=True,stderr=subprocess.DEVNULL).strip()

def anchors(text):
    found=set()
    for heading in ('Evidence Baseline','Source Anchors','Current Capability Inventory'):
        m=re.search(rf"^##\s+{re.escape(heading)}\s*$\n?(.*?)(?=^##\s+|\Z)",text,re.M|re.S)
        if not m: continue
        for x in re.findall(r'`([^`]+)`',m.group(1)):
            path=x.split('#',1)[0].replace('\\','/').strip()
            if '/' in path: found.add(path)
    return found

def overlaps(changed, anchor):
    a=anchor.rstrip('/')
    return changed==a or changed.startswith(a+'/') or a.startswith(changed.rstrip('/')+'/')

def evaluate(path,current_source=None):
    text=path.read_text(encoding='utf-8');fm=frontmatter(text);root=repo_root(path)
    stored_source=fm.get('source_revision',''); grounded=fm.get('grounded_commit','')
    if not root or not grounded:return {'state':'UNKNOWN','reason':'missing git root or grounded_commit'}
    try:head=git(root,'rev-parse','HEAD')
    except Exception:return {'state':'UNKNOWN','reason':'cannot resolve HEAD'}
    if current_source and stored_source and current_source!=stored_source:
        return {'state':'REGROUND_REQUIRED','reason':'source_revision changed','head':head,'grounded_commit':grounded}
    if head==grounded:return {'state':'REUSE','reason':'source and repository revision unchanged','head':head}
    try:changed=[x for x in git(root,'diff','--name-only',f'{grounded}..{head}').splitlines() if x.strip()]
    except Exception:return {'state':'REGROUND_REQUIRED','reason':'grounded_commit not comparable to HEAD','head':head}
    a=anchors(text)
    if not a:return {'state':'REGROUND_REQUIRED','reason':'repository changed and no reusable anchors recorded','changed_files':changed}
    hit=sorted({c for c in changed if any(overlaps(c,x) for x in a)})
    if hit:return {'state':'REGROUND_REQUIRED','reason':'repository changes intersect evidence anchors','changed_files':hit}
    return {'state':'VERIFY_ONLY','reason':'repository moved but recorded evidence anchors were untouched','changed_files':changed}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('artifact',type=Path);ap.add_argument('--source-revision');ap.add_argument('--json',action='store_true');a=ap.parse_args()
    r=evaluate(a.artifact.resolve(),a.source_revision)
    if a.json:print(json.dumps(r,ensure_ascii=False,indent=2))
    else:print(r['state']+': '+r['reason'])
    return 0
if __name__=='__main__':raise SystemExit(main())
