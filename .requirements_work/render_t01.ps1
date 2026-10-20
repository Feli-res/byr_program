$ErrorActionPreference = 'Stop'
$workPath = Join-Path $PSScriptRoot 't01-20261020'
$draftPath = Join-Path $workPath 'updated-requirements.docx'
$renderPath = Join-Path $workPath 'native-pages'
New-Item -ItemType Directory -Path $renderPath -Force | Out-Null
Add-Type -AssemblyName System.Drawing
$wordApp = New-Object -ComObject Word.Application
$wordApp.Visible = $false
$wordApp.DisplayAlerts = 0
$wordApp.AutomationSecurity = 3
$wordDoc = $null
try {
    $wordDoc = $wordApp.Documents.Open($draftPath, $false, $true, $false)
    $wordDoc.Repaginate()
    $pageCount = $wordDoc.ComputeStatistics(2)
    $pageTexts = @()
    for ($pageNo=1; $pageNo -le $pageCount; $pageNo++) {
        $rangeStart = $wordDoc.GoTo(1,1,$pageNo).Start
        if ($pageNo -lt $pageCount) { $rangeEnd=$wordDoc.GoTo(1,1,($pageNo+1)).Start } else { $rangeEnd=$wordDoc.Content.End }
        $pageRange = $wordDoc.Range($rangeStart,$rangeEnd)
        $emfPath = Join-Path $renderPath ('page-'+$pageNo+'.emf')
        [IO.File]::WriteAllBytes($emfPath,[byte[]]$pageRange.EnhMetaFileBits)
        $metafile = [Drawing.Imaging.Metafile]::FromFile($emfPath)
        try {
            $targetWidth=1400
            $targetHeight=[int][Math]::Round($metafile.Height*$targetWidth/$metafile.Width)
            $bitmap = New-Object Drawing.Bitmap($targetWidth,$targetHeight)
            $bitmap.SetResolution(168,168)
            $graphics = [Drawing.Graphics]::FromImage($bitmap)
            try {
                $graphics.Clear([Drawing.Color]::White)
                $graphics.DrawImage($metafile,0,0,$targetWidth,$targetHeight)
                $bitmap.Save((Join-Path $renderPath ('page-'+$pageNo+'.png')),[Drawing.Imaging.ImageFormat]::Png)
            } finally { $graphics.Dispose(); $bitmap.Dispose() }
        } finally { $metafile.Dispose() }
        $pageTexts += @{ page=$pageNo; start=$rangeStart; end=$rangeEnd; text=$pageRange.Text }
    }
    Get-ChildItem -LiteralPath $renderPath -File | Where-Object { $_.Name -match '^page-(\d+)\.(png|emf)$' -and [int]$Matches[1] -gt $pageCount } | ForEach-Object { Remove-Item -LiteralPath $_.FullName }
    $pageTexts | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $workPath 'native-page-text.json') -Encoding utf8
    Write-Output ('Rendered pages: '+$pageCount)
} finally {
    if ($null -ne $wordDoc) { $wordDoc.Close(0) }
    $wordApp.Quit()
}
