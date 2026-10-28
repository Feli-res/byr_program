$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'Use-ProjectTools.ps1')
$taskRoot=Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$composeArgs=@('--env-file',(Join-Path $taskRoot '.local\checks.env'),'-f',(Join-Path $PSScriptRoot 'compose.yaml'))
$mysqlVersion=& docker compose @composeArgs exec -T mysql mysqld --version
if ($LASTEXITCODE -ne 0) { throw 'Start check services before recording versions.' }
$redisVersion=& docker compose @composeArgs exec -T redis redis-server --version
if ($LASTEXITCODE -ne 0) { throw 'Reading Redis version failed.' }
$report=@{
    recorded_at=(Get-Date -Format o)
    node=(& node --version)
    npm=(& npm.cmd --version)
    rustc=(& rustc --version)
    cargo=(& cargo --version)
    gcc=(& gcc -dumpfullversion)
    docker=(& docker version --format '{{.Server.Version}}')
    compose=(& docker compose version --short)
    mysql=$mysqlVersion
    redis=$redisVersion
    mysql_image='mysql:8.4@sha256:0f51e63e537a1f176423fa03ef559aabe6fa4372a53160a44bc7e75da7d15364'
    redis_image='redis:7-alpine@sha256:858f009f9709ce576febc734aa78b8f6d624b82571f9ddb6bda4377c833b3499'
    next='16.4.2'
    react='19.3.1'
    scope='local development computer; no production or second computer validation'
    formal_application_tested=$false
    school_login_executed=$false
}
$report | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'results\environment.json') -Encoding utf8
$report | ConvertTo-Json
