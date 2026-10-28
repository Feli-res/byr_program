param([switch]$KeepDatabase)
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'Use-DevEnvironment.ps1')
$processPath=Join-Path $projectRoot '.local\dev-processes.json'
if (Test-Path -LiteralPath $processPath) {
    $records=Get-Content -LiteralPath $processPath -Raw -Encoding UTF8 | ConvertFrom-Json
    foreach ($record in $records) {
        $process=Get-Process -Id $record.id -ErrorAction SilentlyContinue
        if ($process -and $process.StartTime.ToUniversalTime().ToString('o') -eq $record.started) {
            # Next.js starts its own worker; stop only the descendants of our recorded web process.
            if ($record.kind -eq 'web') {
                function Stop-DevChild([int]$parentProcessId) {
                    foreach ($child in @(Get-CimInstance Win32_Process -Filter ('ParentProcessId='+$parentProcessId))) {
                        Stop-DevChild $child.ProcessId
                        Stop-Process -Id $child.ProcessId -ErrorAction SilentlyContinue
                    }
                }
                Stop-DevChild $process.Id
            }
            Stop-Process -Id $process.Id -ErrorAction SilentlyContinue
        }
    }
    Remove-Item -LiteralPath $processPath
}
if (-not $KeepDatabase) {
    Invoke-DevCommand 'docker.exe' @('compose','--env-file',(Join-Path $projectRoot 'deploy\.env'),'-f',(Join-Path $projectRoot 'deploy\compose.dev.yaml'),'stop')
}
Write-Output 'Stopped development processes. Database volumes and records are retained.'
