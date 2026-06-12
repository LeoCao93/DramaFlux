"""API Server 的环境变量配置。

所有配置都使用 ``HONGGUO_API_`` 前缀读取，既便于本地 PowerShell 启动，
也方便未来将 API Server 与 Signer Service 分开部署。
"""

from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ApiSettings(BaseSettings):
    """API Server 启动时需要的外部配置。"""

    # 忽略未知环境变量，避免同一台机器上的 Signer 配置影响 API Server。
    model_config = SettingsConfigDict(env_prefix="HONGGUO_API_", extra="ignore")

    signer_url: str = "http://127.0.0.1:18001"
    signer_token: str = "local-development"
    session_file: Path = Path(".local/session.json")
    timeout_seconds: float = 30.0

    @field_validator("signer_token")
    @classmethod
    def validate_signer_token(cls, value: str) -> str:
        """拒绝空 token，防止服务间认证被意外关闭。"""

        if not value.strip():
            raise ValueError("signer_token must not be blank")
        return value
