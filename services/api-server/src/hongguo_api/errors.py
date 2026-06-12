"""API Server 内部使用的安全错误类型。

这些异常只携带稳定、脱敏的信息。上游响应正文、cookie、token 和完整签名 URL
不会进入异常文本，从而避免 FastAPI 日志或公开错误响应泄漏敏感数据。
"""


class HongguoApiError(RuntimeError):
    """所有已脱敏业务错误的基类。"""


class SessionMissingError(HongguoApiError):
    def __init__(self) -> None:
        super().__init__("Hongguo session is missing")


class SessionExpiredError(HongguoApiError):
    def __init__(self) -> None:
        super().__init__("Hongguo session expired")


class RiskControlledError(HongguoApiError):
    def __init__(self) -> None:
        super().__init__("Hongguo upstream risk control triggered")


class UpstreamTimeoutError(HongguoApiError):
    def __init__(self) -> None:
        super().__init__("Hongguo upstream request timed out")


class UpstreamTransportError(HongguoApiError):
    def __init__(self) -> None:
        super().__init__("Could not reach Hongguo upstream")


class UpstreamInvalidResponseError(HongguoApiError):
    def __init__(self) -> None:
        super().__init__("Hongguo upstream returned an invalid response")


class UpstreamHttpError(HongguoApiError):
    """上游返回非成功 HTTP 状态码。"""

    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        super().__init__(f"Hongguo upstream returned HTTP {status_code}")
