from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from check_remote_acp_v21_discovery_drift import compare_discovery
from remote_acp_v21_pins import (
    CATALOG_CONTRACT_DIGEST,
    FRONTEND_CONTRACT_DIGEST,
    FRONTEND_CONTRACT_VERSION,
    FULL_LIVE_IDS,
    L2_ENV_ID,
    L2_K8S_CONTEXT,
    L2_K8S_NAMESPACE,
    PRERUN_LIVE_IDS,
    REMOTE_ACP_CONTRACT_DIGEST,
)
from validate_pg_summary import validate_summary


def _ok_discovery(**overrides):
    base = {
        "frontendContractVersion": FRONTEND_CONTRACT_VERSION,
        "frontendContractDigest": FRONTEND_CONTRACT_DIGEST,
        "catalogContractDigest": CATALOG_CONTRACT_DIGEST,
        "remoteAcpContractDigest": REMOTE_ACP_CONTRACT_DIGEST,
    }
    base.update(overrides)
    return base


def test_compare_discovery_ok():
    result = compare_discovery(_ok_discovery())
    assert result["ok"] is True
    assert result["status"] == "OK"


def test_compare_discovery_drift():
    result = compare_discovery(_ok_discovery(frontendContractDigest="0" * 64))
    assert result["ok"] is False
    assert result["status"] == "DRIFT"
    assert "frontendContractDigest" in result["mismatches"]


def test_compare_discovery_missing_field():
    payload = _ok_discovery()
    del payload["catalogContractDigest"]
    result = compare_discovery(payload)
    assert result["ok"] is False


def _full_passed_summary(**overrides):
    passed = datetime(2026, 10, 7, 12, 0, 0, tzinfo=timezone.utc)
    expires = passed + timedelta(days=14)
    doc = {
        "envId": L2_ENV_ID,
        "k8sContext": L2_K8S_CONTEXT,
        "namespace": L2_K8S_NAMESPACE,
        "pin": FRONTEND_CONTRACT_VERSION,
        "g7CommitSha": "a" * 40,
        "g7SourceSha256": "b" * 64,
        "cases": {cid: "PASS" for cid in FULL_LIVE_IDS},
        "productionGate": "passed",
        "claimAuthorized": False,
        "passedAt": passed.isoformat().replace("+00:00", "Z"),
        "expiresAt": expires.isoformat().replace("+00:00", "Z"),
        "obsJoin": {
            "traceId": "trace-1",
            "operationId": "op-1",
            "backendLogPointer": "deploy/backend pod=x ts=2026-10-07T12:00:05Z",
            "agentLogPointer": "deploy/agent pod=y ts=2026-10-07T12:00:06Z",
        },
    }
    doc.update(overrides)
    return doc


def test_validate_full_passed_ok():
    assert validate_summary(_full_passed_summary(), mode="full") == []


def test_validate_full_rejects_bad_expires():
    errors = validate_summary(
        _full_passed_summary(expiresAt="2026-10-08T12:00:00.000Z"),
        mode="full",
    )
    assert any("expiresAt" in e for e in errors)


def test_validate_full_rejects_url():
    errors = validate_summary(
        _full_passed_summary(
            obsJoin={
                "traceId": "t",
                "backendLogPointer": "http://192.168.50.247:4510/x",
                "agentLogPointer": "agent-log",
            }
        ),
        mode="full",
    )
    assert any("URL" in e for e in errors)


def test_validate_claim_requires_signoffs():
    doc = _full_passed_summary(claimAuthorized=True)
    errors = validate_summary(doc, mode="full")
    assert any("desktopVersion" in e for e in errors)


def test_validate_prerun_ok():
    doc = {
        "envId": "nodeskclaw-staging",
        "k8sContext": L2_K8S_CONTEXT,
        "namespace": "nodeskclaw-staging",
        "pin": FRONTEND_CONTRACT_VERSION,
        "g7CommitSha": "a" * 40,
        "g7SourceSha256": "b" * 64,
        "cases": {cid: "PASS" for cid in PRERUN_LIVE_IDS},
        "productionGate": "unpassed",
        "claimAuthorized": False,
    }
    assert validate_summary(doc, mode="prerun") == []


def test_validate_prerun_rejects_passed_gate():
    doc = {
        "envId": "nodeskclaw-staging",
        "k8sContext": L2_K8S_CONTEXT,
        "namespace": "nodeskclaw-staging",
        "pin": FRONTEND_CONTRACT_VERSION,
        "g7CommitSha": "a" * 40,
        "g7SourceSha256": "b" * 64,
        "cases": {cid: "PASS" for cid in PRERUN_LIVE_IDS},
        "productionGate": "passed",
        "claimAuthorized": False,
    }
    errors = validate_summary(doc, mode="prerun")
    assert any("unpassed" in e for e in errors)


def test_drift_cli_env_incomplete(monkeypatch, capsys):
    import check_remote_acp_v21_discovery_drift as mod

    monkeypatch.delenv("SMC_REMOTE_EXPERT_G7_BACKEND_URL", raising=False)
    monkeypatch.delenv("SMC_REMOTE_EXPERT_G7_TOKEN", raising=False)
    monkeypatch.delenv("NODESKCLAW_BACKEND_URL", raising=False)
    monkeypatch.delenv("NODESKCLAW_JWT", raising=False)
    code = mod.main([])
    assert code == 2
    out = json.loads(capsys.readouterr().out)
    assert out["errorCode"] == "DRIFT_ENV_INCOMPLETE"
