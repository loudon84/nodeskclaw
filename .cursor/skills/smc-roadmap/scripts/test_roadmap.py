import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('v',HERE/'validate_roadmap.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def text(rows):
    return '---\nroadmap_id: ROADMAP-TEST\nversion: 1.0.0\nstatus: ACTIVE\narchitecture_decision: AD.md\nsource_revision: AD@1\nupdated_at: 2026-08-28T00:00:00Z\n---\n\n## Roadmap Items\n\n| Item ID | Outcome | Depends On | Status | Exit Criteria | PRD | Plan | Implementation Commit | Verification Evidence |\n|---|---|---|---|---|---|---|---|---|\n'+rows+'\n'

class T(unittest.TestCase):
    def check(self,s):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'r.md';p.write_text(s);return m.validate(p,check_git=False,check_architecture=False)

    def test_valid(self):
        self.assertEqual([],self.check(text('| RM-01 | x | - | DONE | y | p.md | q.md | abcdef123 | verify.txt |\n| RM-02 | z | RM-01 | READY | y | - | - | - | - |')))

    def test_ready_dep(self):
        self.assertTrue(any('READY_DEPENDENCY_NOT_DONE' in x for x in self.check(text('| RM-01 | x | - | READY | y | - | - | - | - |\n| RM-02 | z | RM-01 | READY | y | - | - | - | - |'))))

    def test_done_evidence(self):
        self.assertTrue(any('IMPLEMENTATION_COMMIT' in x for x in self.check(text('| RM-01 | x | - | DONE | y | p | q | - | - |'))))

    def test_prd_cannot_be_reused_by_two_items(self):
        errors=self.check(text('| RM-01 | x | - | IN_PRD | y | same.md | - | - | - |\n| RM-02 | z | - | IN_PRD | y | same.md | - | - | - |'))
        self.assertTrue(any('ROADMAP_STAGE_PRD_REUSED' in x for x in errors))

    def test_done_commit_must_exist_in_git(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            subprocess.run(['git','init','-q',str(root)],check=True)
            subprocess.run(['git','-C',str(root),'config','user.email','test@example.com'],check=True)
            subprocess.run(['git','-C',str(root),'config','user.name','Test'],check=True)
            (root/'x').write_text('x')
            subprocess.run(['git','-C',str(root),'add','x'],check=True)
            subprocess.run(['git','-C',str(root),'commit','-q','-m','x'],check=True)
            sha=subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()
            p=root/'roadmap.md';p.write_text(text(f'| RM-01 | x | - | DONE | y | p.md | q.md | {sha} | verify.txt |'))
            self.assertEqual([],m.validate(p,check_git=True,check_architecture=False))
            p.write_text(text('| RM-01 | x | - | DONE | y | p.md | q.md | deadbeef | verify.txt |'))
            self.assertTrue(any('COMMIT_NOT_FOUND' in x for x in m.validate(p,check_git=True,check_architecture=False)))

if __name__=='__main__':unittest.main()
