from datetime import datetime
import threading

import pytest
from fastapi.testclient import TestClient

from hongguo_signer.frida_runtime.manager import FridaRuntimeBusyError
from hongguo_signer.main import create_app


class FakeRuntime:
    def __init__(self) -> None:
        self.pid_value: int | None = 3318
        self.healthy = True
        self.error: BaseException | None = None
        self.reconnect_calls = 0
        self.sign_calls: list[tuple[str, dict[str, str]]] = []
        self.capture_calls: list[int] = []

    @property
    def pid(self) -> int:
        if self.pid_value is None:
            raise RuntimeError("detached secret")
        return self.pid_value

    def health(self) -> bool:
        return self.healthy

    def sign(self, url: str, headers: dict[str, str]) -> dict[str, str]:
        self.sign_calls.append((url, headers))
        if self.error is not None:
            raise self.error
        return {"X-Khronos": "123", "X-Gorgon": "abc"}

    def capture_session(self, timeout_ms: int) -> dict[str, object]:
        self.capture_calls.append(timeout_ms)
        if self.error is not None:
            raise self.error
        return {
            "url": (
                "https://api5-normal-sinfonlinea.fqnovel.com/path?"
                "device_id=1&iid=2&access_token=drop"
            ),
            "headers": {
                "cookie": "session=secret",
                "x-tt-token": "token",
                "authorization": "drop",
            },
        }

    def reconnect(self) -> None:
        self.reconnect_calls += 1
        if self.error is not None:
            raise self.error


@pytest.fixture
def runtime() -> FakeRuntime:
    return FakeRuntime()


@pytest.fixture
def client(runtime: FakeRuntime) -> TestClient:
    return TestClient(create_app(runtime, service_token="test-token"))


def auth(token: str = "test-token") -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_health_is_safe_when_runtime_is_detached(runtime: FakeRuntime) -> None:
    runtime.pid_value = None
    runtime.healthy = False
    client = TestClient(create_app(runtime, service_token="detached secret"))

    response = client.get("/v1/health")

    assert response.status_code == 200
    assert response.json() == {"ready": False, "app_pid": None}
    assert "detached secret" not in response.text


def test_sign_endpoint_returns_contract_with_utc_timestamp(
    client: TestClient,
    runtime: FakeRuntime,
) -> None:
    response = client.post(
        "/v1/sign",
        headers=auth(),
        json={
            "url": "https://example.test/path",
            "headers": {"User-Agent": "test"},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["headers"]["X-Gorgon"] == "abc"
    assert body["app_pid"] == 3318
    assert datetime.fromisoformat(body["signed_at"]).utcoffset().total_seconds() == 0
    assert runtime.sign_calls == [
        ("https://example.test/path", {"User-Agent": "test"})
    ]


@pytest.mark.parametrize(
    "headers",
    [{}, {"Authorization": "Basic test-token"}, auth("wrong-token")],
)
def test_protected_endpoints_reject_invalid_bearer_token(
    client: TestClient,
    headers: dict[str, str],
) -> None:
    response = client.post(
        "/v1/sign",
        headers=headers,
        json={"url": "https://example.test/path", "headers": {}},
    )

    assert response.status_code == 401
    assert response.json() == {
        "code": "unauthorized",
        "message": "invalid service token",
        "request_id": None,
    }
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("service_token", ["", " ", "\t\r\n"])
def test_create_app_rejects_blank_service_token(
    runtime: FakeRuntime,
    service_token: str,
) -> None:
    with pytest.raises(ValueError, match="service_token"):
        create_app(runtime, service_token=service_token)


def test_capture_endpoint_returns_session_snapshot(
    client: TestClient,
    runtime: FakeRuntime,
) -> None:
    response = client.post(
        "/v1/session/capture?timeout_ms=2500",
        headers=auth(),
    )

    assert response.status_code == 200
    assert response.json()["api_host"] == "api5-normal-sinfonlinea.fqnovel.com"
    assert response.json()["base_query"] == {"device_id": "1", "iid": "2"}
    assert response.json()["session_headers"] == {
        "cookie": "session=secret",
        "x-tt-token": "token",
    }
    assert runtime.capture_calls == [2500]


@pytest.mark.parametrize("timeout_ms", [0, 60001])
def test_capture_endpoint_bounds_timeout(
    client: TestClient,
    runtime: FakeRuntime,
    timeout_ms: int,
) -> None:
    response = client.post(
        f"/v1/session/capture?timeout_ms={timeout_ms}",
        headers=auth(),
    )

    assert response.status_code == 422
    assert runtime.capture_calls == []


def test_admin_reconnect_calls_runtime(client: TestClient, runtime: FakeRuntime) -> None:
    response = client.post("/v1/admin/reconnect", headers=auth())

    assert response.status_code == 200
    assert response.json() == {"reconnected": True}
    assert runtime.reconnect_calls == 1


@pytest.mark.parametrize(
    ("error", "status_code", "code"),
    [
        (RuntimeError("token=super-secret"), 503, "signer_unavailable"),
        (FridaRuntimeBusyError("busy secret"), 409, "signer_busy"),
        (TimeoutError("timeout secret"), 504, "signer_timeout"),
    ],
)
def test_runtime_errors_are_mapped_without_leaking_details(
    runtime: FakeRuntime,
    error: BaseException,
    status_code: int,
    code: str,
) -> None:
    runtime.error = error
    client = TestClient(create_app(runtime, service_token="super-secret"))

    response = client.post(
        "/v1/sign",
        headers=auth("super-secret"),
        json={"url": "https://example.test/path", "headers": {}},
    )

    assert response.status_code == status_code
    assert response.json()["code"] == code
    assert "secret" not in response.text


def test_all_responses_include_security_headers(client: TestClient) -> None:
    response = client.get("/v1/health")

    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"


def test_concurrent_sign_returns_busy_without_blocking_runtime() -> None:
    entered = threading.Event()
    release = threading.Event()

    class BlockingRuntime(FakeRuntime):
        def sign(self, url: str, headers: dict[str, str]) -> dict[str, str]:
            self.sign_calls.append((url, headers))
            entered.set()
            release.wait(0.5)
            return {"X-Gorgon": "abc"}

    runtime = BlockingRuntime()
    client = TestClient(create_app(runtime, service_token="test-token"))
    first_response: list[object] = []

    def call_first() -> None:
        first_response.append(
            client.post(
                "/v1/sign",
                headers=auth(),
                json={"url": "https://example.test/one", "headers": {}},
            )
        )

    first = threading.Thread(target=call_first)
    first.start()
    assert entered.wait(0.2)

    busy = client.post(
        "/v1/sign",
        headers=auth(),
        json={"url": "https://example.test/two", "headers": {}},
    )
    health = client.get("/v1/health")
    reconnect = client.post("/v1/admin/reconnect", headers=auth())
    release.set()
    first.join(0.5)

    assert busy.status_code == 409
    assert busy.json()["code"] == "signer_busy"
    assert len(runtime.sign_calls) == 1
    assert health.status_code == 200
    assert reconnect.status_code == 409
    assert reconnect.json()["code"] == "signer_busy"
    assert runtime.reconnect_calls == 0
    assert first_response[0].status_code == 200


def test_admin_reconnect_returns_busy_during_active_capture() -> None:
    entered = threading.Event()
    release = threading.Event()

    class BlockingRuntime(FakeRuntime):
        def capture_session(self, timeout_ms: int) -> dict[str, object]:
            self.capture_calls.append(timeout_ms)
            entered.set()
            release.wait(0.5)
            return {
                "url": "https://api.fqnovel.com/path",
                "headers": {},
            }

    runtime = BlockingRuntime()
    client = TestClient(create_app(runtime, service_token="test-token"))
    capture_response: list[object] = []

    capture = threading.Thread(
        target=lambda: capture_response.append(
            client.post(
                "/v1/session/capture?timeout_ms=1000",
                headers=auth(),
            )
        )
    )
    capture.start()
    assert entered.wait(0.2)

    reconnect = client.post("/v1/admin/reconnect", headers=auth())
    release.set()
    capture.join(0.5)

    assert reconnect.status_code == 409
    assert reconnect.json()["code"] == "signer_busy"
    assert runtime.reconnect_calls == 0
    assert capture_response[0].status_code == 200


def test_operation_gate_is_released_after_runtime_exception(
    runtime: FakeRuntime,
) -> None:
    runtime.error = RuntimeError("failed")
    client = TestClient(create_app(runtime, service_token="test-token"))

    failed = client.post(
        "/v1/sign",
        headers=auth(),
        json={"url": "https://example.test/one", "headers": {}},
    )
    runtime.error = None
    retried = client.post(
        "/v1/sign",
        headers=auth(),
        json={"url": "https://example.test/two", "headers": {}},
    )

    assert failed.status_code == 503
    assert retried.status_code == 200
