from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from hongguo_signer.config import SignerSettings
from hongguo_signer.device.adb import AdbClient
from hongguo_signer.device.mumu_cli import discover_instance
from hongguo_signer.frida_runtime.bootstrap import ensure_frida_server
from hongguo_signer.frida_runtime.manager import FridaManager
from hongguo_signer.frida_runtime.watchdog import Watchdog
from hongguo_signer.main import create_app


def build_app(settings: SignerSettings | None = None) -> FastAPI:
    configured = settings or SignerSettings()
    instance = discover_instance(configured.mumu_cli, configured.vmindex)
    adb = AdbClient(configured.adb, instance.adb_serial)
    adb.connect()
    if "uid=0(root)" not in adb.root_id():
        raise RuntimeError("MuMu root access is unavailable")
    if adb.pidof(configured.package_name) is None:
        raise RuntimeError("Hongguo app is not running")

    ensure_frida_server(
        adb,
        configured.frida_server_path,
        configured.frida_remote_path,
        port=configured.frida_port,
    )
    runtime = FridaManager(
        endpoint=f"{configured.frida_host}:{configured.frida_port}",
        package_name=configured.package_name,
        script_path=Path(__file__).parent / "frida_runtime" / "oracle.js",
    )
    runtime.connect()
    watchdog = Watchdog(
        runtime.health,
        runtime.reconnect,
        interval=configured.watchdog_interval,
    )

    app = create_app(runtime, configured.service_token)
    original_lifespan = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        watchdog.start()
        try:
            async with original_lifespan(application):
                yield
        finally:
            watchdog.stop()
            runtime.close()

    app.router.lifespan_context = lifespan
    return app


app = build_app()
