$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'Use-DevEnvironment.ps1')
Push-Location -LiteralPath $projectRoot
try {
    Invoke-DevCommand 'cargo.exe' @('fmt','--all','--','--check')
    Invoke-DevCommand 'cargo.exe' @('clippy','--locked','--all-targets','--','-D','warnings')
    Invoke-DevCommand 'cargo.exe' @('test','--locked','-p','youzhihui-api')
    Invoke-DevCommand 'cargo.exe' @('build','--locked','-p','youzhihui-api')
    Push-Location -LiteralPath (Join-Path $projectRoot 'apps\web')
    try {Invoke-DevCommand 'npm.cmd' @('run','build')} finally {Pop-Location}
    Invoke-DevCommand 'python.exe' @('scripts/verify_admin.py')
} finally {Pop-Location}
