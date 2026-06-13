"""分类落地页及今日上新响应解析。"""

import json
from collections.abc import Mapping
from typing import Any

from hongguo_api.models import DramaItem, DramaPage

_OPERATIONAL_SUBTITLES = {"今日上新"}


def _safe_int(value: object) -> int:
    """安全读取上游数字字段。"""

    if isinstance(value, bool):
        return 0
    try:
        return max(0, int(value))  # type: ignore[arg-type]
    except (TypeError, ValueError, OverflowError):
        return 0


def _categories(value: object) -> list[str]:
    """兼容 JSON 字符串或数组形式的分类字段。"""

    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return []
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        if not isinstance(item, Mapping):
            continue
        name = item.get("name")
        if isinstance(name, str) and name:
            result.append(name)
    return result


def _text(value: object) -> str:
    """将可选上游文本字段归一化为空字符串或原始文本。"""

    return value if isinstance(value, str) else ""


def _subtitles(value: object) -> list[str]:
    """提取运营副标题，并忽略空值和非对象成员。"""

    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        if not isinstance(item, Mapping):
            continue
        content = item.get("content")
        if isinstance(content, str) and content:
            result.append(content)
    return result


def parse_latest(payload: Mapping[str, Any], today_only: bool) -> DramaPage:
    """将一个上游上新页面完整归一化为稳定的列表模型。

    ``today_only`` 暂时保留以兼容现有调用方；跨页收集和今日筛选属于
    ``HongguoClient`` 的职责，解析器不会丢弃当前页面中的非今日条目。
    """

    del today_only

    data_value = payload.get("data")
    if not isinstance(data_value, Mapping):
        return DramaPage()
    raw_items = data_value.get("video_data")
    items: list[DramaItem] = []
    if isinstance(raw_items, list):
        for value in raw_items:
            if not isinstance(value, Mapping):
                continue
            series_id = value.get("series_id")
            if series_id is None or isinstance(series_id, (dict, list)):
                continue
            subtitles = _subtitles(value.get("sub_title_list"))
            categories = _categories(value.get("category_schema"))
            descriptive_subtitles = [
                subtitle
                for subtitle in subtitles
                if subtitle not in _OPERATIONAL_SUBTITLES
            ]
            item_type = next(iter(descriptive_subtitles or categories), "")
            if not categories:
                categories = descriptive_subtitles
            items.append(
                DramaItem(
                    series_id=str(series_id),
                    title=_text(value.get("title")),
                    author=_text(value.get("author"))
                    or _text(value.get("copyright")),
                    type=item_type,
                    duration=_text(value.get("duration")),
                    publish_time=_text(value.get("publish_time")),
                    intro=_text(value.get("video_desc"))
                    or _text(value.get("intro")),
                    record_number=_text(value.get("record_number")),
                    subtitles=subtitles,
                    episode_count=_safe_int(value.get("episode_cnt")),
                    play_count=_safe_int(value.get("play_cnt")),
                    cover=_text(value.get("cover")),
                    copyright=_text(value.get("copyright")),
                    categories=categories,
                    is_today="今日上新" in subtitles,
                )
            )
    return DramaPage(
        items=items,
        has_more=data_value.get("has_more") is True,
    )
