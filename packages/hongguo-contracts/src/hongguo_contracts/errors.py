from pydantic import BaseModel, ConfigDict


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    code: str
    message: str
    request_id: str | None = None
