$ErrorActionPreference='Stop'
$projectRoot=Split-Path -Parent $PSScriptRoot
if (Test-Path -LiteralPath (Join-Path $projectRoot '.local\cargo\bin\cargo.exe')) {
    . (Join-Path $projectRoot 'checks\Use-ProjectTools.ps1')
}
$env:NEXT_TELEMETRY_DISABLED='1'
$devLog=Join-Path $projectRoot '.local\logs\dev'
New-Item -ItemType Directory -Path $devLog -Force | Out-Null
$envPath=Join-Path $projectRoot 'deploy\.env'
if (-not (Test-Path -LiteralPath $envPath)) {throw 'Run scripts/Prepare-Dev.ps1 first.'}
$allowed=@('MYSQL_DATABASE','MYSQL_USER','MYSQL_PASSWORD','MYSQL_ROOT_PASSWORD','MYSQL_PORT','REDIS_PORT','API_BIND','WEB_PORT','WEB_ORIGIN','API_INTERNAL_URL','DEV_TOOLS_ENABLED','RUST_LOG','AUTH_SECRET','COOKIE_SECURE','UPLOAD_ROOT')
foreach ($line in Get-Content -LiteralPath $envPath -Encoding UTF8) {
    if ([string]::IsNullOrWhiteSpace($line) -or $line.TrimStart().StartsWith('#')) {continue}
    if ($line -notmatch '^([A-Z_]+)=(.*)$' -or $allowed -notcontains $Matches[1]) {throw 'Unexpected setting in deploy/.env'}
    [Environment]::SetEnvironmentVariable($Matches[1],$Matches[2],'Process')
}
foreach ($key in $allowed) {if (-not [Environment]::GetEnvironmentVariable($key,'Process')) {throw ('Missing setting: '+$key)}}
if ($env:MYSQL_PASSWORD.StartsWith('CHANGE_ME') -or $env:MYSQL_ROOT_PASSWORD.StartsWith('CHANGE_ME')) {throw 'Set real local passwords in deploy/.env'}
if ($env:MYSQL_DATABASE -notmatch '^[a-zA-Z0-9_]+$' -or $env:MYSQL_USER -notmatch '^[a-zA-Z0-9_]+$') {throw 'Invalid local database or user name'}
$env:DATABASE_URL='mysql://'+[Uri]::EscapeDataString($env:MYSQL_USER)+':'+[Uri]::EscapeDataString($env:MYSQL_PASSWORD)+'@127.0.0.1:'+$env:MYSQL_PORT+'/'+$env:MYSQL_DATABASE
$env:REDIS_URL='redis://127.0.0.1:'+$env:REDIS_PORT+'/'

function Invoke-DevCommand([string]$Program,[string[]]$Arguments) {
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) {throw ('Command failed: '+$Program)}
}
