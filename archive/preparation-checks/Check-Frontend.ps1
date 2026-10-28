$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Use-ProjectTools.ps1')
$taskRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$sourcePath = Join-Path $taskRoot '.upstream\FRAS-lab-website-892e0b14d2a784c833597ecb9fc91f2a41b996d2\frontend'
$copyPath = Join-Path $taskRoot '.local\fras-frontend'
if (-not (Test-Path -LiteralPath $copyPath)) { Copy-Item -LiteralPath $sourcePath -Destination $copyPath -Recurse }
Push-Location -LiteralPath $copyPath
$preview = $null
try {
    & npm.cmd ci --ignore-scripts --no-audit --no-fund
    if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency install failed.' }
    & npm.cmd run build
    if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
    $nodePath = (Get-Command node.exe).Source
    $vitePath = Join-Path $copyPath 'node_modules\vite\bin\vite.js'
    $preview = Start-Process -FilePath $nodePath -ArgumentList @('"'+$vitePath+'"','preview','--host','127.0.0.1','--port','25173','--strictPort') -WorkingDirectory $copyPath -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $taskRoot '.local\logs\frontend-preview.log') -RedirectStandardError (Join-Path $taskRoot '.local\logs\frontend-preview-error.log')
    $response = $null
    for ($attempt=0; $attempt -lt 20; $attempt++) {
        try { $response=Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:25173/' -TimeoutSec 2; break } catch { Start-Sleep -Milliseconds 300 }
    }
    if ($null -eq $response -or $response.StatusCode -ne 200 -or $response.Content -notmatch 'id="app"') { throw 'Frontend preview HTTP check failed.' }
    $asset = [regex]::Match($response.Content,'src="([^"]+\.js)"').Groups[1].Value
    if (-not $asset.StartsWith('/assets/')) { throw 'Expected built JavaScript asset.' }
    $assetResponse = Invoke-WebRequest -UseBasicParsing -Uri ('http://127.0.0.1:25173'+$asset) -TimeoutSec 5
    if ($assetResponse.StatusCode -ne 200) { throw 'Frontend asset HTTP check failed.' }
    $report = @{ source='FRAS-lab-website frontend'; install='passed'; build='passed'; preview_http=200; javascript_http=200; backend_api_tested=$false; node=(& node --version); npm=(& npm.cmd --version) }
    $report | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'results\frontend-result.json') -Encoding utf8
    $report | ConvertTo-Json
} finally {
    if ($null -ne $preview -and -not $preview.HasExited) { Stop-Process -Id $preview.Id }
    Pop-Location
}
