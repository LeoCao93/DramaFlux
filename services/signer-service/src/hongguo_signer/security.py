from collections.abc import Mapping
from typing import Any


CANONICAL_SECURITY_HEADERS = {
    "x-argus": "X-Argus",
    "x-gorgon": "X-Gorgon",
    "x-ladon": "X-Ladon",
    "x-khronos": "X-Khronos",
    "x-helios": "X-Helios",
    "x-medusa": "X-Medusa",
    "x-ss-req-ticket": "X-SS-REQ-TICKET",
}

CANONICAL_SESSION_HEADERS = {
    "cookie": "cookie",
    "x-tt-token": "x-tt-token",
    "user-agent": "user-agent",
    "x-tt-store-region": "x-tt-store-region",
    "x-tt-store-region-src": "x-tt-store-region-src",
    "passport-sdk-version": "passport-sdk-version",
    "sdk-version": "sdk-version",
}


def filter_security_headers(headers: Mapping[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for key, value in headers.items():
        canonical = CANONICAL_SECURITY_HEADERS.get(str(key).lower())
        if canonical is not None and value:
            result[canonical] = str(value)
    return result


def filter_session_headers(headers: Mapping[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for key, value in headers.items():
        canonical = CANONICAL_SESSION_HEADERS.get(str(key).lower())
        if canonical is not None and value is not None:
            result[canonical] = str(value)
    return result
