import re
import subprocess
from pathlib import Path


ANDROID_PACKAGE_PATTERN = re.compile(
    r"[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+"
)


class AdbClient:
    def __init__(self, executable: Path, serial: str) -> None:
        self.executable = executable
        self.serial = serial

    def _invoke(self, args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(self.executable), *args],
            check=check,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )

    def _run(self, *args: str, check: bool = True) -> str:
        result = self._invoke(["-s", self.serial, *args], check=check)
        return result.stdout.strip()

    def connect(self) -> None:
        self._invoke(["connect", self.serial])

    def shell(self, command: str, *, check: bool = True) -> str:
        return self._run("shell", command, check=check)

    def push(self, local_path: Path, remote_path: str) -> None:
        self._run("push", str(local_path), remote_path)

    def forward(self, local: str, remote: str) -> None:
        self._run("forward", local, remote)

    def root_id(self) -> str:
        return self.shell("su -c id")

    def pidof(self, package_name: str) -> int | None:
        if ANDROID_PACKAGE_PATTERN.fullmatch(package_name) is None:
            raise ValueError(f"invalid Android package name: {package_name!r}")

        result = self._invoke(
            ["-s", self.serial, "shell", "pidof", package_name],
            check=False,
        )
        stdout = result.stdout.strip()
        stderr = result.stderr.strip()

        if result.returncode == 0:
            return int(stdout.split()[0]) if stdout else None
        if result.returncode == 1 and not stdout and not stderr:
            return None
        raise subprocess.CalledProcessError(
            result.returncode,
            result.args,
            output=result.stdout,
            stderr=result.stderr,
        )
