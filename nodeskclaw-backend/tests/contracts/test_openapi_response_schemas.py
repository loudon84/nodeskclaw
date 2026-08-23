from app.contracts.work_expert.constants import WORK_EXPERT_OPENAPI_PATHS
from scripts.contracts import _load_openapi_subset, is_empty_json_schema


def test_contract_http_paths_have_non_empty_200_schema():
    openapi = _load_openapi_subset()
    empty = []
    for path in WORK_EXPERT_OPENAPI_PATHS:
        path_item = openapi["paths"][path]
        for method, operation in path_item.items():
            if method.startswith("x-") or not isinstance(operation, dict):
                continue
            content = (
                operation.get("responses", {})
                .get("200", {})
                .get("content", {})
            )
            assert content, f"{method.upper()} {path} missing 200 content"
            for media, body in content.items():
                schema = body.get("schema")
                if is_empty_json_schema(schema):
                    empty.append(f"{method.upper()} {path} {media}")
    assert empty == []
