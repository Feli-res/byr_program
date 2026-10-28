$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$demandPath = Join-Path $taskRoot 'demand'
$baselinePath = Join-Path $demandPath 'T01_首版需求基线与验收清单.md'
$baseline = Get-Content -Raw -LiteralPath $baselinePath -Encoding UTF8
$features = [regex]::Matches($baseline,'(?m)^\| F(\d{2}) \|')
$cases = [regex]::Matches($baseline,'(?m)^\| AC(\d{2}) \|')
if ($features.Count -ne 9 -or $cases.Count -ne 20) { throw 'Requirement or acceptance case count mismatch.' }
for ($i=0;$i -lt 9;$i++) { if ([int]$features[$i].Groups[1].Value -ne ($i+1)) { throw 'Feature numbering mismatch.' } }
for ($i=0;$i -lt 20;$i++) { if ([int]$cases[$i].Groups[1].Value -ne ($i+1)) { throw 'Acceptance numbering mismatch.' } }
$files = @($baselinePath,(Join-Path $demandPath '程设项目规划.md'),(Join-Path $demandPath 'AI+创新点设计.md'),(Join-Path $taskRoot '邮智汇_程设项目计划书.md'))
foreach ($path in $files) {
    $text = Get-Content -Raw -LiteralPath $path -Encoding UTF8
    foreach ($link in [regex]::Matches($text,'\]\(([^)]+)\)')) {
        $target = $link.Groups[1].Value.Trim('<','>')
        if ($target -match '^(https?://|mailto:|#)') { continue }
        $target = ($target -split '#',2)[0] -replace ':\d+$',''
        if (-not [System.IO.Path]::IsPathRooted($target)) {
            $target = Join-Path (Split-Path -Parent $path) $target
        }
        if (-not (Test-Path -LiteralPath $target)) { throw ('Broken local link in '+$path+': '+$target) }
    }
}
foreach ($required in @('不接校园 CAS','99,999.99','5～1,440','200 MiB','7 天','与原 Word 的差异及适用规则')) {
    if (-not $baseline.Contains($required)) { throw ('Missing agreed rule: '+$required) }
}
$resultPath=Join-Path $PSScriptRoot 'results'
New-Item -ItemType Directory -Path $resultPath -Force | Out-Null
$report=@{ step='4.1'; status='passed'; feature_count=9; acceptance_case_count=20; links='passed'; word_modified=$false; application_functions_tested=$false; requirement_sha256=(Get-FileHash -LiteralPath $baselinePath -Algorithm SHA256).Hash }
$report | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $resultPath 'requirements-result.json') -Encoding utf8
$report | ConvertTo-Json
