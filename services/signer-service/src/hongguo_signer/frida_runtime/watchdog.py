import threading
from collections.abc import Callable


class Watchdog:
    def __init__(
        self,
        check: Callable[[], bool],
        recover: Callable[[], None],
        *,
        interval: float = 15.0,
    ) -> None:
        if interval <= 0:
            raise ValueError("watchdog interval must be positive")
        self.check = check
        self.recover = recover
        self.interval = interval
        self.stop_event = threading.Event()
        self._recovery_lock = threading.Lock()
        self._lifecycle_lock = threading.Lock()
        self._thread: threading.Thread | None = None

    def check_once(self) -> None:
        try:
            healthy = self.check()
        except Exception:
            healthy = False
        if healthy:
            return

        if not self._recovery_lock.acquire(blocking=False):
            return
        try:
            try:
                self.recover()
            except Exception:
                pass
        finally:
            self._recovery_lock.release()

    def run(self, stop_event: threading.Event | None = None) -> None:
        event = stop_event or self.stop_event
        while not event.wait(self.interval):
            self.check_once()

    def start(self) -> threading.Thread:
        with self._lifecycle_lock:
            if self._thread is not None and self._thread.is_alive():
                return self._thread
            self.stop_event = threading.Event()
            self._thread = threading.Thread(
                target=self.run,
                args=(self.stop_event,),
                daemon=True,
                name="signer-watchdog",
            )
            self._thread.start()
            return self._thread

    def stop(self) -> None:
        with self._lifecycle_lock:
            thread = self._thread
            self.stop_event.set()
            if thread is not None and thread is not threading.current_thread():
                thread.join()
            if self._thread is thread:
                self._thread = None
