"""红果平台业务接口客户端。

该类只描述各业务能力对应的上游路径和请求参数；动态签名、HTTP 错误和连接池由
``SignedTransport`` 统一处理，响应结构转换则交给各自 parser。
"""

import uuid
from collections.abc import Mapping
from typing import Any

from hongguo_api.models import DramaPage
from hongguo_api.pagination import CursorError, decode_cursor, encode_cursor
from hongguo_api.parsers.detail import SeriesDetail, parse_detail
from hongguo_api.parsers.latest import parse_latest
from hongguo_api.parsers.rank import parse_rank
from hongguo_api.parsers.search import decode_search_cursor, parse_search
from hongguo_api.parsers.video import VideoResult, parse_video_model
from hongguo_api.upstream.transport import SignedTransport

_RANK_BOARDS = {
    "recommend": "comic_series_hot_rank",
    "hot": "comic_series_hot_play",
    "new": "comic_series_new_rank",
    "must_watch": "ranklist_must_watch",
    "followed": "ranklist_followed",
    "hot_search": "ranklist_hot_search_sc",
}


class HongguoClient:
    """实现搜索、上新、榜单、详情和视频模型等红果业务能力。"""

    def __init__(self, transport: SignedTransport) -> None:
        self.transport = transport

    async def search(
        self,
        query: str,
        page: int = 1,
        page_size: int = 30,
        cursor: str | None = None,
    ) -> DramaPage:
        """搜索短剧，并在有 cursor 时恢复上游分页状态。"""

        upstream_query = {
            "query": query,
            "tab_name": "feed",
            "search_source": "1",
            "offset": str((page - 1) * page_size),
            "count": str(page_size),
            "use_correct": "true",
        }
        if cursor is not None:
            # 对外 cursor 是不透明字符串，调用方无需了解 passback/search_id。
            state = decode_search_cursor(cursor)
            upstream_query["offset"] = str(state["offset"])
            for key in ("passback", "search_id"):
                value = state[key]
                if value is not None:
                    upstream_query[key] = value
        payload = await self.transport.request(
            "GET",
            "/reading/bookapi/search/tab/v",
            query=upstream_query,
        )
        return parse_search(payload)

    async def latest(
        self,
        genre: str,
        today_only: bool,
        page: int = 1,
        page_size: int = 30,
        cursor: str | None = None,
    ) -> DramaPage:
        """请求分类落地页，并按需要筛选“今日上新”条目。"""

        state = (
            decode_cursor(cursor, "latest")
            if cursor is not None
            else {
                "offset": (page - 1) * page_size,
                "session_id": "",
                "filter_ids": [],
            }
        )
        offset = self._state_int(state, "offset")
        session_id = self._state_string(state, "session_id")
        filter_ids = self._state_string_list(state, "filter_ids")
        items = []
        has_more = False
        today_cluster_seen = False

        for _ in range(20):
            payload = await self.transport.request(
                "POST",
                "/reading/distribution/category/landpage/v",
                body={
                    "filter_ids": ",".join(filter_ids),
                    "req_scene": "default" if genre == "short_play" else genre,
                    "offset": offset,
                    "need_selector_panel": False,
                    "limit": page_size,
                    "select_items": {
                        "category_dim_epoch": [],
                        "online_time": [] if genre == "short_play" else ["days_7"],
                        "gender": [],
                        "category_dim_role": [],
                        "genre": [genre],
                        "sort": ["online_time"],
                        "category_dim_theme": [],
                    },
                    "session_id": session_id,
                    "req_type": "only_content",
                    "client_req_type": 3,
                },
            )
            parsed = parse_latest(payload, today_only=False)
            page_items = parsed.items
            filter_ids.extend(item.series_id for item in page_items)
            selected = (
                [item for item in page_items if item.is_today]
                if genre == "short_play" and today_only
                else page_items
            )
            if any(item.is_today for item in page_items):
                today_cluster_seen = True
            items.extend(selected)

            data = payload.get("data")
            data = data if isinstance(data, Mapping) else {}
            has_more = data.get("has_more") is True
            raw_next_offset = data.get("next_offset")
            offset = (
                raw_next_offset
                if isinstance(raw_next_offset, int)
                and not isinstance(raw_next_offset, bool)
                and raw_next_offset >= 0
                else offset + len(page_items)
            )
            raw_session_id = data.get("session_id")
            if isinstance(raw_session_id, str):
                session_id = raw_session_id

            enough = len(items) >= page_size
            passed_today_cluster = (
                genre == "short_play"
                and today_only
                and today_cluster_seen
                and not any(item.is_today for item in page_items)
            )
            if enough or not has_more or not page_items or passed_today_cluster:
                break

        next_cursor = None
        if has_more:
            next_cursor = encode_cursor(
                "latest",
                {
                    "offset": offset,
                    "session_id": session_id,
                    "filter_ids": filter_ids,
                },
            )
        return DramaPage(
            items=items[:page_size],
            page=page,
            page_size=page_size,
            next_cursor=next_cursor,
            has_more=next_cursor is not None,
        )

    @staticmethod
    def _state_int(state: Mapping[str, Any], key: str) -> int:
        value = state.get(key)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            return value
        raise CursorError("cursor is invalid")

    @staticmethod
    def _state_string(state: Mapping[str, Any], key: str) -> str:
        value = state.get(key)
        if isinstance(value, str):
            return value
        raise CursorError("cursor is invalid")

    @staticmethod
    def _state_string_list(state: Mapping[str, Any], key: str) -> list[str]:
        value = state.get(key)
        if isinstance(value, list) and all(isinstance(item, str) for item in value):
            return list(value)
        raise CursorError("cursor is invalid")

    async def rank(
        self,
        board: str,
        page: int = 1,
        page_size: int = 30,
        cursor: str | None = None,
    ) -> DramaPage:
        """根据公开榜单名称请求对应的上游榜单选择项。"""

        try:
            upstream_board = _RANK_BOARDS[board]
        except KeyError:
            raise ValueError(f"unsupported board: {board}") from None

        rank_offset = 0
        session_uuid = str(uuid.uuid4())
        if cursor is not None:
            state = decode_cursor(cursor, "rank")
            if set(state) != {"board", "next_offset", "session_uuid"}:
                raise CursorError("cursor is invalid")
            if state.get("board") != board:
                raise CursorError("cursor does not belong to this board")
            rank_offset = self._state_int(state, "next_offset")
            session_uuid = self._state_string(state, "session_uuid")
            if not session_uuid:
                raise CursorError("cursor is invalid")

        query = {
            "cell_id": "7470092475068071998",
            "tab_type": "26",
            "client_req_type": "2",
            "client_template": "2",
            "selected_items": "comic_series_rank",
            "sub_selected_items": upstream_board,
            "session_uuid": session_uuid,
        }
        if cursor is not None:
            query["offset"] = str(rank_offset)

        payload = await self.transport.request(
            "GET",
            "/reading/bookapi/bookmall/cell/change/v",
            query=query,
        )
        parsed = parse_rank(
            payload,
            rank_offset=rank_offset,
            page=page,
            page_size=page_size,
        )

        data = payload.get("data")
        data = data if isinstance(data, Mapping) else {}
        cell_view = data.get("cell_view")
        cell_view = cell_view if isinstance(cell_view, Mapping) else {}
        next_offset = cell_view.get("next_offset")
        has_valid_continuation = (
            cell_view.get("has_more") is True
            and isinstance(next_offset, int)
            and not isinstance(next_offset, bool)
            and next_offset >= 0
        )
        next_cursor = (
            encode_cursor(
                "rank",
                {
                    "board": board,
                    "next_offset": next_offset,
                    "session_uuid": session_uuid,
                },
            )
            if has_valid_continuation
            else None
        )
        return parsed.model_copy(
            update={
                "next_cursor": next_cursor,
                "has_more": next_cursor is not None,
            }
        )

    async def detail(self, series_id: str) -> SeriesDetail:
        """获取短剧元数据及全部剧集列表。"""

        payload = await self.transport.request(
            "POST",
            "/novel/player/multi_video_detail/v1/",
            body={
                "biz_param": {
                    "detail_page_version": 0,
                    "disable_digg_stat": False,
                    "disable_video_relate_book": False,
                    "need_all_video_definition": False,
                    "need_mp4_align": False,
                    "screen_width_px": "900",
                    "source": 7,
                    "use_os_player": False,
                    "use_server_dns": False,
                },
                "series_id": str(series_id),
            },
        )
        return parse_detail(payload, series_id)

    async def resolve_video(
        self,
        video_id: str,
        quality: str,
        fast: bool = True,
    ) -> VideoResult:
        """获取指定单集的视频模型并选择最合适的清晰度。"""

        del fast
        payload = await self.transport.request(
            "POST",
            "/novel/player/multi_video_model/v1/",
            body={
                "biz_param": {
                    "detail_page_version": 0,
                    "device_level": 3,
                    "disable_digg_stat": False,
                    "disable_video_relate_book": False,
                    "need_all_video_definition": True,
                    "need_mp4_align": False,
                    "use_os_player": False,
                    "use_server_dns": False,
                    "video_platform": 1024,
                },
                "mixed_video_id_map": {"1": [str(video_id)]},
            },
        )
        return parse_video_model(payload, video_id, quality)
