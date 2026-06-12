param(
    [string]$SignerUrl = "http://127.0.0.1:18001",
    [string]$Token = $env:HONGGUO_API_SIGNER_TOKEN,
    [string]$OutputPath = ".local/session.json",
    [int]$TimeoutMs = 30000
)

$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($Token)) {
    throw "Set HONGGUO_API_SIGNER_TOKEN or pass -Token."
}

$headers = @{ Authorization = "Bearer $Token" }
$snapshot = Invoke-RestMethod `
    -Method Post `
    -Uri "$SignerUrl/v1/session/capture?timeout_ms=$TimeoutMs" `
    -Headers $headers

$parent = Split-Path -Parent $OutputPath
if ($parent) {
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
}
$snapshot | ConvertTo-Json -Depth 10 | Set-Content -Encoding utf8 $OutputPath
Write-Host "Session saved to $OutputPath"
