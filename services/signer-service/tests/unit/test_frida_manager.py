import threading
import time
from collections import UserDict
from pathlib import Path
from types import MappingProxyType

import pytest

from hongguo_signer.frida_runtime.manager import (
    FridaManager,
    FridaRuntimeBusyError,
    normalize_rpc_headers,
)
from hongguo_signer.frida_runtime.watchdog import Watchdog


class FakeExports:
    def __init__(self) -> None:
        self.sign_result: object = {
            "x-argus": "argus",
            "Cookie": "session=secret",
        }
        self.grab_result: object = {
            "url": "https://api.example.test/resource",
            "headers": {
                "X-Gorgon": "gorgon",
                "x-tt-token": "secret",
                "cookie": "session=secret",
            },
        }
        self.health_result = True
        self.health_error: Exception | None = None
        self.sign_blocker: threading.Event | None = None
        self.grab_blocker: threading.Event | None = None
        self.sign_calls: list[tuple[str, dict[str, str]]] = []
        self.grab_calls: list[int] = []

    def sign(self, url: str, headers: dict[str, str]) -> object:
        self.sign_calls.append((url, headers))
        if self.sign_blocker is not None:
            self.sign_blocker.wait()
        return self.sign_result

    def health(self) -> object:
        if self.health_error is not None:
            raise self.health_error
        return self.health_result

    def grab(self, timeout_ms: int) -> object:
        self.grab_calls.append(timeout_ms)
        if self.grab_blocker is not None:
            self.grab_blocker.wait()
        return self.grab_result


class FakeScript:
    def __init__(
        self,
        source: str,
        events: list[object],
        load_error: Exception | None = None,
    ) -> None:
        self.source = source
        self.events = events
        self.load_error = load_error
        self.exports_sync = FakeExports()

    def load(self) -> None:
        self.events.append("load")
        if self.load_error is not None:
            raise self.load_error


class FakeSession:
    def __init__(
        self,
        events: list[object],
        load_error: Exception | None = None,
    ) -> None:
        self.events = events
        self.load_error = load_error
        self.scripts: list[FakeScript] = []
        self.detached = False
        self.detached_callback: object = None

    def create_script(self, source: str) -> FakeScript:
        self.events.append(("create_script", source))
        script = FakeScript(source, self.events, self.load_error)
        self.scripts.append(script)
        return script

    def on(self, signal: str, callback: object) -> None:
        self.events.append(("on", signal))
        self.detached_callback = callback

    def detach(self) -> None:
        self.events.append("detach")
        self.detached = True

    def emit_detached(self) -> None:
        callback = self.detached_callback
        assert callable(callback)
        callback("process-terminated", None)


class FakeProcess:
    pid = 4321


class FakeDevice:
    def __init__(self, events: list[object]) -> None:
        self.events = events
        self.sessions: list[FakeSession] = []
        self.next_load_error: Exception | None = None

    @property
    def session(self) -> FakeSession:
        return self.sessions[-1]

    def get_process(self, package_name: str) -> FakeProcess:
        self.events.append(("get_process", package_name))
        return FakeProcess()

    def attach(self, pid: int) -> FakeSession:
        self.events.append(("attach", pid))
        session = FakeSession(self.events, self.next_load_error)
        self.next_load_error = None
        self.sessions.append(session)
        return session


class FakeDeviceManager:
    def __init__(self, events: list[object]) -> None:
        self.events = events
        self.device = FakeDevice(events)

    def add_remote_device(self, endpoint: str) -> FakeDevice:
        self.events.append(("add_remote_device", endpoint))
        return self.device


class FakeFrida:
    def __init__(self) -> None:
        self.events: list[object] = []
        self.device_manager = FakeDeviceManager(self.events)
        self.manager_calls = 0

    def get_device_manager(self) -> FakeDeviceManager:
        self.manager_calls += 1
        return self.device_manager


def make_manager(
    tmp_path: Path,
) -> tuple[FridaManager, FakeFrida, FakeScript]:
    script_path = tmp_path / "oracle.js"
    script_path.write_text("rpc.exports = {};", encoding="utf-8")
    fake_frida = FakeFrida()
    manager = FridaManager(
        endpoint="127.0.0.1:27042",
        package_name="com.phoenix.read",
        script_path=script_path,
        frida_module=fake_frida,
    )
    manager.connect()
    script = fake_frida.device_manager.device.session.scripts[0]
    return manager, fake_frida, script


def test_normalize_rpc_headers_accepts_map_values() -> None:
    assert normalize_rpc_headers(
        {"X-Khronos": 123, "X-Argus": None}
    ) == {"X-Khronos": "123"}


def test_normalize_rpc_headers_accepts_non_dict_mapping() -> None:
    headers = UserDict({"X-Khronos": 123, "X-Argus": None})

    assert normalize_rpc_headers(headers) == {"X-Khronos": "123"}


@pytest.mark.parametrize("value", [None, [], "headers"])
def test_normalize_rpc_headers_rejects_non_objects(value: object) -> None:
    with pytest.raises(TypeError, match="sign RPC did not return an object"):
        normalize_rpc_headers(value)


def test_connect_attaches_by_package_and_loads_script(tmp_path: Path) -> None:
    manager, fake_frida, _ = make_manager(tmp_path)

    assert manager.pid == 4321
    assert fake_frida.events == [
        ("add_remote_device", "127.0.0.1:27042"),
        ("get_process", "com.phoenix.read"),
        ("attach", 4321),
        ("on", "detached"),
        ("create_script", "rpc.exports = {};"),
        "load",
    ]


def test_pid_requires_an_attachment(tmp_path: Path) -> None:
    manager = FridaManager(
        endpoint="127.0.0.1:27042",
        package_name="com.phoenix.read",
        script_path=tmp_path / "oracle.js",
        frida_module=FakeFrida(),
    )

    with pytest.raises(RuntimeError, match="Frida is not attached"):
        _ = manager.pid


def test_sign_connects_lazily_and_returns_only_security_headers(
    tmp_path: Path,
) -> None:
    script_path = tmp_path / "oracle.js"
    script_path.write_text("rpc.exports = {};", encoding="utf-8")
    fake_frida = FakeFrida()
    manager = FridaManager(
        endpoint="127.0.0.1:27042",
        package_name="com.phoenix.read",
        script_path=script_path,
        frida_module=fake_frida,
    )

    result = manager.sign(
        "https://api.example.test",
        {"User-Agent": "test-agent"},
    )
    script = fake_frida.device_manager.device.session.scripts[0]

    assert result == {"X-Argus": "argus"}
    assert script.exports_sync.sign_calls == [
        ("https://api.example.test", {"User-Agent": "test-agent"})
    ]
    assert fake_frida.manager_calls == 1


def test_health_is_false_before_connect_and_uses_rpc_after_connect(
    tmp_path: Path,
) -> None:
    script_path = tmp_path / "oracle.js"
    script_path.write_text("rpc.exports = {};", encoding="utf-8")
    fake_frida = FakeFrida()
    manager = FridaManager(
        endpoint="127.0.0.1:27042",
        package_name="com.phoenix.read",
        script_path=script_path,
        frida_module=fake_frida,
    )

    assert manager.health() is False

    manager.connect()

    assert manager.health() is True


def test_runtime_state_distinguishes_idle_active_stale_and_busy_hung(
    tmp_path: Path,
) -> None:
    manager, _, script = make_manager(tmp_path)
    assert manager.runtime_state().value == "idle"

    blocker = threading.Event()
    script.exports_sync.grab_blocker = blocker
    capture = threading.Thread(target=lambda: manager.capture_session(1000))
    capture.start()
    while not script.exports_sync.grab_calls:
        time.sleep(0.001)

    assert manager.runtime_state().value == "active"

    manager._mark_stale(script)
    assert manager.runtime_state().value == "busy_hung"

    blocker.set()
    capture.join(0.2)
    assert manager.runtime_state().value == "stale"


def test_watchdog_does_not_recover_during_active_capture(
    tmp_path: Path,
) -> None:
    manager, _, script = make_manager(tmp_path)
    blocker = threading.Event()
    script.exports_sync.grab_blocker = blocker
    recovered = threading.Event()
    watchdog = Watchdog(manager.health, recovered.set, interval=0.01)
    capture_result: list[dict[str, object]] = []

    capture = threading.Thread(
        target=lambda: capture_result.append(manager.capture_session(1000))
    )
    capture.start()
    while not script.exports_sync.grab_calls:
        time.sleep(0.001)
    watchdog.start()

    time.sleep(0.05)
    blocker.set()
    capture.join(0.2)
    watchdog.stop()

    assert recovered.is_set() is False
    assert capture_result[0]["url"] == "https://api.example.test/resource"
    assert manager.runtime_state().value == "idle"


def test_session_detach_clears_state_and_allows_reconnect(tmp_path: Path) -> None:
    manager, fake_frida, _ = make_manager(tmp_path)
    first_session = fake_frida.device_manager.device.session

    first_session.emit_detached()

    with pytest.raises(RuntimeError, match="Frida is not attached"):
        _ = manager.pid

    manager.connect()

    assert manager.pid == 4321
    assert len(fake_frida.device_manager.device.sessions) == 2


def test_load_failure_detaches_partial_session_and_leaves_clean_state(
    tmp_path: Path,
) -> None:
    script_path = tmp_path / "oracle.js"
    script_path.write_text("rpc.exports = {};", encoding="utf-8")
    fake_frida = FakeFrida()
    fake_frida.device_manager.device.next_load_error = RuntimeError("load failed")
    manager = FridaManager(
        endpoint="127.0.0.1:27042",
        package_name="com.phoenix.read",
        script_path=script_path,
        frida_module=fake_frida,
    )

    with pytest.raises(RuntimeError, match="load failed"):
        manager.connect()

    failed_session = fake_frida.device_manager.device.session
    assert failed_session.detached is True
    with pytest.raises(RuntimeError, match="Frida is not attached"):
        _ = manager.pid

    manager.connect()

    assert manager.pid == 4321
    assert len(fake_frida.device_manager.device.sessions) == 2


def test_close_detaches_session_and_reconnects_cleanly(tmp_path: Path) -> None:
    manager, fake_frida, _ = make_manager(tmp_path)
    first_session = fake_frida.device_manager.device.session

    manager.close()

    assert first_session.detached is True
    with pytest.raises(RuntimeError, match="Frida is not attached"):
        _ = manager.pid

    manager.connect()

    assert len(fake_frida.device_manager.device.sessions) == 2


def test_health_rpc_exception_returns_false_and_marks_runtime_stale(
    tmp_path: Path,
) -> None:
    manager, _, script = make_manager(tmp_path)
    script.exports_sync.health_error = RuntimeError("script destroyed")

    assert manager.health() is False
    with pytest.raises(RuntimeError, match="Frida is not attached"):
        _ = manager.pid


def test_sign_timeout_marks_stale_without_blocking_reconnect(
    tmp_path: Path,
) -> None:
    script_path = tmp_path / "oracle.js"
    script_path.write_text("rpc.exports = {};", encoding="utf-8")
    fake_frida = FakeFrida()
    manager = FridaManager(
        endpoint="127.0.0.1:27042",
        package_name="com.phoenix.read",
        script_path=script_path,
        frida_module=fake_frida,
        sign_timeout=0.02,
    )
    manager.connect()
    first_script = fake_frida.device_manager.device.session.scripts[0]
    blocker = threading.Event()
    first_script.exports_sync.sign_blocker = blocker

    started = time.monotonic()
    with pytest.raises(TimeoutError, match="Frida sign RPC timed out"):
        manager.sign("https://api.example.test", {})
    elapsed = time.monotonic() - started

    reconnect = threading.Thread(target=manager.connect)
    reconnect.start()
    reconnect.join(timeout=0.2)
    blocker.set()

    assert elapsed < 0.2
    assert reconnect.is_alive() is False
    assert len(fake_frida.device_manager.device.sessions) == 2


def test_hung_rpc_rejects_repeated_calls_without_spawning_workers(
    tmp_path: Path,
) -> None:
    script_path = tmp_path / "oracle.js"
    script_path.write_text("rpc.exports = {};", encoding="utf-8")
    fake_frida = FakeFrida()
    manager = FridaManager(
        endpoint="127.0.0.1:27042",
        package_name="com.phoenix.read",
        script_path=script_path,
        frida_module=fake_frida,
        sign_timeout=0.02,
    )
    manager.connect()
    first_script = fake_frida.device_manager.device.session.scripts[0]
    blocker = threading.Event()
    first_script.exports_sync.sign_blocker = blocker

    with pytest.raises(TimeoutError, match="Frida sign RPC timed out"):
        manager.sign("https://api.example.test/first", {})

    manager.reconnect()
    started = time.monotonic()
    with pytest.raises(FridaRuntimeBusyError, match="RPC worker is still active"):
        manager.sign("https://api.example.test/second", {})
    with pytest.raises(FridaRuntimeBusyError, match="RPC worker is still active"):
        manager.capture_session(100)
    health = manager.health()
    elapsed = time.monotonic() - started
    rpc_workers = [
        thread
        for thread in threading.enumerate()
        if thread.name.startswith("frida-") and thread.name.endswith("-rpc")
    ]

    assert health is False
    assert elapsed < 0.1
    assert first_script.exports_sync.sign_calls == [
        ("https://api.example.test/first", {})
    ]
    assert len(rpc_workers) == 1

    blocker.set()
    rpc_workers[0].join(timeout=0.2)


@pytest.mark.parametrize("timeout_ms", [0, -1])
def test_capture_session_requires_positive_timeout(
    tmp_path: Path,
    timeout_ms: int,
) -> None:
    manager, _, script = make_manager(tmp_path)

    with pytest.raises(ValueError, match="timeout_ms must be positive"):
        manager.capture_session(timeout_ms)

    assert script.exports_sync.grab_calls == []


def test_capture_timeout_includes_agent_timeout_and_small_overhead(
    tmp_path: Path,
) -> None:
    manager, _, script = make_manager(tmp_path)
    blocker = threading.Event()
    script.exports_sync.grab_blocker = blocker
    manager.capture_timeout_overhead = 0.02
    errors: list[BaseException] = []
    elapsed: list[float] = []

    def capture() -> None:
        started = time.monotonic()
        try:
            manager.capture_session(10)
        except BaseException as error:
            errors.append(error)
        finally:
            elapsed.append(time.monotonic() - started)

    caller = threading.Thread(target=capture)
    caller.start()
    caller.join(timeout=0.15)
    completed_before_release = not caller.is_alive()
    blocker.set()
    caller.join(timeout=0.2)

    assert script.exports_sync.grab_calls == [10]
    assert completed_before_release is True
    assert len(errors) == 1
    assert isinstance(errors[0], TimeoutError)
    assert str(errors[0]) == "Frida grab RPC timed out"
    assert 0.02 <= elapsed[0] < 0.15


def test_capture_session_normalizes_and_sanitizes_headers(tmp_path: Path) -> None:
    manager, _, script = make_manager(tmp_path)

    result = manager.capture_session(2500)

    assert result == {
        "url": "https://api.example.test/resource",
        "headers": {
            "x-tt-token": "secret",
            "cookie": "session=secret",
        },
    }
    assert script.exports_sync.grab_calls == [2500]


def test_capture_session_accepts_non_dict_mappings(tmp_path: Path) -> None:
    manager, _, script = make_manager(tmp_path)
    script.exports_sync.grab_result = MappingProxyType(
        {
            "url": "https://api.example.test/resource",
            "headers": MappingProxyType(
                {
                    "X-Gorgon": "gorgon",
                    "cookie": "session=secret",
                }
            ),
        }
    )

    assert manager.capture_session(2500) == {
        "url": "https://api.example.test/resource",
        "headers": {"cookie": "session=secret"},
    }


@pytest.mark.parametrize("value", [None, [], "session"])
def test_capture_session_rejects_non_objects(
    tmp_path: Path,
    value: object,
) -> None:
    manager, _, script = make_manager(tmp_path)
    script.exports_sync.grab_result = value

    with pytest.raises(TypeError, match="grab RPC did not return an object"):
        manager.capture_session(100)


def test_concurrent_sign_calls_share_one_attachment(tmp_path: Path) -> None:
    script_path = tmp_path / "oracle.js"
    script_path.write_text("rpc.exports = {};", encoding="utf-8")
    fake_frida = FakeFrida()
    original_add = fake_frida.device_manager.add_remote_device

    def delayed_add(endpoint: str) -> FakeDevice:
        time.sleep(0.02)
        return original_add(endpoint)

    fake_frida.device_manager.add_remote_device = delayed_add  # type: ignore[method-assign]
    manager = FridaManager(
        endpoint="127.0.0.1:27042",
        package_name="com.phoenix.read",
        script_path=script_path,
        frida_module=fake_frida,
    )
    barrier = threading.Barrier(3)
    results: list[dict[str, str]] = []

    def sign() -> None:
        barrier.wait()
        results.append(manager.sign("https://api.example.test", {}))

    threads = [threading.Thread(target=sign) for _ in range(2)]
    for thread in threads:
        thread.start()
    barrier.wait()
    for thread in threads:
        thread.join()

    assert results == [{"X-Argus": "argus"}, {"X-Argus": "argus"}]
    assert fake_frida.manager_calls == 1
    assert len(fake_frida.device_manager.device.session.scripts) == 1


def test_oracle_uses_required_java_collections_and_restores_grab_hook() -> None:
    source = (
        Path(__file__).parents[2]
        / "src"
        / "hongguo_signer"
        / "frida_runtime"
        / "oracle.js"
    ).read_text(encoding="utf-8")

    assert 'Java.use("java.util.HashMap")' in source
    assert 'Java.use("java.util.ArrayList")' in source
    assert "tryAddSecurityFactor.overload(" in source
    assert '"java.lang.String"' in source
    assert '"java.util.Map"' in source
    assert "function restoreHook()" in source
    assert source.count("restoreHook();") >= 3
    timer_install = source.index("timer = setTimeout")
    hook_install = source.index("overload.implementation = function")
    assert timer_install < hook_install
    assert "if (!(timeoutMs > 0))" in source
    assert "}, timeoutMs);" in source
