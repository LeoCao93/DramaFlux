param(
    [string]$AppImport = "hongguo_api.bootstrap_app:app",
    [string]$HostAddress = "127.0.0.1",
    [int]$Port = 18000
)

$ErrorActionPreference = "Stop"

$ServiceRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$WorkspaceRoot = (Resolve-Path (Join-Path $ServiceRoot "..\..")).Path
$env:UV_CACHE_DIR = Join-Path $WorkspaceRoot ".uv-cache"

Push-Location $WorkspaceRoot
try {
    & uv run --project $ServiceRoot uvicorn $AppImport `
        --host $HostAddress `
        --port $Port
    if ($LASTEXITCODE -ne 0) {
        throw "API service exited with code $LASTEXITCODE."
    }
}
finally {
    Pop-Location
}
