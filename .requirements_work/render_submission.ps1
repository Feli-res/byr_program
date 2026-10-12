$ErrorActionPreference='Stop'
$rootPath = Split-Path -Parent $PSScriptRoot
$docPath = Join-Path $rootPath '北邮校园综合交互论坛_需求分析文档.docx'
$renderPath = Join-Path $PSScriptRoot 'submission-render'
New-Item -ItemType Directory -Path $renderPath -Force | Out-Null
$wordApp = New-Object -ComObject Word.Application
$wordApp.Visible=$false
$wordApp.DisplayAlerts=0
try {
  $wordDoc = $wordApp.Documents.Open($docPath,$false,$true)
  $wordDoc.Repaginate()
  $pageCount = $wordDoc.ComputeStatistics(2)
  Write-Output ('pages='+$pageCount)
  for($pageNo=1;$pageNo -le $pageCount;$pageNo++) {
    $rangeStart=$wordDoc.GoTo(1,1,$pageNo).Start
    if($pageNo -lt $pageCount) {$rangeEnd=$wordDoc.GoTo(1,1,($pageNo+1)).Start} else {$rangeEnd=$wordDoc.Content.End}
    [IO.File]::WriteAllBytes((Join-Path $renderPath ('page-'+$pageNo+'.emf')),[byte[]]$wordDoc.Range($rangeStart,$rangeEnd).EnhMetaFileBits)
  }
  $dateRange=$wordDoc.Content
  if($dateRange.Find.Execute('2026 年 10 月')) {[IO.File]::WriteAllBytes((Join-Path $renderPath 'cover-date.emf'),[byte[]]$dateRange.EnhMetaFileBits)}
  $wordDoc.Close(0)
  Write-Output 'rendered all pages'
} finally {$wordApp.Quit()}
