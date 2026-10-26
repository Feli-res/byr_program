param([switch]$Production)
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'Use-DevEnvironment.ps1')
$processPath=Join-Path $projectRoot '.local\dev-processes.json'
if (Test-Path -LiteralPath $processPath) {throw 'A process record exists. Run scripts/Stop-Dev.ps1 first.'}
Invoke-DevCommand 'docker.exe' @('compose','--env-file',(Join-Path $projectRoot 'deploy\.env'),'-f',(Join-Path $projectRoot 'deploy\compose.dev.yaml'),'up','-d','--wait','--wait-timeout','240')
$targetPath=if ($env:CARGO_TARGET_DIR) {$env:CARGO_TARGET_DIR} else {Join-Path $projectRoot 'target'}
$apiBinary=Join-Path $targetPath 'debug\youzhihui-api.exe'
if (-not (Test-Path -LiteralPath $apiBinary)) {throw 'Run scripts/Prepare-Dev.ps1 first.'}
$webPath=Join-Path $projectRoot 'apps\web'
$nextPath=Join-Path $webPath 'node_modules\next\dist\bin\next'
$apiAddress=[Uri]$env:API_INTERNAL_URL
foreach ($port in @($apiAddress.Port,[int]$env:WEB_PORT)) {
    $listener=[Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback,$port)
    try {$listener.Start()} catch {throw ('Port already in use: '+$port)} finally {$listener.Stop()}
}
$processes=@()
try {
    $api=Start-Process -FilePath $apiBinary -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $devLog 'api.log') -RedirectStandardError (Join-Path $devLog 'api-error.log')
    $processes+=@{id=$api.Id;started=$api.StartTime.ToUniversalTime().ToString('o');kind='api'}
    $mode=if ($Production) {'start'} else {'dev'}
    $web=Start-Process -FilePath (Get-Command node.exe).Source -ArgumentList @('"'+$nextPath+'"',$mode,'--hostname','127.0.0.1','--port',$env:WEB_PORT) -WorkingDirectory $webPath -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $devLog 'web.log') -RedirectStandardError (Join-Path $devLog 'web-error.log')
    $processes+=@{id=$web.Id;started=$web.StartTime.ToUniversalTime().ToString('o');kind='web'}
    $processes | ConvertTo-Json | Set-Content -LiteralPath $processPath -Encoding UTF8
    foreach ($address in @(($env:API_INTERNAL_URL+'/health/ready'),($env:WEB_ORIGIN+'/dev-check'))) {
        $response=$null
        for ($attempt=0;$attempt -lt 60;$attempt++) {
            try {$response=Invoke-WebRequest -UseBasicParsing -Uri $address -TimeoutSec 3;break} catch {Start-Sleep -Milliseconds 500}
        }
        if ($null -eq $response -or $response.StatusCode -ne 200) {throw 'Service did not become ready. See .local/logs/dev.'}
    }
    Write-Output ('Open '+$env:WEB_ORIGIN+'/dev-check')
    Write-Output 'Processes run in the background. Stop them with scripts/Stop-Dev.ps1.'
} catch {
    foreach ($record in $processes) {Stop-Process -Id $record.id -ErrorAction SilentlyContinue}
    Remove-Item -LiteralPath $processPath -ErrorAction SilentlyContinue
    throw
}
