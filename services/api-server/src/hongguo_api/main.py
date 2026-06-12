"""FastAPI 应用工厂与统一异常映射。"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from hongguo_api.api.routes import HongguoService, build_router
from hongguo_api.errors import (
    RiskControlledError,
    SessionExpiredError,
    SessionMissingError,
    UpstreamHttpError,
    UpstreamInvalidResponseError,
    UpstreamTimeoutError,
    UpstreamTransportError,
)
from hongguo_api.parsers.detail import DetailNotFoundError, DetailParseError
from hongguo_api.parsers.search import CursorError
from hongguo_api.parsers.video import (
    EncryptedStreamError,
    VideoModelParseError,
    VideoNotFoundError,
)
from hongguo_api.signer.client import (
    SignerResponseError,
    SignerServiceError,
    SignerTimeoutError,
    SignerTransportError,
)


def create_app(service: HongguoService) -> FastAPI:
    """创建只依赖 ``HongguoService`` 协议的 FastAPI 应用。"""

    app = FastAPI(title="Hongguo Local API", version="1.0")
    app.include_router(build_router(service))

    def install_handler(
        error_type: type[Exception],
        status_code: int,
        code: str,
        message: str,
    ) -> None:
        """把内部异常转换成稳定且不泄漏敏感信息的 HTTP 错误。"""

        async def handler(request: Request, error: Exception) -> JSONResponse:
            # 不把原始异常文本返回给调用方，其中可能含上游地址或凭证。
            del error
            return JSONResponse(
                status_code=status_code,
                content={
                    "code": code,
                    "message": message,
                    "request_id": request.headers.get("x-request-id"),
                },
            )

        app.add_exception_handler(error_type, handler)  # type: ignore[arg-type]

    # 统一维护异常、HTTP 状态、机器错误码和公开消息之间的映射。
    mappings: list[tuple[type[Exception], int, str, str]] = [
        (SessionMissingError, 503, "session_missing", "Hongguo session is missing"),
        (SessionExpiredError, 401, "session_expired", "Hongguo session expired"),
        (
            SignerTimeoutError,
            503,
            "signer_unavailable",
            "Hongguo signer is unavailable",
        ),
        (
            SignerTransportError,
            503,
            "signer_unavailable",
            "Hongguo signer is unavailable",
        ),
        (
            SignerResponseError,
            502,
            "signer_invalid_response",
            "Hongguo signer returned invalid data",
        ),
        (
            SignerServiceError,
            503,
            "signer_unavailable",
            "Hongguo signer is unavailable",
        ),
        (RiskControlledError, 429, "risk_controlled", "Hongguo risk control triggered"),
        (UpstreamTimeoutError, 504, "upstream_timeout", "Hongguo upstream timed out"),
        (UpstreamTransportError, 502, "upstream_unavailable", "Hongguo upstream unavailable"),
        (
            UpstreamInvalidResponseError,
            502,
            "upstream_invalid_response",
            "Hongguo upstream returned invalid data",
        ),
        (UpstreamHttpError, 502, "upstream_http_error", "Hongguo upstream failed"),
        (CursorError, 400, "invalid_cursor", "cursor is invalid"),
        (DetailNotFoundError, 404, "book_not_found", "book was not found"),
        (VideoNotFoundError, 404, "video_not_found", "video was not found"),
        (
            DetailParseError,
            502,
            "upstream_invalid_response",
            "Hongguo upstream returned invalid data",
        ),
        (
            VideoModelParseError,
            502,
            "upstream_invalid_response",
            "Hongguo upstream returned invalid data",
        ),
        (
            EncryptedStreamError,
            422,
            "encrypted_stream_unsupported",
            "encrypted stream is not supported",
        ),
    ]
    for mapping in mappings:
        install_handler(*mapping)

    return app
