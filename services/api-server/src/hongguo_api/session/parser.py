"""将 Signer 捕获的自然 App 请求转换成可信会话快照。

这里只允许红果域名、已知设备 query 字段和已知会话 header，防止抓包数据把
API Server 变成任意目标请求器，或把无关敏感字段长期保存到磁盘。
"""

from collections.abc import Mapping
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlsplit

from hongguo_contracts.signer import SessionSnapshot


ALLOWED_QUERY_FIELDS = frozenset(
    {
        "ac",
        "iid",
        "device_id",
        "cdid",
        "klink_egdi",
        "aid",
        "app_dark_mode",
        "app_mini_window",
        "app_name",
        "version_code",
        "version_name",
        "channel",
        "compliance_status",
        "device_brand",
        "device_platform",
        "device_type",
        "dpi",
        "dragon_device_type",
        "font_scale",
        "gender",
        "host_abi",
        "is_android_pad_screen",
        "language",
        "manifest_version_code",
        "need_personal_recommend",
        "network_type",
        "os",
        "os_api",
        "os_version",
        "resolution",
        "rom_version",
        "ssmix",
        "update_version_code",
    }
)
ALLOWED_SESSION_HEADERS = frozenset(
    {
        "authorization",
        "cookie",
        "lc",
        "x-tt-token",
        "user-agent",
        "x-reading-request",
        "x-tt-store-region",
        "x-tt-store-region-src",
        "x-vc-bdturing-sdk-version",
        "x-xs-from-web",
        "passport-sdk-version",
        "sdk-version",
    }
)


class SessionCaptureError(ValueError):
    """Raised when a raw signer capture is malformed or untrusted."""


def parse_session_capture(captured: object) -> SessionSnapshot:
    """校验、过滤并标准化一次原始会话捕获。"""

    if not isinstance(captured, Mapping):
        raise SessionCaptureError("invalid signer capture: expected an object")

    url = captured.get("url")
    raw_headers = captured.get("headers")
    if not isinstance(url, str) or not isinstance(raw_headers, Mapping):
        raise SessionCaptureError(
            "invalid signer capture: url must be a string and headers an object"
        )
    if not all(
        isinstance(key, str) and isinstance(value, str) for key, value in raw_headers.items()
    ):
        raise SessionCaptureError("invalid signer capture: header names and values must be strings")

    parsed = urlsplit(url)
    hostname = parsed.hostname
    # 只接受可信 HTTPS 红果上游，拒绝用户名密码形式和相似后缀域名。
    if (
        parsed.scheme.lower() != "https"
        or hostname is None
        or (hostname.lower() != "fqnovel.com" and not hostname.lower().endswith(".fqnovel.com"))
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise SessionCaptureError("capture URL must use a trusted HTTPS fqnovel host")

    base_query: dict[str, str] = {}
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        normalized_key = key.lower()
        if normalized_key not in ALLOWED_QUERY_FIELDS:
            continue
        # 同名字段只采用首次出现的值，避免参数污染和歧义。
        if normalized_key in base_query:
            continue
        base_query[normalized_key] = value

    session_headers: dict[str, str] = {}
    for key, value in raw_headers.items():
        # header 名称不区分大小写，落盘时统一为小写。
        normalized_key = key.lower()
        if normalized_key in ALLOWED_SESSION_HEADERS:
            session_headers[normalized_key] = value

    return SessionSnapshot(
        api_host=hostname.lower(),
        base_query=base_query,
        session_headers=session_headers,
        captured_at=datetime.now(timezone.utc),
    )
