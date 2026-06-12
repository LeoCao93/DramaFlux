from dataclasses import dataclass

from hongguo_signer.config import SignerSettings
from hongguo_signer.device.adb import AdbClient
from hongguo_signer.device.mumu_cli import MuMuInstance, discover_instance


@dataclass(frozen=True)
class DeviceState:
    instance: MuMuInstance
    root_ready: bool
    app_pid: int | None


class DeviceManager:
    def __init__(self, settings: SignerSettings) -> None:
        self.settings = settings

    def inspect(self) -> DeviceState:
        instance = discover_instance(self.settings.mumu_cli, self.settings.vmindex)
        adb = AdbClient(self.settings.adb, instance.adb_serial)
        adb.connect()
        root_ready = "uid=0(root)" in adb.root_id()
        app_pid = adb.pidof(self.settings.package_name)
        return DeviceState(instance=instance, root_ready=root_ready, app_pid=app_pid)
