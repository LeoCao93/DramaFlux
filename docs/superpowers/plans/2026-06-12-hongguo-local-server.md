# Hongguo Local Server Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build independently deployable Python services that use a MuMu-hosted Hongguo app as a Frida signing oracle and expose local search, latest, ranking, series, episode, and video-model APIs.

**Architecture:** A Windows-local Signer Service owns MuMu, ADB, root, Frida, `oracle.js`, and session capture. A separate API Server owns signed upstream requests and Hongguo response parsing. A small contracts package defines their versioned HTTP protocol without sharing implementation code.

**Tech Stack:** Python 3.10+, uv workspace, FastAPI, Uvicorn, Pydantic v2, pydantic-settings, httpx, Frida Python bindings, cachetools, pytest, pytest-asyncio, respx, Ruff.

---

## File Map

### Workspace and contracts

- Create `pyproject.toml`: uv workspace membership and shared development tools.
- Create `.gitignore`: Python, uv, local session, Frida binary, logs, and test caches.
- Create `packages/hongguo-contracts/pyproject.toml`: shared package metadata.
- Create `packages/hongguo-contracts/src/hongguo_contracts/signer.py`: signer request/response/session models.
- Create `packages/hongguo-contracts/src/hongguo_contracts/errors.py`: stable cross-service error envelope.

### Signer Service

- Create `services/signer-service/src/hongguo_signer/config.py`: MuMu, ADB, Frida, package, bind, and auth settings.
- Create `services/signer-service/src/hongguo_signer/device/mumu_cli.py`: parse `mumu-cli info`.
- Create `services/signer-service/src/hongguo_signer/device/adb.py`: safe subprocess wrapper and device operations.
- Create `services/signer-service/src/hongguo_signer/device/manager.py`: environment readiness orchestration.
- Create `services/signer-service/src/hongguo_signer/frida_runtime/manager.py`: Frida attach and RPC lifecycle.
- Create `services/signer-service/src/hongguo_signer/frida_runtime/watchdog.py`: recovery loop.
- Create `services/signer-service/src/hongguo_signer/frida_runtime/oracle.js`: in-process signing and session observation RPC.
- Create `services/signer-service/src/hongguo_signer/security.py`: service-token validation and returned-header allowlist.
- Create `services/signer-service/src/hongguo_signer/main.py`: FastAPI routes and lifespan.

### API Server

- Create `services/api-server/src/hongguo_api/config.py`: API, signer, upstream, session, timeout, and cache settings.
- Create `services/api-server/src/hongguo_api/session/storage.py`: session snapshot persistence and validation.
- Create `services/api-server/src/hongguo_api/signer/client.py`: versioned Signer Service HTTP client.
- Create `services/api-server/src/hongguo_api/upstream/transport.py`: deterministic signed HTTP transport.
- Create `services/api-server/src/hongguo_api/upstream/client.py`: endpoint request construction.
- Create `services/api-server/src/hongguo_api/parsers/*.py`: normalized response parsing.
- Create `services/api-server/src/hongguo_api/api/*.py`: local business routes and health.
- Create `services/api-server/src/hongguo_api/main.py`: FastAPI composition and lifespan.

### Operations and tests

- Create `services/signer-service/scripts/check_environment.ps1`: local prerequisite report.
- Create `services/signer-service/scripts/start.ps1`: Signer startup.
- Create `services/api-server/scripts/start.ps1`: API startup.
- Create fixture-driven unit and integration tests under each service.
- Create opt-in live tests under `tests/live`.

---

### Task 1: Bootstrap the uv Workspace and Shared Contracts

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `packages/hongguo-contracts/pyproject.toml`
- Create: `packages/hongguo-contracts/src/hongguo_contracts/__init__.py`
- Create: `packages/hongguo-contracts/src/hongguo_contracts/signer.py`
- Create: `packages/hongguo-contracts/src/hongguo_contracts/errors.py`
- Create: `packages/hongguo-contracts/tests/test_models.py`

- [ ] **Step 1: Create the workspace metadata**

```toml
# pyproject.toml
[project]
name = "hongguo-video-workspace"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = []

[tool.uv]
package = false

[tool.uv.workspace]
members = [
  "packages/hongguo-contracts",
]

[dependency-groups]
dev = [
  "pytest>=8.3",
  "pytest-asyncio>=0.25",
  "respx>=0.22",
  "ruff>=0.9",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = [
  "packages/hongguo-contracts/tests",
  "services/signer-service/tests",
  "services/api-server/tests",
]

[tool.ruff]
line-length = 100
target-version = "py310"
```

```gitignore
# .gitignore
.venv/
__pycache__/
*.py[cod]
.pytest_cache/
.ruff_cache/
.local/
*.log
services/*/.env
```

- [ ] **Step 2: Write failing contract-model tests**

```python
# packages/hongguo-contracts/tests/test_models.py
from datetime import datetime, timezone

from hongguo_contracts.signer import SessionSnapshot, SignRequest, SignResponse


def test_sign_request_normalizes_url_to_string() -> None:
    request = SignRequest(
        url="https://example.test/path?a=1",
        headers={"x-ss-stub": "ABC"},
    )
    assert str(request.url) == "https://example.test/path?a=1"


def test_sign_response_carries_process_identity() -> None:
    now = datetime.now(timezone.utc)
    response = SignResponse(
        headers={"X-Khronos": "123"},
        app_pid=42,
        signed_at=now,
    )
    assert response.app_pid == 42
    assert response.signed_at == now


def test_session_snapshot_separates_query_and_headers() -> None:
    snapshot = SessionSnapshot(
        api_host="api.example.test",
        base_query={"device_id": "1"},
        session_headers={"x-tt-token": "secret"},
        captured_at=datetime.now(timezone.utc),
    )
    assert snapshot.base_query["device_id"] == "1"
    assert snapshot.session_headers["x-tt-token"] == "secret"
```

- [ ] **Step 3: Run the tests and verify import failure**

Run:

```powershell
uv run pytest packages/hongguo-contracts/tests/test_models.py -q
```

Expected: FAIL because `hongguo_contracts` does not exist.

- [ ] **Step 4: Implement the contracts package**

```toml
# packages/hongguo-contracts/pyproject.toml
[project]
name = "hongguo-contracts"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = ["pydantic>=2.10"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

```python
# packages/hongguo-contracts/src/hongguo_contracts/signer.py
from datetime import datetime

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field


class SignRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: AnyHttpUrl
    headers: dict[str, str] = Field(default_factory=dict)


class SignResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    headers: dict[str, str]
    app_pid: int
    signed_at: datetime


class SessionSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    api_host: str
    base_query: dict[str, str]
    session_headers: dict[str, str]
    captured_at: datetime
```

```python
# packages/hongguo-contracts/src/hongguo_contracts/errors.py
from pydantic import BaseModel, ConfigDict


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    request_id: str | None = None
```

```python
# packages/hongguo-contracts/src/hongguo_contracts/__init__.py
from .errors import ErrorResponse
from .signer import SessionSnapshot, SignRequest, SignResponse

__all__ = ["ErrorResponse", "SessionSnapshot", "SignRequest", "SignResponse"]
```

- [ ] **Step 5: Sync and verify contracts**

Run:

```powershell
uv sync --all-packages
uv run pytest packages/hongguo-contracts/tests/test_models.py -q
uv run ruff check packages/hongguo-contracts
```

Expected: all tests PASS and Ruff reports no errors.

- [ ] **Step 6: Initialize version control and commit**

```powershell
git init
git add pyproject.toml .gitignore packages/hongguo-contracts
git commit -m "build: initialize uv workspace and signer contracts"
```

---

### Task 2: Implement MuMu Discovery and Root-Aware ADB Operations

**Files:**
- Modify: `pyproject.toml`
- Create: `services/signer-service/pyproject.toml`
- Create: `services/signer-service/src/hongguo_signer/__init__.py`
- Create: `services/signer-service/src/hongguo_signer/config.py`
- Create: `services/signer-service/src/hongguo_signer/device/mumu_cli.py`
- Create: `services/signer-service/src/hongguo_signer/device/adb.py`
- Create: `services/signer-service/src/hongguo_signer/device/manager.py`
- Test: `services/signer-service/tests/unit/test_device.py`

- [ ] **Step 1: Write failing device tests**

```python
# services/signer-service/tests/unit/test_device.py
import json

from hongguo_signer.device.mumu_cli import MuMuInstance, parse_instance


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


def test_instance_serial_uses_discovered_endpoint() -> None:
    instance = MuMuInstance(0, "127.0.0.1", 16384, "start_finished", True)
    assert instance.adb_serial == "127.0.0.1:16384"
```

- [ ] **Step 2: Run the tests and verify failure**

Run:

```powershell
uv run pytest services/signer-service/tests/unit/test_device.py -q
```

Expected: FAIL because `hongguo_signer` does not exist.

- [ ] **Step 3: Add Signer package metadata and configuration**

First update the root workspace membership:

```toml
[tool.uv.workspace]
members = [
  "packages/hongguo-contracts",
  "services/signer-service",
]
```

```toml
# services/signer-service/pyproject.toml
[project]
name = "hongguo-signer-service"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
  "fastapi>=0.115",
  "frida>=17",
  "hongguo-contracts",
  "pydantic-settings>=2.7",
  "uvicorn>=0.34",
]

[tool.uv.sources]
hongguo-contracts = { workspace = true }

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

```python
# services/signer-service/src/hongguo_signer/config.py
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class SignerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="HONGGUO_SIGNER_", extra="ignore")

    mumu_home: Path = Path(r"D:\MuMu Player 12")
    vmindex: int = 0
    package_name: str = "com.phoenix.read"
    frida_host: str = "127.0.0.1"
    frida_port: int = 27042
    frida_remote_path: str = "/data/local/tmp/frida-server"
    service_token: str = "local-development"

    @property
    def mumu_cli(self) -> Path:
        return self.mumu_home / "nx_main" / "mumu-cli.exe"

    @property
    def adb(self) -> Path:
        return self.mumu_home / "shell" / "adb.exe"
```

- [ ] **Step 4: Implement discovery and command wrappers**

```python
# services/signer-service/src/hongguo_signer/device/mumu_cli.py
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
    return MuMuInstance(
        index=int(data["index"]),
        adb_host=data["adb_host_ip"],
        adb_port=int(data["adb_port"]),
        player_state=data["player_state"],
        process_started=bool(data["is_process_started"]),
    )


def discover_instance(cli: Path, vmindex: int) -> MuMuInstance:
    result = subprocess.run(
        [str(cli), "info", "--vmindex", str(vmindex)],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return parse_instance(result.stdout)
```

```python
# services/signer-service/src/hongguo_signer/device/adb.py
import subprocess
from pathlib import Path


class AdbClient:
    def __init__(self, executable: Path, serial: str) -> None:
        self.executable = executable
        self.serial = serial

    def _run(self, *args: str) -> str:
        result = subprocess.run(
            [str(self.executable), "-s", self.serial, *args],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        return result.stdout.strip()

    def connect(self) -> None:
        subprocess.run(
            [str(self.executable), "connect", self.serial],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

    def shell(self, command: str) -> str:
        return self._run("shell", command)

    def push(self, local_path: Path, remote_path: str) -> None:
        self._run("push", str(local_path), remote_path)

    def forward(self, local: str, remote: str) -> None:
        self._run("forward", local, remote)

    def root_id(self) -> str:
        return self.shell("su -c id")

    def pidof(self, package_name: str) -> int | None:
        value = self.shell(f"pidof {package_name}")
        return int(value.split()[0]) if value else None
```

```python
# services/signer-service/src/hongguo_signer/device/manager.py
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
        return DeviceState(instance, root_ready, adb.pidof(self.settings.package_name))
```

- [ ] **Step 5: Run device tests and a local smoke check**

Run:

```powershell
uv sync --all-packages
uv run pytest services/signer-service/tests/unit/test_device.py -q
uv run python -c "from hongguo_signer.config import SignerSettings; from hongguo_signer.device.manager import DeviceManager; print(DeviceManager(SignerSettings()).inspect())"
```

Expected: tests PASS; smoke output reports port `16384`, `root_ready=True`, and a Hongguo PID when the app is running.

- [ ] **Step 6: Commit**

```powershell
git add services/signer-service
git commit -m "feat(signer): discover MuMu and verify rooted device"
```

---

### Task 3: Build the Frida Runtime and Java Signing Agent

**Files:**
- Create: `services/signer-service/src/hongguo_signer/frida_runtime/manager.py`
- Create: `services/signer-service/src/hongguo_signer/frida_runtime/oracle.js`
- Create: `services/signer-service/src/hongguo_signer/security.py`
- Test: `services/signer-service/tests/unit/test_security.py`
- Test: `services/signer-service/tests/unit/test_frida_manager.py`

- [ ] **Step 1: Write failing allowlist and manager tests**

```python
# services/signer-service/tests/unit/test_security.py
from hongguo_signer.security import filter_security_headers


def test_filter_security_headers_removes_session_data() -> None:
    result = filter_security_headers(
        {
            "X-Argus": "a",
            "x-gorgon": "g",
            "cookie": "secret",
            "x-tt-token": "secret",
        }
    )
    assert result == {"X-Argus": "a", "X-Gorgon": "g"}
```

```python
# services/signer-service/tests/unit/test_frida_manager.py
from hongguo_signer.frida_runtime.manager import normalize_rpc_headers


def test_normalize_rpc_headers_accepts_map_values() -> None:
    assert normalize_rpc_headers({"X-Khronos": "123"}) == {"X-Khronos": "123"}
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
uv run pytest services/signer-service/tests/unit/test_security.py services/signer-service/tests/unit/test_frida_manager.py -q
```

Expected: FAIL because the modules do not exist.

- [ ] **Step 3: Implement header filtering and the Frida manager**

```python
# services/signer-service/src/hongguo_signer/security.py
CANONICAL_SECURITY_HEADERS = {
    "x-argus": "X-Argus",
    "x-gorgon": "X-Gorgon",
    "x-ladon": "X-Ladon",
    "x-khronos": "X-Khronos",
    "x-helios": "X-Helios",
    "x-medusa": "X-Medusa",
    "x-ss-req-ticket": "X-SS-REQ-TICKET",
}


def filter_security_headers(headers: dict[str, str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for key, value in headers.items():
        canonical = CANONICAL_SECURITY_HEADERS.get(key.lower())
        if canonical and value:
            result[canonical] = str(value)
    return result
```

```python
# services/signer-service/src/hongguo_signer/frida_runtime/manager.py
import threading
from pathlib import Path
from typing import Any

import frida

from hongguo_signer.security import filter_security_headers


def normalize_rpc_headers(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        raise TypeError("Frida sign RPC did not return an object")
    return {str(key): str(item) for key, item in value.items() if item is not None}


class FridaManager:
    def __init__(self, endpoint: str, package_name: str, script_path: Path) -> None:
        self.endpoint = endpoint
        self.package_name = package_name
        self.script_path = script_path
        self._lock = threading.RLock()
        self._session = None
        self._script = None
        self._pid: int | None = None

    @property
    def pid(self) -> int:
        if self._pid is None:
            raise RuntimeError("Frida is not attached")
        return self._pid

    def connect(self) -> None:
        with self._lock:
            device = frida.get_device_manager().add_remote_device(self.endpoint)
            process = device.get_process(self.package_name)
            session = device.attach(process.pid)
            script = session.create_script(self.script_path.read_text(encoding="utf-8"))
            script.load()
            self._session = session
            self._script = script
            self._pid = process.pid

    def sign(self, url: str, headers: dict[str, str]) -> dict[str, str]:
        with self._lock:
            if self._script is None:
                self.connect()
            raw = self._script.exports_sync.sign(url, headers)
            return filter_security_headers(normalize_rpc_headers(raw))

    def health(self) -> bool:
        with self._lock:
            if self._script is None:
                return False
            return bool(self._script.exports_sync.health())

    def capture_session(self, timeout_ms: int) -> dict[str, Any]:
        with self._lock:
            if self._script is None:
                self.connect()
            value = self._script.exports_sync.grab(timeout_ms)
            if not isinstance(value, dict):
                raise TypeError("Frida grab RPC did not return an object")
            return value
```

- [ ] **Step 4: Add the Java-layer RPC agent**

```javascript
// services/signer-service/src/hongguo_signer/frida_runtime/oracle.js
var networkParams = null;

function getNetworkParams() {
    if (networkParams === null) {
        networkParams = Java.use(
            "com.bytedance.frameworks.baselib.network.http.NetworkParams"
        );
    }
    return networkParams;
}

function mapToObject(map) {
    var output = {};
    var iterator = map.keySet().iterator();
    while (iterator.hasNext()) {
        var key = iterator.next();
        var value = map.get(key);
        var text = value === null ? null : value.toString();
        if (text && text.charAt(0) === "[" && text.charAt(text.length - 1) === "]") {
            text = text.substring(1, text.length - 1);
        }
        output[key.toString()] = text;
    }
    return output;
}

rpc.exports = {
    health: function () {
        return new Promise(function (resolve, reject) {
            Java.perform(function () {
                try {
                    getNetworkParams();
                    resolve(true);
                } catch (error) {
                    reject(String(error));
                }
            });
        });
    },

    sign: function (url, headersObject) {
        return new Promise(function (resolve, reject) {
            Java.perform(function () {
                try {
                    var HashMap = Java.use("java.util.HashMap");
                    var ArrayList = Java.use("java.util.ArrayList");
                    var headers = HashMap.$new();
                    Object.keys(headersObject).forEach(function (key) {
                        var values = ArrayList.$new();
                        values.add(String(headersObject[key]));
                        headers.put(key, values);
                    });
                    var signed = getNetworkParams().tryAddSecurityFactor(url, headers);
                    resolve(mapToObject(signed));
                } catch (error) {
                    reject(String(error));
                }
            });
        });
    },

    grab: function (timeoutMs) {
        return new Promise(function (resolve, reject) {
            Java.perform(function () {
                var target = getNetworkParams();
                var overload = target.tryAddSecurityFactor.overload(
                    "java.lang.String",
                    "java.util.Map"
                );
                var completed = false;
                overload.implementation = function (url, headers) {
                    var result = overload.call(this, url, headers);
                    if (!completed) {
                        var text = url.toString();
                        var naturalRequest =
                            text.indexOf("fqnovel.com") >= 0 &&
                            text.indexOf("device_id=") >= 0 &&
                            headers.containsKey("x-ss-req-ticket");
                        if (naturalRequest) {
                            completed = true;
                            overload.implementation = null;
                            resolve({url: text, headers: mapToObject(headers)});
                        }
                    }
                    return result;
                };
                setTimeout(function () {
                    if (!completed) {
                        overload.implementation = null;
                        reject("session capture timed out");
                    }
                }, timeoutMs || 30000);
            });
        });
    }
};
```

- [ ] **Step 5: Run offline tests**

Run:

```powershell
uv run pytest services/signer-service/tests/unit/test_security.py services/signer-service/tests/unit/test_frida_manager.py -q
uv run ruff check services/signer-service/src services/signer-service/tests
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add services/signer-service
git commit -m "feat(signer): add Frida signing runtime and RPC agent"
```

---

### Task 4: Add Frida Server Bootstrap and Signer HTTP API

**Files:**
- Create: `services/signer-service/src/hongguo_signer/frida_runtime/bootstrap.py`
- Create: `services/signer-service/src/hongguo_signer/frida_runtime/watchdog.py`
- Create: `services/signer-service/src/hongguo_signer/main.py`
- Create: `services/signer-service/.env.example`
- Create: `services/signer-service/scripts/check_environment.ps1`
- Create: `services/signer-service/scripts/start.ps1`
- Test: `services/signer-service/tests/integration/test_signer_api.py`

- [ ] **Step 1: Write failing Signer API tests with a fake runtime**

```python
# services/signer-service/tests/integration/test_signer_api.py
from fastapi.testclient import TestClient

from hongguo_signer.main import create_app


class FakeRuntime:
    pid = 3318

    def health(self) -> bool:
        return True

    def sign(self, url: str, headers: dict[str, str]) -> dict[str, str]:
        assert url.startswith("https://")
        return {"X-Khronos": "123", "X-Gorgon": "abc"}

    def capture_session(self, timeout_ms: int) -> dict:
        return {
            "url": "https://api.example.test/path?device_id=1&iid=2",
            "headers": {"x-tt-token": "token", "cookie": "cookie"},
        }


def test_sign_endpoint_returns_versioned_contract() -> None:
    client = TestClient(create_app(FakeRuntime(), service_token="test-token"))
    response = client.post(
        "/v1/sign",
        headers={"Authorization": "Bearer test-token"},
        json={"url": "https://example.test/path", "headers": {}},
    )
    assert response.status_code == 200
    assert response.json()["headers"]["X-Gorgon"] == "abc"


def test_sign_endpoint_rejects_missing_token() -> None:
    client = TestClient(create_app(FakeRuntime(), service_token="test-token"))
    response = client.post(
        "/v1/sign",
        json={"url": "https://example.test/path", "headers": {}},
    )
    assert response.status_code == 401
```

- [ ] **Step 2: Run and verify failure**

Run:

```powershell
uv run pytest services/signer-service/tests/integration/test_signer_api.py -q
```

Expected: FAIL because `create_app` does not exist.

- [ ] **Step 3: Implement Frida bootstrap and recovery**

```python
# services/signer-service/src/hongguo_signer/frida_runtime/bootstrap.py
from pathlib import Path

from hongguo_signer.device.adb import AdbClient


def ensure_frida_server(adb: AdbClient, local_binary: Path, remote_path: str) -> None:
    if not adb.shell("pidof frida-server || true"):
        adb.push(local_binary, remote_path)
        adb.shell(f"su -c 'chmod 755 {remote_path}'")
        adb.shell(f"su -c 'nohup {remote_path} >/data/local/tmp/frida.log 2>&1 &'")
    adb.forward("tcp:27042", "tcp:27042")
```

```python
# services/signer-service/src/hongguo_signer/frida_runtime/watchdog.py
import threading
import time
from collections.abc import Callable


class Watchdog:
    def __init__(self, check: Callable[[], bool], recover: Callable[[], None]) -> None:
        self.check = check
        self.recover = recover
        self.stop_event = threading.Event()

    def run(self) -> None:
        while not self.stop_event.wait(15):
            try:
                if not self.check():
                    self.recover()
            except Exception:
                self.recover()

    def start(self) -> threading.Thread:
        thread = threading.Thread(target=self.run, daemon=True, name="signer-watchdog")
        thread.start()
        return thread
```

- [ ] **Step 4: Implement the authenticated FastAPI service**

```python
# services/signer-service/src/hongguo_signer/main.py
from datetime import datetime, timezone
from typing import Protocol

from fastapi import Depends, FastAPI, Header, HTTPException

from hongguo_contracts.signer import SignRequest, SignResponse


class Runtime(Protocol):
    pid: int

    def health(self) -> bool: ...
    def sign(self, url: str, headers: dict[str, str]) -> dict[str, str]: ...
    def capture_session(self, timeout_ms: int) -> dict: ...


def create_app(runtime: Runtime, service_token: str) -> FastAPI:
    app = FastAPI(title="Hongguo Signer Service", version="1.0")

    def authorize(authorization: str | None = Header(default=None)) -> None:
        if authorization != f"Bearer {service_token}":
            raise HTTPException(status_code=401, detail="invalid service token")

    @app.get("/v1/health")
    def health() -> dict:
        return {"ready": runtime.health(), "app_pid": runtime.pid}

    @app.post("/v1/sign", response_model=SignResponse, dependencies=[Depends(authorize)])
    def sign(request: SignRequest) -> SignResponse:
        headers = runtime.sign(str(request.url), request.headers)
        return SignResponse(
            headers=headers,
            app_pid=runtime.pid,
            signed_at=datetime.now(timezone.utc),
        )

    @app.post("/v1/session/capture", dependencies=[Depends(authorize)])
    def capture_session() -> dict:
        return runtime.capture_session(30000)

    return app
```

```dotenv
# services/signer-service/.env.example
HONGGUO_SIGNER_MUMU_HOME=D:\MuMu Player 12
HONGGUO_SIGNER_VMINDEX=0
HONGGUO_SIGNER_PACKAGE_NAME=com.phoenix.read
HONGGUO_SIGNER_SERVICE_TOKEN=local-development
```

- [ ] **Step 5: Add local scripts**

```powershell
# services/signer-service/scripts/check_environment.ps1
$ErrorActionPreference = "Stop"
$mumu = "D:\MuMu Player 12\nx_main\mumu-cli.exe"
$adb = "D:\MuMu Player 12\shell\adb.exe"
& $mumu version
& $mumu info --vmindex 0
& $adb connect 127.0.0.1:16384
& $adb -s 127.0.0.1:16384 shell "su -c id"
& $adb -s 127.0.0.1:16384 shell "pidof com.phoenix.read"
```

```powershell
# services/signer-service/scripts/start.ps1
$ErrorActionPreference = "Stop"
uv run --project services/signer-service `
  uvicorn hongguo_signer.bootstrap_app:app --host 127.0.0.1 --port 18001
```

- [ ] **Step 6: Run tests**

Run:

```powershell
uv run pytest services/signer-service/tests/integration/test_signer_api.py -q
uv run ruff check services/signer-service
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add services/signer-service
git commit -m "feat(signer): expose authenticated signing service"
```

---

### Task 5: Capture and Persist the Logged-In Session

**Files:**
- Modify: `pyproject.toml`
- Create: `services/api-server/pyproject.toml`
- Create: `services/api-server/src/hongguo_api/config.py`
- Create: `services/api-server/src/hongguo_api/session/storage.py`
- Create: `services/api-server/src/hongguo_api/signer/client.py`
- Test: `services/api-server/tests/unit/test_session_storage.py`
- Test: `services/api-server/tests/integration/test_signer_client.py`

- [ ] **Step 1: Write failing storage tests**

```python
# services/api-server/tests/unit/test_session_storage.py
from datetime import datetime, timezone

from hongguo_contracts.signer import SessionSnapshot
from hongguo_api.session.storage import SessionStore


def test_session_store_round_trips_without_field_loss(tmp_path) -> None:
    store = SessionStore(tmp_path / "session.json")
    snapshot = SessionSnapshot(
        api_host="api5-normal-sinfonlinea.fqnovel.com",
        base_query={"device_id": "1", "iid": "2"},
        session_headers={"x-tt-token": "token", "cookie": "cookie"},
        captured_at=datetime.now(timezone.utc),
    )
    store.save(snapshot)
    assert store.load() == snapshot
```

- [ ] **Step 2: Run and verify failure**

Run:

```powershell
uv run pytest services/api-server/tests/unit/test_session_storage.py -q
```

Expected: FAIL because `hongguo_api` does not exist.

- [ ] **Step 3: Add API Server package and settings**

Update the root workspace membership:

```toml
[tool.uv.workspace]
members = [
  "packages/hongguo-contracts",
  "services/signer-service",
  "services/api-server",
]
```

```toml
# services/api-server/pyproject.toml
[project]
name = "hongguo-api-server"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
  "cachetools>=5.5",
  "fastapi>=0.115",
  "hongguo-contracts",
  "httpx>=0.28",
  "pydantic-settings>=2.7",
  "uvicorn>=0.34",
]

[tool.uv.sources]
hongguo-contracts = { workspace = true }

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

```python
# services/api-server/src/hongguo_api/config.py
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class ApiSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="HONGGUO_API_", extra="ignore")

    signer_url: str = "http://127.0.0.1:18001"
    signer_token: str = "local-development"
    session_file: Path = Path(".local/session.json")
    timeout_seconds: float = 30.0
```

- [ ] **Step 4: Implement session persistence and Signer client**

```python
# services/api-server/src/hongguo_api/session/storage.py
import json
from pathlib import Path

from hongguo_contracts.signer import SessionSnapshot


class SessionStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def save(self, snapshot: SessionSnapshot) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(".tmp")
        temp.write_text(snapshot.model_dump_json(indent=2), encoding="utf-8")
        temp.replace(self.path)

    def load(self) -> SessionSnapshot:
        data = json.loads(self.path.read_text(encoding="utf-8"))
        return SessionSnapshot.model_validate(data)
```

```python
# services/api-server/src/hongguo_api/signer/client.py
import httpx

from hongguo_contracts.signer import SignRequest, SignResponse


class SignerClient:
    def __init__(self, base_url: str, token: str, client: httpx.AsyncClient) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.client = client

    async def sign(self, url: str, headers: dict[str, str]) -> dict[str, str]:
        request = SignRequest(url=url, headers=headers)
        response = await self.client.post(
            f"{self.base_url}/v1/sign",
            headers={"Authorization": f"Bearer {self.token}"},
            json=request.model_dump(mode="json"),
        )
        response.raise_for_status()
        return SignResponse.model_validate(response.json()).headers
```

- [ ] **Step 5: Add and run Signer client integration test**

```python
# services/api-server/tests/integration/test_signer_client.py
import httpx
import respx

from hongguo_api.signer.client import SignerClient


@respx.mock
async def test_signer_client_uses_versioned_endpoint_and_token() -> None:
    route = respx.post("http://signer.test/v1/sign").mock(
        return_value=httpx.Response(
            200,
            json={
                "headers": {"X-Khronos": "123"},
                "app_pid": 42,
                "signed_at": "2026-06-12T00:00:00Z",
            },
        )
    )
    async with httpx.AsyncClient() as client:
        signer = SignerClient("http://signer.test", "token", client)
        assert await signer.sign("https://upstream.test/path", {}) == {
            "X-Khronos": "123"
        }
    assert route.calls[0].request.headers["authorization"] == "Bearer token"
```

Run:

```powershell
uv sync --all-packages
uv run pytest services/api-server/tests/unit/test_session_storage.py services/api-server/tests/integration/test_signer_client.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add services/api-server
git commit -m "feat(api): persist session snapshots and call signer service"
```

---

### Task 6: Implement Deterministic Signed Upstream Transport

**Files:**
- Create: `services/api-server/src/hongguo_api/errors.py`
- Create: `services/api-server/src/hongguo_api/upstream/transport.py`
- Test: `services/api-server/tests/unit/test_transport.py`

- [ ] **Step 1: Write failing serialization and signing-order tests**

```python
# services/api-server/tests/unit/test_transport.py
import hashlib

import httpx
import respx

from hongguo_contracts.signer import SessionSnapshot
from hongguo_api.upstream.transport import SignedTransport, compact_json


def test_compact_json_is_deterministic_utf8() -> None:
    body = compact_json({"title": "红果", "enabled": True})
    assert body == '{"title":"红果","enabled":true}'.encode()


@respx.mock
async def test_transport_signs_exact_url_and_body() -> None:
    signed: dict = {}

    class FakeSigner:
        async def sign(self, url: str, headers: dict[str, str]) -> dict[str, str]:
            signed["url"] = url
            signed["stub"] = headers["x-ss-stub"]
            return {"X-Khronos": "123"}

    route = respx.post(url__startswith="https://api.example.test/path").mock(
        return_value=httpx.Response(200, json={"code": 0})
    )
    snapshot = SessionSnapshot.model_validate(
        {
            "api_host": "api.example.test",
            "base_query": {"device_id": "1", "aid": "8662"},
            "session_headers": {"x-tt-token": "token"},
            "captured_at": "2026-06-12T00:00:00Z",
        }
    )
    async with httpx.AsyncClient() as client:
        transport = SignedTransport(snapshot, FakeSigner(), client)
        await transport.request("POST", "/path", body={"a": 1}, query={"q": "x"})
    expected = hashlib.md5(b'{"a":1}').hexdigest().upper()
    assert signed["stub"] == expected
    assert "device_id=1" in signed["url"]
    assert route.called
```

- [ ] **Step 2: Run and verify failure**

Run:

```powershell
uv run pytest services/api-server/tests/unit/test_transport.py -q
```

Expected: FAIL because `SignedTransport` does not exist.

- [ ] **Step 3: Implement stable errors and transport**

```python
# services/api-server/src/hongguo_api/errors.py
class HongguoError(RuntimeError):
    code = "hongguo_error"


class SessionExpiredError(HongguoError):
    code = "session_expired"


class RiskControlledError(HongguoError):
    code = "risk_controlled"


class UpstreamInvalidResponseError(HongguoError):
    code = "upstream_invalid_response"
```

```python
# services/api-server/src/hongguo_api/upstream/transport.py
import hashlib
import json
import time
from typing import Any, Protocol
from urllib.parse import urlencode

import httpx

from hongguo_contracts.signer import SessionSnapshot
from hongguo_api.errors import UpstreamInvalidResponseError


class Signer(Protocol):
    async def sign(self, url: str, headers: dict[str, str]) -> dict[str, str]: ...


def compact_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")


class SignedTransport:
    def __init__(
        self,
        session: SessionSnapshot,
        signer: Signer,
        client: httpx.AsyncClient,
    ) -> None:
        self.session = session
        self.signer = signer
        self.client = client

    def build_url(self, path: str, query: dict[str, str] | None) -> str:
        params = dict(self.session.base_query)
        params.update(query or {})
        params["_rticket"] = str(int(time.time() * 1000))
        return f"https://{self.session.api_host}{path}?{urlencode(params)}"

    async def request(
        self,
        method: str,
        path: str,
        *,
        body: Any | None = None,
        query: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        url = self.build_url(path, query)
        headers = dict(self.session.session_headers)
        headers["content-type"] = "application/json; charset=utf-8"
        content = compact_json(body) if body is not None else None
        if content is not None:
            headers["x-ss-stub"] = hashlib.md5(content).hexdigest().upper()
        headers.update(await self.signer.sign(url, headers))
        response = await self.client.request(method, url, headers=headers, content=content)
        response.raise_for_status()
        value = response.json()
        if not isinstance(value, dict):
            raise UpstreamInvalidResponseError("upstream JSON root is not an object")
        return value
```

- [ ] **Step 4: Run tests**

Run:

```powershell
uv run pytest services/api-server/tests/unit/test_transport.py -q
uv run ruff check services/api-server/src/hongguo_api/upstream services/api-server/tests/unit/test_transport.py
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add services/api-server
git commit -m "feat(api): add deterministic signed upstream transport"
```

---

### Task 7: Implement Search, Latest, and Ranking Parsers and Client Methods

**Files:**
- Create: `services/api-server/src/hongguo_api/models.py`
- Create: `services/api-server/src/hongguo_api/parsers/search.py`
- Create: `services/api-server/src/hongguo_api/parsers/latest.py`
- Create: `services/api-server/src/hongguo_api/parsers/rank.py`
- Create: `services/api-server/src/hongguo_api/upstream/client.py`
- Create: `services/api-server/tests/fixtures/search.json`
- Create: `services/api-server/tests/fixtures/latest.json`
- Create: `services/api-server/tests/fixtures/rank.json`
- Test: `services/api-server/tests/unit/test_list_parsers.py`

- [ ] **Step 1: Add sanitized fixture fragments**

```json
// services/api-server/tests/fixtures/search.json
{
  "search_tabs": [{
    "next_offset": 20,
    "passback": "pass",
    "search_id": "search",
    "has_more": true,
    "data": [{
      "book_id": "100",
      "video_detail": {"episode_cnt": 10, "series_title": "测试短剧"},
      "video_data": {"cover": "https://img.test/1", "copyright": "测试版权"}
    }]
  }]
}
```

```json
// services/api-server/tests/fixtures/latest.json
{
  "data": {
    "has_more": false,
    "video_data": [{
      "series_id": "100",
      "title": "今日短剧",
      "episode_cnt": 12,
      "sub_title_list": [{"content": "今日上新"}],
      "category_schema": "[{\"name\":\"都市\"}]"
    }]
  }
}
```

```json
// services/api-server/tests/fixtures/rank.json
{
  "data": {
    "cell_view": {
      "has_more": false,
      "cell_data": [{
        "video_data": [{
          "series_id": "100",
          "vid": "101",
          "title": "榜单短剧",
          "episode_cnt": 20,
          "play_cnt": 300
        }]
      }]
    }
  }
}
```

- [ ] **Step 2: Write failing parser tests**

```python
# services/api-server/tests/unit/test_list_parsers.py
import json
from pathlib import Path

from hongguo_api.parsers.latest import parse_latest
from hongguo_api.parsers.rank import parse_rank
from hongguo_api.parsers.search import parse_search

FIXTURES = Path(__file__).parents[1] / "fixtures"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_search_parser_preserves_cursor_state() -> None:
    page = parse_search(load("search.json"))
    assert page.items[0].series_id == "100"
    assert page.next_cursor is not None


def test_latest_parser_uses_official_today_label() -> None:
    page = parse_latest(load("latest.json"), today_only=True)
    assert page.items[0].is_today is True


def test_rank_parser_flattens_cell_video_data() -> None:
    page = parse_rank(load("rank.json"))
    assert page.items[0].video_id == "101"
```

- [ ] **Step 3: Run and verify failure**

Run:

```powershell
uv run pytest services/api-server/tests/unit/test_list_parsers.py -q
```

Expected: FAIL because parsers and models do not exist.

- [ ] **Step 4: Implement shared list models and parsers**

```python
# services/api-server/src/hongguo_api/models.py
from pydantic import BaseModel, Field


class DramaItem(BaseModel):
    series_id: str
    video_id: str | None = None
    title: str
    episode_count: int = 0
    play_count: int = 0
    cover: str = ""
    copyright: str = ""
    categories: list[str] = Field(default_factory=list)
    is_today: bool = False


class DramaPage(BaseModel):
    items: list[DramaItem]
    next_cursor: str | None = None
    has_more: bool = False
```

```python
# services/api-server/src/hongguo_api/parsers/search.py
import base64
import json

from hongguo_api.models import DramaItem, DramaPage


def parse_search(payload: dict) -> DramaPage:
    tabs = payload.get("search_tabs") or []
    tab = tabs[0] if tabs else {}
    items: list[DramaItem] = []
    for cell in tab.get("data") or []:
        detail = cell.get("video_detail") or {}
        video = cell.get("video_data") or {}
        series_id = cell.get("book_id") or cell.get("search_result_id")
        if not series_id:
            continue
        items.append(
            DramaItem(
                series_id=str(series_id),
                title=detail.get("series_title") or video.get("title") or "",
                episode_count=int(detail.get("episode_cnt") or video.get("episode_cnt") or 0),
                cover=video.get("cover") or "",
                copyright=video.get("copyright") or "",
            )
        )
    state = {
        "offset": tab.get("next_offset"),
        "passback": tab.get("passback"),
        "search_id": tab.get("search_id"),
    }
    cursor = None
    if tab.get("has_more"):
        cursor = base64.urlsafe_b64encode(
            json.dumps(state, separators=(",", ":")).encode()
        ).decode()
    return DramaPage(items=items, next_cursor=cursor, has_more=bool(tab.get("has_more")))
```

```python
# services/api-server/src/hongguo_api/parsers/latest.py
import json

from hongguo_api.models import DramaItem, DramaPage


def parse_latest(payload: dict, today_only: bool) -> DramaPage:
    data = payload.get("data") or {}
    items: list[DramaItem] = []
    for value in data.get("video_data") or []:
        labels = [item.get("content") for item in value.get("sub_title_list") or []]
        is_today = "今日上新" in labels
        if today_only and not is_today:
            continue
        categories = [
            item.get("name", "")
            for item in json.loads(value.get("category_schema") or "[]")
            if item.get("name")
        ]
        items.append(
            DramaItem(
                series_id=str(value["series_id"]),
                title=value.get("title") or "",
                episode_count=int(value.get("episode_cnt") or 0),
                cover=value.get("cover") or "",
                copyright=value.get("copyright") or "",
                categories=categories,
                is_today=is_today,
            )
        )
    return DramaPage(items=items, has_more=bool(data.get("has_more")))
```

```python
# services/api-server/src/hongguo_api/parsers/rank.py
from hongguo_api.models import DramaItem, DramaPage


def parse_rank(payload: dict) -> DramaPage:
    view = ((payload.get("data") or {}).get("cell_view") or {})
    items: list[DramaItem] = []
    for cell in view.get("cell_data") or []:
        for value in cell.get("video_data") or []:
            if not value.get("series_id"):
                continue
            items.append(
                DramaItem(
                    series_id=str(value["series_id"]),
                    video_id=str(value["vid"]) if value.get("vid") else None,
                    title=value.get("title") or "",
                    episode_count=int(value.get("episode_cnt") or 0),
                    play_count=int(value.get("play_cnt") or 0),
                    cover=value.get("cover") or "",
                    copyright=value.get("copyright") or "",
                )
            )
    return DramaPage(items=items, has_more=bool(view.get("has_more")))
```

- [ ] **Step 5: Implement upstream endpoint methods**

```python
# services/api-server/src/hongguo_api/upstream/client.py
import uuid

from hongguo_api.parsers.latest import parse_latest
from hongguo_api.parsers.rank import parse_rank
from hongguo_api.parsers.search import parse_search
from hongguo_api.upstream.transport import SignedTransport


class HongguoClient:
    def __init__(self, transport: SignedTransport) -> None:
        self.transport = transport

    async def search(self, query: str) -> object:
        payload = await self.transport.request(
            "GET",
            "/reading/bookapi/search/tab/v",
            query={
                "query": query,
                "tab_name": "feed",
                "search_source": "1",
                "offset": "0",
                "count": "0",
                "use_correct": "true",
            },
        )
        return parse_search(payload)

    async def latest(self, genre: str, today_only: bool) -> object:
        payload = await self.transport.request(
            "POST",
            "/reading/distribution/category/landpage/v",
            body={
                "filter_ids": "",
                "req_scene": "default" if genre == "short_play" else genre,
                "offset": 0,
                "need_selector_panel": False,
                "limit": 18,
                "select_items": {
                    "category_dim_epoch": [],
                    "online_time": [] if genre == "short_play" else ["days_7"],
                    "gender": [],
                    "category_dim_role": [],
                    "genre": [genre],
                    "sort": ["online_time"],
                    "category_dim_theme": [],
                },
                "session_id": "",
                "req_type": "only_content",
                "client_req_type": 3,
            },
        )
        return parse_latest(payload, today_only=today_only)

    async def rank(self, board: str) -> object:
        mapping = {
            "recommend": "comic_series_hot_rank",
            "hot": "comic_series_hot_play",
            "new": "comic_series_new_rank",
        }
        payload = await self.transport.request(
            "GET",
            "/reading/bookapi/bookmall/cell/change/v",
            query={
                "cell_id": "7470092475068071998",
                "tab_type": "26",
                "client_req_type": "2",
                "client_template": "2",
                "selected_items": "comic_series_rank",
                "sub_selected_items": mapping[board],
                "session_uuid": str(uuid.uuid4()),
            },
        )
        return parse_rank(payload)
```

- [ ] **Step 6: Run tests and commit**

Run:

```powershell
uv run pytest services/api-server/tests/unit/test_list_parsers.py -q
uv run ruff check services/api-server
```

Expected: PASS.

```powershell
git add services/api-server
git commit -m "feat(api): parse search latest and ranking responses"
```

---

### Task 8: Implement Series Detail, Episode, and Video-Model Parsing

**Files:**
- Create: `services/api-server/src/hongguo_api/parsers/detail.py`
- Create: `services/api-server/src/hongguo_api/parsers/video.py`
- Create: `services/api-server/tests/fixtures/detail.json`
- Create: `services/api-server/tests/fixtures/video_model.json`
- Test: `services/api-server/tests/unit/test_detail_video_parsers.py`
- Modify: `services/api-server/src/hongguo_api/upstream/client.py`

- [ ] **Step 1: Add sanitized fixtures and failing tests**

```json
// services/api-server/tests/fixtures/detail.json
{
  "data": {
    "100": {
      "video_data": {
        "series_title": "详情短剧",
        "episode_cnt": 2,
        "video_list": [
          {"vid": "101", "vid_index": 1, "title": "第1集", "duration": 60},
          {"vid": "102", "vid_index": 2, "title": "第2集", "duration": 61}
        ]
      }
    }
  }
}
```

```json
// services/api-server/tests/fixtures/video_model.json
{
  "data": {
    "101": {
      "video_model": "{\"video_list\":[{\"video_id\":\"v-low\",\"main_url\":\"https://video.test/720\",\"video_meta\":{\"definition\":\"720p\",\"height\":1280,\"bitrate\":800,\"size\":100}},{\"video_id\":\"v-high\",\"main_url\":\"https://video.test/1080\",\"video_meta\":{\"definition\":\"1080p\",\"height\":1920,\"bitrate\":1500,\"size\":200},\"encrypt_info\":{\"encrypt\":false}}]}"
    }
  }
}
```

```python
# services/api-server/tests/unit/test_detail_video_parsers.py
import json
from pathlib import Path

from hongguo_api.parsers.detail import parse_detail
from hongguo_api.parsers.video import EncryptedStreamError, parse_video_model

FIXTURES = Path(__file__).parents[1] / "fixtures"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_detail_parser_orders_episodes() -> None:
    detail = parse_detail(load("detail.json"), "100")
    assert [item.index for item in detail.episodes] == [1, 2]
    assert detail.episodes[0].video_id == "101"


def test_video_parser_selects_requested_quality() -> None:
    video = parse_video_model(load("video_model.json"), "101", "1080p")
    assert video.vod_id == "v-high"
    assert video.url == "https://video.test/1080"


def test_video_parser_rejects_only_encrypted_candidates() -> None:
    payload = {
        "data": {
            "101": {
                "video_model": json.dumps(
                    {
                        "video_list": [
                            {
                                "video_id": "v",
                                "main_url": "https://video.test/e",
                                "video_meta": {"definition": "1080p"},
                                "encrypt_info": {"encrypt": True},
                            }
                        ]
                    }
                )
            }
        }
    }
    try:
        parse_video_model(payload, "101", "1080p")
    except EncryptedStreamError:
        return
    raise AssertionError("expected EncryptedStreamError")
```

- [ ] **Step 2: Run and verify failure**

Run:

```powershell
uv run pytest services/api-server/tests/unit/test_detail_video_parsers.py -q
```

Expected: FAIL because parsers do not exist.

- [ ] **Step 3: Implement detail and video parsers**

```python
# services/api-server/src/hongguo_api/parsers/detail.py
from pydantic import BaseModel


class Episode(BaseModel):
    index: int
    video_id: str
    title: str
    duration: int | None = None
    cover: str = ""


class SeriesDetail(BaseModel):
    series_id: str
    title: str
    episode_count: int
    intro: str = ""
    cover: str = ""
    episodes: list[Episode]


def parse_detail(payload: dict, series_id: str) -> SeriesDetail:
    data = ((payload.get("data") or {}).get(str(series_id)) or {}).get("video_data") or {}
    episodes = [
        Episode(
            index=int(item.get("vid_index") or 0),
            video_id=str(item["vid"]),
            title=item.get("title") or "",
            duration=item.get("duration"),
            cover=item.get("episode_cover") or item.get("cover") or "",
        )
        for item in data.get("video_list") or []
        if item.get("vid")
    ]
    episodes.sort(key=lambda item: item.index)
    return SeriesDetail(
        series_id=str(series_id),
        title=data.get("series_title") or str(series_id),
        episode_count=int(data.get("episode_cnt") or len(episodes)),
        intro=data.get("series_intro") or "",
        cover=data.get("series_cover") or "",
        episodes=episodes,
    )
```

```python
# services/api-server/src/hongguo_api/parsers/video.py
import json

from pydantic import BaseModel


class EncryptedStreamError(RuntimeError):
    pass


class VideoResult(BaseModel):
    video_id: str
    vod_id: str
    requested_quality: str
    selected_quality: str
    url: str
    backup_url: str | None = None
    encrypted: bool = False


def _quality_value(value: str) -> int:
    digits = "".join(character for character in value if character.isdigit())
    return int(digits or 0)


def parse_video_model(payload: dict, video_id: str, quality: str) -> VideoResult:
    wrapper = (payload.get("data") or {}).get(str(video_id)) or {}
    model = json.loads(wrapper.get("video_model") or "{}")
    candidates = [
        item
        for item in model.get("video_list") or []
        if item.get("main_url")
    ]
    unencrypted = [
        item for item in candidates if not (item.get("encrypt_info") or {}).get("encrypt")
    ]
    if candidates and not unencrypted:
        raise EncryptedStreamError(video_id)
    target = _quality_value(quality)
    exact = [
        item
        for item in unencrypted
        if (item.get("video_meta") or {}).get("definition") == quality
    ]
    pool = exact or [
        item
        for item in unencrypted
        if _quality_value((item.get("video_meta") or {}).get("definition", "")) <= target
    ] or unencrypted
    selected = max(
        pool,
        key=lambda item: (
            _quality_value((item.get("video_meta") or {}).get("definition", "")),
            int((item.get("video_meta") or {}).get("bitrate") or 0),
        ),
    )
    meta = selected.get("video_meta") or {}
    return VideoResult(
        video_id=str(video_id),
        vod_id=str(selected.get("video_id") or ""),
        requested_quality=quality,
        selected_quality=meta.get("definition") or "unknown",
        url=selected["main_url"],
        backup_url=selected.get("backup_url"),
    )
```

- [ ] **Step 4: Add detail and video methods to `HongguoClient`**

```python
# add these imports at the top of services/api-server/src/hongguo_api/upstream/client.py
from hongguo_api.parsers.detail import parse_detail
from hongguo_api.parsers.video import parse_video_model


# add these methods inside the existing HongguoClient class
async def detail(self, series_id: str) -> object:
    payload = await self.transport.request(
        "POST",
        "/novel/player/multi_video_detail/v1/",
        body={
            "biz_param": {
                "detail_page_version": 0,
                "disable_digg_stat": False,
                "disable_video_relate_book": False,
                "need_all_video_definition": False,
                "need_mp4_align": False,
                "screen_width_px": "900",
                "source": 7,
                "use_os_player": False,
                "use_server_dns": False,
            },
            "series_id": str(series_id),
        },
    )
    return parse_detail(payload, series_id)


async def resolve_video(self, video_id: str, quality: str) -> object:
    payload = await self.transport.request(
        "POST",
        "/novel/player/multi_video_model/v1/",
        body={
            "biz_param": {
                "detail_page_version": 0,
                "device_level": 3,
                "disable_digg_stat": False,
                "disable_video_relate_book": False,
                "need_all_video_definition": True,
                "need_mp4_align": False,
                "use_os_player": False,
                "use_server_dns": False,
                "video_platform": 1024,
            },
            "mixed_video_id_map": {"1": [str(video_id)]},
        },
    )
    return parse_video_model(payload, video_id, quality)
```

Indent both methods by four spaces so they are members of the existing
`HongguoClient` class. Keep the two parser imports with the existing imports.

- [ ] **Step 5: Run tests and commit**

Run:

```powershell
uv run pytest services/api-server/tests/unit/test_detail_video_parsers.py -q
uv run ruff check services/api-server
```

Expected: PASS.

```powershell
git add services/api-server
git commit -m "feat(api): parse series details and video models"
```

---

### Task 9: Expose the Local Business API

**Files:**
- Create: `services/api-server/src/hongguo_api/api/schemas.py`
- Create: `services/api-server/src/hongguo_api/api/routes.py`
- Create: `services/api-server/src/hongguo_api/main.py`
- Create: `services/api-server/.env.example`
- Create: `services/api-server/scripts/start.ps1`
- Test: `services/api-server/tests/integration/test_routes.py`

- [ ] **Step 1: Write failing route tests with a fake Hongguo client**

```python
# services/api-server/tests/integration/test_routes.py
from fastapi.testclient import TestClient

from hongguo_api.main import create_app
from hongguo_api.models import DramaItem, DramaPage


class FakeHongguo:
    async def search(self, query: str) -> DramaPage:
        return DramaPage(items=[DramaItem(series_id="1", title=query)])

    async def latest(self, genre: str, today_only: bool) -> DramaPage:
        return DramaPage(items=[])

    async def rank(self, board: str) -> DramaPage:
        return DramaPage(items=[])

    async def detail(self, series_id: str):
        return {"series_id": series_id, "episodes": []}

    async def resolve_video(self, video_id: str, quality: str):
        return {"video_id": video_id, "requested_quality": quality}


def test_search_route_wraps_result() -> None:
    client = TestClient(create_app(FakeHongguo()))
    response = client.get("/api/search", params={"q": "测试"})
    assert response.status_code == 200
    assert response.json()["data"]["items"][0]["title"] == "测试"


def test_health_route_is_available() -> None:
    client = TestClient(create_app(FakeHongguo()))
    assert client.get("/health").json()["server"] == "ready"
```

- [ ] **Step 2: Run and verify failure**

Run:

```powershell
uv run pytest services/api-server/tests/integration/test_routes.py -q
```

Expected: FAIL because `create_app` does not exist.

- [ ] **Step 3: Implement response schema and routes**

```python
# services/api-server/src/hongguo_api/api/schemas.py
from typing import Any

from pydantic import BaseModel


class ApiResponse(BaseModel):
    code: int = 200
    message: str = "success"
    data: Any
    cached: bool = False
    request_id: str
```

```python
# services/api-server/src/hongguo_api/api/routes.py
import uuid
from typing import Protocol

from fastapi import APIRouter, Query

from hongguo_api.api.schemas import ApiResponse


class HongguoService(Protocol):
    async def search(self, query: str): ...
    async def latest(self, genre: str, today_only: bool): ...
    async def rank(self, board: str): ...
    async def detail(self, series_id: str): ...
    async def resolve_video(self, video_id: str, quality: str): ...


def build_router(service: HongguoService) -> APIRouter:
    router = APIRouter()

    def response(data) -> ApiResponse:
        return ApiResponse(data=data, request_id=str(uuid.uuid4()))

    @router.get("/health")
    async def health() -> dict:
        return {"server": "ready"}

    @router.get("/api/search", response_model=ApiResponse)
    async def search(q: str = Query(min_length=1, max_length=100)) -> ApiResponse:
        return response(await service.search(q))

    @router.get("/api/latest", response_model=ApiResponse)
    async def latest(
        genre: str = "short_play",
        today_only: bool = True,
    ) -> ApiResponse:
        return response(await service.latest(genre, today_only))

    @router.get("/api/rank", response_model=ApiResponse)
    async def rank(board: str = "hot") -> ApiResponse:
        return response(await service.rank(board))

    @router.get("/api/books/{series_id}", response_model=ApiResponse)
    async def detail(series_id: str) -> ApiResponse:
        return response(await service.detail(series_id))

    @router.get("/api/books/{series_id}/episodes", response_model=ApiResponse)
    async def episodes(series_id: str) -> ApiResponse:
        detail_value = await service.detail(series_id)
        episodes_value = (
            detail_value.episodes
            if hasattr(detail_value, "episodes")
            else detail_value["episodes"]
        )
        return response(episodes_value)

    @router.get("/api/videos/{video_id}", response_model=ApiResponse)
    async def video(video_id: str, quality: str = "1080p") -> ApiResponse:
        return response(await service.resolve_video(video_id, quality))

    return router
```

```python
# services/api-server/src/hongguo_api/main.py
from fastapi import FastAPI

from hongguo_api.api.routes import HongguoService, build_router


def create_app(service: HongguoService) -> FastAPI:
    app = FastAPI(title="Hongguo Local API", version="1.0")
    app.include_router(build_router(service))
    return app
```

- [ ] **Step 4: Add environment and startup files**

```dotenv
# services/api-server/.env.example
HONGGUO_API_SIGNER_URL=http://127.0.0.1:18001
HONGGUO_API_SIGNER_TOKEN=local-development
HONGGUO_API_SESSION_FILE=.local/session.json
HONGGUO_API_TIMEOUT_SECONDS=30
```

```powershell
# services/api-server/scripts/start.ps1
$ErrorActionPreference = "Stop"
uv run --project services/api-server `
  uvicorn hongguo_api.bootstrap_app:app --host 127.0.0.1 --port 18000
```

- [ ] **Step 5: Run tests and commit**

Run:

```powershell
uv run pytest services/api-server/tests/integration/test_routes.py -q
uv run ruff check services/api-server
```

Expected: PASS.

```powershell
git add services/api-server
git commit -m "feat(api): expose local Hongguo HTTP routes"
```

---

### Task 10: Wire Production Composition, Caching, and Error Mapping

**Files:**
- Create: `services/signer-service/src/hongguo_signer/bootstrap_app.py`
- Create: `services/api-server/src/hongguo_api/bootstrap_app.py`
- Create: `services/api-server/src/hongguo_api/cache.py`
- Modify: `services/api-server/src/hongguo_api/main.py`
- Modify: `services/api-server/src/hongguo_api/api/routes.py`
- Test: `services/api-server/tests/integration/test_error_mapping.py`

- [ ] **Step 1: Write failing encrypted-stream error mapping test**

```python
# services/api-server/tests/integration/test_error_mapping.py
from fastapi.testclient import TestClient

from hongguo_api.main import create_app
from hongguo_api.parsers.video import EncryptedStreamError


class FailingService:
    async def resolve_video(self, video_id: str, quality: str):
        raise EncryptedStreamError(video_id)


def test_encrypted_stream_maps_to_422() -> None:
    client = TestClient(create_app(FailingService()))
    response = client.get("/api/videos/1")
    assert response.status_code == 422
    assert response.json()["code"] == "encrypted_stream_unsupported"
```

- [ ] **Step 2: Run and verify failure**

Run:

```powershell
uv run pytest services/api-server/tests/integration/test_error_mapping.py -q
```

Expected: FAIL because the exception is not mapped.

- [ ] **Step 3: Add exception mapping**

```python
# add to services/api-server/src/hongguo_api/main.py
from fastapi import Request
from fastapi.responses import JSONResponse

from hongguo_api.parsers.video import EncryptedStreamError


@app.exception_handler(EncryptedStreamError)
async def encrypted_stream_handler(
    request: Request,
    error: EncryptedStreamError,
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "code": "encrypted_stream_unsupported",
            "message": "encrypted stream is not supported",
            "request_id": request.headers.get("x-request-id"),
        },
    )
```

Insert the handler inside `create_app` before returning the app.

- [ ] **Step 4: Compose the real Signer runtime**

```python
# services/signer-service/src/hongguo_signer/bootstrap_app.py
from pathlib import Path

from hongguo_signer.config import SignerSettings
from hongguo_signer.frida_runtime.manager import FridaManager
from hongguo_signer.main import create_app

settings = SignerSettings()
runtime = FridaManager(
    endpoint=f"{settings.frida_host}:{settings.frida_port}",
    package_name=settings.package_name,
    script_path=Path(__file__).parent / "frida_runtime" / "oracle.js",
)
runtime.connect()
app = create_app(runtime, settings.service_token)
```

- [ ] **Step 5: Compose the real API runtime**

```python
# services/api-server/src/hongguo_api/bootstrap_app.py
import httpx

from hongguo_api.config import ApiSettings
from hongguo_api.main import create_app
from hongguo_api.session.storage import SessionStore
from hongguo_api.signer.client import SignerClient
from hongguo_api.upstream.client import HongguoClient
from hongguo_api.upstream.transport import SignedTransport

settings = ApiSettings()
http_client = httpx.AsyncClient(timeout=settings.timeout_seconds)
session = SessionStore(settings.session_file).load()
signer = SignerClient(settings.signer_url, settings.signer_token, http_client)
transport = SignedTransport(session, signer, http_client)
service = HongguoClient(transport)
app = create_app(service)
```

- [ ] **Step 6: Run the complete offline suite**

Run:

```powershell
uv run pytest -q
uv run ruff check .
```

Expected: all offline tests PASS.

- [ ] **Step 7: Commit**

```powershell
git add services
git commit -m "feat: compose signer and API services"
```

---

### Task 11: Add Opt-In Live Signer and Upstream Tests

**Files:**
- Create: `services/signer-service/tests/live/conftest.py`
- Create: `services/signer-service/tests/live/test_signer_live.py`
- Create: `services/api-server/tests/live/test_search_live.py`
- Create: `services/api-server/tests/live/test_detail_video_live.py`

- [ ] **Step 1: Add a live-test gate**

```python
# services/signer-service/tests/live/conftest.py
import os

import pytest


def pytest_collection_modifyitems(config, items) -> None:
    if os.getenv("HONGGUO_RUN_LIVE_TESTS") == "1":
        return
    marker = pytest.mark.skip(reason="set HONGGUO_RUN_LIVE_TESTS=1")
    for item in items:
        if "tests/live" in str(item.fspath).replace("\\", "/"):
            item.add_marker(marker)
```

- [ ] **Step 2: Add a repeated live signing test**

```python
# services/signer-service/tests/live/test_signer_live.py
import os

import httpx


async def test_signer_returns_fresh_headers_repeatedly() -> None:
    token = os.environ["HONGGUO_SIGNER_SERVICE_TOKEN"]
    values = []
    async with httpx.AsyncClient(base_url="http://127.0.0.1:18001") as client:
        for index in range(20):
            response = await client.post(
                "/v1/sign",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "url": f"https://api5-normal-sinfonlinea.fqnovel.com/test?_rticket={index}",
                    "headers": {},
                },
            )
            response.raise_for_status()
            values.append(response.json()["headers"])
    assert all(value for value in values)
```

- [ ] **Step 3: Add live API smoke tests**

```python
# services/api-server/tests/live/test_search_live.py
import httpx


async def test_live_search_returns_items() -> None:
    async with httpx.AsyncClient(base_url="http://127.0.0.1:18000", timeout=60) as client:
        response = await client.get("/api/search", params={"q": "妈妈"})
        response.raise_for_status()
        assert response.json()["data"]["items"]
```

```python
# services/api-server/tests/live/test_detail_video_live.py
import os

import httpx


async def test_live_detail_and_video_resolution() -> None:
    series_id = os.environ["HONGGUO_LIVE_SERIES_ID"]
    async with httpx.AsyncClient(base_url="http://127.0.0.1:18000", timeout=60) as client:
        detail = await client.get(f"/api/books/{series_id}")
        detail.raise_for_status()
        episodes = detail.json()["data"]["episodes"]
        assert episodes
        video_id = episodes[0]["video_id"]
        video = await client.get(f"/api/videos/{video_id}", params={"quality": "1080p"})
        video.raise_for_status()
        assert video.json()["data"]["url"].startswith("http")
```

- [ ] **Step 4: Verify tests skip by default**

Run:

```powershell
uv run pytest services/signer-service/tests/live services/api-server/tests/live -q
```

Expected: all live tests SKIPPED.

- [ ] **Step 5: Run live acceptance after both services are running**

Run:

```powershell
$env:HONGGUO_RUN_LIVE_TESTS="1"
$env:HONGGUO_SIGNER_SERVICE_TOKEN="local-development"
$env:HONGGUO_LIVE_SERIES_ID="7643004551879986200"
uv run pytest services/signer-service/tests/live services/api-server/tests/live -v
```

Expected: repeated signing, search, detail, and video tests PASS. If a stream is encrypted, the video endpoint must return the documented 422 error instead of attempting decryption.

- [ ] **Step 6: Commit**

```powershell
git add services/*/tests/live
git commit -m "test: add opt-in live signer and upstream checks"
```

---

### Task 12: Document Bootstrap, Operations, and Recovery

**Files:**
- Create: `README.md`
- Create: `services/signer-service/README.md`
- Create: `services/api-server/README.md`
- Create: `docs/troubleshooting.md`

- [ ] **Step 1: Document the exact local startup sequence**

```markdown
# README.md

## Local startup

1. Start MuMu instance `0`.
2. Log in to Hongguo and leave the app running.
3. Verify the device:

   ```powershell
   & "D:\MuMu Player 12\nx_main\mumu-cli.exe" info --vmindex 0
   & "D:\MuMu Player 12\shell\adb.exe" connect 127.0.0.1:16384
   & "D:\MuMu Player 12\shell\adb.exe" -s 127.0.0.1:16384 shell "su -c id"
   ```

4. Start the Signer Service:

   ```powershell
   .\services\signer-service\scripts\start.ps1
   ```

5. Capture and save the current session.
6. Start the API Server:

   ```powershell
   .\services\api-server\scripts\start.ps1
   ```

7. Verify:

   ```powershell
   Invoke-RestMethod http://127.0.0.1:18000/health
   Invoke-RestMethod "http://127.0.0.1:18000/api/search?q=妈妈"
   ```
```

- [ ] **Step 2: Document service ownership and secret handling**

In `services/signer-service/README.md`, document MuMu, ADB, root, Frida binary version matching, `oracle.js`, loopback binding, service token, and watchdog recovery.

In `services/api-server/README.md`, document session capture, `.local/session.json`, upstream endpoint mapping, cache TTLs, and API examples.

Do not include real cookies, tokens, signed playback URLs, or user identifiers.

- [ ] **Step 3: Add deterministic troubleshooting checks**

```markdown
# docs/troubleshooting.md

## ADB device missing

```powershell
& "D:\MuMu Player 12\shell\adb.exe" connect 127.0.0.1:16384
& "D:\MuMu Player 12\shell\adb.exe" devices -l
```

## Root unavailable

```powershell
& "D:\MuMu Player 12\shell\adb.exe" -s 127.0.0.1:16384 shell "su -c id"
```

Expected: `uid=0(root)`.

## Frida version mismatch

```powershell
uv run python -c "import frida; print(frida.__version__)"
& "D:\MuMu Player 12\shell\adb.exe" -s 127.0.0.1:16384 shell "/data/local/tmp/frida-server --version"
```

Both versions must match.

## App PID changed

```powershell
& "D:\MuMu Player 12\shell\adb.exe" -s 127.0.0.1:16384 shell "pidof com.phoenix.read"
```

The Signer watchdog should reattach automatically.
```

- [ ] **Step 4: Run final verification**

Run:

```powershell
uv sync --all-packages
uv run pytest -q
uv run ruff check .
```

Expected: all offline tests PASS and all live tests remain skipped unless explicitly enabled.

- [ ] **Step 5: Commit**

```powershell
git add README.md services/*/README.md docs/troubleshooting.md
git commit -m "docs: add local bootstrap and recovery guide"
```

---

## Final Acceptance Checklist

- [ ] `mumu-cli info --vmindex 0` is parsed without hard-coding the ADB port.
- [ ] ADB connects and root verification returns UID 0.
- [ ] Python Frida and `frida-server` versions match.
- [ ] Signer attaches to `com.phoenix.read` and loads `oracle.js`.
- [ ] `/v1/sign` returns only approved dynamic security headers.
- [ ] Twenty sequential live signing calls succeed.
- [ ] Signer recovers after a Hongguo process restart.
- [ ] Session capture produces `.local/session.json` without logging secrets.
- [ ] Signed transport sends exactly the bytes and URL that were signed.
- [ ] Search cursor state survives an API round trip.
- [ ] Latest short plays use the official `今日上新` marker.
- [ ] Ranking data is flattened from the upstream cell structure.
- [ ] Series episodes are ordered by `vid_index`.
- [ ] Video selection returns the requested or best lower quality.
- [ ] Encrypted-only video models return `encrypted_stream_unsupported`.
- [ ] API Server imports no Frida or ADB implementation.
- [ ] Signer Service imports no Hongguo business parser.
- [ ] `uv run pytest -q` passes with live tests skipped.
- [ ] `uv run ruff check .` passes.
