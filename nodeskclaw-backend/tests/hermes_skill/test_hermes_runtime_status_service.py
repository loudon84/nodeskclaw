from app.services.hermes_external.hermes_runtime_status_service import HermesRuntimeStatusService


def test_runtime_ready_when_running_and_gateway_online():
    svc = HermesRuntimeStatusService()
    pair = svc.compute(docker_status="running", gateway_status="online", gateway_port=18900)
    assert pair.gateway_runtime_status == "ready"
    assert pair.mcp_status == "ready"


def test_runtime_degraded_when_gateway_timeout():
    svc = HermesRuntimeStatusService()
    pair = svc.compute(docker_status="running", gateway_status="timeout", gateway_port=18900)
    assert pair.gateway_runtime_status == "degraded"
    assert pair.mcp_status == "unavailable"


def test_runtime_unconfigured_without_gateway_port():
    svc = HermesRuntimeStatusService()
    pair = svc.compute(docker_status="running", gateway_status="unknown", gateway_port=None)
    assert pair.gateway_runtime_status == "unconfigured"
    assert pair.mcp_status == "unconfigured"


def test_runtime_unavailable_when_container_missing():
    svc = HermesRuntimeStatusService()
    pair = svc.compute(docker_status="missing", gateway_status="offline", gateway_port=18900)
    assert pair.gateway_runtime_status == "unavailable"
