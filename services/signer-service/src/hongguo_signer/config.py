from pathlib import Path
import re

import frida
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


SERVICE_ROOT = Path(__file__).resolve().parents[2]
ANDROID_ABSOLUTE_PATH_PATTERN = re.compile(
    r"/(?:[A-Za-z0-9._-]+/)*[A-Za-z0-9._-]+"
)


def validate_android_absolute_path(value: str) -> str:
    if (
        ANDROID_ABSOLUTE_PATH_PATTERN.fullmatch(value) is None
        or any(part in {".", ".."} for part in value.split("/"))
    ):
        raise ValueError("must be a safe absolute Android path")
    return value


class SignerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="HONGGUO_SIGNER_", extra="ignore")

    mumu_home: Path = Path(r"D:\MuMu Player 12")
    vmindex: int = 0
    package_name: str = "com.phoenix.read"
    frida_host: str = "127.0.0.1"
    frida_port: int = 27042
    frida_server_path: Path = (
        SERVICE_ROOT
        / "bin"
        / f"frida-server-{frida.__version__}-android-x86_64"
    )
    frida_remote_path: str = "/data/local/tmp/frida-server"
    watchdog_interval: float = 15.0
    service_token: str = "local-development"

    @field_validator("frida_remote_path")
    @classmethod
    def validate_frida_remote_path(cls, value: str) -> str:
        return validate_android_absolute_path(value)

    @field_validator("service_token")
    @classmethod
    def validate_service_token(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("service_token must not be blank")
        return value

    @property
    def mumu_cli(self) -> Path:
        return self.mumu_home / "nx_main" / "mumu-cli.exe"

    @property
    def adb(self) -> Path:
        return self.mumu_home / "shell" / "adb.exe"
