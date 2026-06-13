"""短剧详情与剧集列表解析。"""

import json
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field


class DetailParseError(ValueError):
    """详情响应不符合预期结构。"""


class DetailNotFoundError(LookupError):
    """响应合法，但其中不存在指定短剧。"""


class Episode(BaseModel):
    """标准化单集信息。"""

    model_config = ConfigDict(extra="forbid", strict=True)

    index: int = Field(ge=0)
    video_id: str = Field(min_length=1)
    title: str
    first_pass_time: str = ""
    volume_name: str = ""
    duration_seconds: int | None = Field(default=None, ge=0)
    cover: str = ""


class SeriesDetail(BaseModel):
    """短剧详情及按序排列的全部剧集。"""

    model_config = ConfigDict(extra="forbid", strict=True)

    series_id: str = Field(min_length=1)
    title: str
    author: str = ""
    category: str = ""
    categories: list[str] = Field(default_factory=list)
    duration: str = ""
    publish_time: str = ""
    episode_count: int = Field(ge=0)
    intro: str = ""
    cover: str = ""
    episodes: list[Episode]


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    """要求字段为对象，否则将协议漂移报告为解析错误。"""

    if not isinstance(value, Mapping):
        raise DetailParseError(f"{field} must be an object")
    return value


def _text(value: Any, default: str = "") -> str:
    """只接受真实字符串，避免把对象等脏数据暴露到 API。"""

    return value if isinstance(value, str) else default


def _identifier(value: Any) -> str | None:
    """将字符串或整数 ID 标准化为非空字符串。"""

    if isinstance(value, bool):
        return None
    if isinstance(value, (str, int)):
        result = str(value).strip()
        return result or None
    return None


def _integer(value: Any, default: int | None = None) -> int | None:
    """将上游数字标准化为非负整数。"""

    if isinstance(value, bool):
        return default
    try:
        result = int(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return result if result >= 0 else default


def _http_url(value: Any) -> str:
    """只保留无用户信息的 HTTP(S) 图片地址。"""

    if not isinstance(value, str):
        return ""
    try:
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return ""
        if parsed.username is not None or parsed.password is not None:
            return ""
    except ValueError:
        return ""
    return value


def _categories(value: Any) -> list[str]:
    """解析分类 JSON/list，并按上游顺序去重。"""

    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return []
    if not isinstance(value, list):
        return []

    categories: list[str] = []
    seen: set[str] = set()
    for raw_item in value:
        if not isinstance(raw_item, Mapping):
            continue
        name = _text(raw_item.get("name")).strip()
        if name and name not in seen:
            categories.append(name)
            seen.add(name)
    return categories


def parse_detail(payload: dict[str, Any], series_id: str) -> SeriesDetail:
    """解析指定短剧详情，跳过无 ID/序号的脏剧集并稳定排序。"""

    root = _mapping(payload, "response")
    data = _mapping(root.get("data"), "data")
    series_key = str(series_id)
    if series_key not in data:
        raise DetailNotFoundError("series detail was not found")

    wrapper = _mapping(data[series_key], "series")
    video_data = _mapping(wrapper.get("video_data"), "video_data")
    if not video_data:
        raise DetailParseError("video_data must not be empty")
    raw_video_list = video_data.get("video_list")
    if not isinstance(raw_video_list, list):
        raise DetailParseError("video_list must be an array")

    episodes: list[Episode] = []
    for raw_item in raw_video_list:
        if not isinstance(raw_item, Mapping):
            continue
        video_id = _identifier(raw_item.get("vid"))
        index = _integer(raw_item.get("vid_index"))
        if video_id is None or index is None:
            continue
        episodes.append(
            Episode(
                index=index,
                video_id=video_id,
                title=_text(raw_item.get("title")),
                first_pass_time=_text(raw_item.get("firstPassTime")),
                volume_name=_text(raw_item.get("volume_name")),
                duration_seconds=_integer(raw_item.get("duration")),
                cover=_http_url(
                    raw_item.get("episode_cover") or raw_item.get("cover")
                ),
            )
        )

    # 先按 vid_index 排序，重复序号再按 video_id 保证结果确定。
    episodes.sort(key=lambda item: (item.index, item.video_id))
    episode_count = _integer(video_data.get("episode_cnt"), len(episodes))
    categories = _categories(video_data.get("category_schema"))
    category = _text(video_data.get("category")).strip()
    if not category and categories:
        category = categories[0]
    return SeriesDetail(
        series_id=series_key,
        title=_text(video_data.get("series_title"), series_key),
        author=_text(video_data.get("author")),
        category=category,
        categories=categories,
        duration=_text(video_data.get("duration")),
        publish_time=_text(video_data.get("publish_time")),
        episode_count=episode_count if episode_count is not None else len(episodes),
        intro=_text(video_data.get("series_intro")),
        cover=_http_url(video_data.get("series_cover")),
        episodes=episodes,
    )
