"""RAGFlow contract tests — skipped unless RAGFLOW_CONTRACT_TEST=1."""

from __future__ import annotations

import os

import pytest


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "ragflow_contract: live RAGFlow contract tests (require RAGFLOW_CONTRACT_TEST=1)",
    )


def pytest_collection_modifyitems(config, items):
    if os.environ.get("RAGFLOW_CONTRACT_TEST") == "1":
        return
    skip = pytest.mark.skip(reason="RAGFLOW_CONTRACT_TEST=1 required for live RAGFlow contract tests")
    for item in items:
        if "ragflow_contract" in str(item.fspath):
            item.add_marker(skip)
