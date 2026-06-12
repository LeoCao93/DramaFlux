from datetime import datetime

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field


class SignRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    url: AnyHttpUrl
    headers: dict[str, str] = Field(default_factory=dict)


class SignResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    headers: dict[str, str]
    app_pid: int
    signed_at: datetime


class SessionSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    api_host: str
    base_query: dict[str, str]
    session_headers: dict[str, str]
    captured_at: datetime
