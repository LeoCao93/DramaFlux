"""排行榜 cell 响应解析。"""

from collections.abc import Mapping
from typing import Any

from hongguo_api.models import DramaItem, DramaPage


def _safe_int(value: object) -> int:
    """安全读取集数和播放量。"""

    if isinstance(value, bool):
        return 0
    try:
        return max(0, int(value))  # type: ignore[arg-type]
    except (TypeError, ValueError, OverflowError):
        return 0


def parse_rank(payload: Mapping[str, Any]) -> DramaPage:
    """展平 ``cell_data[].video_data[]`` 为统一短剧列表。"""

    data_value = payload.get("data")
    data = data_value if isinstance(data_value, Mapping) else {}
    view_value = data.get("cell_view")
    view = view_value if isinstance(view_value, Mapping) else {}
    raw_cells = view.get("cell_data")
    items: list[DramaItem] = []
    # 上游榜单使用“页面 cell -> cell 内视频”的两层结构。
    if isinstance(raw_cells, list):
        for cell in raw_cells:
            if not isinstance(cell, Mapping):
                continue
            raw_videos = cell.get("video_data")
            if not isinstance(raw_videos, list):
                continue
            for value in raw_videos:
                if not isinstance(value, Mapping):
                    continue
                series_id = value.get("series_id")
                if series_id is None or isinstance(series_id, (dict, list)):
                    continue
                video_id = value.get("vid")
                items.append(
                    DramaItem(
                        series_id=str(series_id),
                        video_id=(
                            str(video_id)
                            if video_id is not None
                            and not isinstance(video_id, (dict, list))
                            else None
                        ),
                        title=str(value.get("title") or ""),
                        episode_count=_safe_int(value.get("episode_cnt")),
                        play_count=_safe_int(value.get("play_cnt")),
                        cover=str(value.get("cover") or ""),
                        copyright=str(value.get("copyright") or ""),
                    )
                )
    return DramaPage(items=items, has_more=view.get("has_more") is True)
