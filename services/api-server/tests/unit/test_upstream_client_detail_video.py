from hongguo_api.upstream.client import HongguoClient


class FakeTransport:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.calls: list[tuple[str, str, dict]] = []

    async def request(self, method: str, path: str, **kwargs: object) -> dict:
        self.calls.append((method, path, kwargs))
        return self.payload


async def test_detail_uses_multi_video_detail_endpoint() -> None:
    transport = FakeTransport(
        {
            "data": {
                "100": {
                    "video_data": {
                        "series_title": "title",
                        "video_list": [{"vid": "101", "vid_index": 1}],
                    }
                }
            }
        }
    )
    detail = await HongguoClient(transport).detail("100")  # type: ignore[arg-type]

    method, path, kwargs = transport.calls[0]
    assert (method, path) == ("POST", "/novel/player/multi_video_detail/v1/")
    assert kwargs["body"]["series_id"] == "100"  # type: ignore[index]
    assert detail.episodes[0].video_id == "101"


async def test_video_uses_multi_video_model_endpoint() -> None:
    transport = FakeTransport(
        {
            "data": {
                "101": {
                    "video_model": {
                        "video_list": [
                            {
                                "video_id": "vod",
                                "main_url": "https://video.test/stream",
                                "video_meta": {"definition": "1080p"},
                            }
                        ]
                    }
                }
            }
        }
    )
    video = await HongguoClient(transport).resolve_video(  # type: ignore[arg-type]
        "101",
        "1080p",
        True,
    )

    method, path, kwargs = transport.calls[0]
    assert (method, path) == ("POST", "/novel/player/multi_video_model/v1/")
    assert kwargs["body"]["mixed_video_id_map"] == {"1": ["101"]}  # type: ignore[index]
    assert video.vod_id == "vod"
