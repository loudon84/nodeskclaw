"""Frontend contract v1.0.0 package check."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from frontend_contract import check_contract  # noqa: E402


# @lat: [[decisions/knowledge-frontend-contract#Check Gate]]
def test_frontend_contract_v100_check():
    check_contract()
