import threading
import time

from hongguo_signer.frida_runtime.watchdog import Watchdog


def test_watchdog_recovers_when_runtime_is_unhealthy() -> None:
    recovered = threading.Event()
    watchdog = Watchdog(lambda: False, recovered.set, interval=0.01)

    thread = watchdog.start()
    assert recovered.wait(0.2)
    watchdog.stop()
    thread.join(0.2)

    assert thread.is_alive() is False


def test_watchdog_recovers_when_health_check_raises() -> None:
    recovered = threading.Event()

    def check() -> bool:
        raise RuntimeError("detached")

    watchdog = Watchdog(check, recovered.set, interval=0.01)

    thread = watchdog.start()
    assert recovered.wait(0.2)
    watchdog.stop()
    thread.join(0.2)

    assert thread.is_alive() is False


def test_watchdog_does_not_overlap_recoveries() -> None:
    entered = threading.Event()
    release = threading.Event()
    calls = 0

    def recover() -> None:
        nonlocal calls
        calls += 1
        entered.set()
        release.wait(0.2)

    watchdog = Watchdog(lambda: False, recover, interval=0.01)

    first = threading.Thread(target=watchdog.check_once)
    second = threading.Thread(target=watchdog.check_once)
    first.start()
    assert entered.wait(0.2)
    second.start()
    second.join(0.1)
    release.set()
    first.join(0.2)

    assert calls == 1


def test_watchdog_stop_interrupts_interval_wait() -> None:
    watchdog = Watchdog(lambda: True, lambda: None, interval=10)
    thread = watchdog.start()

    started = time.monotonic()
    watchdog.stop()

    assert time.monotonic() - started < 0.2
    assert thread.is_alive() is False


def test_watchdog_continues_after_recovery_raises() -> None:
    recovered = threading.Event()
    calls = 0

    def recover() -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("recovery failed")
        recovered.set()

    watchdog = Watchdog(lambda: False, recover, interval=0.01)

    thread = watchdog.start()
    assert recovered.wait(0.2)
    watchdog.stop()
    thread.join(0.2)

    assert calls >= 2
    assert thread.is_alive() is False


def test_watchdog_immediate_restart_uses_fresh_event_and_live_thread() -> None:
    watchdog = Watchdog(lambda: True, lambda: None, interval=10)
    first = watchdog.start()

    watchdog.stop()
    second = watchdog.start()

    assert first.is_alive() is False
    assert second is not first
    assert second.is_alive() is True

    watchdog.stop()


def test_watchdog_stop_waits_for_active_recovery_before_returning() -> None:
    entered = threading.Event()
    release = threading.Event()

    def recover() -> None:
        entered.set()
        release.wait(0.5)

    watchdog = Watchdog(lambda: False, recover, interval=0.01)
    thread = watchdog.start()
    assert entered.wait(0.2)

    stopper = threading.Thread(target=watchdog.stop)
    stopper.start()
    time.sleep(0.02)
    assert stopper.is_alive() is True

    release.set()
    stopper.join(0.2)

    assert stopper.is_alive() is False
    assert thread.is_alive() is False
