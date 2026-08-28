import importlib.util,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('m',HERE/'assess_plan_review.py')
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
BASE="""## Change Matrix
| Change ID | File / Symbol | Kind | Action | Existing Owner | Todo Owner | Target State | PRD Capability | New File? |
|---|---|---|---|---|---|---|---|---|
| C01 | a#b | PROD | MODIFY | X | T1 | ok | feature | no |

## Implementation Decisions
| Change ID | Strategy | Root-Cause / Reuse Evidence | Why This Is Minimum |
|---|---|---|---|
| C01 | MODIFY_EXISTING | x | y |

## Write Ownership Ledger
| Todo | Owns Changes | Writes | Reads | Depends On | Parallel Safe |
|---|---|---|---|---|---|
| T1 | C01 | a#b | - | - | no |

## Integration Hotspots
None

## Todo T1 — x
"""
class T(unittest.TestCase):
    def test_low(self): self.assertEqual([],m.assess(BASE))
    def test_new_dep(self): self.assertIn('NEW_DEPENDENCY',m.assess(BASE.replace('MODIFY_EXISTING','NEW_DEPENDENCY')))
    def test_replace(self): self.assertIn('REPLACE',m.assess(BASE.replace('| MODIFY |','| REPLACE |')))
if __name__=='__main__': unittest.main()
