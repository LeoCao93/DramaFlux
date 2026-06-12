"""分类落地页及今日上新响应解析。"""

import json
from collections.abc import Mapping
from typing import Any

from hongguo_api.models import DramaItem, DramaPage


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


def parse_latest(payload: Mapping[str, Any], today_only: bool) -> DramaPage:
    """解析上新列表，并可只保留带官方今日标签的项目。"""

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
            # 上游通过 sub_title_list 展示“今日上新”等运营标签。
            subtitles = value.get("sub_title_list")
            labels = (
                [
                    item.get("content")
                    for item in subtitles
                    if isinstance(item, Mapping)
                ]
                if isinstance(subtitles, list)
                else []
            )
            is_today = "今日上新" in labels
            if today_only and not is_today:
                continue
            items.append(
                DramaItem(
                    series_id=str(series_id),
                    title=str(value.get("title") or ""),
                    episode_count=_safe_int(value.get("episode_cnt")),
                    cover=str(value.get("cover") or ""),
                    copyright=str(value.get("copyright") or ""),
                    categories=_categories(value.get("category_schema")),
                    is_today=is_today,
                )
            )
    return DramaPage(
        items=items,
        has_more=data_value.get("has_more") is True,
    )
