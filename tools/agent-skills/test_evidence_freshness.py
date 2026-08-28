#!/usr/bin/env python3
from __future__ import annotations
import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('evidence_freshness',HERE/'evidence_freshness.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def sh(root,*args):
    return subprocess.check_output(['git','-C',str(root),*args],text=True).strip()

def commit(root,msg):
    subprocess.run(['git','-C',str(root),'add','.'],check=True,stdout=subprocess.DEVNULL)
    subprocess.run(['git','-C',str(root),'commit','-q','-m',msg],check=True)
    return sh(root,'rev-parse','HEAD')

class T(unittest.TestCase):
    def setUp(self):
        self.td=tempfile.TemporaryDirectory();self.root=Path(self.td.name)
        subprocess.run(['git','init','-q',str(self.root)],check=True)
        subprocess.run(['git','-C',str(self.root),'config','user.email','test@example.com'],check=True)
        subprocess.run(['git','-C',str(self.root),'config','user.name','Test'],check=True)
        (self.root/'src').mkdir();(self.root/'src/owner.py').write_text('x=1\n');(self.root/'other.py').write_text('x=1\n')
        self.base=commit(self.root,'base')
        self.artifact=self.root/'artifact.md'
        self.write_artifact(self.base)
    def tearDown(self):self.td.cleanup()
    def write_artifact(self,grounded,source='AD-1@1.0/RM-01'):
        self.artifact.write_text(f'''---\nsource_revision: {source}\ngrounded_commit: {grounded}\n---\n\n## Evidence Baseline\n- `src/owner.py#Owner`\n''')
    def test_reuse_when_head_same(self):
        # artifact itself is intentionally uncommitted evidence metadata; grounded source HEAD stays base.
        self.assertEqual('REUSE',m.evaluate(self.artifact,'AD-1@1.0/RM-01')['state'])
    def test_verify_only_when_unrelated_file_changes(self):
        (self.root/'other.py').write_text('x=2\n');commit(self.root,'unrelated')
        self.assertEqual('VERIFY_ONLY',m.evaluate(self.artifact,'AD-1@1.0/RM-01')['state'])
    def test_reground_when_anchor_changes(self):
        (self.root/'src/owner.py').write_text('x=2\n');commit(self.root,'owner')
        self.assertEqual('REGROUND_REQUIRED',m.evaluate(self.artifact,'AD-1@1.0/RM-01')['state'])
    def test_reground_when_source_revision_changes(self):
        self.assertEqual('REGROUND_REQUIRED',m.evaluate(self.artifact,'AD-1@2.0/RM-01')['state'])
if __name__=='__main__':unittest.main()
