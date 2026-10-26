$ErrorActionPreference='Stop'
$projectRoot=Split-Path -Parent $PSScriptRoot
$envPath=Join-Path $projectRoot 'deploy\.env'
if (-not (Test-Path -LiteralPath $envPath)) {
    function New-LocalSecret {
        $bytes=New-Object byte[] 32
        $random=[Security.Cryptography.RandomNumberGenerator]::Create()
        try {$random.GetBytes($bytes); return ([BitConverter]::ToString($bytes)).Replace('-','').ToLowerInvariant()} finally {$random.Dispose()}
    }
    $template=[IO.File]::ReadAllText((Join-Path $projectRoot 'deploy\.env.example'))
    $template=$template.Replace('CHANGE_ME_RANDOM_USER_PASSWORD',(New-LocalSecret)).Replace('CHANGE_ME_RANDOM_ROOT_PASSWORD',(New-LocalSecret)).Replace('CHANGE_ME_RANDOM_AUTH_SECRET',(New-LocalSecret))
    [IO.File]::WriteAllText($envPath,$template,(New-Object Text.UTF8Encoding($false)))
}
# Upgrade an existing 4.4 local configuration without changing its database passwords.
$current=[IO.File]::ReadAllText($envPath)
if ($current -notmatch '(?m)^AUTH_SECRET=') {
    $bytes=New-Object byte[] 32
    $random=[Security.Cryptography.RandomNumberGenerator]::Create()
    try {$random.GetBytes($bytes)} finally {$random.Dispose()}
    $secret=([BitConverter]::ToString($bytes)).Replace('-','').ToLowerInvariant()
    [IO.File]::AppendAllText($envPath,("`nAUTH_SECRET="+$secret+"`nCOOKIE_SECURE=false`nUPLOAD_ROOT=.local/uploads`n"),(New-Object Text.UTF8Encoding($false)))
}
. (Join-Path $PSScriptRoot 'Use-DevEnvironment.ps1')
Push-Location -LiteralPath $projectRoot
try {
    Invoke-DevCommand 'docker.exe' @('compose','--env-file','deploy/.env','-f','deploy/compose.dev.yaml','up','-d','--wait','--wait-timeout','240')
    Invoke-DevCommand 'cargo.exe' @('build','--locked','-p','youzhihui-api')
    Invoke-DevCommand 'cargo.exe' @('run','--locked','-p','youzhihui-api','--','--migrate')
    Push-Location -LiteralPath (Join-Path $projectRoot 'apps\web')
    try {
        Invoke-DevCommand 'npm.cmd' @('ci','--ignore-scripts','--no-audit','--no-fund')
        Invoke-DevCommand 'npm.cmd' @('run','build')
    } finally {Pop-Location}
    Write-Output 'Prepared development database, API and web application. Run scripts/Start-Dev.ps1 next.'
} finally {Pop-Location}
