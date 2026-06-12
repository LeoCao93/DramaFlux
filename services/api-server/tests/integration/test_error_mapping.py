from fastapi.testclient import TestClient

from hongguo_api.errors import (
    RiskControlledError,
    SessionExpiredError,
    UpstreamTimeoutError,
)
from hongguo_api.main import create_app
from hongguo_api.parsers.detail import DetailNotFoundError
from hongguo_api.parsers.search import CursorError
from hongguo_api.parsers.video import VideoNotFoundError
from hongguo_api.signer.client import SignerTransportError


class FailingService:
    def __init__(self, error: Exception) -> None:
        self.error = error

    async def resolve_video(self, video_id: str, quality: str) -> object:
        raise self.error


def test_encrypted_stream_maps_to_422() -> None:
    from hongguo_api.parsers.video import EncryptedStreamError

    response = TestClient(create_app(FailingService(EncryptedStreamError("1")))).get(
        "/api/videos/1"
    )
    assert response.status_code == 422
    assert response.json()["code"] == "encrypted_stream_unsupported"


def test_stable_upstream_error_mapping_does_not_leak_details() -> None:
    cases = [
        (SessionExpiredError(), 401, "session_expired"),
        (RiskControlledError(), 429, "risk_controlled"),
        (UpstreamTimeoutError(), 504, "upstream_timeout"),
        (SignerTransportError("secret"), 503, "signer_unavailable"),
    ]
    for error, status, code in cases:
        response = TestClient(create_app(FailingService(error))).get("/api/videos/1")
        assert response.status_code == status
        assert response.json()["code"] == code
        assert "top-secret" not in response.text


def test_resource_and_cursor_errors_have_stable_statuses() -> None:
    cases = [
        (DetailNotFoundError("secret"), 404, "book_not_found"),
        (VideoNotFoundError("secret"), 404, "video_not_found"),
        (CursorError(), 400, "invalid_cursor"),
    ]
    for error, status, code in cases:
        response = TestClient(create_app(FailingService(error))).get("/api/videos/1")
        assert response.status_code == status
        assert response.json()["code"] == code
        assert "secret" not in response.text
