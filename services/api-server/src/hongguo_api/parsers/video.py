"""视频模型解析、清晰度选择和加密流检测。

红果不同版本返回过两种结构：``video_list`` 可能是数组，也可能是以
``video_1``、``video_2`` 为键的对象；播放地址也可能是 HTTP URL 或 Base64
编码字符串。本模块将这些差异统一为 ``VideoResult``。
"""

import base64
import binascii
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qs, urlsplit

from pydantic import BaseModel, ConfigDict, Field


class VideoModelParseError(ValueError):
    """视频模型响应格式损坏或不存在任何可用播放地址。"""


class VideoNotFoundError(LookupError):
    """响应合法，但指定 video_id 不存在或没有任何流。"""


class EncryptedStreamError(RuntimeError):
    """存在播放流，但全部需要 CENC/DRM 解密。"""


class VideoResult(BaseModel):
    """对外返回的单集播放信息。"""

    model_config = ConfigDict(extra="forbid", strict=True)

    video_id: str = Field(min_length=1)
    vid: str
    vod_id: str
    requested_quality: str
    selected_quality: str
    url: str = Field(min_length=1)
    backup_url: str | None = None
    encrypted: bool = False
    expires_at: str | None = None


@dataclass(frozen=True)
class _Candidate:
    """内部使用的标准化清晰度候选项。"""

    vod_id: str
    definition: str
    resolution: int
    bitrate: int
    codec_score: int
    url: str
    backup_url: str | None
    encrypted: bool


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    """要求字段为对象，否则报告明确的协议格式错误。"""

    if not isinstance(value, Mapping):
        raise VideoModelParseError(f"{field} must be an object")
    return value


def _non_negative_int(value: Any) -> int:
    """把码率、高度等字段安全转换为非负整数。"""

    if isinstance(value, bool):
        return 0
    try:
        result = int(value)
    except (TypeError, ValueError, OverflowError):
        return 0
    return max(result, 0)


def _quality_value(value: Any) -> int:
    """从 ``1080p`` 等标签中提取用于比较的数字分辨率。"""

    if not isinstance(value, str):
        return 0
    digits = "".join(character for character in value if character.isdigit())
    return int(digits or 0)


def _http_url(value: Any) -> str | None:
    """解析普通或 Base64 编码的 HTTP(S) 播放地址。

    用户名密码形式、非 HTTP 协议和损坏的 Base64 都会被拒绝。
    """

    if not isinstance(value, str):
        return None
    if not value.startswith(("http://", "https://")):
        # 真实 App 响应中的 main_url/backup_url_1 经常使用 Base64 包装。
        try:
            value = base64.b64decode(value, validate=True).decode("utf-8")
        except (binascii.Error, UnicodeDecodeError, ValueError):
            return None
    try:
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return None
        if parsed.username is not None or parsed.password is not None:
            return None
    except ValueError:
        return None
    return value


def _is_encrypted(value: Any) -> bool:
    """兼容 bool、整数和字符串形式的加密标记。"""

    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value == 1
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes"}
    return False


def _expires_at(url: str) -> str | None:
    """从播放地址读取正 Unix 秒时间戳并转换为 UTC ISO 时间。"""

    try:
        query = parse_qs(urlsplit(url).query, keep_blank_values=True)
        raw_value = next(
            (
                query[key][0]
                for key in ("x-expires", "expires", "expire")
                if query.get(key)
            ),
            None,
        )
        timestamp = int(raw_value) if raw_value is not None else 0
        if timestamp <= 0:
            return None
        return datetime.fromtimestamp(timestamp, tz=UTC).isoformat().replace(
            "+00:00",
            "Z",
        )
    except (OSError, OverflowError, TypeError, ValueError):
        return None


def _codec_score(meta: Mapping[str, Any]) -> int:
    """在相同清晰度和码率下对编码格式做稳定排序。"""

    codec = str(
        meta.get("codec")
        or meta.get("codec_type")
        or meta.get("vcodec")
        or ""
    ).lower()
    if "264" in codec or "avc" in codec:
        return 2
    if "265" in codec or "hevc" in codec:
        return 1
    return 0


def _decode_model(raw_model: Any) -> Mapping[str, Any]:
    """兼容上游直接对象或嵌套 JSON 字符串形式的视频模型。"""

    if isinstance(raw_model, str):
        try:
            raw_model = json.loads(raw_model)
        except (TypeError, ValueError) as error:
            raise VideoModelParseError("video_model is not valid JSON") from error
    return _mapping(raw_model, "video_model")


def _candidate(raw_item: Any) -> _Candidate | None:
    """将一条宽松上游流记录转换为内部候选项。"""

    if not isinstance(raw_item, Mapping):
        return None
    url = _http_url(raw_item.get("main_url"))
    if url is None:
        return None
    raw_meta = raw_item.get("video_meta") or {}
    if not isinstance(raw_meta, Mapping):
        return None
    # fixture 把字段放在 video_meta 中，真实 App 响应可能放在流对象顶层。
    definition = raw_meta.get("definition") or raw_item.get("definition")
    definition = definition if isinstance(definition, str) else "unknown"
    resolution = (
        _quality_value(definition)
        or _non_negative_int(raw_meta.get("height"))
        or _non_negative_int(raw_item.get("vheight"))
    )
    raw_encrypt_info = raw_item.get("encrypt_info") or {}
    encrypt_info = raw_encrypt_info if isinstance(raw_encrypt_info, Mapping) else {}
    return _Candidate(
        vod_id=str(raw_item.get("video_id") or ""),
        definition=definition,
        resolution=resolution,
        bitrate=_non_negative_int(raw_meta.get("bitrate") or raw_item.get("bitrate")),
        codec_score=_codec_score(raw_meta),
        url=url,
        backup_url=_http_url(
            raw_item.get("backup_url") or raw_item.get("backup_url_1")
        ),
        encrypted=_is_encrypted(
            encrypt_info.get("encrypt") or raw_item.get("encrypt")
        ),
    )


def _select(candidates: list[_Candidate], quality: str) -> _Candidate:
    """按精确、最佳较低、最近较高的顺序选择清晰度。"""

    target = _quality_value(quality)
    if target <= 0:
        # 无法识别请求标签时，选择综合质量最高的候选。
        return max(
            candidates,
            key=lambda item: (item.resolution, item.bitrate, item.codec_score),
        )

    exact = [item for item in candidates if item.resolution == target]
    if exact:
        return max(exact, key=lambda item: (item.bitrate, item.codec_score))

    lower = [item for item in candidates if 0 < item.resolution < target]
    if lower:
        return max(
            lower,
            key=lambda item: (item.resolution, item.bitrate, item.codec_score),
        )

    known_higher = [item for item in candidates if item.resolution > target]
    if known_higher:
        nearest_resolution = min(item.resolution for item in known_higher)
        nearest = [
            item for item in known_higher if item.resolution == nearest_resolution
        ]
        return max(nearest, key=lambda item: (item.bitrate, item.codec_score))

    return max(candidates, key=lambda item: (item.bitrate, item.codec_score))


def parse_video_model(
    payload: dict[str, Any],
    video_id: str,
    quality: str,
) -> VideoResult:
    """解析指定 video_id 的视频模型并返回未加密的最佳播放流。"""

    root = _mapping(payload, "response")
    data = _mapping(root.get("data"), "data")
    video_key = str(video_id)
    if video_key not in data:
        raise VideoNotFoundError("video model was not found")

    wrapper = _mapping(data[video_key], "video")
    model = _decode_model(wrapper.get("video_model"))
    raw_video_list = model.get("video_list")
    # 新版真实响应使用对象，旧版/fixture 使用数组。
    if isinstance(raw_video_list, Mapping):
        raw_video_list = list(raw_video_list.values())
    if not isinstance(raw_video_list, list):
        raise VideoModelParseError("video_list must be an array or object")
    if not raw_video_list:
        raise VideoNotFoundError("video model contains no streams")

    candidates = [
        candidate
        for raw_item in raw_video_list
        if (candidate := _candidate(raw_item)) is not None
    ]
    if not candidates:
        raise VideoModelParseError("video model contains no valid playback URLs")

    # 项目明确不实现 CENC/DRM 解密。
    unencrypted = [item for item in candidates if not item.encrypted]
    if not unencrypted:
        raise EncryptedStreamError("encrypted stream is unsupported")

    selected = _select(unencrypted, quality)
    return VideoResult(
        video_id=video_key,
        vid=str(model.get("video_id") or ""),
        vod_id=selected.vod_id,
        requested_quality=quality,
        selected_quality=selected.definition,
        url=selected.url,
        backup_url=selected.backup_url,
        encrypted=False,
        expires_at=_expires_at(selected.url),
    )
