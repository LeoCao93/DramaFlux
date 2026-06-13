import base64
import binascii
import json
import math
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

_CURSOR_VERSION = 1
_MAX_CURSOR_LENGTH = 4096
_MAX_COLLECTION_DEPTH = 2


class CursorError(ValueError):
    """游标格式无效或与当前接口不匹配。"""


class PageRequest(BaseModel):
    """列表接口共用的页码、页大小和游标参数。"""

    model_config = ConfigDict(extra="forbid", strict=True)

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=30, ge=1, le=100)
    cursor: str | None = Field(default=None, max_length=_MAX_CURSOR_LENGTH)

    @model_validator(mode="after")
    def validate_mode(self) -> "PageRequest":
        if self.cursor is not None and self.page != 1:
            raise ValueError("cursor cannot be combined with page > 1")
        return self

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


def _validate_cursor_value(value: Any, collection_depth: int) -> None:
    if isinstance(value, dict):
        if collection_depth > _MAX_COLLECTION_DEPTH:
            raise CursorError("cursor state is nested too deeply")
        for key, item in value.items():
            if not isinstance(key, str):
                raise CursorError("cursor object keys must be strings")
            _validate_cursor_value(item, collection_depth + 1)
        return

    if isinstance(value, list):
        if collection_depth > _MAX_COLLECTION_DEPTH:
            raise CursorError("cursor state is nested too deeply")
        for item in value:
            _validate_cursor_value(item, collection_depth + 1)
        return

    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float) and math.isfinite(value):
        return
    raise CursorError("cursor state contains an unsupported value")


def encode_cursor(namespace: str, state: dict[str, Any]) -> str:
    """将接口命名空间和上游翻页状态编码成不透明游标。"""

    if not isinstance(namespace, str) or not namespace:
        raise CursorError("cursor namespace must not be empty")
    if not isinstance(state, dict):
        raise CursorError("cursor state must be an object")
    _validate_cursor_value(state, collection_depth=1)

    payload = {"v": _CURSOR_VERSION, "ns": namespace, "state": state}
    try:
        raw = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise CursorError("cursor state is not JSON serializable") from error

    cursor = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
    if len(cursor) > _MAX_CURSOR_LENGTH:
        raise CursorError("cursor is too long")
    return cursor


def decode_cursor(cursor: str, namespace: str) -> dict[str, Any]:
    """解码并校验指定接口命名空间下的不透明游标。"""

    if (
        not isinstance(cursor, str)
        or not cursor
        or len(cursor) > _MAX_CURSOR_LENGTH
        or not isinstance(namespace, str)
        or not namespace
    ):
        raise CursorError("invalid cursor")

    padding = "=" * (-len(cursor) % 4)
    try:
        raw = base64.b64decode(
            cursor + padding,
            altchars=b"-_",
            validate=True,
        )
        payload = json.loads(raw.decode("utf-8"))
    except (binascii.Error, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CursorError("invalid cursor") from error

    if (
        not isinstance(payload, dict)
        or set(payload) != {"v", "ns", "state"}
        or payload.get("v") != _CURSOR_VERSION
        or payload.get("ns") != namespace
        or not isinstance(payload.get("state"), dict)
    ):
        raise CursorError("invalid cursor")

    state = payload["state"]
    _validate_cursor_value(state, collection_depth=1)
    return state
