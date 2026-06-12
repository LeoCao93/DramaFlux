"""搜索响应解析和不透明分页游标。"""

import base64
import binascii
import json
from collections.abc import Mapping
from typing import Any

from hongguo_api.models import DramaItem, DramaPage

_CURSOR_VERSION = 1
_MAX_CURSOR_LENGTH = 2048
_MAX_CURSOR_VALUE_LENGTH = 4096


class CursorError(ValueError):
    """公开 cursor 无法安全解码或不符合当前版本协议。"""

    def __init__(self) -> None:
        super().__init__("invalid search cursor")


def _safe_int(value: object) -> int:
    """将上游宽松数字转换为非负整数，失败时返回 0。"""

    if isinstance(value, bool):
        return 0
    try:
        return max(0, int(value))  # type: ignore[arg-type]
    except (TypeError, ValueError, OverflowError):
        return 0


def _cursor_state(value: Mapping[str, object]) -> dict[str, int | str | None]:
    """验证 cursor 内部状态，限制字段类型和长度。"""

    offset = value.get("offset")
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
        raise CursorError()

    state: dict[str, int | str | None] = {"offset": offset}
    for key in ("passback", "search_id"):
        item = value.get(key)
        if item is not None and (
            not isinstance(item, str) or len(item) > _MAX_CURSOR_VALUE_LENGTH
        ):
            raise CursorError()
        state[key] = item
    return state


def encode_search_cursor(state: Mapping[str, object]) -> str:
    """将上游分页状态编码成 URL-safe、带版本号的不透明 cursor。"""

    normalized = _cursor_state(state)
    payload = {"v": _CURSOR_VERSION, **normalized}
    raw = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    encoded = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
    if len(encoded) > _MAX_CURSOR_LENGTH:
        raise CursorError()
    return encoded


def decode_search_cursor(cursor: str | None) -> dict[str, int | str | None]:
    """解码并严格验证客户端传回的搜索 cursor。"""

    if not cursor or len(cursor) > _MAX_CURSOR_LENGTH:
        raise CursorError()
    try:
        # 对外省略 Base64 padding，解码时按长度恢复。
        padding = "=" * (-len(cursor) % 4)
        raw = base64.b64decode(cursor + padding, altchars=b"-_", validate=True)
        value = json.loads(raw.decode("utf-8"))
    except (binascii.Error, UnicodeDecodeError, json.JSONDecodeError):
        raise CursorError() from None
    if (
        not isinstance(value, dict)
        or set(value) != {"v", "offset", "passback", "search_id"}
        or value.get("v") != _CURSOR_VERSION
    ):
        raise CursorError()
    return _cursor_state(value)


def parse_search(payload: Mapping[str, Any]) -> DramaPage:
    """把搜索 tab 的嵌套结构转换为统一 ``DramaPage``。"""

    tabs = payload.get("search_tabs")
    if not isinstance(tabs, list) or not tabs or not isinstance(tabs[0], Mapping):
        return DramaPage()
    tab = tabs[0]
    raw_items = tab.get("data")
    items: list[DramaItem] = []
    if isinstance(raw_items, list):
        for cell in raw_items:
            if not isinstance(cell, Mapping):
                continue
            # 不同 App 版本可能把标题和集数放在两个不同子对象中。
            detail_value = cell.get("video_detail")
            video_value = cell.get("video_data")
            detail = detail_value if isinstance(detail_value, Mapping) else {}
            video = video_value if isinstance(video_value, Mapping) else {}
            series_id = cell.get("book_id") or cell.get("search_result_id")
            if series_id is None or isinstance(series_id, (dict, list)):
                continue
            items.append(
                DramaItem(
                    series_id=str(series_id),
                    title=str(detail.get("series_title") or video.get("title") or ""),
                    episode_count=_safe_int(
                        detail.get("episode_cnt") or video.get("episode_cnt")
                    ),
                    cover=str(video.get("cover") or ""),
                    copyright=str(video.get("copyright") or ""),
                )
            )

    next_offset = tab.get("next_offset")
    # 只有 has_more 与合法 next_offset 同时存在时才生成下一页 cursor，
    # 避免缺失 offset 时产生永远指向当前页的循环游标。
    has_more = (
        tab.get("has_more") is True
        and isinstance(next_offset, int)
        and not isinstance(next_offset, bool)
        and next_offset >= 0
    )
    cursor = None
    if has_more:
        try:
            cursor = encode_search_cursor(
                {
                    "offset": next_offset,
                    "passback": tab.get("passback"),
                    "search_id": tab.get("search_id"),
                }
            )
        except CursorError:
            has_more = False
    return DramaPage(items=items, next_cursor=cursor, has_more=has_more)
