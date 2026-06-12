"""会话快照的安全持久化。

会话文件可能包含设备标识、cookie 和 token，因此保存过程采用同目录临时文件、
``fsync`` 和原子替换，避免进程中断后留下半份 JSON。
"""

import os
import tempfile
from pathlib import Path

from hongguo_contracts.signer import SessionSnapshot
from pydantic import ValidationError


class SessionStoreError(Exception):
    """Base error for session persistence failures."""


class SessionFileMissingError(SessionStoreError):
    """Raised when no captured session file exists."""


class InvalidSessionFileError(SessionStoreError):
    """Raised when a captured session file cannot be validated."""


class SessionStore:
    """负责 ``SessionSnapshot`` 的原子保存和严格加载。"""

    def __init__(self, path: Path) -> None:
        self.path = path

    def save(self, snapshot: SessionSnapshot) -> None:
        """将已验证的会话模型原子写入磁盘。"""

        if not isinstance(snapshot, SessionSnapshot):
            raise TypeError("snapshot must be a SessionSnapshot")

        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = snapshot.model_dump_json(indent=2)
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                suffix=".tmp",
                delete=False,
            ) as temporary:
                # 临时文件与目标文件位于同一目录，保证 os.replace 可原子完成。
                temporary_path = Path(temporary.name)
                temporary.write(payload)
                temporary.flush()
                os.fsync(temporary.fileno())
            self._restrict_permissions(temporary_path)
            os.replace(temporary_path, self.path)
            temporary_path = None
            self._restrict_permissions(self.path)
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    def load(self) -> SessionSnapshot:
        """读取并严格校验会话文件。"""

        try:
            payload = self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            raise SessionFileMissingError(
                f"session file does not exist: {self.path}"
            ) from None
        except (OSError, UnicodeError) as error:
            raise InvalidSessionFileError(
                f"could not read session file {self.path}: {error}"
            ) from None

        try:
            # strict=True 禁止将错误类型静默转换成合法字段。
            return SessionSnapshot.model_validate_json(payload, strict=True)
        except ValidationError as error:
            if any(item["type"] == "json_invalid" for item in error.errors()):
                raise InvalidSessionFileError(
                    f"session file contains invalid JSON: {self.path}"
                ) from None
            raise InvalidSessionFileError(
                f"session file contains an invalid session snapshot: {self.path}"
            ) from None

    @staticmethod
    def _restrict_permissions(path: Path) -> None:
        """尽可能将会话文件权限收紧为仅当前用户读写。"""

        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
