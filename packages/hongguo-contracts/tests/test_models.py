from datetime import datetime, timezone

import pytest
from hongguo_contracts import ErrorResponse
from hongguo_contracts.signer import SessionSnapshot, SignRequest, SignResponse
from pydantic import ValidationError


def test_sign_request_normalizes_url_to_string() -> None:
    request = SignRequest(
        url="https://example.test/path?a=1",
        headers={"x-ss-stub": "ABC"},
    )

    assert str(request.url) == "https://example.test/path?a=1"


def test_sign_response_carries_process_identity() -> None:
    now = datetime.now(timezone.utc)
    response = SignResponse(
        headers={"X-Khronos": "123"},
        app_pid=42,
        signed_at=now,
    )

    assert response.app_pid == 42
    assert response.signed_at == now


def test_session_snapshot_separates_query_and_headers() -> None:
    snapshot = SessionSnapshot(
        api_host="api.example.test",
        base_query={"device_id": "1"},
        session_headers={"x-tt-token": "secret"},
        captured_at=datetime.now(timezone.utc),
    )

    assert snapshot.base_query["device_id"] == "1"
    assert snapshot.session_headers["x-tt-token"] == "secret"


def test_error_response_carries_stable_error_details() -> None:
    response = ErrorResponse(
        code="signer_unavailable",
        message="signer is unavailable",
        request_id="request-1",
    )

    assert response.model_dump() == {
        "code": "signer_unavailable",
        "message": "signer is unavailable",
        "request_id": "request-1",
    }


def test_sign_request_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        SignRequest(
            url="https://example.test/path",
            headers={},
            unexpected="value",
        )


def test_sign_response_rejects_string_app_pid() -> None:
    with pytest.raises(ValidationError):
        SignResponse(
            headers={"X-Khronos": "123"},
            app_pid="42",
            signed_at=datetime.now(timezone.utc),
        )


def test_session_snapshot_rejects_non_string_query_values() -> None:
    with pytest.raises(ValidationError):
        SessionSnapshot(
            api_host="api.example.test",
            base_query={"device_id": 1},
            session_headers={},
            captured_at=datetime.now(timezone.utc),
        )


def test_error_response_rejects_non_string_code() -> None:
    with pytest.raises(ValidationError):
        ErrorResponse(
            code=503,
            message="signer is unavailable",
        )
