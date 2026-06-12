"""跨接口复用的标准化短剧业务模型。"""

from pydantic import BaseModel, ConfigDict, Field


class DramaItem(BaseModel):
    """搜索、上新和榜单接口统一返回的短剧摘要。"""

    # strict=True 防止字符串数字等脏数据在业务层被静默转换。
    model_config = ConfigDict(extra="forbid", strict=True)

    series_id: str
    video_id: str | None = None
    title: str
    episode_count: int = 0
    play_count: int = 0
    cover: str = ""
    copyright: str = ""
    categories: list[str] = Field(default_factory=list)
    is_today: bool = False


class DramaPage(BaseModel):
    """短剧列表页，以及可选的下一页游标。"""

    model_config = ConfigDict(extra="forbid", strict=True)

    items: list[DramaItem] = Field(default_factory=list)
    next_cursor: str | None = None
    has_more: bool = False
