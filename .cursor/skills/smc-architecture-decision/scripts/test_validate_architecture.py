import importlib.util, tempfile, unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('v',HERE/'validate_architecture.py'); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
SECTIONS=m.SECTIONS

def doc(status='REVIEW_REQUIRED', verdict='', approved=''):
    body='---\ndecision_id: AD-001\nversion: 1.0.0\nstatus: %s\ntarget_branch: main\nreview_verdict: %s\napproved_at: %s\nsource_revision: proposal@v1\ngrounded_commit: abcdef1234567\n---\n' % (status,verdict,approved)
    for s in SECTIONS: body+=f'\n## {s}\n\ncontent\n'
    return body
class T(unittest.TestCase):
    def test_review_required(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'AD-001-DRAFT.md'; p.write_text(doc()); self.assertEqual([],m.validate(p))
    def test_approved_draft_name_fails(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'AD-001-DRAFT.md'; p.write_text(doc('APPROVED','PASS','2026-08-28T00:00:00Z')); self.assertIn('ARCH_APPROVED_FILENAME_HAS_DRAFT',m.validate(p))
if __name__=='__main__': unittest.main()
