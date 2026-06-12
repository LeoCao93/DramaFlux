"""API Server 的生产依赖组装入口。

该模块只负责创建对象并连接依赖，不包含具体业务逻辑。Uvicorn 默认导入本模块
底部的 ``app``。这种集中组装方式让路由、缓存、平台客户端和签名传输都能在测试
中被替换为 Fake 实现。
"""

from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from hongguo_api.cache import CachedHongguoService
from hongguo_api.config import ApiSettings
from hongguo_api.errors import SessionMissingError
from hongguo_api.main import create_app
from hongguo_api.session.storage import (
    InvalidSessionFileError,
    SessionFileMissingError,
    SessionStore,
)
from hongguo_api.signer.client import SignerClient
from hongguo_api.upstream.client import HongguoClient
from hongguo_api.upstream.transport import SignedTransport


class MissingSessionService:
    """会话缺失时使用的占位业务实现。

    让 API Server 在首次安装、会话过期或文件损坏时仍能启动并暴露健康接口；
    所有业务请求则统一返回 ``session_missing``，而不是在模块导入阶段崩溃。
    """

    async def _missing(self) -> object:
        raise SessionMissingError()

    async def search(self, query: str, cursor: str | None = None) -> object:
        return await self._missing()

    async def latest(
        self,
        genre: str,
        today_only: bool,
        cursor: str | None = None,
    ) -> object:
        return await self._missing()

    async def rank(self, board: str, cursor: str | None = None) -> object:
        return await self._missing()

    async def detail(self, series_id: str) -> object:
        return await self._missing()

    async def resolve_video(self, video_id: str, quality: str) -> object:
        return await self._missing()


def build_app(settings: ApiSettings | None = None) -> FastAPI:
    """根据配置组装完整 FastAPI 应用。"""

    configured = settings or ApiSettings()
    try:
        session = SessionStore(configured.session_file).load()
    except (SessionFileMissingError, InvalidSessionFileError):
        return create_app(MissingSessionService())

    # API Server 内所有出站请求共享连接池，减少 TCP/TLS 握手开销。
    http_client = httpx.AsyncClient(timeout=configured.timeout_seconds)

    # SignerClient 只通过版本化 HTTP 协议访问 Signer Service，不导入 Frida。
    signer = SignerClient(
        configured.signer_url,
        configured.signer_token,
        http_client,
        timeout_seconds=configured.timeout_seconds,
    )
    transport = SignedTransport(session, signer, http_client)

    # 最外层使用缓存装饰器；缓存未命中时才进入真正的 HongguoClient。
    service = CachedHongguoService(HongguoClient(transport))
    app = create_app(service)

    original_lifespan = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        """在 ASGI 应用退出时可靠关闭共享 HTTP 连接池。"""

        try:
            async with original_lifespan(application):
                yield
        finally:
            await http_client.aclose()

    app.router.lifespan_context = lifespan
    return app


app = build_app()
