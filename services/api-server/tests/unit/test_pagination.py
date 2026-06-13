import base64

import pytest

from hongguo_api.pagination import (
    CursorError,
    PageRequest,
    decode_cursor,
    encode_cursor,
)


def test_page_request_accepts_default_first_page() -> None:
    request = PageRequest(page=1, page_size=30, cursor=None)

    assert request.offset == 0


def test_page_request_rejects_cursor_with_explicit_later_page() -> None:
    with pytest.raises(ValueError, match="cursor"):
        PageRequest(page=2, page_size=30, cursor="next")


def test_cursor_round_trips_versioned_namespace_and_state() -> None:
    cursor = encode_cursor(
        "latest",
        {"offset": 18, "session_id": "s", "filter_ids": ["1", "2"]},
    )

    assert decode_cursor(cursor, "latest") == {
        "offset": 18,
        "session_id": "s",
        "filter_ids": ["1", "2"],
    }


def test_cursor_rejects_wrong_namespace() -> None:
    cursor = encode_cursor("latest", {"offset": 18})

    with pytest.raises(CursorError):
        decode_cursor(cursor, "rank")


@pytest.mark.parametrize(
    "cursor",
    [
        "",
        "not-base64!",
        base64.urlsafe_b64encode(b"[]").decode().rstrip("="),
        base64.urlsafe_b64encode(
            b'{"v":2,"ns":"latest","state":{}}'
        ).decode().rstrip("="),
        base64.urlsafe_b64encode(
            b'{"v":1,"ns":"latest","state":[]}'
        ).decode().rstrip("="),
        "a" * 4097,
    ],
)
def test_cursor_rejects_malformed_or_unsafe_input(cursor: str) -> None:
    with pytest.raises(CursorError):
        decode_cursor(cursor, "latest")


def test_cursor_rejects_state_nested_beyond_two_collection_levels() -> None:
    with pytest.raises(CursorError):
        encode_cursor("latest", {"outer": {"inner": {"too_deep": "value"}}})
