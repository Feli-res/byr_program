$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'Use-DevEnvironment.ps1')
Push-Location -LiteralPath $projectRoot
try {
    Invoke-DevCommand 'cargo.exe' @('fmt','--all','--','--check')
    Invoke-DevCommand 'cargo.exe' @('test','--locked','-p','youzhihui-api')
    Invoke-DevCommand 'cargo.exe' @('build','--locked','-p','youzhihui-api')
    Invoke-DevCommand 'python.exe' @('scripts/verify_runtime.py')
} finally {Pop-Location}
