"""knowledge.retrieve tool handler."""

from __future__ import annotations

import json
from typing import Any

from client import retrieve
from config import ConfigError, load_settings
from session_scope import ScopeError, resolve_knowledge_set_id

TOOL_NAME = "knowledge.retrieve"
TOOL_DESCRIPTION = "Retrieve enterprise knowledge from assigned KnowledgeSet."

TOOL_SCHEMA: dict[str, Any] = {
    "name": TOOL_NAME,
    "description": TOOL_DESCRIPTION,
    "parameters": {
        "type": "object",
        "properties": {
            "knowledge_set_id": {
                "type": "string",
                "description": "KnowledgeSet ID; falls back to session scope when omitted",
            },
            "query": {
                "type": "string",
                "description": "User question",
            },
            "top_k": {
                "type": "integer",
                "default": 10,
                "description": "Max chunks to return",
            },
        },
        "required": ["query"],
    },
}

_plugin_config: dict[str, Any] | None = None
_session_store: dict[str, str] = {}


def set_plugin_config(config: dict[str, Any] | None) -> None:
    global _plugin_config
    _plugin_config = config


def set_session_store(store: dict[str, str] | None) -> None:
    global _session_store
    _session_store = dict(store or {})


def _json_result(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False)


def knowledge_retrieve(args: dict[str, Any], **kwargs: Any) -> str:
    try:
        settings = load_settings(_plugin_config)
        knowledge_set_id = resolve_knowledge_set_id(args, kwargs, _session_store)
        query = str(args.get("query") or "").strip()
        if not query:
            return _json_result(
                {
                    "code": 40000,
                    "error_code": 40000,
                    "message_key": "validation.knowledge.query_required",
                    "message": "query is required",
                    "data": None,
                }
            )
        top_k_raw = args.get("top_k", 10)
        top_k = int(top_k_raw) if top_k_raw is not None else 10
        payload = retrieve(
            settings,
            knowledge_set_id=knowledge_set_id,
            query=query,
            top_k=top_k,
        )
        return _json_result(payload)
    except ConfigError as exc:
        return _json_result(
            {
                "code": 50300,
                "error_code": 50300,
                "message_key": "errors.knowledge.plugin_config_missing",
                "message": str(exc),
                "data": None,
                "plugin_ops_hint": "Check SMC_KB_API_TOKEN in ~/.hermes/.env, then restart Hermes gateway.",
            }
        )
    except ScopeError as exc:
        return _json_result(
            {
                "code": 40000,
                "error_code": 40000,
                "message_key": "validation.knowledge.knowledge_set_id_required",
                "message": str(exc),
                "data": None,
            }
        )
    except Exception as exc:  # noqa: BLE001 — tool boundary
        return _json_result(
            {
                "code": 50000,
                "error_code": 50000,
                "message_key": "errors.knowledge.plugin_internal_error",
                "message": str(exc),
                "data": None,
            }
        )
