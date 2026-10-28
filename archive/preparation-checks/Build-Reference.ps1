$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Use-ProjectTools.ps1')
$taskRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$logPath = Join-Path $taskRoot '.local\logs\hnu-cargo-check.log'
$manifest = Join-Path $taskRoot '.upstream\hnu-doc-d71b9976bcd6606b0e74855fda092338687218af\Cargo.toml'
$ErrorActionPreference = 'Continue'
& cargo check --locked --manifest-path $manifest -p hnudoc 2>&1 | ForEach-Object { $_.ToString() } | Out-File -LiteralPath $logPath -Encoding utf8
$buildExit = $LASTEXITCODE
$ErrorActionPreference = 'Stop'
Get-Content -LiteralPath $logPath -Encoding UTF8 -Tail 24
$resultPath=Join-Path $PSScriptRoot 'results'
New-Item -ItemType Directory -Path $resultPath -Force | Out-Null
@{ source='hnu-doc d71b9976bcd6606b0e74855fda092338687218af'; command='cargo check --locked -p hnudoc'; exit_code=$buildExit; status=$(if ($buildExit -eq 0) { 'passed' } else { 'failed' }); school_login_executed=$false; backend_started=$false; rustc=(& rustc --version) } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $resultPath 'reference-check.json') -Encoding utf8
Write-Output ('REFERENCE_CHECK_EXIT='+$buildExit)
exit $buildExit
