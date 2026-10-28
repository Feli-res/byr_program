$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'Use-DevEnvironment.ps1')
Push-Location -LiteralPath $projectRoot
try {
    $probe="import sys; from pathlib import Path; r=Path.cwd(); sys.path[:0]=[str(r/'.local/accounts-qa/python'),str(r/'.local/design-qa/python')]; import jsonschema"
    $ErrorActionPreference='Continue'
    & python.exe -c $probe 2>&1 | Out-Null
    $dependencyExit=$LASTEXITCODE
    $ErrorActionPreference='Stop'
    if ($dependencyExit -ne 0) {Invoke-DevCommand 'python.exe' @('-m','pip','install','--target','.local/accounts-qa/python','-r','docs/accounts/requirements-tests.txt')}
    Invoke-DevCommand 'cargo.exe' @('fmt','--all','--','--check')
    Invoke-DevCommand 'cargo.exe' @('clippy','--locked','--all-targets','--','-D','warnings')
    Invoke-DevCommand 'cargo.exe' @('test','--locked','-p','youzhihui-api')
    Invoke-DevCommand 'cargo.exe' @('build','--locked','-p','youzhihui-api')
    Push-Location -LiteralPath (Join-Path $projectRoot 'apps\web')
    try {Invoke-DevCommand 'npm.cmd' @('run','build')} finally {Pop-Location}
    Invoke-DevCommand 'python.exe' @('scripts/verify_accounts.py')
} finally {Pop-Location}
