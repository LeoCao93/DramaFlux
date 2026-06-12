"""确定性动态签名 HTTP 传输层。

本模块保证“Signer 所见即上游所收”：最终 URL、请求体字节和影响签名的请求头
必须在请求签名之前确定，签名完成后原样发送。
"""

import hashlib
import json
import time
from collections.abc import Callable, Mapping
from typing import Any, Protocol
from urllib.parse import urlencode

import httpx
from hongguo_contracts.signer import SessionSnapshot

from hongguo_api.errors import (
    RiskControlledError,
    SessionExpiredError,
    UpstreamHttpError,
    UpstreamInvalidResponseError,
    UpstreamTimeoutError,
    UpstreamTransportError,
)


class Signer(Protocol):
    """传输层所需的最小签名能力。"""

    async def sign(self, url: str, headers: dict[str, str]) -> dict[str, str]: ...


def compact_json(value: object) -> bytes:
    """将对象稳定序列化为 UTF-8 紧凑 JSON 字节。"""

    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")


class SignedTransport:
    """负责 URL 构造、x-ss-stub、动态签名、HTTP 请求和响应分类。"""

    def __init__(
        self,
        session: SessionSnapshot,
        signer: Signer,
        client: httpx.AsyncClient,
        *,
        clock_ms: Callable[[], int] | None = None,
    ) -> None:
        host = session.api_host.lower().rstrip(".")
        # 即使 session 文件被手工篡改，也不允许向任意主机发送签名请求。
        if host != "fqnovel.com" and not host.endswith(".fqnovel.com"):
            raise ValueError("session must use a trusted fqnovel host")
        self.session = session
        self.signer = signer
        self.client = client
        self.clock_ms = clock_ms or (lambda: int(time.time() * 1000))

    async def request(
        self,
        method: str,
        path: str,
        *,
        body: object | None = None,
        query: Mapping[str, str | int | float | bool] | None = None,
    ) -> dict[str, Any]:
        """发送一次经过 App 动态签名的上游请求。"""

        normalized_method = method.upper()
        url = self._build_url(path, query)
        # accept-encoding 由 httpx 管理；将其纳入签名可能导致签名内容与实际发送不一致。
        headers = {
            key: value
            for key, value in self.session.session_headers.items()
            if key.lower() != "accept-encoding"
        }

        content: bytes | None = None
        if body is not None:
            # MD5 必须基于即将发送的同一份字节，不能在签名后重新 json.dumps。
            content = compact_json(body)
            headers["content-type"] = "application/json; charset=utf-8"
            headers["x-ss-stub"] = hashlib.md5(content).hexdigest().upper()

        # 传入副本，避免 Signer 客户端意外修改本地待发送请求头。
        signed_headers = await self.signer.sign(url, dict(headers))
        headers.update(signed_headers)

        try:
            # 这里使用前面签名时的原始 URL、headers 和 content，不再重建请求。
            response = await self.client.request(
                normalized_method,
                url,
                headers=headers,
                content=content,
            )
        except httpx.TimeoutException:
            raise UpstreamTimeoutError() from None
        except httpx.RequestError:
            raise UpstreamTransportError() from None

        if not response.is_success:
            raise UpstreamHttpError(response.status_code)

        try:
            payload = response.json()
        except ValueError:
            raise UpstreamInvalidResponseError() from None
        if not isinstance(payload, dict):
            raise UpstreamInvalidResponseError()

        self._classify(payload)
        return payload

    def _build_url(
        self,
        path: str,
        query: Mapping[str, str | int | float | bool] | None,
    ) -> str:
        """合并设备参数、接口参数与毫秒时间票据，生成最终签名 URL。"""

        if not path.startswith("/") or path.startswith("//"):
            raise ValueError("path must be an absolute URL path")
        params: dict[str, str | int | float | bool] = dict(self.session.base_query)
        if query:
            params.update(query)
        params["_rticket"] = self.clock_ms()
        return f"https://{self.session.api_host}{path}?{urlencode(params)}"

    @staticmethod
    def _classify(payload: Mapping[str, Any]) -> None:
        """把上游业务错误分类为稳定的本地异常。"""

        code = payload.get("code")
        if code in (None, 0, 200, "0", "200"):
            return

        # 不把 message 放入异常，只用它辅助识别登录过期和风控。
        message_parts = [
            payload.get("message"),
            payload.get("msg"),
        ]
        base_response = payload.get("BaseResp")
        if isinstance(base_response, Mapping):
            message_parts.append(base_response.get("StatusMessage"))
        message = " ".join(
            str(part).lower() for part in message_parts if part is not None
        )

        if code in (401, 403, 8, 1001, "401", "403", "8", "1001") or any(
            marker in message
            for marker in ("token", "login", "session", "登录", "未登录", "凭证", "过期")
        ):
            raise SessionExpiredError()

        if code in (
            110001,
            100001,
            100002,
            "110001",
            "100001",
            "100002",
        ) or any(
            marker in message
            for marker in (
                "verify",
                "captcha",
                "risk",
                "rate limit",
                "too many",
                "验证",
                "频繁",
                "稍后",
            )
        ):
            raise RiskControlledError()

        raise UpstreamInvalidResponseError()
