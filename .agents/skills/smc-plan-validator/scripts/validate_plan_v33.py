#!/usr/bin/env python3
"""Compatibility-preserving validator core for smc.plan.v3.3/v3.4.

The v3.3 CLI remains a strict v3.3 validator.  v3.4 imports validate_plan()
with expected_contract="smc.plan.v3.4", adds Cursor content projection checks
through plan_state.validate(), then reuses the legacy v3.2 structural gates.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sys
import tempfile
from pathlib import Path

HERE=Path(__file__).resolve().parent
DELIVERY=HERE.parents[1]/"smc-plan-delivery"/"scripts"
sys.path.insert(0,str(DELIVERY))
from common import parse_first_table, parse_top_level_frontmatter, repo_relative_path, section, strip_md  # type: ignore
from plan_state import legacy_content_warnings, validate as validate_cursor_todos  # type: ignore

VALID_POLICIES={"LOCAL_TRANSIENT","LOCAL_DURABLE","CI_ARTIFACT","EXTERNAL_ARTIFACT","REPO_SUMMARY"}


def load_legacy():
    path=HERE/"validate_plan.py"
    if not path.is_file():raise RuntimeError("PLAN_LEGACY_VALIDATOR_MISSING: expected smc-plan-validator/scripts/validate_plan.py from baseline package")
    spec=importlib.util.spec_from_file_location("smc_plan_validator_v32",path)
    module=importlib.util.module_from_spec(spec);assert spec and spec.loader
    # Python 3.12 dataclasses require the executing module to be registered.
    sys.modules[spec.name]=module
    spec.loader.exec_module(module)
    return module


def repo_root(plan:Path)->Path:
    import subprocess
    r=subprocess.run(["git","-C",str(plan.parent),"rev-parse","--show-toplevel"],capture_output=True,text=True,encoding="utf-8",errors="replace")
    return Path(r.stdout.strip()).resolve() if r.returncode==0 else plan.parent.resolve()


def duplicate_checks(plan:Path,pid:str)->list[dict[str,str]]:
    root=repo_root(plan);plans=root/".cursor"/"plans";out=[]
    if not plans.is_dir():return out
    body=lambda t:re.sub(r"\s+"," ",re.sub(r"\A---.*?---\s*","",t,flags=re.S)).strip()
    this_body=body(plan.read_text(encoding="utf-8"))
    for other in plans.glob("*.plan.md"):
        if other.resolve()==plan.resolve():continue
        text=other.read_text(encoding="utf-8",errors="replace");fm=parse_top_level_frontmatter(text)
        opid=fm.get("plan_id","").strip()
        if opid and opid==pid:out.append({"code":"PLAN_ID_DUPLICATE","detail":repo_relative_path(other, root)})
        elif this_body and body(text)==this_body:out.append({"code":"PLAN_SEMANTIC_DUPLICATE","detail":repo_relative_path(other, root)})
    return out


def contract_checks(plan:Path,expected_contract:str)->list[dict[str,str]]:
    text=plan.read_text(encoding="utf-8");fm=parse_top_level_frontmatter(text);errors=[]
    def add(c,d):errors.append({"code":c,"detail":d})
    if fm.get("plan_contract")!=expected_contract:add("PLAN_CONTRACT_INVALID",f"plan_contract must be {expected_contract}")
    pid=fm.get("plan_id","").strip()
    if not pid:add("PLAN_ID_MISSING","plan_id is required")
    if fm.get("commit_policy")!="post_review":add("PLAN_COMMIT_POLICY_INVALID","commit_policy must be post_review")
    for key in ("name","overview","isProject"):
        if key not in fm or not fm[key].strip():add("PLAN_CURSOR_METADATA_MISSING",key)
    errors.extend({"code":x.split(":",1)[0],"detail":x.split(":",1)[1].strip() if ":" in x else ""} for x in validate_cursor_todos(plan))
    if pid:errors.extend(duplicate_checks(plan,pid))
    header,rows=parse_first_table(section(text,"Verification Ledger"))
    if "Evidence Policy" not in header:add("PLAN_TABLE_MISSING_COLUMN","Verification Ledger missing Evidence Policy")
    if "Evidence Output" in header:add("PLAN_V33_LEGACY_EVIDENCE_OUTPUT_FORBIDDEN","replace Evidence Output with Evidence Policy")
    for i,row in enumerate(rows,1):
        vid=strip_md(row.get("Verification ID",f"row {i}")).upper();policy=strip_md(row.get("Evidence Policy","")).upper()
        if policy not in VALID_POLICIES:add("PLAN_EVIDENCE_POLICY_INVALID",f"{vid}: {policy}")
    return errors


def transform_to_v32(text:str)->str:
    lines=text.splitlines();in_ver=False;policy_idx=None;header_seen=False
    for i,line in enumerate(lines):
        if re.match(r"^plan_contract\s*:\s*smc\.plan\.v3\.[34]\s*$",line):lines[i]="plan_contract: smc.plan.v3.2"
        if line.strip()=="## Verification Ledger":in_ver=True;continue
        if in_ver and line.startswith("## "):in_ver=False
        if in_ver and line.strip().startswith("|") and "Verification ID" in line and "Evidence Policy" in line:
            cells=[c.strip() for c in line.strip().strip("|").split("|")];policy_idx=cells.index("Evidence Policy");cells[policy_idx]="Evidence Output";lines[i]="| "+" | ".join(cells)+" |";header_seen=True;continue
        if in_ver and header_seen and policy_idx is not None and line.strip().startswith("|"):
            cells=[c.strip() for c in line.strip().strip("|").split("|")]
            if cells and all(re.fullmatch(r":?-{3,}:?",c.replace(" ","")) for c in cells):continue
            if policy_idx<len(cells):cells[policy_idx]="SMC_EVIDENCE_LEDGER";lines[i]="| "+" | ".join(cells)+" |"
    return "\n".join(lines).rstrip()+"\n"


def validate_plan(plan:Path,expected_contract:str="smc.plan.v3.3")->list[dict[str,str]]:
    errors=contract_checks(plan,expected_contract)
    if errors:return errors
    try:legacy=load_legacy()
    except RuntimeError as exc:return [{"code":"PLAN_LEGACY_VALIDATOR_MISSING","detail":str(exc)}]
    compat=transform_to_v32(plan.read_text(encoding="utf-8"))
    fd,tmp=tempfile.mkstemp(prefix=plan.stem+".",suffix=".smc-v32-compat.tmp",dir=str(plan.parent));os.close(fd);tmp_path=Path(tmp)
    try:
        tmp_path.write_text(compat,encoding="utf-8")
        for e in legacy.validate_plan(tmp_path):errors.append({"code":e.code,"detail":e.detail})
    finally:
        try:tmp_path.unlink()
        except FileNotFoundError:pass
    ded=[];seen=set()
    for e in errors:
        k=(e["code"],e["detail"])
        if k not in seen:seen.add(k);ded.append(e)
    return ded


def main()->int:
    ap=argparse.ArgumentParser();ap.add_argument("plan",type=Path);ap.add_argument("--json",action="store_true");a=ap.parse_args();plan=a.plan.resolve()
    if not plan.is_file():
        payload={"valid":False,"plan":str(plan),"errors":[{"code":"PLAN_NOT_FOUND","detail":str(plan)}]}
        print(json.dumps(payload,ensure_ascii=False,indent=2) if a.json else f"PLAN_NOT_FOUND: {plan}",file=sys.stdout if a.json else sys.stderr);return 2
    errors=validate_plan(plan,"smc.plan.v3.3")
    warnings=legacy_content_warnings(plan)
    if a.json:print(json.dumps({"valid":not errors,"plan":str(plan),"errors":errors,"warnings":warnings},ensure_ascii=False,indent=2))
    elif errors:print("\n".join(f"{e['code']}: {e['detail']}".rstrip(": ") for e in errors),file=sys.stderr)
    else:
        for warning in warnings:print(warning,file=sys.stderr)
        print("Plan v3.3 validation passed")
    return 1 if errors else 0
if __name__=="__main__":raise SystemExit(main())
