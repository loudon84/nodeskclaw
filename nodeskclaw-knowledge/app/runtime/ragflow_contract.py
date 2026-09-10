"""RAGFlow compatibility contract — L1/L2/L3 probe semantics consumed by RagflowRuntimeAdapter."""

# @lat: [[knowledge#Isolation From Ragflow]]
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Protocol

MINIMUM_SUPPORTED_RAGFLOW_VERSION = "0.17.0"

CAPABILITY_SUPPORTED = "supported"
CAPABILITY_UNSUPPORTED = "unsupported"
CAPABILITY_UNAVAILABLE = "unavailable"
CAPABILITY_UNKNOWN = "unknown"


class RagflowProbeClient(Protocol):
    async def system_health(self) -> bool: ...

    async def get_system_version(self) -> str | None: ...

    async def list_datasets(self, page: int = 1, page_size: int = 1) -> list[Any]: ...

    async def probe_retrieval_endpoint(self) -> bool: ...

    async def probe_dataset_search(self, dataset_id: str) -> bool: ...

    async def probe_dataset_graph(self, dataset_id: str) -> bool: ...

    async def probe_document_chunks(self, dataset_id: str, document_id: str) -> dict[str, Any]: ...

    async def probe_retrieval_features(self, dataset_id: str) -> dict[str, dict[str, bool] | bool]: ...


@dataclass
class RagflowCompatibilityProfile:
    reachable: bool = False
    runtime_version: str | None = None
    dataset_api: bool = False
    document_api: bool = False
    chunk_retrieval: bool = False
    auto_questions_build: bool = False
    question_fields_visible: bool = False
    knowledge_compilation: bool = False
    raptor_build: bool = False
    raptor_source_lineage: bool = False
    kg_retrieval: bool = False
    dataset_graph: bool = False
    toc_enhance: bool = False
    metadata_filter: bool = False
    knn_top_k: bool = False
    knn_num_candidates: bool = False
    rerank_candidates_count: bool = False
    probe_dataset_id: str | None = None
    probe_document_id: str | None = None
    probe_errors: list[str] = field(default_factory=list)
    feature_status: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def fact(self, name: str) -> str:
        if not self.reachable:
            return CAPABILITY_UNAVAILABLE
        status = self.feature_status.get(name)
        if status in {
            CAPABILITY_SUPPORTED,
            CAPABILITY_UNSUPPORTED,
            CAPABILITY_UNAVAILABLE,
            CAPABILITY_UNKNOWN,
        }:
            return status
        return CAPABILITY_UNKNOWN


def _observed_status(observed: bool | None) -> str:
    if observed is None:
        return CAPABILITY_UNKNOWN
    if observed:
        return CAPABILITY_SUPPORTED
    return CAPABILITY_UNKNOWN


async def probe_l1_transport(client: RagflowProbeClient) -> tuple[bool, str | None, list[str]]:
    errors: list[str] = []
    reachable = False
    version: str | None = None
    try:
        reachable = await client.system_health()
    except Exception as exc:
        errors.append(f"l1_health:{exc}")
    if reachable:
        try:
            version = await client.get_system_version()
        except Exception as exc:
            errors.append(f"l1_version:{exc}")
    return reachable, version, errors


async def probe_l2_endpoints(
    client: RagflowProbeClient,
    *,
    dataset_id: str | None = None,
    document_id: str | None = None,
) -> tuple[dict[str, bool | None], str | None, str | None, list[str]]:
    errors: list[str] = []
    result: dict[str, bool | None] = {
        "dataset_api": None,
        "document_api": None,
        "chunk_retrieval": None,
        "auto_questions_build": None,
        "question_fields_visible": None,
        "dataset_graph": None,
        "knowledge_compilation": None,
        "raptor_build": None,
        "raptor_source_lineage": None,
    }
    probe_dataset_id = dataset_id
    probe_document_id = document_id

    try:
        datasets = await client.list_datasets(page=1, page_size=1)
        result["dataset_api"] = bool(datasets is not None)
        if not probe_dataset_id and datasets:
            probe_dataset_id = str(getattr(datasets[0], "id", "") or "")
    except Exception as exc:
        errors.append(f"l2_dataset_api:{exc}")

    if probe_dataset_id:
        try:
            result["dataset_graph"] = bool(await client.probe_dataset_graph(probe_dataset_id))
        except Exception as exc:
            errors.append(f"l2_dataset_graph:{exc}")
        try:
            search_ok = bool(await client.probe_dataset_search(probe_dataset_id))
            result["document_api"] = bool(search_ok)
        except Exception as exc:
            errors.append(f"l2_dataset_search:{exc}")

    if probe_dataset_id and probe_document_id:
        try:
            chunk_probe = await client.probe_document_chunks(probe_dataset_id, probe_document_id)
            result["chunk_retrieval"] = bool(chunk_probe.get("chunk_retrieval"))
            result["question_fields_visible"] = bool(chunk_probe.get("question_fields_visible"))
            result["auto_questions_build"] = result["question_fields_visible"]
            result["raptor_source_lineage"] = bool(chunk_probe.get("raptor_source_lineage"))
            result["knowledge_compilation"] = bool(chunk_probe.get("knowledge_compilation"))
            result["raptor_build"] = result["knowledge_compilation"]
        except Exception as exc:
            errors.append(f"l2_chunk_read:{exc}")

    try:
        result["chunk_retrieval"] = result["chunk_retrieval"] or bool(await client.probe_retrieval_endpoint())
    except Exception as exc:
        errors.append(f"l2_retrieval:{exc}")

    return result, probe_dataset_id, probe_document_id, errors


def _l3_feature_status(raw: dict[str, Any], key: str) -> str:
    value = raw.get(key)
    if not isinstance(value, dict):
        return CAPABILITY_UNKNOWN
    if not value.get("transport"):
        return CAPABILITY_UNKNOWN
    if value.get("supported") and value.get("operational"):
        return CAPABILITY_SUPPORTED
    if value.get("supported") is False:
        return CAPABILITY_UNSUPPORTED
    return CAPABILITY_UNKNOWN


def _l3_feature_operational(raw: dict[str, Any], key: str) -> bool:
    return _l3_feature_status(raw, key) == CAPABILITY_SUPPORTED


async def probe_l3_features(
    client: RagflowProbeClient,
    *,
    dataset_id: str | None,
) -> tuple[dict[str, str], list[str]]:
    errors: list[str] = []
    defaults = {
        "kg_retrieval": CAPABILITY_UNKNOWN,
        "toc_enhance": CAPABILITY_UNKNOWN,
        "metadata_filter": CAPABILITY_UNKNOWN,
        "knn_top_k": CAPABILITY_UNKNOWN,
        "knn_num_candidates": CAPABILITY_UNKNOWN,
        "rerank_candidates_count": CAPABILITY_UNKNOWN,
        "knowledge_compilation": CAPABILITY_UNKNOWN,
    }
    if not dataset_id:
        return defaults, errors
    try:
        raw = await client.probe_retrieval_features(dataset_id)
        features = raw if isinstance(raw, dict) else {}
        merged = {key: _l3_feature_status(features, key) for key in defaults}
        return merged, errors
    except Exception as exc:
        errors.append(f"l3_features:{exc}")
        return defaults, errors


async def probe_compatibility_profile(
    client: RagflowProbeClient,
    *,
    dataset_id: str | None = None,
    document_id: str | None = None,
) -> RagflowCompatibilityProfile:
    reachable, version, l1_errors = await probe_l1_transport(client)
    profile = RagflowCompatibilityProfile(reachable=reachable, runtime_version=version, probe_errors=l1_errors)
    if not reachable:
        return profile

    l2, probe_dataset_id, probe_document_id, l2_errors = await probe_l2_endpoints(
        client,
        dataset_id=dataset_id,
        document_id=document_id,
    )
    profile.probe_errors.extend(l2_errors)
    profile.probe_dataset_id = probe_dataset_id
    profile.probe_document_id = probe_document_id
    for key, value in l2.items():
        if value is not None:
            setattr(profile, key, bool(value))
        profile.feature_status[key] = _observed_status(value)

    l3, l3_errors = await probe_l3_features(client, dataset_id=probe_dataset_id)
    profile.probe_errors.extend(l3_errors)
    for key, status in l3.items():
        profile.feature_status[key] = status
        if status == CAPABILITY_SUPPORTED:
            setattr(profile, key, True)
            if key == "knowledge_compilation":
                profile.knowledge_compilation = True
                profile.raptor_build = True
                profile.feature_status["knowledge_compilation"] = CAPABILITY_SUPPORTED
                profile.feature_status["raptor_build"] = CAPABILITY_SUPPORTED
        elif status == CAPABILITY_UNSUPPORTED:
            setattr(profile, key, False)

    return profile
