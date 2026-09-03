#!/usr/bin/env python3
"""Create a non-executable smc.plan.v3.3 seed from an APPROVED Stage PRD."""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

ACTIONS={"KEEP","MODIFY","ADD","REPLACE","REMOVE"}


def fm(text:str)->dict[str,str]:
    lines=text.splitlines()
    if not lines or lines[0].strip()!="---": raise ValueError("PRD_FRONTMATTER_MISSING")
    try:end=next(i for i,x in enumerate(lines[1:],1) if x.strip()=="---")
    except StopIteration:raise ValueError("PRD_FRONTMATTER_UNCLOSED")
    out={}
    for line in lines[1:end]:
        if line and not line[0].isspace() and ":" in line:
            k,v=line.split(":",1);out[k.strip()]=v.strip().strip('"\'')
    return out


def section(text:str,heading:str)->str|None:
    m=re.search(rf"^##\s+{re.escape(heading)}\s*$\n?(.*?)(?=^##\s+|\Z)",text,re.M|re.S)
    return m.group(1).strip() if m else None


def cells(line:str)->list[str]:return [x.strip() for x in line.strip().strip("|").split("|")]

def table(body:str)->list[dict[str,str]]:
    lines=[x.strip() for x in body.splitlines() if x.strip().startswith("|")]
    for i in range(len(lines)-1):
        h,s=cells(lines[i]),cells(lines[i+1])
        if len(h)==len(s) and all(re.fullmatch(r":?-{3,}:?",x.replace(" ","")) for x in s):
            rows=[]
            for raw in lines[i+2:]:
                v=cells(raw)
                if len(v)!=len(h):break
                rows.append(dict(zip(h,v)))
            return rows
    return []


def clean(v:str)->str:return re.sub(r"[`*_]","",v).strip()

def action(row:dict[str,str])->str|None:
    for v in row.values():
        c=clean(v).upper()
        for a in ACTIONS:
            if c==a or re.search(rf"\b{a}\b",c):return a
    return None

def cid(row:dict[str,str],fallback:int)->str:
    for k,v in row.items():
        if k.lower().strip() in {"change id","id","change_id"} and re.fullmatch(r"C\d{2,}(?:\.\d+)?",clean(v).upper()):return clean(v).upper()
    return f"C{fallback:02d}"

def capability(row:dict[str,str],act:str)->str:
    for token in ("capability","feature","item","scope","change","target"):
        for k,v in row.items():
            if token in k.lower() and clean(v) and clean(v).upper()!=act:return clean(v)
    return next((clean(v) for v in row.values() if clean(v) and clean(v).upper()!=act),"<PRD CAPABILITY>")

def changes(text:str)->list[tuple[str,str,str]]:
    body=section(text,"Change Classification")
    if not body:raise ValueError("PRD_CHANGE_CLASSIFICATION_MISSING")
    rows=table(body);out=[];n=1;used=set()
    for row in rows:
        a=action(row)
        if not a or a=="KEEP":continue
        c=cid(row,n)
        while c in used:c=f"C{n:02d}";n+=1
        used.add(c);out.append((c,a,capability(row,a)));n+=1
    if not out:raise ValueError("PRD_HAS_NO_NON_KEEP_CHANGE")
    return out

EXPLICIT=r"^\s*[-*]\s+\*\*([A-Za-z]+-\d+)(?:\s*/\s*[^*：:]+)?\*\*\s*[：:]\s*(.+?)\s*$"
def requirements(text:str)->list[tuple[str,str,str]]:
    out=[]
    for heading,prefix in (("Acceptance Criteria","AC"),("Definition of Done","DOD")):
        body=section(text,heading)
        if not body:raise ValueError(f"PRD_{prefix}_MISSING")
        explicit=[(m.group(1).upper(),re.sub(r"\s+"," ",clean(m.group(2)))) for m in re.finditer(EXPLICIT,body,re.M)]
        if explicit:out.extend((rid,prefix,ob) for rid,ob in explicit);continue
        items=[re.sub(r"\s+"," ",clean(m.group(1))) for m in re.finditer(r"^\s*\d+[.)]\s+(.+?)\s*$",body,re.M)]
        if not items:raise ValueError(f"PRD_{prefix}_UNPARSEABLE")
        out.extend((f"{prefix}-{i:02d}",prefix,ob) for i,ob in enumerate(items,1))
    return out

def rel(frm:Path,to:Path)->str:return os.path.relpath(to.resolve(),frm.parent.resolve()).replace("\\","/")
def slug(s:str)->str:return (re.sub(r"[^A-Za-z0-9]+","-",s).strip("-").lower()[:48] or "todo")

def render(prd:Path,out:Path,meta:dict[str,str],pid:str,chs,reqs)->str:
    title=meta.get("work_item_id") or pid
    source=meta.get("source_revision") or f"{title}@{meta.get('version','unknown')}"
    grounded=meta.get("grounded_commit") or "<GROUND>"
    cursor="\n".join([f"  - id: t{i}-{slug(cap)}\n    status: pending" for i,(_,_,cap) in enumerate(chs,1)])
    matrix=[];decisions=[];ledger=[];todos=[]
    for i,(c,a,cap) in enumerate(chs,1):
        t=f"T{i}";matrix.append(f"| {c} | `<GROUND>` | PROD | {a} | <GROUND> | {t} | <TARGET> | {cap} | no |")
        decisions.append(f"| {c} | <DECIDE> | <GROUND> | <DECIDE> |")
        ledger.append(f"| {t} | {c} | `<GROUND>` | - | - | no |")
        todos.append(f"## Todo {t} — {cap}\n\n**Owns Changes**\n- {c}\n\n**Goal**\n<DECIDE>\n\n**Immediate anchors**\n- `<GROUND>`\n\n**Changes**\n- <DECIDE>\n\n**Stop conditions**\n- [ ] <VERIFY>\n\n**Triggered reads**\n- None unless a listed trigger becomes true")
    coverage=[f"| {rid} | {src} | {ob} | <CLASSIFY> | - | - | <VERIFY> | <EVIDENCE_CLASS> | yes |" for rid,src,ob in reqs]
    return f'''---
name: {title}
overview: SMC governed implementation plan for {title}
todos:
{cursor}
isProject: false
plan_contract: smc.plan.v3.3
plan_id: {pid}
commit_policy: post_review
source_revision: {source}
grounded_commit: {grounded}
grounding_source: committed_baseline
working_tree_fingerprint: clean
---

# {title} Implementation Plan

## Approved PRD

[Approved PRD]({rel(out,prd)})

## Scope

- In: <DECIDE>
- Out: <DECIDE>
- Production Owner inherited from PRD: <GROUND>

## Grounding Evidence Ledger

| Change ID | Target | Baseline State | Symbol / Entry Resolution | Caller / Callee Evidence | Existing Reuse Search | Result |
|---|---|---|---|---|---|---|
| <DECIDE> | `<GROUND>` | <GROUND> | <GROUND> | <GROUND> | <GROUND> | <GROUND> |

## Requirement Coverage Ledger

| Requirement | Source | Obligation | Classification | Change IDs | Todo | Verification IDs | Evidence Class | Blocking |
|---|---|---|---|---|---|---|---|---|
{chr(10).join(coverage)}

## Lifecycle Closure Matrix

| Journey | Requirements | Trigger | Nonterminal State | Success Writer | Failure / Cancel Writer | Evidence IDs |
|---|---|---|---|---|---|---|
| <DECIDE> | <DECIDE> | <DECIDE> | <DECIDE> | <DECIDE> | <DECIDE> | <VERIFY> |

## Contract / Data Flow Closure Matrix

| Flow | Requirements | Producer | Transport / Schema | Consumer | Required Fields | Validation Owner | Failure Mapping | Retry / Idempotency Identity | Evidence IDs |
|---|---|---|---|---|---|---|---|---|---|
| <DECIDE> | <DECIDE> | <GROUND> | <GROUND> | <GROUND> | <GROUND> | <GROUND> | <GROUND> | <GROUND> | <VERIFY> |

## Verification Ledger

| Verification ID | Level | Entry Point / Command | Oracle | Negative / Regression | Evidence Policy | Environment | Blocking |
|---|---|---|---|---|---|---|---|
| V01 | <VERIFY_LEVEL> | <VERIFY> | <VERIFY> | <VERIFY> | LOCAL_TRANSIENT | <ENVIRONMENT> | yes |

## Immediate Read

- `<GROUND>`

## Triggered Read

- If <trigger>: `<GROUND>`
- Otherwise: do not read

## Change Matrix

| Change ID | File / Symbol | Kind | Action | Existing Owner | Todo Owner | Target State | PRD Capability | New File? |
|---|---|---|---|---|---|---|---|---|
{chr(10).join(matrix)}

## Implementation Decisions

| Change ID | Strategy | Root-Cause / Reuse Evidence | Why This Is Minimum |
|---|---|---|---|
{chr(10).join(decisions)}

## Write Ownership Ledger

| Todo | Owns Changes | Writes | Reads | Depends On | Parallel Safe |
|---|---|---|---|---|---|
{chr(10).join(ledger)}

## Integration Hotspots

None

## Generated Outputs Ledger

None

{chr(10).join(x+chr(10) for x in todos)}
## Verification

Run all blocking Verification Ledger entries through `smc-plan-delivery/scripts/evidence.py`.

## Completion Gate

| Exit State | Allowed When | Blocking Evidence |
|---|---|---|
| IMPLEMENTED_AND_PROVEN | all Cursor todos completed; completion audit FRESH PASS; implementation review FRESH PASS; all blocking Verification FRESH PASS; durable Evidence Manifest FRESH | V01 via SMC evidence ledger + durable Evidence Manifest |
| IMPLEMENTED_NOT_PROVEN | implementation exists but proof is pending/stale | pending/stale gate IDs |
| BLOCKED | environment/dependency prevents proof | blocker record |
| RETURN_PRD | approved owner/boundary conflicts | PRD revision request |
'''

def main()->int:
    ap=argparse.ArgumentParser();ap.add_argument("prd",type=Path);ap.add_argument("output",type=Path);ap.add_argument("--plan-id",required=True)
    a=ap.parse_args();prd=a.prd.resolve();out=a.output.resolve()
    if not prd.is_file():print(f"PRD_NOT_FOUND: {prd}",file=sys.stderr);return 2
    if out.exists():print(f"PLAN_ALREADY_EXISTS: {out}",file=sys.stderr);return 2
    text=prd.read_text(encoding="utf-8")
    try:
        meta=fm(text)
        if meta.get("status")!="APPROVED":raise ValueError("PRD_NOT_APPROVED")
        if meta.get("review_verdict")!="PASS":raise ValueError("PRD_REVIEW_NOT_PASS")
        if not meta.get("approved_at"):raise ValueError("PRD_APPROVED_AT_MISSING")
        chs=changes(text);reqs=requirements(text)
    except ValueError as e:print(str(e),file=sys.stderr);return 1
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(render(prd,out,meta,a.plan_id,chs,reqs),encoding="utf-8")
    print(f"Plan v3.3 seed created: {out}\nPlan ID: {a.plan_id}\nTodos: {len(chs)}\nRequirements: {len(reqs)}\nSeed is NOT executable until grounding placeholders are resolved and validators pass.")
    return 0
if __name__=="__main__":raise SystemExit(main())
