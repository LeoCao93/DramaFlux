import queue
import threading
from collections.abc import Callable, Mapping
from enum import Enum
from pathlib import Path
from typing import Any, Protocol

import frida

from hongguo_signer.security import filter_security_headers, filter_session_headers


class RpcExports(Protocol):
    def sign(self, url: str, headers: dict[str, str]) -> object: ...

    def health(self) -> object: ...

    def grab(self, timeout_ms: int) -> object: ...


class Script(Protocol):
    exports_sync: RpcExports

    def load(self) -> None: ...


class Session(Protocol):
    def create_script(self, source: str) -> Script: ...

    def on(
        self,
        signal: str,
        callback: Callable[..., None],
    ) -> None: ...

    def detach(self) -> None: ...


class Process(Protocol):
    pid: int


class Application(Protocol):
    identifier: str
    pid: int


class Device(Protocol):
    def get_process(self, package_name: str) -> Process: ...

    def enumerate_applications(self) -> list[Application]: ...

    def attach(self, pid: int) -> Session: ...


class DeviceManager(Protocol):
    def add_remote_device(self, endpoint: str) -> Device: ...


class FridaModule(Protocol):
    def get_device_manager(self) -> DeviceManager: ...


class FridaRuntimeBusyError(RuntimeError):
    """Raised when a previous synchronous RPC worker is still active."""


class FridaRuntimeState(Enum):
    IDLE = "idle"
    ACTIVE = "active"
    STALE = "stale"
    BUSY_HUNG = "busy_hung"


def normalize_rpc_headers(value: Any) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise TypeError("Frida sign RPC did not return an object")
    return {
        str(key): str(item)
        for key, item in value.items()
        if item is not None
    }


class FridaManager:
    def __init__(
        self,
        endpoint: str,
        package_name: str,
        script_path: Path,
        *,
        frida_module: FridaModule = frida,
        sign_timeout: float = 5.0,
        health_timeout: float = 2.0,
        capture_timeout_overhead: float = 0.5,
    ) -> None:
        self.endpoint = endpoint
        self.package_name = package_name
        self.script_path = script_path
        self.sign_timeout = sign_timeout
        self.health_timeout = health_timeout
        self.capture_timeout_overhead = capture_timeout_overhead
        self._frida = frida_module
        self._state_lock = threading.RLock()
        self._rpc_call_lock = threading.Lock()
        self._worker_lock = threading.Lock()
        self._active_worker: threading.Thread | None = None
        self._active_worker_script: Script | None = None
        self._active_worker_timed_out = False
        self._session: Session | None = None
        self._script: Script | None = None
        self._pid: int | None = None

    @property
    def pid(self) -> int:
        with self._state_lock:
            if self._pid is None:
                raise RuntimeError("Frida is not attached")
            return self._pid

    def connect(self) -> None:
        with self._state_lock:
            if self._script is not None:
                return

            session: Session | None = None
            try:
                device = self._frida.get_device_manager().add_remote_device(
                    self.endpoint
                )
                try:
                    process = device.get_process(self.package_name)
                except frida.ProcessNotFoundError:
                    application = next(
                        (
                            item
                            for item in device.enumerate_applications()
                            if item.identifier == self.package_name and item.pid > 0
                        ),
                        None,
                    )
                    if application is None:
                        raise
                    process = application
                session = device.attach(process.pid)
                self._session = session
                self._pid = process.pid
                session.on(
                    "detached",
                    lambda *args: self._handle_detached(session),
                )
                source = self.script_path.read_text(encoding="utf-8")
                script = session.create_script(source)
                script.load()
                self._script = script
            except BaseException:
                self._clear_state_locked()
                if session is not None:
                    self._detach_session(session)
                raise

    def close(self) -> None:
        with self._state_lock:
            session = self._clear_state_locked()
        if session is not None:
            self._detach_session(session)

    def reconnect(self) -> None:
        self.close()
        self.connect()

    def sign(
        self,
        url: str,
        headers: dict[str, str],
    ) -> dict[str, str]:
        script = self._connected_runtime()
        raw = self._call_rpc(
            script,
            "sign",
            self.sign_timeout,
            lambda: script.exports_sync.sign(url, headers),
        )
        return filter_security_headers(normalize_rpc_headers(raw))

    def health(self) -> bool:
        state = self.runtime_state()
        if state is FridaRuntimeState.ACTIVE:
            return True
        if state is not FridaRuntimeState.IDLE:
            return False

        with self._state_lock:
            script = self._script
        if script is None:
            return False

        try:
            return bool(
                self._call_rpc(
                    script,
                    "health",
                    self.health_timeout,
                    script.exports_sync.health,
                    wait_for_slot=False,
                )
            )
        except BaseException:
            return False

    def runtime_state(self) -> FridaRuntimeState:
        with self._worker_lock:
            self._reap_worker_locked()
            worker_active = self._active_worker is not None
            worker_script = self._active_worker_script
            worker_timed_out = self._active_worker_timed_out
        with self._state_lock:
            script = self._script

        if worker_active:
            if not worker_timed_out and worker_script is script:
                return FridaRuntimeState.ACTIVE
            return FridaRuntimeState.BUSY_HUNG
        if script is not None:
            return FridaRuntimeState.IDLE
        return FridaRuntimeState.STALE

    def capture_session(self, timeout_ms: int) -> dict[str, Any]:
        if timeout_ms <= 0:
            raise ValueError("timeout_ms must be positive")

        script = self._connected_runtime()
        timeout = timeout_ms / 1000 + self.capture_timeout_overhead
        raw = self._call_rpc(
            script,
            "grab",
            timeout,
            lambda: script.exports_sync.grab(timeout_ms),
        )
        if not isinstance(raw, Mapping):
            raise TypeError("Frida grab RPC did not return an object")

        result = {str(key): value for key, value in raw.items()}
        if "headers" in result:
            result["headers"] = filter_session_headers(
                normalize_rpc_headers(result["headers"])
            )
        return result

    def _connected_runtime(self) -> Script:
        self.connect()
        with self._state_lock:
            if self._script is None:
                raise RuntimeError("Frida is not attached")
            return self._script

    def _call_rpc(
        self,
        script: Script,
        name: str,
        timeout: float,
        operation: Callable[[], object],
        *,
        wait_for_slot: bool = True,
    ) -> object:
        acquired = self._rpc_call_lock.acquire(blocking=wait_for_slot)
        if not acquired:
            raise FridaRuntimeBusyError("Frida RPC worker is still active")
        try:
            result: queue.Queue[tuple[bool, object]] = queue.Queue(maxsize=1)

            def invoke() -> None:
                try:
                    result.put((True, operation()))
                except BaseException as error:
                    result.put((False, error))
                finally:
                    self._clear_active_worker(threading.current_thread())

            with self._worker_lock:
                self._reap_worker_locked()
                if self._active_worker is not None:
                    raise FridaRuntimeBusyError(
                        "Frida RPC worker is still active"
                    )
                worker = threading.Thread(
                    target=invoke,
                    name=f"frida-{name}-rpc",
                    daemon=True,
                )
                self._active_worker = worker
                self._active_worker_script = script
                self._active_worker_timed_out = False
                worker.start()

            try:
                succeeded, value = result.get(timeout=max(0, timeout))
            except queue.Empty:
                with self._worker_lock:
                    if self._active_worker is worker:
                        self._active_worker_timed_out = True
                self._mark_stale(script)
                raise TimeoutError(f"Frida {name} RPC timed out") from None

            # The worker publishes its result before its finally block runs.
            # Clear it here so the next serialized caller cannot observe a
            # completed worker as a hung RPC.
            self._clear_active_worker(worker)
            if not succeeded:
                self._mark_stale(script)
                if isinstance(value, BaseException):
                    raise value
                raise RuntimeError(f"Frida {name} RPC failed")
            return value
        finally:
            self._rpc_call_lock.release()

    def _worker_is_active(self) -> bool:
        with self._worker_lock:
            self._reap_worker_locked()
            return self._active_worker is not None

    def _clear_active_worker(self, worker: threading.Thread) -> None:
        with self._worker_lock:
            if self._active_worker is worker:
                self._active_worker = None
                self._active_worker_script = None
                self._active_worker_timed_out = False

    def _reap_worker_locked(self) -> None:
        if (
            self._active_worker is not None
            and not self._active_worker.is_alive()
        ):
            self._active_worker = None
            self._active_worker_script = None
            self._active_worker_timed_out = False

    def _handle_detached(self, session: Session) -> None:
        with self._state_lock:
            if self._session is session:
                self._clear_state_locked()

    def _mark_stale(self, script: Script) -> None:
        with self._state_lock:
            if self._script is not script:
                return
            session = self._clear_state_locked()
        if session is not None:
            threading.Thread(
                target=self._detach_session,
                args=(session,),
                name="frida-stale-detach",
                daemon=True,
            ).start()

    def _clear_state_locked(self) -> Session | None:
        session = self._session
        self._session = None
        self._script = None
        self._pid = None
        return session

    @staticmethod
    def _detach_session(session: Session) -> None:
        try:
            session.detach()
        except BaseException:
            pass
