param([string]$PdfName = 'fras-before.pdf')
$ErrorActionPreference = 'Stop'
$rootPath = Split-Path -Parent $PSScriptRoot
$docPath = Join-Path $rootPath 'demand\北邮校园综合交互论坛_需求分析文档.docx'
$renderPath = Join-Path $PSScriptRoot 'fras-update'
New-Item -ItemType Directory -Path $renderPath -Force | Out-Null
$pdfPath = Join-Path $renderPath $PdfName
$wordApp = New-Object -ComObject Word.Application
$wordApp.Visible = $false
$wordApp.DisplayAlerts = 0
$wordDoc = $null
try {
    $wordDoc = $wordApp.Documents.Open($docPath, $false, $true)
    $wordDoc.Repaginate()
    $pageCount = $wordDoc.ComputeStatistics(2)
    $wordDoc.ExportAsFixedFormat($pdfPath, 17)
    Write-Output ('pages=' + $pageCount)
    Write-Output ('pdf=' + $pdfPath)
} finally {
    if ($null -ne $wordDoc) { $wordDoc.Close(0) }
    $wordApp.Quit()
}
