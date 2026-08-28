#!/usr/bin/env python3
from __future__ import annotations
import argparse,importlib.util,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('vr',HERE/'validate_roadmap.py');vr=importlib.util.module_from_spec(spec);spec.loader.exec_module(vr)
def main():
    ap=argparse.ArgumentParser();ap.add_argument('roadmap',type=Path);a=ap.parse_args();p=a.roadmap.resolve();errs=vr.validate(p)
    if errs:print('\n'.join(errs),file=sys.stderr);return 1
    _,rows=vr.table(vr.section(p.read_text(encoding='utf-8'),'Roadmap Items'))
    for r in rows:
        if r['Status'].strip().upper()=='READY':
            print(f"{r['Item ID'].strip()}\t{r['Outcome'].strip()}");return 0
    print('ROADMAP_NO_READY_ITEM');return 3
if __name__=='__main__':raise SystemExit(main())
