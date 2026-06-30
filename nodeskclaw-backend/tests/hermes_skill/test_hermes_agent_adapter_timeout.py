import httpx
from app.services.hermes_skill.hermes_agent_adapter import HermesAgentAdapter


def test_build_request_timeout_has_all_four_params():
    timeout = HermesAgentAdapter._build_request_timeout()
    assert isinstance(timeout, httpx.Timeout)
    assert timeout.connect is not None
    assert timeout.read is not None
    assert timeout.write is not None
    assert timeout.pool is not None


def test_build_request_timeout_custom_read():
    timeout = HermesAgentAdapter._build_request_timeout(read_timeout=999.0)
    assert timeout.read == 999.0
    assert timeout.connect is not None
    assert timeout.write is not None
    assert timeout.pool is not None


def test_build_stream_timeout_has_all_four_params():
    timeout = HermesAgentAdapter._build_stream_timeout()
    assert isinstance(timeout, httpx.Timeout)
    assert timeout.connect is not None
    assert timeout.read is None
    assert timeout.write is not None
    assert timeout.pool is not None


def test_timeout_does_not_raise_parameter_error():
    timeout_req = HermesAgentAdapter._build_request_timeout()
    httpx.Timeout(
        connect=timeout_req.connect,
        read=timeout_req.read,
        write=timeout_req.write,
        pool=timeout_req.pool,
    )

    timeout_stream = HermesAgentAdapter._build_stream_timeout()
    httpx.Timeout(
        connect=timeout_stream.connect,
        read=timeout_stream.read,
        write=timeout_stream.write,
        pool=timeout_stream.pool,
    )
