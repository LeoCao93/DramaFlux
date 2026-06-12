import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import pytest
from hongguo_contracts.signer import SessionSnapshot
from pydantic import ValidationError

from hongguo_api.config import ApiSettings
from hongguo_api.session.storage import (
    InvalidSessionFileError,
    SessionFileMissingError,
    SessionStore,
)


def snapshot() -> SessionSnapshot:
    return SessionSnapshot(
        api_host="api5-normal-sinfonlinea.fqnovel.com",
        base_query={"device_id": "1", "iid": "2"},
        session_headers={"x-tt-token": "token", "cookie": "cookie"},
        captured_at=datetime(2026, 6, 12, tzinfo=timezone.utc),
    )


def test_api_settings_have_local_defaults() -> None:
    settings = ApiSettings()

    assert settings.signer_url == "http://127.0.0.1:18001"
    assert settings.signer_token == "local-development"
    assert settings.session_file == Path(".local/session.json")
    assert settings.timeout_seconds == 30.0


def test_api_settings_reject_blank_signer_token() -> None:
    with pytest.raises(ValidationError, match="signer_token must not be blank"):
        ApiSettings(signer_token=" \t ")


def test_session_store_round_trips_utf8_json_without_field_loss(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "session.json"
    store = SessionStore(path)
    value = snapshot().model_copy(
        update={"session_headers": {"user-agent": "红果/1.0"}}
    )

    store.save(value)

    assert store.load() == value
    assert "红果/1.0" in path.read_text(encoding="utf-8")


def test_session_store_replaces_existing_file_atomically(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "session.json"
    path.write_text('{"old": true}', encoding="utf-8")
    replacements: list[tuple[Path, Path]] = []
    real_replace = os.replace

    def recording_replace(source: Path, destination: Path) -> None:
        replacements.append((Path(source), Path(destination)))
        real_replace(source, destination)

    monkeypatch.setattr(os, "replace", recording_replace)

    SessionStore(path).save(snapshot())

    assert len(replacements) == 1
    assert replacements[0][1] == path
    assert replacements[0][0].parent == path.parent
    assert replacements[0][0] != path
    assert not replacements[0][0].exists()


def test_session_store_applies_restrictive_permissions_best_effort(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    chmod_calls: list[tuple[Path, int]] = []

    def denied_chmod(path: Path, mode: int) -> None:
        chmod_calls.append((Path(path), mode))
        raise OSError("unsupported")

    monkeypatch.setattr(os, "chmod", denied_chmod)
    path = tmp_path / "session.json"

    SessionStore(path).save(snapshot())

    assert chmod_calls
    assert all(mode == 0o600 for _, mode in chmod_calls)
    assert SessionStore(path).load() == snapshot()


def test_session_store_reports_missing_file_clearly(tmp_path: Path) -> None:
    path = tmp_path / "missing.json"

    with pytest.raises(SessionFileMissingError, match=re.escape(str(path))):
        SessionStore(path).load()


@pytest.mark.parametrize(
    ("contents", "message"),
    [
        ("not json", "invalid JSON"),
        (json.dumps({"api_host": "api.fqnovel.com"}), "invalid session snapshot"),
        (
            json.dumps(
                {
                    **snapshot().model_dump(mode="json"),
                    "unexpected": "field",
                }
            ),
            "invalid session snapshot",
        ),
    ],
)
def test_session_store_reports_invalid_content_clearly(
    tmp_path: Path, contents: str, message: str
) -> None:
    path = tmp_path / "session.json"
    path.write_text(contents, encoding="utf-8")

    with pytest.raises(InvalidSessionFileError, match=message):
        SessionStore(path).load()
