$ErrorActionPreference = "Stop"

$ServiceRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$WorkspaceRoot = (Resolve-Path (Join-Path $ServiceRoot "..\..")).Path
$env:UV_CACHE_DIR = Join-Path $WorkspaceRoot ".uv-cache"

Push-Location $WorkspaceRoot
try {
    # 使用管道方式传递 Python 代码，避免 PowerShell here-string 双引号被 Strip
    # here-string 内容通过 stdin 传给 Python exec()，保持代码原样不变
    $settingsJson = @"
import json
import frida
from hongguo_signer.config import SignerSettings
from hongguo_signer.frida_runtime.bootstrap import local_frida_server_version

settings = SignerSettings()
print(json.dumps({
    "mumu_cli": str(settings.mumu_cli),
    "adb": str(settings.adb),
    "vmindex": settings.vmindex,
    "package_name": settings.package_name,
    "frida_server_path": str(settings.frida_server_path),
    "frida_server_version": (
        local_frida_server_version(settings.frida_server_path)
        if settings.frida_server_path.is_file()
        else None
    ),
    "python_frida_version": frida.__version__,
}))
"@ | & uv run --project $ServiceRoot python -c "import sys; exec(sys.stdin.read())"
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to load signer settings."
    }

    $settings = $settingsJson | ConvertFrom-Json
    foreach ($path in @(
        $settings.mumu_cli,
        $settings.adb,
        $settings.frida_server_path
    )) {
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
            throw "Required local file not found: $path"
        }
    }
    if ($settings.frida_server_version -ne $settings.python_frida_version) {
        throw (
            "frida-server version {0} does not match Python frida {1}" -f
            $settings.frida_server_version,
            $settings.python_frida_version
        )
    }

    & $settings.mumu_cli version
    & $settings.mumu_cli info --vmindex $settings.vmindex
    # 使用管道方式传递 Python 代码，避免 PowerShell here-string 双引号被 Strip
    # here-string 内容通过 stdin 传给 Python exec()，保持代码原样不变
    @"
from hongguo_signer.config import SignerSettings
from hongguo_signer.device.manager import DeviceManager

print(DeviceManager(SignerSettings()).inspect())
"@ | & uv run --project $ServiceRoot python -c "import sys; exec(sys.stdin.read())"
    if ($LASTEXITCODE -ne 0) {
        throw "MuMu, ADB, root, or app process check failed."
    }
}
finally {
    Pop-Location
}
