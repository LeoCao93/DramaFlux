"""对外 HTTP API 的统一响应模型。"""

from typing import Any

from pydantic import BaseModel, ConfigDict


class ApiResponse(BaseModel):
    """成功响应外壳。

    ``data`` 保存具体业务模型；``request_id`` 用于问题定位；``cached`` 预留给
    缓存命中信息。错误响应由 ``main.py`` 中的异常处理器单独生成。
    """

    model_config = ConfigDict(extra="forbid")

    code: int = 200
    message: str = "success"
    data: Any
    cached: bool = False
    request_id: str
