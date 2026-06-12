import hashlib
import json
from datetime import datetime, timezone

import httpx
import pytest
import respx
from hongguo_contracts.signer import SessionSnapshot

from hongguo_api.errors import (
    RiskControlledError,
    SessionExpiredError,
    UpstreamHttpError,
    UpstreamInvalidResponseError,
    UpstreamTimeoutError,
)
from hongguo_api.upstream.transport import SignedTransport, compact_json


def session() -> SessionSnapshot:
    return SessionSnapshot(
        api_host="api.example.fqnovel.com",
        base_query={"device_id": "1", "aid": "8662"},
        session_headers={
            "x-tt-token": "top-secret",
            "cookie": "session=secret",
            "accept-encoding": "gzip",
        },
        captured_at=datetime(2026, 6, 12, tzinfo=timezone.utc),
    )


def test_compact_json_is_deterministic_utf8() -> None:
    assert compact_json({"title": "红果", "enabled": True}) == (
        '{"title":"红果","enabled":true}'.encode()
    )


@respx.mock
async def test_transport_signs_and_sends_identical_url_body_and_stub() -> None:
    observed: dict[str, object] = {}

    class FakeSigner:
        async def sign(self, url: str, headers: dict[str, str]) -> dict[str, str]:
            observed["signed_url"] = url
            observed["signed_headers"] = dict(headers)
            return {"X-Khronos": "123", "X-Gorgon": "abc"}

    route = respx.post(url__startswith="https://api.example.fqnovel.com/path?").mock(
        return_value=httpx.Response(200, json={"code": 0, "data": {"ok": True}})
    )
    async with httpx.AsyncClient() as client:
        transport = SignedTransport(
            session(),
            FakeSigner(),
            client,
            clock_ms=lambda: 1_781_193_600_123,
        )
        result = await transport.request(
            "POST",
            "/path",
            body={"title": "红果", "a": 1},
            query={"q": "测试"},
        )

    request = route.calls[0].request
    expected_body = compact_json({"title": "红果", "a": 1})
    expected_stub = hashlib.md5(expected_body).hexdigest().upper()
    assert result["data"]["ok"] is True
    assert str(request.url) == observed["signed_url"]
    assert request.content == expected_body
    assert observed["signed_headers"]["x-ss-stub"] == expected_stub
    assert request.headers["x-ss-stub"] == expected_stub
    assert request.headers["x-khronos"] == "123"
    assert "accept-encoding" not in observed["signed_headers"]
    assert "q=%E6%B5%8B%E8%AF%95" in str(request.url)
    assert "_rticket=1781193600123" in str(request.url)


@respx.mock
async def test_get_request_has_no_stub_or_body() -> None:
    class FakeSigner:
        async def sign(self, url: str, headers: dict[str, str]) -> dict[str, str]:
            assert "x-ss-stub" not in headers
            return {"X-Khronos": "123"}

    route = respx.get(url__startswith="https://api.example.fqnovel.com/path?").mock(
        return_value=httpx.Response(200, json={"code": 0})
    )
    async with httpx.AsyncClient() as client:
        transport = SignedTransport(
            session(),
            FakeSigner(),
            client,
            clock_ms=lambda: 1,
        )
        await transport.request("GET", "/path")

    assert route.calls[0].request.content == b""


@respx.mock
async def test_transport_classifies_session_expiry_without_leaking_message() -> None:
    class FakeSigner:
        async def sign(self, url: str, headers: dict[str, str]) -> dict[str, str]:
            return {"X-Khronos": "123"}

    respx.get(url__startswith="https://api.example.fqnovel.com/path?").mock(
        return_value=httpx.Response(
            200,
            json={"code": 401, "message": "token top-secret expired"},
        )
    )
    async with httpx.AsyncClient() as client:
        transport = SignedTransport(session(), FakeSigner(), client, clock_ms=lambda: 1)
        with pytest.raises(SessionExpiredError) as caught:
            await transport.request("GET", "/path")

    assert str(caught.value) == "Hongguo session expired"


@respx.mock
async def test_transport_classifies_risk_control() -> None:
    class FakeSigner:
        async def sign(self, url: str, headers: dict[str, str]) -> dict[str, str]:
            return {"X-Khronos": "123"}

    respx.get(url__startswith="https://api.example.fqnovel.com/path?").mock(
        return_value=httpx.Response(
            200,
            json={"code": 110001, "message": "verify required"},
        )
    )
    async with httpx.AsyncClient() as client:
        transport = SignedTransport(session(), FakeSigner(), client, clock_ms=lambda: 1)
        with pytest.raises(RiskControlledError):
            await transport.request("GET", "/path")


@respx.mock
async def test_transport_rejects_non_object_and_invalid_json() -> None:
    class FakeSigner:
        async def sign(self, url: str, headers: dict[str, str]) -> dict[str, str]:
            return {"X-Khronos": "123"}

    route = respx.get(url__startswith="https://api.example.fqnovel.com/path?").mock(
        return_value=httpx.Response(200, json=[])
    )
    async with httpx.AsyncClient() as client:
        transport = SignedTransport(session(), FakeSigner(), client, clock_ms=lambda: 1)
        with pytest.raises(UpstreamInvalidResponseError):
            await transport.request("GET", "/path")

        route.mock(return_value=httpx.Response(200, text="not-json"))
        with pytest.raises(UpstreamInvalidResponseError):
            await transport.request("GET", "/path")


async def test_transport_maps_timeout_without_secret_leakage() -> None:
    class FakeSigner:
        async def sign(self, url: str, headers: dict[str, str]) -> dict[str, str]:
            return {"X-Khronos": "123"}

    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout(
            "top-secret " + str(request.url),
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        transport = SignedTransport(session(), FakeSigner(), client, clock_ms=lambda: 1)
        with pytest.raises(UpstreamTimeoutError) as caught:
            await transport.request("GET", "/path", query={"secret": "value"})

    assert str(caught.value) == "Hongguo upstream request timed out"


@respx.mock
async def test_transport_maps_http_status_without_response_body() -> None:
    class FakeSigner:
        async def sign(self, url: str, headers: dict[str, str]) -> dict[str, str]:
            return {"X-Khronos": "123"}

    respx.get(url__startswith="https://api.example.fqnovel.com/path?").mock(
        return_value=httpx.Response(
            503,
            text=json.dumps({"secret": "must-not-leak"}),
        )
    )
    async with httpx.AsyncClient() as client:
        transport = SignedTransport(session(), FakeSigner(), client, clock_ms=lambda: 1)
        with pytest.raises(UpstreamHttpError) as caught:
            await transport.request("GET", "/path")

    assert caught.value.status_code == 503
    assert "must-not-leak" not in str(caught.value)


def test_transport_rejects_untrusted_session_host() -> None:
    snapshot = session().model_copy(update={"api_host": "attacker.example"})

    with pytest.raises(ValueError, match="trusted fqnovel"):
        SignedTransport(snapshot, object(), httpx.AsyncClient())  # type: ignore[arg-type]
