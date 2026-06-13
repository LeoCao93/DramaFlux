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
    author: str = ""
    type: str = ""
    duration: str = ""
    publish_time: str = ""
    intro: str = ""
    record_number: str = ""
    subtitles: list[str] = Field(default_factory=list)
    rank: int | None = Field(default=None, ge=1)
    score: float | None = None


class DramaPage(BaseModel):
    """短剧列表页，以及可选的下一页游标。"""

    model_config = ConfigDict(extra="forbid", strict=True)

    items: list[DramaItem] = Field(default_factory=list)
    next_cursor: str | None = None
    has_more: bool = False
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=30, ge=1, le=100)
    total: int | None = Field(default=None, ge=0)
