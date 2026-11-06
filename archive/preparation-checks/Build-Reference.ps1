$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Use-ProjectTools.ps1')
$taskRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$logPath = Join-Path $taskRoot '.local\logs\hnu-cargo-check.log'
$referenceRoot = Join-Path $taskRoot '.local\public-cleanup-20261106\upstream-original'
if (-not (Test-Path -LiteralPath $referenceRoot)) { $referenceRoot = Join-Path $taskRoot '.upstream' }
$manifest = Join-Path $referenceRoot 'hnu-doc-d71b9976bcd6606b0e74855fda092338687218af\Cargo.toml'
if (-not (Test-Path -LiteralPath $(if ($manifest) { $manifest } else { $sourcePath }))) { throw 'Reference source missing; obtain the fixed version listed in .upstream/README.md.' }
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
