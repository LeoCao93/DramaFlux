from hongguo_api.cache import CachedHongguoService


class CountingService:
    def __init__(self) -> None:
        self.calls = 0

    async def search(self, query: str, cursor: str | None = None) -> dict:
        self.calls += 1
        return {"query": query, "cursor": cursor, "call": self.calls}

    async def latest(
        self,
        genre: str,
        today_only: bool,
        cursor: str | None = None,
    ) -> dict:
        self.calls += 1
        return {"call": self.calls}

    async def rank(self, board: str, cursor: str | None = None) -> dict:
        self.calls += 1
        return {"call": self.calls}

    async def detail(self, series_id: str) -> dict:
        self.calls += 1
        return {"call": self.calls}

    async def resolve_video(self, video_id: str, quality: str) -> dict:
        self.calls += 1
        return {"call": self.calls}


async def test_cache_reuses_same_key_and_separates_cursor() -> None:
    source = CountingService()
    cached = CachedHongguoService(source)

    first = await cached.search("测试", None)
    second = await cached.search("测试", None)
    paged = await cached.search("测试", "next")

    assert first == second
    assert paged != first
    assert source.calls == 2


async def test_all_business_methods_are_cached() -> None:
    source = CountingService()
    cached = CachedHongguoService(source)

    operations = [
        lambda: cached.latest("short_play", True, None),
        lambda: cached.rank("hot", None),
        lambda: cached.detail("1"),
        lambda: cached.resolve_video("2", "1080p"),
    ]
    for operation in operations:
        assert await operation() == await operation()

    assert source.calls == 4
