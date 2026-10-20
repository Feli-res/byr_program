$ErrorActionPreference='Stop'
$taskRoot=Split-Path -Parent $PSScriptRoot
$composeArgs=@('--env-file',(Join-Path $taskRoot '.local\checks.env'),'-f',(Join-Path $PSScriptRoot 'compose.yaml'))
& docker compose @composeArgs restart
if ($LASTEXITCODE -ne 0) { throw 'Restarting check services failed.' }
& docker compose @composeArgs up -d --wait --wait-timeout 240
if ($LASTEXITCODE -ne 0) { throw 'Restarted check services are not healthy.' }
& (Join-Path $PSScriptRoot 'Run-Smoke.ps1') -VerifyOnly
