from __future__ import annotations

import json
from pathlib import Path

from scripts import contracts as contracts_module


BACKEND_ROOT = Path(__file__).resolve().parents[2]
ROOT = BACKEND_ROOT / "contracts/integration-account/v1.0.0"
REMOTE_V12_ROOT = BACKEND_ROOT / "contracts/remote-agent/v1.2.0"
IMPL = "9d9085538fd1b0077cbd5a2056c5b07b9df795fa"
ERRORS = {
    "toolkit-required.json": (40000, "errors.integration.toolkit_required", "toolkit_slug 不能为空"),
    "composio-unconfigured.json": (40000, "errors.integration.composio_unconfigured", "管理员尚未配置外部账号连接"),
    "connect-unavailable.json": (40000, "errors.integration.connect_unavailable", "暂时无法创建连接链接"),
    "account-not-confirmed.json": (40900, "errors.integration.account_not_confirmed", "外部账号尚未完成连接"),
    "account-not-found.json": (40400, "errors.integration.account_not_found", "外部账号不存在"),
}


def _load(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def test_integration_account_bundle_checksums_and_identity():
    contracts_module._validate_skill_run_checksums_exact(ROOT)
    manifest = _load("manifest.json")
    assert manifest["contractName"] == "INTEGRATION-ACCOUNT-CONTRACT"
    assert manifest["contractVersion"] == "1.0.0"
    assert manifest["implementationHeadSha"] == IMPL
    assert manifest["releaseCommitSha"] != IMPL
    assert len(manifest["releaseCommitSha"]) == 40
    assert len(list((ROOT / "golden").glob("*.json"))) == 14


def test_integration_account_endpoint_matrix_lists_seven_public_routes():
    matrix = _load("http/endpoint-matrix.json")
    endpoints = matrix["endpoints"]
    assert len(endpoints) == 7
    assert matrix["successBody"] == "ApiResponse envelope"
    encoded = json.dumps(matrix)
    assert "/internal" not in encoded
    assert "session" not in encoded.lower()
    paths = {item["path"] for item in endpoints}
    assert "/api/v1/integrations/composio/connect" in paths
    assert all(item["success"] == [200] for item in endpoints)
    assert matrix["providerNetwork"]["list"] == "none"
    assert matrix["providerNetwork"]["get"] == "none"
    assert matrix["providerNetwork"]["delete"] == "none"
    remote = json.loads((REMOTE_V12_ROOT / "http/endpoint-matrix.json").read_text(encoding="utf-8"))
    assert remote["successBody"] == "bare JSON"
    assert matrix["errorBody"]["errorCodeType"] == "integer"
    assert remote["errorBody"]["errorCodeType"] == "string symbol"


def test_integration_account_success_shapes_and_error_goldens():
    assert _load("golden/list-empty.json")["data"] == []
    listed = _load("golden/list-active.json")
    assert listed["code"] == 0
    assert listed["error_code"] is None
    assert listed["message"] == "success"
    assert listed["data"][0]["status"] == "ACTIVE"
    connect = _load("golden/connect-gmail.json")["data"]
    assert set(connect) == {"account_id", "url"}
    assert "example.com" in connect["url"]
    assert _load("schemas/connect.request.schema.json")["required"] == ["toolkit_slug"]
    assert _load("golden/delete.json")["data"] == {"deleted": True}
    authorizing = _load("golden/account-authorizing.json")
    assert authorizing["connected_account_id"] is None
    assert authorizing["status"] == "AUTHORIZING"
    account = _load("schemas/account.schema.json")
    assert account["additionalProperties"] is False
    assert set(account["properties"]) == {
        "id",
        "provider",
        "toolkit_slug",
        "alias",
        "status",
        "connected_account_id",
    }
    for name, (code, key, message) in ERRORS.items():
        body = _load(f"golden/{name}")
        assert body["code"] == code
        assert body["error_code"] == code
        assert body["message_key"] == key
        assert body["message"] == message
        assert body["data"] is None
