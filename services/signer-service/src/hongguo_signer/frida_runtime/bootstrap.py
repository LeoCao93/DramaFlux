import re
import shlex
import time
from pathlib import Path

import frida

from hongguo_signer.device.adb import AdbClient
from hongguo_signer.config import validate_android_absolute_path


FRIDA_VERSION_PATTERN = re.compile(r"frida-server[-_](\d+\.\d+\.\d+)")


def local_frida_server_version(local_binary: Path) -> str:
    match = FRIDA_VERSION_PATTERN.search(local_binary.name)
    if match is None:
        raise ValueError(
            "local frida-server filename must include its semantic version"
        )
    return match.group(1)


def _root_shell(
    adb: AdbClient,
    command: str,
    *,
    check: bool = True,
) -> str:
    return adb.shell(f"su -c {shlex.quote(command)}", check=check)


def _wait_for_pid(adb: AdbClient, attempts: int = 20) -> str:
    for _ in range(attempts):
        pid = adb.shell("pidof frida-server", check=False).strip()
        if pid:
            return pid.split()[0]
        time.sleep(0.05)
    raise RuntimeError("configured frida-server did not start")


def proc_net_listener_inodes(source: str, port: int) -> set[str]:
    inodes: set[str] = set()
    for line in source.splitlines():
        fields = line.split()
        if len(fields) < 10 or ":" not in fields[1]:
            continue
        _, port_text = fields[1].rsplit(":", 1)
        try:
            local_port = int(port_text, 16)
        except ValueError:
            continue
        inode = fields[9]
        if (
            local_port == port
            and fields[3].upper() == "0A"
            and inode.isdigit()
        ):
            inodes.add(inode)
    return inodes


def proc_net_has_listener(source: str, port: int) -> bool:
    return bool(proc_net_listener_inodes(source, port))


def proc_fd_socket_inodes(source: str) -> set[str]:
    inodes: set[str] = set()
    for line in source.splitlines():
        match = re.fullmatch(r"socket:\[(\d+)\]", line.strip())
        if match is not None:
            inodes.add(match.group(1))
    return inodes


def _pid_is_alive(adb: AdbClient, pid: str) -> bool:
    result = _root_shell(
        adb,
        f"kill -0 {pid} 2>/dev/null && printf alive",
        check=False,
    )
    return result.strip() == "alive"


def _wait_for_listener(
    adb: AdbClient,
    pid: str,
    port: int,
    attempts: int = 20,
) -> None:
    sockets_command = "cat /proc/net/tcp /proc/net/tcp6 2>/dev/null"
    fd_command = (
        f"for fd in /proc/{pid}/fd/*; do "
        'readlink "$fd" 2>/dev/null || true; '
        "done"
    )
    for _ in range(attempts):
        if not _pid_is_alive(adb, pid):
            raise RuntimeError("configured frida-server process exited")
        listener_inodes = proc_net_listener_inodes(
            _root_shell(adb, sockets_command, check=False),
            port,
        )
        pid_socket_inodes = proc_fd_socket_inodes(
            _root_shell(adb, fd_command, check=False)
        )
        if listener_inodes & pid_socket_inodes:
            return
        time.sleep(0.05)
    raise RuntimeError("configured frida-server is not ready")


def ensure_frida_server(
    adb: AdbClient,
    local_binary: Path,
    remote_path: str,
    *,
    port: int = 27042,
    python_frida_version: str = frida.__version__,
) -> None:
    if not local_binary.is_file():
        raise FileNotFoundError(f"local frida-server not found: {local_binary}")
    if not 1 <= port <= 65535:
        raise ValueError("Frida port must be between 1 and 65535")
    try:
        validate_android_absolute_path(remote_path)
    except ValueError as error:
        raise ValueError(f"invalid Frida remote path: {remote_path!r}") from error

    local_version = local_frida_server_version(local_binary)
    if local_version != python_frida_version:
        raise ValueError(
            f"local frida-server {local_version} does not match "
            f"Python frida {python_frida_version}"
        )

    _root_shell(adb, "pkill -x frida-server", check=False)

    quoted_remote_path = shlex.quote(remote_path)
    remote_exists = _root_shell(
        adb,
        f"test -f {quoted_remote_path} && printf present",
        check=False,
    ).strip() == "present"
    remote_version = ""
    if remote_exists:
        remote_version = _root_shell(
            adb,
            f"{quoted_remote_path} --version",
            check=False,
        ).strip()
    if not remote_exists or remote_version != python_frida_version:
        adb.push(local_binary, remote_path)
    _root_shell(adb, f"chmod 755 {quoted_remote_path}")
    _root_shell(
        adb,
        (
            f"nohup {quoted_remote_path} -l 0.0.0.0:{port} "
            ">/data/local/tmp/frida.log 2>&1 &"
        )
    )

    running_pid = _wait_for_pid(adb)
    if not running_pid.isdigit():
        raise RuntimeError("frida-server returned an invalid process id")
    running_path = _root_shell(
        adb,
        f"readlink -f /proc/{running_pid}/exe",
        check=False,
    ).strip()
    if running_path != remote_path:
        raise RuntimeError("running process is not the configured remote binary")
    running_version = _root_shell(
        adb,
        f"{quoted_remote_path} --version",
        check=False,
    ).strip()
    if running_version != python_frida_version:
        raise RuntimeError("running frida-server version does not match Python frida")
    _wait_for_listener(adb, running_pid, port)
    endpoint = f"tcp:{port}"
    adb.forward(endpoint, endpoint)
