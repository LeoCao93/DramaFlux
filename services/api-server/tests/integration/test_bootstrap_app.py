from fastapi.testclient import TestClient

from hongguo_api.bootstrap_app import build_app
from hongguo_api.config import ApiSettings


def test_api_starts_without_session_and_returns_stable_error(tmp_path) -> None:
    app = build_app(
        ApiSettings(
            signer_token="token",
            session_file=tmp_path / "missing.json",
        )
    )

    client = TestClient(app)
    assert client.get("/health").status_code == 200
    response = client.get("/api/search", params={"q": "测试"})
    assert response.status_code == 503
    assert response.json()["code"] == "session_missing"
