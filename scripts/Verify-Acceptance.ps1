$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'Use-DevEnvironment.ps1')
Push-Location -LiteralPath $projectRoot
try {
    $probe="import sys; from pathlib import Path; r=Path.cwd(); sys.path[:0]=[str(r/'.local/chat-qa/python'),str(r/'.local/accounts-qa/python'),str(r/'.local/design-qa/python')]; import jsonschema, websockets"
    $ErrorActionPreference='Continue'
    & python.exe -c $probe 2>&1 | Out-Null
    $dependencyExit=$LASTEXITCODE
    $ErrorActionPreference='Stop'
    if ($dependencyExit -ne 0) {Invoke-DevCommand 'python.exe' @('-m','pip','install','--target','.local/accounts-qa/python','-r','docs/accounts/requirements-tests.txt')}
    if ($dependencyExit -ne 0) {Invoke-DevCommand 'python.exe' @('-m','pip','install','--target','.local/chat-qa/python','-r','docs/chat/requirements-tests.txt')}
    Invoke-DevCommand 'cargo.exe' @('fmt','--all','--','--check')
    Invoke-DevCommand 'cargo.exe' @('clippy','--locked','--all-targets','--','-D','warnings')
    Invoke-DevCommand 'cargo.exe' @('test','--locked','-p','youzhihui-api')
    Invoke-DevCommand 'cargo.exe' @('build','--locked','-p','youzhihui-api')
    Invoke-DevCommand 'node.exe' @('--test','apps/web/tests/unit/money.test.mjs')
    Push-Location -LiteralPath (Join-Path $projectRoot 'apps\web')
    try {Invoke-DevCommand 'npm.cmd' @('run','build')} finally {Pop-Location}
    Invoke-DevCommand 'python.exe' @('scripts/verify_acceptance.py','--regressions')
} finally {Pop-Location}
