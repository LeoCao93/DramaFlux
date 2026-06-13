from typing import Any

from hongguo_api.pagination import decode_cursor
from hongguo_api.upstream.client import HongguoClient


def latest_payload(
    items: list[dict[str, Any]],
    *,
    has_more: bool,
    next_offset: int,
    session_id: str,
) -> dict[str, Any]:
    return {
        "data": {
            "video_data": items,
            "has_more": has_more,
            "next_offset": next_offset,
            "session_id": session_id,
        }
    }


def latest_item(series_id: str, *, today: bool) -> dict[str, Any]:
    subtitles = [{"content": "今日上新"}] if today else [{"content": "都市"}]
    return {
        "series_id": series_id,
        "title": series_id,
        "sub_title_list": subtitles,
    }


class SequencedTransport:
    def __init__(self, payloads: list[dict[str, Any]]) -> None:
        self.payloads = list(payloads)
        self.calls: list[tuple[str, str, dict[str, Any]]] = []

    async def request(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        self.calls.append((method, path, kwargs))
        return self.payloads.pop(0)


async def test_latest_collects_today_items_across_pages() -> None:
    transport = SequencedTransport(
        [
            latest_payload(
                [
                    latest_item("today-1", today=True),
                    latest_item("old-1", today=False),
                ],
                has_more=True,
                next_offset=2,
                session_id="session-1",
            ),
            latest_payload(
                [
                    latest_item("today-2", today=True),
                    latest_item("old-2", today=False),
                ],
                has_more=True,
                next_offset=4,
                session_id="session-2",
            ),
        ]
    )
    client = HongguoClient(transport)  # type: ignore[arg-type]

    result = await client.latest(
        "short_play",
        True,
        page=1,
        page_size=2,
        cursor=None,
    )

    assert [item.series_id for item in result.items] == ["today-1", "today-2"]
    assert len(transport.calls) == 2
    second_body = transport.calls[1][2]["body"]
    assert second_body["offset"] == 2
    assert second_body["filter_ids"] == "today-1,old-1"
    assert second_body["session_id"] == "session-1"
    assert result.has_more is True
    assert result.next_cursor is not None
    assert decode_cursor(result.next_cursor, "latest") == {
        "filter_ids": ["today-1", "old-1", "today-2", "old-2"],
        "offset": 4,
        "session_id": "session-2",
    }


async def test_latest_cursor_restores_upstream_state() -> None:
    from hongguo_api.pagination import encode_cursor

    cursor = encode_cursor(
        "latest",
        {
            "offset": 18,
            "session_id": "saved-session",
            "filter_ids": ["seen-1", "seen-2"],
        },
    )
    transport = SequencedTransport(
        [
            latest_payload(
                [latest_item("new-1", today=False)],
                has_more=False,
                next_offset=19,
                session_id="next-session",
            )
        ]
    )
    client = HongguoClient(transport)  # type: ignore[arg-type]

    result = await client.latest(
        "short_play",
        False,
        page=1,
        page_size=30,
        cursor=cursor,
    )

    body = transport.calls[0][2]["body"]
    assert body["offset"] == 18
    assert body["filter_ids"] == "seen-1,seen-2"
    assert body["session_id"] == "saved-session"
    assert [item.series_id for item in result.items] == ["new-1"]
    assert result.has_more is False
    assert result.next_cursor is None
