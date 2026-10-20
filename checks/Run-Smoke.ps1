param([switch]$VerifyOnly)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Use-ProjectTools.ps1')
$taskRoot = Split-Path -Parent $PSScriptRoot
$envPath = Join-Path $taskRoot '.local\checks.env'
if (-not (Test-Path -LiteralPath $envPath)) { throw 'Run Prepare-Checks.ps1 first.' }
$settings = @{}
foreach ($line in Get-Content -LiteralPath $envPath) {
    if ($line -match '^([^=]+)=(.*)$') { $settings[$Matches[1]] = $Matches[2] }
}
$env:MYSQL_CHECK_URL = 'mysql://byr_check:'+$settings['MYSQL_CHECK_PASSWORD']+'@127.0.0.1:23306/byr_check'
$tokenPath = Join-Path $taskRoot '.local\check-token.txt'
if (-not $VerifyOnly) {
    [IO.File]::WriteAllText($tokenPath,[guid]::NewGuid().ToString('N'))
}
$env:CHECK_TOKEN = [IO.File]::ReadAllText($tokenPath).Trim()
$arguments = @('run','--locked','--manifest-path',(Join-Path $PSScriptRoot 'rust-smoke\Cargo.toml'))
if ($VerifyOnly) { $arguments += @('--','--verify-only') }
try {
    $result = & cargo @arguments
    if ($LASTEXITCODE -ne 0) { throw 'Rust smoke check failed.' }
    $result | Write-Output
    $resultPath=Join-Path $PSScriptRoot 'results'
    New-Item -ItemType Directory -Path $resultPath -Force | Out-Null
    $fileName = if ($VerifyOnly) { 'rust-restart-result.json' } else { 'rust-smoke-result.json' }
    $result | Set-Content -LiteralPath (Join-Path $resultPath $fileName) -Encoding utf8
} finally {
    Remove-Item Env:\MYSQL_CHECK_URL -ErrorAction SilentlyContinue
    Remove-Item Env:\CHECK_TOKEN -ErrorAction SilentlyContinue
}
