$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Use-ProjectTools.ps1')
$taskRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$referenceRoot = Join-Path $taskRoot '.local\public-cleanup-20261106\upstream-original'
if (-not (Test-Path -LiteralPath $referenceRoot)) { $referenceRoot = Join-Path $taskRoot '.upstream' }
$manifest=Join-Path $referenceRoot 'hnu-doc-d71b9976bcd6606b0e74855fda092338687218af\Cargo.toml'
if (-not (Test-Path -LiteralPath $(if ($manifest) { $manifest } else { $sourcePath }))) { throw 'Reference source missing; obtain the fixed version listed in .upstream/README.md.' }
$logPath=Join-Path $taskRoot '.local\logs\hnu-pow-test.log'
$ErrorActionPreference='Continue'
& cargo test --locked --manifest-path $manifest -p hnudoc utils::pow::tests::pow_correct -- --exact 2>&1 | ForEach-Object { $_.ToString() } | Out-File -LiteralPath $logPath -Encoding utf8
$testExit=$LASTEXITCODE
$ErrorActionPreference='Stop'
Get-Content -LiteralPath $logPath -Encoding UTF8 -Tail 24
$resultPath=Join-Path $PSScriptRoot 'results'
New-Item -ItemType Directory -Path $resultPath -Force | Out-Null
@{ test='utils::pow::tests::pow_correct'; exit_code=$testExit; status=$(if ($testExit -eq 0) { 'passed' } else { 'failed' }); school_login_executed=$false; all_reference_tests_run=$false } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $resultPath 'reference-unit-result.json') -Encoding utf8
exit $testExit
