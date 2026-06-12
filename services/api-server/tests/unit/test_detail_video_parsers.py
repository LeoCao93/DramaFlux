import json
import base64
from pathlib import Path

import pytest

from hongguo_api.parsers.detail import DetailNotFoundError, DetailParseError, parse_detail
from hongguo_api.parsers.video import (
    EncryptedStreamError,
    VideoModelParseError,
    VideoNotFoundError,
    parse_video_model,
)

FIXTURES = Path(__file__).parents[1] / "fixtures"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def video_payload(video_list: object) -> dict:
    return {
        "data": {
            "101": {
                "video_model": json.dumps(
                    {"video_list": video_list},
                    ensure_ascii=False,
                )
            }
        }
    }


def test_detail_parser_orders_valid_episodes_and_skips_malformed_entries() -> None:
    detail = parse_detail(load("detail.json"), "100")

    assert detail.series_id == "100"
    assert detail.title == "详情短剧"
    assert detail.episode_count == 3
    assert [item.index for item in detail.episodes] == [1, 2]
    assert [item.video_id for item in detail.episodes] == ["101", "102"]
    assert detail.episodes[1].cover == "https://image.test/episode-2.jpg"


@pytest.mark.parametrize("payload", [None, [], {"data": []}, {"data": {"100": []}}])
def test_detail_parser_rejects_malformed_response_shapes(payload: object) -> None:
    with pytest.raises(DetailParseError):
        parse_detail(payload, "100")  # type: ignore[arg-type]


def test_detail_parser_reports_missing_series() -> None:
    with pytest.raises(DetailNotFoundError):
        parse_detail({"data": {}}, "100")


def test_detail_parser_rejects_malformed_video_list() -> None:
    payload = {"data": {"100": {"video_data": {"video_list": "not-a-list"}}}}

    with pytest.raises(DetailParseError):
        parse_detail(payload, "100")


def test_detail_parser_uses_safe_metadata_fallbacks() -> None:
    payload = {
        "data": {
            "100": {
                "video_data": {
                    "series_title": 123,
                    "episode_cnt": "bad",
                    "video_list": [{"vid": 101, "vid_index": "1", "duration": "60"}],
                }
            }
        }
    }

    detail = parse_detail(payload, "100")

    assert detail.title == "100"
    assert detail.episode_count == 1
    assert detail.episodes[0].video_id == "101"
    assert detail.episodes[0].duration == 60


def test_video_parser_selects_requested_quality_and_ignores_invalid_urls() -> None:
    video = parse_video_model(load("video_model.json"), "101", "1080p")

    assert video.vod_id == "v-high"
    assert video.selected_quality == "1080p"
    assert video.url == "https://video.test/1080"


def test_video_parser_selects_best_lower_quality() -> None:
    video = parse_video_model(load("video_model.json"), "101", "900p")

    assert video.vod_id == "v-low"
    assert video.selected_quality == "720p"
    assert video.backup_url == "https://backup.test/720"


def test_video_parser_uses_lowest_higher_quality_when_no_lower_exists() -> None:
    video = parse_video_model(load("video_model.json"), "101", "480p")

    assert video.vod_id == "v-low"


def test_video_parser_rejects_only_encrypted_candidates() -> None:
    payload = video_payload(
        [
            {
                "video_id": "v",
                "main_url": "https://video.test/encrypted",
                "video_meta": {"definition": "1080p"},
                "encrypt_info": {"encrypt": True},
            }
        ]
    )

    with pytest.raises(EncryptedStreamError):
        parse_video_model(payload, "101", "1080p")


@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        {"data": []},
        {"data": {"101": []}},
        {"data": {"101": {"video_model": "{not-json"}}},
        {"data": {"101": {"video_model": json.dumps([])}}},
        {"data": {"101": {"video_model": json.dumps({"video_list": "bad"})}}},
    ],
)
def test_video_parser_rejects_malformed_response_shapes(payload: object) -> None:
    with pytest.raises(VideoModelParseError):
        parse_video_model(payload, "101", "1080p")  # type: ignore[arg-type]


def test_video_parser_reports_missing_video() -> None:
    with pytest.raises(VideoNotFoundError):
        parse_video_model({"data": {}}, "101", "1080p")


def test_video_parser_rejects_models_without_valid_playback_urls() -> None:
    payload = video_payload(
        [
            {
                "video_id": "v",
                "main_url": "file:///local/video.mp4",
                "video_meta": {"definition": "1080p"},
            }
        ]
    )

    with pytest.raises(VideoModelParseError):
        parse_video_model(payload, "101", "1080p")


def test_video_parser_drops_invalid_backup_url() -> None:
    payload = video_payload(
        [
            {
                "video_id": "v",
                "main_url": "https://video.test/main",
                "backup_url": "javascript:alert(1)",
                "video_meta": {"definition": "1080p"},
            }
        ]
    )

    video = parse_video_model(payload, "101", "1080p")

    assert video.backup_url is None


def test_video_parser_accepts_real_object_shape_and_detects_encryption() -> None:
    encoded = base64.b64encode(b"https://video.test/encrypted").decode()
    payload = {
        "data": {
            "101": {
                "video_model": json.dumps(
                    {
                        "video_id": "vod",
                        "video_list": {
                            "video_1": {
                                "definition": "720p",
                                "vheight": 720,
                                "bitrate": 1000,
                                "main_url": encoded,
                                "encrypt": True,
                                "encryption_method": "cenc-aes-ctr",
                            }
                        },
                    }
                )
            }
        }
    }

    with pytest.raises(EncryptedStreamError):
        parse_video_model(payload, "101", "1080p")
