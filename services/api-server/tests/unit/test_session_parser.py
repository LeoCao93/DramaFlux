from datetime import timezone

import pytest

from hongguo_api.session.parser import SessionCaptureError, parse_session_capture


def test_parse_session_capture_keeps_only_allowlisted_fields() -> None:
    captured = {
        "url": (
            "https://api5-normal-sinfonlinea.fqnovel.com/video?"
            "iid=2&device_id=1&cdid=3&klink_egdi=4&aid=8662&"
            "app_name=novelapp&version_code=600&version_name=6.0&"
            "channel=official&device_platform=android&device_type=Pixel&"
            "os_version=14&access_token=query-secret&unrelated=value"
        ),
        "headers": {
            "X-TT-Token": "token",
            "COOKIE": "session=cookie",
            "User-Agent": "Hongguo/1.0",
            "x-tt-store-region": "cn",
            "X-TT-STORE-REGION-SRC": "uid",
            "Passport-SDK-Version": "19",
            "SDK-Version": "2",
            "X-Argus": "signing-secret",
            "x-gorgon": "signing-secret",
            "X-Khronos": "123",
            "x-ladon": "signing-secret",
            "x-ss-stub": "body-signature",
            "Authorization": "Bearer unrelated-secret",
            "lc": "search",
            "X-Reading-Request": "search-context",
            "X-XS-From-Web": "false",
            "X-VC-BDTuring-SDK-Version": "3.3.0",
            "X-Api-Key": "unrelated-secret",
        },
    }

    snapshot = parse_session_capture(captured)

    assert snapshot.api_host == "api5-normal-sinfonlinea.fqnovel.com"
    assert snapshot.base_query == {
        "iid": "2",
        "device_id": "1",
        "cdid": "3",
        "klink_egdi": "4",
        "aid": "8662",
        "app_name": "novelapp",
        "version_code": "600",
        "version_name": "6.0",
        "channel": "official",
        "device_platform": "android",
        "device_type": "Pixel",
        "os_version": "14",
    }
    assert snapshot.session_headers == {
        "authorization": "Bearer unrelated-secret",
        "lc": "search",
        "x-reading-request": "search-context",
        "x-xs-from-web": "false",
        "x-vc-bdturing-sdk-version": "3.3.0",
        "x-tt-token": "token",
        "cookie": "session=cookie",
        "user-agent": "Hongguo/1.0",
        "x-tt-store-region": "cn",
        "x-tt-store-region-src": "uid",
        "passport-sdk-version": "19",
        "sdk-version": "2",
    }
    assert snapshot.captured_at.tzinfo == timezone.utc
    assert snapshot.captured_at.utcoffset().total_seconds() == 0


def test_parse_session_capture_normalizes_mixed_case_query_fields() -> None:
    capture = {
        "url": "https://api.fqnovel.com/path?DEVICE_ID=1&IiD=2",
        "headers": {},
    }

    snapshot = parse_session_capture(capture)

    assert snapshot.base_query == {"device_id": "1", "iid": "2"}


def test_parse_session_capture_keeps_stable_client_fingerprint_only() -> None:
    capture = {
        "url": (
            "https://api.fqnovel.com/path?"
            "ac=wifi&device_brand=MuMu&dpi=320&dragon_device_type=phone&"
            "font_scale=1.0&gender=0&host_abi=x86_64&language=zh&"
            "manifest_version_code=600&need_personal_recommend=1&"
            "network_type=wifi&os=android&os_api=35&resolution=1080x1920&"
            "rom_version=12&ssmix=a&update_version_code=600&"
            "app_dark_mode=0&app_mini_window=0&compliance_status=0&"
            "is_android_pad_screen=0&"
            "_rticket=expired&battery_pct=99&current_volume=7&"
            "down_speed=1024&normal_session_id=ephemeral"
        ),
        "headers": {},
    }

    snapshot = parse_session_capture(capture)

    assert snapshot.base_query == {
        "ac": "wifi",
        "app_dark_mode": "0",
        "app_mini_window": "0",
        "compliance_status": "0",
        "device_brand": "MuMu",
        "dpi": "320",
        "dragon_device_type": "phone",
        "font_scale": "1.0",
        "gender": "0",
        "host_abi": "x86_64",
        "is_android_pad_screen": "0",
        "language": "zh",
        "manifest_version_code": "600",
        "need_personal_recommend": "1",
        "network_type": "wifi",
        "os": "android",
        "os_api": "35",
        "resolution": "1080x1920",
        "rom_version": "12",
        "ssmix": "a",
        "update_version_code": "600",
    }


@pytest.mark.parametrize(
    "url",
    [
        "http://api.fqnovel.com/path?device_id=1",
        "https://fqnovel.com.evil.test/path?device_id=1",
        "https://evilfqnovel.com/path?device_id=1",
        "https://user:password@api.fqnovel.com/path?device_id=1",
        "https:///path?device_id=1",
    ],
)
def test_parse_session_capture_rejects_untrusted_urls(url: str) -> None:
    with pytest.raises(SessionCaptureError, match="HTTPS fqnovel"):
        parse_session_capture({"url": url, "headers": {}})


@pytest.mark.parametrize(
    "captured",
    [
        {},
        {"url": 123, "headers": {}},
        {"url": "https://api.fqnovel.com", "headers": []},
        {
            "url": "https://api.fqnovel.com",
            "headers": {"x-tt-token": 123},
        },
    ],
)
def test_parse_session_capture_rejects_invalid_capture_shape(
    captured: object,
) -> None:
    with pytest.raises(SessionCaptureError, match="invalid signer capture"):
        parse_session_capture(captured)


def test_parse_session_capture_keeps_first_case_insensitive_duplicate_query_field() -> None:
    capture = {
        "url": (
            "https://api.fqnovel.com/path?"
            "DEVICE_ID=first&device_id=second&IiD=original&IID=repeated"
        ),
        "headers": {},
    }

    snapshot = parse_session_capture(capture)

    assert snapshot.base_query == {
        "device_id": "first",
        "iid": "original",
    }
