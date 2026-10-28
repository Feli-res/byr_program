$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Use-ProjectTools.ps1')
$taskRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$webPath = Join-Path $PSScriptRoot 'web-smoke'
$env:NEXT_TELEMETRY_DISABLED='1'
Push-Location -LiteralPath $webPath
$server = $null
try {
    if (Test-Path -LiteralPath 'package-lock.json') { & npm.cmd ci --ignore-scripts --no-audit --no-fund }
    else { & npm.cmd install --ignore-scripts --no-audit --no-fund }
    if ($LASTEXITCODE -ne 0) { throw 'Next.js dependency install failed.' }
    & npm.cmd run build
    if ($LASTEXITCODE -ne 0) { throw 'Next.js build failed.' }
    $nextPath=Join-Path $webPath 'node_modules\next\dist\bin\next'
    $server=Start-Process -FilePath (Get-Command node.exe).Source -ArgumentList @('"'+$nextPath+'"','start','--hostname','127.0.0.1','--port','25174') -WorkingDirectory $webPath -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $taskRoot '.local\logs\next-preview.log') -RedirectStandardError (Join-Path $taskRoot '.local\logs\next-preview-error.log')
    $response=$null
    for ($attempt=0;$attempt -lt 30;$attempt++) {
        try { $response=Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:25174/' -TimeoutSec 2; break } catch { Start-Sleep -Milliseconds 300 }
    }
    if ($null -eq $response -or $response.StatusCode -ne 200 -or $response.Content -notmatch 'tools-ready') { throw 'Next.js HTTP page check failed.' }
    $report=@{ source='independent Next.js / React check'; build='passed'; page_http=200; project_features_tested=$false }
    $report | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'results\web-tools-result.json') -Encoding utf8
    $report | ConvertTo-Json
} finally {
    if ($null -ne $server -and -not $server.HasExited) { Stop-Process -Id $server.Id }
    Pop-Location
}
