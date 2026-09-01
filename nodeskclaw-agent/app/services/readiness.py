from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


def expected_alembic_heads() -> set[str]:
    agent_root = Path(__file__).resolve().parent.parent.parent
    alembic_ini = agent_root / "alembic.ini"
    cfg = Config(str(alembic_ini))
    script = ScriptDirectory.from_config(cfg)
    return set(script.get_heads())
