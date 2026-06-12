import json
import subprocess
from pathlib import Path

import pytest
from pydantic import ValidationError

from hongguo_signer.config import SignerSettings
from hongguo_signer.device.adb import AdbClient
from hongguo_signer.device.manager import DeviceManager
from hongguo_signer.device.mumu_cli import MuMuInstance, parse_instance


def completed(stdout: str = "", stderr: str = "", returncode: int = 0) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess([], returncode, stdout=stdout, stderr=stderr)


def test_signer_settings_use_verified_local_defaults() -> None:
    settings = SignerSettings()

    assert settings.mumu_home == Path(r"D:\MuMu Player 12")
    assert settings.vmindex == 0
    assert settings.package_name == "com.phoenix.read"
    assert settings.mumu_cli == Path(r"D:\MuMu Player 12\nx_main\mumu-cli.exe")
    assert settings.adb == Path(r"D:\MuMu Player 12\shell\adb.exe")
    assert settings.frida_server_path.name.startswith("frida-server-")
    assert settings.watchdog_interval == 15.0


@pytest.mark.parametrize(
    "remote_path",
    [
        "data/local/tmp/frida-server",
        "/data/local/tmp/../frida-server",
        "/data/local/tmp/frida server",
        "/data/local/tmp/frida-server;id",
        "/data/local/tmp/frida-server$(id)",
        "/data//local/tmp/frida-server",
    ],
)
def test_signer_settings_reject_unsafe_frida_remote_path(
    remote_path: str,
) -> None:
    with pytest.raises(ValidationError, match="frida_remote_path"):
        SignerSettings(frida_remote_path=remote_path)


def test_signer_settings_reject_hostile_frida_remote_path_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "HONGGUO_SIGNER_FRIDA_REMOTE_PATH",
        "/data/local/tmp/frida-server;id",
    )

    with pytest.raises(ValidationError, match="frida_remote_path"):
        SignerSettings()


@pytest.mark.parametrize("service_token", ["", " ", "\t\r\n"])
def test_signer_settings_reject_blank_service_token(service_token: str) -> None:
    with pytest.raises(ValidationError, match="service_token"):
        SignerSettings(service_token=service_token)


def test_parse_mumu_instance() -> None:
    raw = json.dumps(
        {
            "index": "0",
            "adb_host_ip": "127.0.0.1",
            "adb_port": 16384,
            "player_state": "start_finished",
            "is_process_started": True,
        }
    )

    instance = parse_instance(raw)

    assert instance == MuMuInstance(
        index=0,
        adb_host="127.0.0.1",
        adb_port=16384,
        player_state="start_finished",
        process_started=True,
    )


@pytest.mark.parametrize("value", ["false", "true", "", None])
def test_parse_mumu_instance_rejects_non_boolean_process_state(value: object) -> None:
    raw = json.dumps(
        {
            "index": "0",
            "adb_host_ip": "127.0.0.1",
            "adb_port": 16384,
            "player_state": "start_finished",
            "is_process_started": value,
        }
    )

    with pytest.raises(ValueError, match="is_process_started"):
        parse_instance(raw)


def test_instance_serial_uses_discovered_endpoint() -> None:
    instance = MuMuInstance(0, "127.0.0.1", 16384, "start_finished", True)

    assert instance.adb_serial == "127.0.0.1:16384"


def test_adb_connect_does_not_include_device_selector(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        calls.append(command)
        return completed("connected to 127.0.0.1:16384")

    monkeypatch.setattr(subprocess, "run", fake_run)
    client = AdbClient(Path("adb.exe"), "127.0.0.1:16384")

    client.connect()

    assert calls == [["adb.exe", "connect", "127.0.0.1:16384"]]


def test_adb_operations_target_discovered_serial(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        calls.append(command)
        return completed("ok")

    monkeypatch.setattr(subprocess, "run", fake_run)
    client = AdbClient(Path("adb.exe"), "127.0.0.1:16384")

    assert client.shell("getprop ro.build.version.release") == "ok"
    client.push(Path("frida-server"), "/data/local/tmp/frida-server")
    client.forward("tcp:27042", "tcp:27042")

    assert calls == [
        [
            "adb.exe",
            "-s",
            "127.0.0.1:16384",
            "shell",
            "getprop ro.build.version.release",
        ],
        [
            "adb.exe",
            "-s",
            "127.0.0.1:16384",
            "push",
            "frida-server",
            "/data/local/tmp/frida-server",
        ],
        [
            "adb.exe",
            "-s",
            "127.0.0.1:16384",
            "forward",
            "tcp:27042",
            "tcp:27042",
        ],
    ]


def test_pidof_returns_none_when_android_reports_no_process(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        return completed(returncode=1)

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert AdbClient(Path("adb.exe"), "127.0.0.1:16384").pidof("missing.app") is None


def test_pidof_returns_none_for_empty_successful_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        return completed()

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert AdbClient(Path("adb.exe"), "127.0.0.1:16384").pidof("missing.app") is None


@pytest.mark.parametrize(
    ("returncode", "stdout", "stderr"),
    [
        (1, "", "error: device offline"),
        (2, "", ""),
        (1, "unexpected output", ""),
    ],
)
def test_pidof_raises_for_unexpected_adb_failure(
    monkeypatch: pytest.MonkeyPatch,
    returncode: int,
    stdout: str,
    stderr: str,
) -> None:
    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        return completed(stdout=stdout, stderr=stderr, returncode=returncode)

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(subprocess.CalledProcessError) as error:
        AdbClient(Path("adb.exe"), "127.0.0.1:16384").pidof("com.phoenix.read")

    assert error.value.returncode == returncode
    assert error.value.stderr == stderr


@pytest.mark.parametrize(
    "package_name",
    [
        "com.phoenix.read;id",
        "com.phoenix.read && id",
        "com.phoenix.$read",
        "com..read",
        "single",
        "1com.phoenix.read",
    ],
)
def test_pidof_rejects_invalid_android_package_name(
    monkeypatch: pytest.MonkeyPatch,
    package_name: str,
) -> None:
    called = False

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        nonlocal called
        called = True
        return completed()

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(ValueError, match="invalid Android package name"):
        AdbClient(Path("adb.exe"), "127.0.0.1:16384").pidof(package_name)

    assert called is False


def test_pidof_accepts_standard_android_package_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        return completed("4321")

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert AdbClient(Path("adb.exe"), "127.0.0.1:16384").pidof("com.example_1.read2") == 4321


def test_root_id_returns_root_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        return completed("uid=0(root) gid=0(root)")

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert AdbClient(Path("adb.exe"), "127.0.0.1:16384").root_id().startswith("uid=0(root)")


def test_device_manager_discovers_connects_and_inspects_app(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instance = MuMuInstance(0, "127.0.0.1", 16384, "start_finished", True)
    events: list[object] = []

    monkeypatch.setattr(
        "hongguo_signer.device.manager.discover_instance",
        lambda cli, vmindex: events.append((cli, vmindex)) or instance,
    )

    class FakeAdb:
        def __init__(self, executable: Path, serial: str) -> None:
            events.append((executable, serial))

        def connect(self) -> None:
            events.append("connect")

        def root_id(self) -> str:
            events.append("root_id")
            return "uid=0(root) gid=0(root)"

        def pidof(self, package_name: str) -> int | None:
            events.append(("pidof", package_name))
            return 4321

    monkeypatch.setattr("hongguo_signer.device.manager.AdbClient", FakeAdb)
    settings = SignerSettings()

    state = DeviceManager(settings).inspect()

    assert state.instance == instance
    assert state.root_ready is True
    assert state.app_pid == 4321
    assert events == [
        (settings.mumu_cli, 0),
        (settings.adb, "127.0.0.1:16384"),
        "connect",
        "root_id",
        ("pidof", "com.phoenix.read"),
    ]
