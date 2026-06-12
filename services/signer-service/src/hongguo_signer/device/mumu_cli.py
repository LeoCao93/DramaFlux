import json
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MuMuInstance:
    index: int
    adb_host: str
    adb_port: int
    player_state: str
    process_started: bool

    @property
    def adb_serial(self) -> str:
        return f"{self.adb_host}:{self.adb_port}"


def parse_instance(raw: str) -> MuMuInstance:
    data = json.loads(raw)
    process_started = data["is_process_started"]
    if type(process_started) is not bool:
        raise ValueError("is_process_started must be a JSON boolean")
    return MuMuInstance(
        index=int(data["index"]),
        adb_host=str(data["adb_host_ip"]),
        adb_port=int(data["adb_port"]),
        player_state=str(data["player_state"]),
        process_started=process_started,
    )


def discover_instance(cli: Path, vmindex: int) -> MuMuInstance:
    result = subprocess.run(
        [str(cli), "info", "--vmindex", str(vmindex)],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=15,
    )
    return parse_instance(result.stdout)
