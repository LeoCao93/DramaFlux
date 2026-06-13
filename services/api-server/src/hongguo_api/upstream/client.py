"""红果平台业务接口客户端。

该类只描述各业务能力对应的上游路径和请求参数；动态签名、HTTP 错误和连接池由
``SignedTransport`` 统一处理，响应结构转换则交给各自 parser。
"""

import uuid

from hongguo_api.models import DramaPage
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

        # 当前上游分页参数尚未确认，因此暂不消费公开 cursor。
        del cursor
        payload = await self.transport.request(
            "POST",
            "/reading/distribution/category/landpage/v",
            body={
                "filter_ids": "",
                "req_scene": "default" if genre == "short_play" else genre,
                "offset": (page - 1) * page_size,
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
                "session_id": "",
                "req_type": "only_content",
                "client_req_type": 3,
            },
        )
        return parse_latest(payload, today_only=today_only)

    async def rank(
        self,
        board: str,
        page: int = 1,
        page_size: int = 30,
        cursor: str | None = None,
    ) -> DramaPage:
        """根据公开榜单名称请求对应的上游榜单选择项。"""

        del cursor
        try:
            upstream_board = _RANK_BOARDS[board]
        except KeyError:
            raise ValueError(f"unsupported board: {board}") from None
        payload = await self.transport.request(
            "GET",
            "/reading/bookapi/bookmall/cell/change/v",
            query={
                "cell_id": "7470092475068071998",
                "tab_type": "26",
                "client_req_type": "2",
                "client_template": "2",
                "selected_items": "comic_series_rank",
                "sub_selected_items": upstream_board,
                "offset": str((page - 1) * page_size),
                "limit": str(page_size),
                # 每次请求生成新的会话 UUID，模拟 App 的榜单切换请求。
                "session_uuid": str(uuid.uuid4()),
            },
        )
        return parse_rank(payload)

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
