"""Signer Service 的异步 HTTP 客户端。

本模块是 API Server 与设备签名层之间唯一的直接通信边界。所有响应均通过共享
contracts 严格校验，且错误不会携带服务 token、签名 URL 或响应正文。
"""

from typing import TypeVar

import httpx
from hongguo_contracts import ErrorResponse
from hongguo_contracts.signer import SessionSnapshot, SignRequest, SignResponse
from pydantic import BaseModel, ValidationError


ResponseModel = TypeVar("ResponseModel", bound=BaseModel)


class SignerClientError(Exception):
    """Base error for signer service calls."""


class SignerTimeoutError(SignerClientError):
    """Raised when the signer service exceeds the configured timeout."""


class SignerTransportError(SignerClientError):
    """Raised when the signer service cannot be reached."""


class SignerResponseError(SignerClientError):
    """Raised when the signer violates its versioned response contract."""


class SignerServiceError(SignerClientError):
    """Raised when the signer returns a valid error response."""

    def __init__(self, status_code: int, code: str) -> None:
        self.status_code = status_code
        self.code = code
        super().__init__(f"signer service returned HTTP {status_code} ({code})")


class SignerClient:
    """调用 Signer Service 的版本化接口。"""

    def __init__(
        self,
        base_url: str,
        token: str,
        client: httpx.AsyncClient,
        *,
        timeout_seconds: float = 30.0,
    ) -> None:
        if not token.strip():
            raise ValueError("token must not be blank")
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.client = client
        self.timeout_seconds = timeout_seconds

    async def sign(self, url: str, headers: dict[str, str]) -> dict[str, str]:
        """请求 App 为最终 URL 和请求头生成动态安全头。"""

        request = SignRequest(url=url, headers=headers)
        response = await self._post(
            "/v1/sign",
            response_type=SignResponse,
            json=request.model_dump(mode="json"),
        )
        return response.headers

    async def capture_session(self, *, timeout_ms: int = 30_000) -> SessionSnapshot:
        """等待 Signer 捕获一次自然 App 请求并返回会话快照。"""

        if not 1 <= timeout_ms <= 60_000:
            raise ValueError("timeout_ms must be between 1 and 60000")
        return await self._post(
            "/v1/session/capture",
            response_type=SessionSnapshot,
            params={"timeout_ms": timeout_ms},
            timeout_seconds=max(self.timeout_seconds, timeout_ms / 1000 + 5),
        )

    async def _post(
        self,
        path: str,
        *,
        response_type: type[ResponseModel],
        json: object | None = None,
        params: dict[str, object] | None = None,
        timeout_seconds: float | None = None,
    ) -> ResponseModel:
        """执行认证 POST，并将结果解析为指定的严格 Pydantic 模型。"""

        try:
            response = await self.client.post(
                f"{self.base_url}{path}",
                headers={"Authorization": f"Bearer {self.token}"},
                json=json,
                params=params,
                timeout=timeout_seconds or self.timeout_seconds,
            )
        except httpx.TimeoutException:
            raise SignerTimeoutError("signer request timed out") from None
        except httpx.RequestError:
            raise SignerTransportError("could not reach signer service") from None

        if not response.is_success:
            # 错误响应同样必须遵守共享 ErrorResponse 协议。
            try:
                error = ErrorResponse.model_validate_json(
                    response.content,
                    strict=True,
                )
            except ValidationError:
                raise SignerResponseError(
                    "signer returned an invalid error response"
                ) from None
            raise SignerServiceError(response.status_code, error.code)

        try:
            # strict=True 可以尽早发现两个独立部署服务之间的协议漂移。
            return response_type.model_validate_json(response.content, strict=True)
        except ValidationError:
            raise SignerResponseError(
                "signer returned an invalid success response"
            ) from None
