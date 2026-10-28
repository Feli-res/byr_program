$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'Use-DevEnvironment.ps1')
Push-Location -LiteralPath $projectRoot
try {
    Invoke-DevCommand 'cargo.exe' @('run','--locked','-p','youzhihui-api','--','--init-admin')
} finally {Pop-Location}
