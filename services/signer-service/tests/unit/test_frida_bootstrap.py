from pathlib import Path
import re

import pytest

from hongguo_signer.frida_runtime import bootstrap
from hongguo_signer.frida_runtime.bootstrap import ensure_frida_server


PROC_NET_HEADER = (
    "  sl  local_address rem_address   st tx_queue rx_queue tr tm->when "
    "retrnsmt   uid  timeout inode"
)


def proc_net_row(
    local_address: str,
    state: str,
    inode: str = "1",
) -> str:
    return (
        f"   0: {local_address} 00000000:0000 {state} "
        f"00000000:00000000 00:00000000 00000000 0 0 {inode}"
    )


def test_proc_net_listener_requires_matching_port_and_listen_state() -> None:
    source = "\n".join(
        [
            PROC_NET_HEADER,
            proc_net_row("0100007F:6982", "01"),
            proc_net_row("00000000:6983", "0A"),
        ]
    )

    assert bootstrap.proc_net_has_listener(source, 27010) is False


def test_proc_net_listener_accepts_matching_ipv6_listen_row() -> None:
    source = "\n".join(
        [
            PROC_NET_HEADER,
            proc_net_row("00000000000000000000000000000000:69A2", "0A"),
        ]
    )

    assert bootstrap.proc_net_has_listener(source, 27042) is True


def test_proc_net_listener_inodes_returns_matching_tcp_and_tcp6_inodes() -> None:
    source = "\n".join(
        [
            PROC_NET_HEADER,
            proc_net_row("00000000:69A2", "0A", "101"),
            proc_net_row(
                "00000000000000000000000000000000:69A2",
                "0A",
                "202",
            ),
            proc_net_row("00000000:69A2", "01", "303"),
            proc_net_row("00000000:69A3", "0A", "404"),
        ]
    )

    assert bootstrap.proc_net_listener_inodes(source, 27042) == {"101", "202"}


def test_proc_net_listener_inodes_ignores_malformed_rows() -> None:
    source = "\n".join(
        [
            PROC_NET_HEADER,
            "",
            "malformed",
            "0: missing-port 00000000:0000 0A",
            proc_net_row("00000000:ZZZZ", "0A", "not-an-inode"),
            proc_net_row("00000000:69A2", "0A", "invalid"),
        ]
    )

    assert bootstrap.proc_net_listener_inodes(source, 27042) == set()


def test_proc_fd_socket_inodes_extracts_socket_targets_safely() -> None:
    source = "\n".join(
        [
            "socket:[101]",
            "/dev/null",
            "socket:[202]",
            "socket:[]",
            "socket:[invalid]",
            "malformed socket:[303] suffix",
        ]
    )

    assert bootstrap.proc_fd_socket_inodes(source) == {"101", "202"}


class FakeAdb:
    def __init__(
        self,
        *,
        remote_exists: bool = False,
        remote_version: str = "",
        started_pid: str = "456",
        running_path: str = "/data/local/tmp/frida-server",
        ready: bool = True,
        listener_inode: str = "101",
        pid_socket_inodes: set[str] | None = None,
    ) -> None:
        self.remote_exists = remote_exists
        self.remote_version = remote_version
        self.started_pid = started_pid
        self.running_path = running_path
        self.ready = ready
        self.listener_inode = listener_inode
        self.pid_socket_inodes = (
            {listener_inode}
            if pid_socket_inodes is None
            else pid_socket_inodes
        )
        self.events: list[object] = []
        self.started = False
        self.listen_port = 27042

    def shell(self, command: str, *, check: bool = True) -> str:
        self.events.append(("shell", command, check))
        if "test -f" in command:
            return "present" if self.remote_exists else ""
        if "--version" in command:
            return self.remote_version
        if "pkill" in command:
            self.started = False
            return ""
        if "nohup" in command:
            self.started = True
            match = re.search(r"0\.0\.0\.0:(\d+)", command)
            assert match is not None
            self.listen_port = int(match.group(1))
            return ""
        if command == "pidof frida-server":
            return self.started_pid if self.started else ""
        if "/fd/" in command:
            return "\n".join(
                f"socket:[{inode}]"
                for inode in sorted(self.pid_socket_inodes)
            )
        if "readlink" in command:
            return self.running_path
        if "kill -0" in command:
            return "alive" if self.started else ""
        if "/proc/net/tcp" in command:
            if self.ready:
                return "\n".join(
                    [
                        PROC_NET_HEADER,
                        proc_net_row(
                            f"00000000:{self.listen_port:04X}",
                            "0A",
                            self.listener_inode,
                        ),
                    ]
                )
            return PROC_NET_HEADER
        return ""

    def push(self, local_path: Path, remote_path: str) -> None:
        self.events.append(("push", local_path, remote_path))
        self.remote_exists = True
        self.remote_version = local_path.name.split("-")[2]

    def forward(self, local: str, remote: str) -> None:
        self.events.append(("forward", local, remote))


def test_bootstrap_rejects_missing_local_server(tmp_path: Path) -> None:
    adb = FakeAdb()

    with pytest.raises(FileNotFoundError, match="local frida-server"):
        ensure_frida_server(
            adb,
            tmp_path / "frida-server-17.11.0-android-x86_64",
            "/data/local/tmp/frida-server",
            python_frida_version="17.11.0",
        )

    assert adb.events == []


def test_bootstrap_rejects_local_python_version_mismatch(tmp_path: Path) -> None:
    binary = tmp_path / "frida-server-16.7.0-android-x86_64"
    binary.write_bytes(b"server")
    adb = FakeAdb()

    with pytest.raises(ValueError, match="does not match Python frida 17.11.0"):
        ensure_frida_server(
            adb,
            binary,
            "/data/local/tmp/frida-server",
            python_frida_version="17.11.0",
        )

    assert adb.events == []


def test_bootstrap_kills_stale_process_and_starts_configured_binary(
    tmp_path: Path,
) -> None:
    binary = tmp_path / "frida-server-17.11.0-android-x86_64"
    binary.write_bytes(b"server")
    adb = FakeAdb(remote_exists=True, remote_version="17.11.0")

    ensure_frida_server(
        adb,
        binary,
        "/data/local/tmp/frida-server",
        port=28042,
        python_frida_version="17.11.0",
    )

    assert not any(event[0] == "push" for event in adb.events)
    commands = [event[1] for event in adb.events if event[0] == "shell"]
    assert "pkill -x frida-server" in commands[0]
    assert any("nohup /data/local/tmp/frida-server" in command for command in commands)
    assert any("readlink" in command for command in commands)
    assert any("/proc/net/tcp" in command for command in commands)
    assert adb.events[-1] == ("forward", "tcp:28042", "tcp:28042")


def test_bootstrap_pushes_chmods_and_starts_missing_server_as_root(
    tmp_path: Path,
) -> None:
    binary = tmp_path / "frida-server-17.11.0-android-x86_64"
    binary.write_bytes(b"server")
    adb = FakeAdb(remote_version="17.11.0")

    ensure_frida_server(
        adb,
        binary,
        "/data/local/tmp/frida-server",
        python_frida_version="17.11.0",
    )

    assert ("push", binary, "/data/local/tmp/frida-server") in adb.events
    commands = [
        event[1]
        for event in adb.events
        if event[0] == "shell"
    ]
    assert any("chmod 755 /data/local/tmp/frida-server" in command for command in commands)
    assert any(
        command.startswith(
            "su -c 'nohup /data/local/tmp/frida-server "
            "-l 0.0.0.0:27042"
        )
        for command in commands
    )
    assert adb.events[-1] == ("forward", "tcp:27042", "tcp:27042")


def test_bootstrap_replaces_running_server_with_wrong_version(
    tmp_path: Path,
) -> None:
    binary = tmp_path / "frida-server-17.11.0-android-x86_64"
    binary.write_bytes(b"server")
    adb = FakeAdb(remote_exists=True, remote_version="16.7.0")

    ensure_frida_server(
        adb,
        binary,
        "/data/local/tmp/frida-server",
        python_frida_version="17.11.0",
    )

    commands = [
        event[1]
        for event in adb.events
        if event[0] == "shell"
    ]
    assert any("pkill" in command for command in commands)
    assert ("push", binary, "/data/local/tmp/frida-server") in adb.events
    assert any("nohup" in command for command in commands)


def test_bootstrap_does_not_reuse_arbitrary_matching_pid(
    tmp_path: Path,
) -> None:
    binary = tmp_path / "frida-server-17.11.0-android-x86_64"
    binary.write_bytes(b"server")
    adb = FakeAdb(
        remote_exists=True,
        remote_version="17.11.0",
        started_pid="999",
        running_path="/data/local/tmp/other/frida-server",
    )

    with pytest.raises(RuntimeError, match="configured remote binary"):
        ensure_frida_server(
            adb,
            binary,
            "/data/local/tmp/frida-server",
            python_frida_version="17.11.0",
        )

    assert not any(event[0] == "forward" for event in adb.events)


def test_bootstrap_requires_remote_listener_readiness(
    tmp_path: Path,
) -> None:
    binary = tmp_path / "frida-server-17.11.0-android-x86_64"
    binary.write_bytes(b"server")
    adb = FakeAdb(
        remote_exists=True,
        remote_version="17.11.0",
        ready=False,
    )

    with pytest.raises(RuntimeError, match="ready"):
        ensure_frida_server(
            adb,
            binary,
            "/data/local/tmp/frida-server",
            python_frida_version="17.11.0",
        )

    assert not any(event[0] == "forward" for event in adb.events)


def test_bootstrap_rejects_listener_owned_by_unrelated_process(
    tmp_path: Path,
) -> None:
    binary = tmp_path / "frida-server-17.11.0-android-x86_64"
    binary.write_bytes(b"server")
    adb = FakeAdb(
        remote_exists=True,
        remote_version="17.11.0",
        listener_inode="101",
        pid_socket_inodes={"202"},
    )

    with pytest.raises(RuntimeError, match="ready"):
        ensure_frida_server(
            adb,
            binary,
            "/data/local/tmp/frida-server",
            python_frida_version="17.11.0",
        )

    assert not any(event[0] == "forward" for event in adb.events)


def test_bootstrap_accepts_listener_inode_owned_by_exact_pid(
    tmp_path: Path,
) -> None:
    binary = tmp_path / "frida-server-17.11.0-android-x86_64"
    binary.write_bytes(b"server")
    adb = FakeAdb(
        remote_exists=True,
        remote_version="17.11.0",
        listener_inode="101",
        pid_socket_inodes={"101", "202"},
    )

    ensure_frida_server(
        adb,
        binary,
        "/data/local/tmp/frida-server",
        python_frida_version="17.11.0",
    )

    assert adb.events[-1] == ("forward", "tcp:27042", "tcp:27042")


@pytest.mark.parametrize(
    "remote_path",
    [
        "data/local/tmp/frida-server",
        "/data/local/tmp/frida-server;id",
        "/data/local/tmp/frida server",
    ],
)
def test_bootstrap_rejects_unsafe_remote_path_before_adb(
    tmp_path: Path,
    remote_path: str,
) -> None:
    binary = tmp_path / "frida-server-17.11.0-android-x86_64"
    binary.write_bytes(b"server")
    adb = FakeAdb()

    with pytest.raises(ValueError, match="remote path"):
        ensure_frida_server(
            adb,
            binary,
            remote_path,
            python_frida_version="17.11.0",
        )

    assert adb.events == []
