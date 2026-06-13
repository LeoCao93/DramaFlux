import base64
import json
from pathlib import Path
from typing import Any

import pytest

from hongguo_api.models import DramaItem, DramaPage
from hongguo_api.parsers.latest import parse_latest
from hongguo_api.parsers.rank import parse_rank
from hongguo_api.parsers.search import (
    CursorError,
    decode_search_cursor,
    encode_search_cursor,
    parse_search,
)
from hongguo_api.upstream.client import HongguoClient

FIXTURES = Path(__file__).parents[1] / "fixtures"


def load(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_drama_models_expose_stable_additive_defaults() -> None:
    item = DramaItem(series_id="1", title="title")

    assert item.author == ""
    assert item.type == ""
    assert item.categories == []
    assert item.duration == ""
    assert item.publish_time == ""
    assert item.intro == ""
    assert item.record_number == ""
    assert item.subtitles == []
    assert item.rank is None
    assert item.score is None

    page = DramaPage(page=2, page_size=30)

    assert page.page == 2
    assert page.page_size == 30
    assert page.total is None


def test_search_parser_preserves_cursor_state_and_skips_malformed_cells() -> None:
    page = parse_search(load("search.json"))

    assert [item.series_id for item in page.items] == ["100", "broken"]
    assert page.items[0].title == "测试短剧"
    assert page.items[1].episode_count == 0
    assert page.has_more is True
    assert decode_search_cursor(page.next_cursor) == {
        "offset": 20,
        "passback": "pass",
        "search_id": "search",
    }


def test_search_parser_handles_malformed_top_level_data() -> None:
    assert parse_search({"search_tabs": "bad"}).items == []
    assert parse_search({"search_tabs": [None]}).items == []


def test_search_cursor_is_deterministic_url_safe_and_round_trips_unicode() -> None:
    state = {"offset": 20, "passback": "中文+/=", "search_id": "id"}

    cursor = encode_search_cursor(state)

    assert cursor == encode_search_cursor(state)
    assert "+" not in cursor and "/" not in cursor and "=" not in cursor
    assert decode_search_cursor(cursor) == state


@pytest.mark.parametrize(
    "cursor",
    [
        "",
        "not-base64!",
        base64.urlsafe_b64encode(b"[]").decode().rstrip("="),
        base64.urlsafe_b64encode(b'{"v":2,"offset":0}').decode().rstrip("="),
        base64.urlsafe_b64encode(b'{"v":1,"offset":-1}').decode().rstrip("="),
        base64.urlsafe_b64encode(
            b'{"v":1,"offset":0,"passback":null,"search_id":null,"admin":true}'
        )
        .decode()
        .rstrip("="),
        "a" * 2049,
    ],
)
def test_search_cursor_rejects_invalid_or_unsafe_input(cursor: str) -> None:
    with pytest.raises(CursorError):
        decode_search_cursor(cursor)


def test_search_parser_does_not_emit_looping_cursor_without_next_offset() -> None:
    page = parse_search({"search_tabs": [{"has_more": True, "data": []}]})

    assert page.has_more is False
    assert page.next_cursor is None


def test_latest_parser_uses_official_today_label_and_safe_categories() -> None:
    page = parse_latest(load("latest.json"), today_only=False)

    assert [item.series_id for item in page.items] == ["100", "101"]
    latest = page.items[0]
    assert latest.author == "影黎万像"
    assert latest.publish_time == "2026-06-13 00:16:00"
    assert latest.intro == "简介"
    assert latest.record_number == "网微剧备字"
    assert latest.duration == "1小时48分钟"
    assert latest.play_count == 1041
    assert latest.subtitles == ["今日上新", "战神归来"]
    assert latest.type == "战神归来"
    assert latest.categories == ["都市"]
    assert latest.is_today is True
    assert page.items[1].is_today is False
    assert page.items[1].categories == []
    assert page.items[1].episode_count == 0


def test_latest_parser_normalizes_the_whole_page_regardless_of_today_only() -> None:
    page = parse_latest(load("latest.json"), today_only=True)

    assert [item.series_id for item in page.items] == ["100", "101"]


def test_latest_parser_handles_malformed_payload_as_empty() -> None:
    assert parse_latest({"data": []}, today_only=False).items == []


def test_rank_parser_uses_evidenced_fields_and_absolute_ranks() -> None:
    page = parse_rank(load("rank.json"), rank_offset=30, page=2, page_size=10)

    assert [item.series_id for item in page.items] == ["100", "102"]
    ranked = page.items[0]
    assert ranked.video_id == "101"
    assert ranked.play_count == 300
    assert ranked.rank == 31
    assert ranked.score == 9.6
    assert ranked.author == "测试作者"
    assert ranked.copyright == "测试作者"
    assert ranked.cover == "https://example.com/cover.jpg"
    assert ranked.intro == "测试简介"
    assert page.items[1].rank == 32
    assert page.items[1].episode_count == 0
    assert page.items[1].score is None
    assert page.items[1].duration == ""
    assert page.items[1].publish_time == ""
    assert page.page == 2
    assert page.page_size == 10
    assert page.has_more is True


class RecordingTransport:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.calls: list[tuple[str, str, dict[str, Any]]] = []

    async def request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        self.calls.append((method, path, kwargs))
        return self.payload


async def test_search_client_decodes_cursor_into_upstream_query() -> None:
    transport = RecordingTransport({"search_tabs": []})
    client = HongguoClient(transport)  # type: ignore[arg-type]
    cursor = encode_search_cursor(
        {"offset": 40, "passback": "next-pass", "search_id": "search-id"}
    )

    await client.search("测试", cursor=cursor)

    method, path, kwargs = transport.calls[0]
    assert (method, path) == ("GET", "/reading/bookapi/search/tab/v")
    assert kwargs["query"]["query"] == "测试"
    assert kwargs["query"]["offset"] == "40"
    assert kwargs["query"]["passback"] == "next-pass"
    assert kwargs["query"]["search_id"] == "search-id"


async def test_search_client_rejects_invalid_cursor_before_transport() -> None:
    transport = RecordingTransport({"search_tabs": []})
    client = HongguoClient(transport)  # type: ignore[arg-type]

    with pytest.raises(CursorError):
        await client.search("测试", cursor="invalid!")

    assert transport.calls == []


async def test_latest_client_builds_expected_request() -> None:
    transport = RecordingTransport({"data": {"video_data": []}})
    client = HongguoClient(transport)  # type: ignore[arg-type]

    await client.latest("short_play", today_only=True)

    method, path, kwargs = transport.calls[0]
    assert (method, path) == ("POST", "/reading/distribution/category/landpage/v")
    assert kwargs["body"]["select_items"]["genre"] == ["short_play"]
    assert kwargs["body"]["select_items"]["online_time"] == []


@pytest.mark.parametrize(
    ("board", "expected"),
    [
        ("recommend", "comic_series_hot_rank"),
        ("hot", "comic_series_hot_play"),
        ("new", "comic_series_new_rank"),
        ("must_watch", "ranklist_must_watch"),
        ("followed", "ranklist_followed"),
        ("hot_search", "ranklist_hot_search_sc"),
    ],
)
async def test_rank_client_maps_supported_boards(board: str, expected: str) -> None:
    transport = RecordingTransport({"data": {}})
    client = HongguoClient(transport)  # type: ignore[arg-type]

    await client.rank(board)

    _, _, kwargs = transport.calls[0]
    assert kwargs["query"]["sub_selected_items"] == expected
    assert "offset" not in kwargs["query"]
    assert "limit" not in kwargs["query"]


async def test_rank_client_rejects_unknown_board_before_transport() -> None:
    transport = RecordingTransport({"data": {}})
    client = HongguoClient(transport)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="unsupported board"):
        await client.rank("secret-board")

    assert transport.calls == []
