import httpx
import pytest
import respx

from hongguo_api.signer.client import (
    SignerClient,
    SignerResponseError,
    SignerServiceError,
    SignerTimeoutError,
    SignerTransportError,
)


@respx.mock
async def test_signer_client_uses_versioned_sign_endpoint_and_bearer_token() -> None:
    route = respx.post("http://signer.test/v1/sign").mock(
        return_value=httpx.Response(
            200,
            json={
                "headers": {"X-Khronos": "123"},
                "app_pid": 42,
                "signed_at": "2026-06-12T00:00:00Z",
            },
        )
    )
    async with httpx.AsyncClient() as http_client:
        signer = SignerClient(
            "http://signer.test/",
            "service-token",
            http_client,
            timeout_seconds=7.5,
        )

        result = await signer.sign("https://api.fqnovel.com/path", {"x-test": "1"})

    request = route.calls[0].request
    assert result == {"X-Khronos": "123"}
    assert request.headers["authorization"] == "Bearer service-token"
    assert request.headers["content-type"] == "application/json"
    assert request.extensions["timeout"]["read"] == 7.5
    assert request.url.path == "/v1/sign"


@respx.mock
async def test_signer_client_captures_strict_session_snapshot() -> None:
    route = respx.post("http://signer.test/v1/session/capture").mock(
        return_value=httpx.Response(
            200,
            json={
                "api_host": "api5-normal-sinfonlinea.fqnovel.com",
                "base_query": {"device_id": "1", "aid": "8662"},
                "session_headers": {"x-tt-token": "token"},
                "captured_at": "2026-06-12T00:00:00Z",
            },
        )
    )
    async with httpx.AsyncClient() as http_client:
        signer = SignerClient("http://signer.test", "token", http_client)

        snapshot = await signer.capture_session(timeout_ms=12_345)

    request = route.calls[0].request
    assert snapshot.api_host == "api5-normal-sinfonlinea.fqnovel.com"
    assert snapshot.base_query == {"device_id": "1", "aid": "8662"}
    assert request.headers["authorization"] == "Bearer token"
    assert request.url.params["timeout_ms"] == "12345"


@pytest.mark.parametrize("timeout_ms", [0, -1, 60_001])
async def test_signer_client_rejects_capture_timeout_outside_service_bounds(
    timeout_ms: int,
) -> None:
    async with httpx.AsyncClient() as http_client:
        signer = SignerClient("http://signer.test", "token", http_client)

        with pytest.raises(ValueError, match="timeout_ms must be between"):
            await signer.capture_session(timeout_ms=timeout_ms)


@respx.mock
async def test_signer_client_rejects_invalid_raw_capture_contract() -> None:
    respx.post("http://signer.test/v1/session/capture").mock(
        return_value=httpx.Response(
            200,
            json={
                "url": "https://api.fqnovel.com/path",
                "headers": {},
            },
        )
    )
    async with httpx.AsyncClient() as http_client:
        signer = SignerClient("http://signer.test", "token", http_client)

        with pytest.raises(SignerResponseError):
            await signer.capture_session()


@pytest.mark.parametrize(
    "response_json",
    [
        {
            "headers": {"X-Khronos": "123"},
            "app_pid": "42",
            "signed_at": "2026-06-12T00:00:00Z",
        },
        {
            "headers": {"X-Khronos": "123"},
            "app_pid": 42,
            "signed_at": "2026-06-12T00:00:00Z",
            "secret": "must-not-leak",
        },
    ],
)
@respx.mock
async def test_signer_client_rejects_invalid_success_contract(
    response_json: dict[str, object],
) -> None:
    respx.post("http://signer.test/v1/sign").mock(
        return_value=httpx.Response(200, json=response_json)
    )
    async with httpx.AsyncClient() as http_client:
        signer = SignerClient("http://signer.test", "token", http_client)

        with pytest.raises(SignerResponseError) as caught:
            await signer.sign("https://api.fqnovel.com/path", {})

    assert "must-not-leak" not in str(caught.value)


async def test_signer_client_translates_timeout_without_leaking_request() -> None:
    async def timeout_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("service-token request-secret", request=request)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(timeout_handler)
    ) as http_client:
        signer = SignerClient("http://signer.test", "service-token", http_client)

        with pytest.raises(SignerTimeoutError) as caught:
            await signer.sign("https://api.fqnovel.com/path?secret=value", {})

    assert str(caught.value) == "signer request timed out"


async def test_signer_client_translates_transport_error_without_leaking_request() -> None:
    async def transport_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("service-token request-secret", request=request)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(transport_handler)
    ) as http_client:
        signer = SignerClient("http://signer.test", "service-token", http_client)

        with pytest.raises(SignerTransportError) as caught:
            await signer.sign("https://api.fqnovel.com/path?secret=value", {})

    assert str(caught.value) == "could not reach signer service"


@respx.mock
async def test_signer_client_exposes_status_and_code_but_not_error_message() -> None:
    respx.post("http://signer.test/v1/sign").mock(
        return_value=httpx.Response(
            503,
            json={
                "code": "signer_unavailable",
                "message": "internal secret path C:/secret",
                "request_id": "request-1",
            },
        )
    )
    async with httpx.AsyncClient() as http_client:
        signer = SignerClient("http://signer.test", "token", http_client)

        with pytest.raises(SignerServiceError) as caught:
            await signer.sign("https://api.fqnovel.com/path", {})

    assert caught.value.status_code == 503
    assert caught.value.code == "signer_unavailable"
    assert "internal secret" not in str(caught.value)
    assert "request-1" not in str(caught.value)


@respx.mock
async def test_signer_client_rejects_invalid_error_contract() -> None:
    respx.post("http://signer.test/v1/sign").mock(
        return_value=httpx.Response(
            500,
            json={"code": 500, "message": "secret"},
        )
    )
    async with httpx.AsyncClient() as http_client:
        signer = SignerClient("http://signer.test", "token", http_client)

        with pytest.raises(SignerResponseError) as caught:
            await signer.sign("https://api.fqnovel.com/path", {})

    assert str(caught.value) == "signer returned an invalid error response"


def test_signer_client_rejects_blank_token() -> None:
    with pytest.raises(ValueError, match="token must not be blank"):
        SignerClient("http://signer.test", " ", httpx.AsyncClient())
