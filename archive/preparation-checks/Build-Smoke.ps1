$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Use-ProjectTools.ps1')
$taskRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$manifest = Join-Path $PSScriptRoot 'rust-smoke\Cargo.toml'
$logPath = Join-Path $taskRoot '.local\logs\rust-smoke-build.log'
if (-not (Test-Path -LiteralPath (Join-Path $PSScriptRoot 'rust-smoke\Cargo.lock'))) {
    & cargo generate-lockfile --manifest-path $manifest
    if ($LASTEXITCODE -ne 0) { throw 'Smoke dependency lock generation failed.' }
}
$ErrorActionPreference = 'Continue'
& cargo build --locked --manifest-path $manifest 2>&1 | ForEach-Object { $_.ToString() } | Out-File -LiteralPath $logPath -Encoding utf8
$buildExit = $LASTEXITCODE
$ErrorActionPreference = 'Stop'
Get-Content -LiteralPath $logPath -Encoding UTF8 -Tail 24
exit $buildExit
