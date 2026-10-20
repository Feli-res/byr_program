$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$localPath = Join-Path $taskRoot '.local'
New-Item -ItemType Directory -Path $localPath -Force | Out-Null
$envPath = Join-Path $localPath 'checks.env'
if (-not (Test-Path -LiteralPath $envPath)) {
    $passwordBytes = New-Object byte[] 24
    $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $rng.GetBytes($passwordBytes)
        $userSecret = ([BitConverter]::ToString($passwordBytes)).Replace('-','').ToLowerInvariant()
        $rng.GetBytes($passwordBytes)
        $rootSecret = ([BitConverter]::ToString($passwordBytes)).Replace('-','').ToLowerInvariant()
    } finally { $rng.Dispose() }
    [IO.File]::WriteAllText($envPath,"MYSQL_CHECK_PASSWORD=$userSecret`nMYSQL_ROOT_PASSWORD=$rootSecret`n",(New-Object Text.UTF8Encoding($false)))
}
docker compose --env-file $envPath -f (Join-Path $PSScriptRoot 'compose.yaml') up -d --wait --wait-timeout 240
if ($LASTEXITCODE -ne 0) { throw 'Check services did not become healthy.' }
