import secrets
import threading
from contextlib import contextmanager
from collections.abc import Iterator
from datetime import datetime, timezone
from typing import Any, Protocol
from urllib.parse import parse_qsl, urlsplit

from fastapi import Depends, FastAPI, Header, Query
from fastapi.responses import JSONResponse
from hongguo_contracts import ErrorResponse
from hongguo_contracts.signer import SessionSnapshot, SignRequest, SignResponse

from hongguo_signer.frida_runtime.manager import FridaRuntimeBusyError
from hongguo_signer.security import filter_session_headers

ALLOWED_SESSION_QUERY_FIELDS = frozenset(
    {
        "iid",
        "device_id",
        "cdid",
        "klink_egdi",
        "aid",
        "app_name",
        "version_code",
        "version_name",
        "channel",
        "device_platform",
        "device_type",
        "os_version",
    }
)


class Runtime(Protocol):
    @property
    def pid(self) -> int: ...

    def health(self) -> bool: ...

    def sign(self, url: str, headers: dict[str, str]) -> dict[str, str]: ...

    def capture_session(self, timeout_ms: int) -> dict[str, Any]: ...

    def reconnect(self) -> None: ...


class ApiError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        *,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.headers = headers


def _runtime_error(error: Exception) -> ApiError:
    if isinstance(error, FridaRuntimeBusyError):
        return ApiError(409, "signer_busy", "signer is busy")
    if isinstance(error, TimeoutError):
        return ApiError(504, "signer_timeout", "signer operation timed out")
    return ApiError(503, "signer_unavailable", "signer is unavailable")


def create_app(runtime: Runtime, service_token: str) -> FastAPI:
    if not service_token.strip():
        raise ValueError("service_token must not be blank")

    app = FastAPI(title="Hongguo Signer Service", version="1.0")
    operation_lock = threading.Lock()

    @app.middleware("http")
    async def security_headers(request: Any, call_next: Any) -> Any:
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @app.exception_handler(ApiError)
    def handle_api_error(request: Any, error: ApiError) -> JSONResponse:
        body = ErrorResponse(
            code=error.code,
            message=error.message,
            request_id=None,
        )
        return JSONResponse(
            status_code=error.status_code,
            content=body.model_dump(),
            headers=error.headers,
        )

    def authorize(authorization: str | None = Header(default=None)) -> None:
        scheme, separator, supplied_token = (authorization or "").partition(" ")
        valid_scheme = secrets.compare_digest(scheme.lower(), "bearer")
        valid_token = secrets.compare_digest(supplied_token, service_token)
        if separator != " " or not valid_scheme or not valid_token:
            raise ApiError(
                401,
                "unauthorized",
                "invalid service token",
                headers={"WWW-Authenticate": "Bearer"},
            )

    @contextmanager
    def operation_slot() -> Iterator[None]:
        if not operation_lock.acquire(blocking=False):
            raise ApiError(409, "signer_busy", "signer is busy")
        try:
            yield
        finally:
            operation_lock.release()

    @app.get("/v1/health")
    def health() -> dict[str, object]:
        try:
            ready = runtime.health()
        except Exception:
            ready = False

        app_pid: int | None = None
        if ready:
            try:
                app_pid = runtime.pid
            except Exception:
                ready = False
        return {"ready": ready, "app_pid": app_pid}

    @app.post(
        "/v1/sign",
        response_model=SignResponse,
        dependencies=[Depends(authorize)],
    )
    def sign(request: SignRequest) -> SignResponse:
        try:
            with operation_slot():
                headers = runtime.sign(str(request.url), request.headers)
                app_pid = runtime.pid
        except ApiError:
            raise
        except Exception as error:
            raise _runtime_error(error) from None
        return SignResponse(
            headers=headers,
            app_pid=app_pid,
            signed_at=datetime.now(timezone.utc),
        )

    @app.post(
        "/v1/session/capture",
        response_model=SessionSnapshot,
        dependencies=[Depends(authorize)],
    )
    def capture_session(
        timeout_ms: int = Query(default=30000, ge=1, le=60000),
    ) -> SessionSnapshot:
        try:
            with operation_slot():
                captured = runtime.capture_session(timeout_ms)
                parsed = urlsplit(str(captured["url"]))
                hostname = parsed.hostname
                if (
                    parsed.scheme.lower() != "https"
                    or hostname is None
                    or (
                        hostname.lower() != "fqnovel.com"
                        and not hostname.lower().endswith(".fqnovel.com")
                    )
                    or parsed.username is not None
                    or parsed.password is not None
                ):
                    raise ValueError("captured request is not a trusted fqnovel URL")
                headers = filter_session_headers(
                    dict(captured.get("headers", {}))
                )
        except ApiError:
            raise
        except Exception as error:
            raise _runtime_error(error) from None
        return SessionSnapshot(
            api_host=hostname.lower(),
            base_query={
                key.lower(): value
                for key, value in parse_qsl(parsed.query, keep_blank_values=True)
                if key.lower() in ALLOWED_SESSION_QUERY_FIELDS
            },
            session_headers=headers,
            captured_at=datetime.now(timezone.utc),
        )

    @app.post(
        "/v1/admin/reconnect",
        dependencies=[Depends(authorize)],
    )
    def reconnect() -> dict[str, bool]:
        try:
            with operation_slot():
                runtime.reconnect()
        except ApiError:
            raise
        except Exception as error:
            raise _runtime_error(error) from None
        return {"reconnected": True}

    return app
