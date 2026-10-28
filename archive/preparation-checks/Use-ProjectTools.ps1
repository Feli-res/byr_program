$ErrorActionPreference='Stop'
$taskRoot=Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
. (Join-Path $taskRoot 'scripts/Use-ProjectTools.ps1')
New-Item -ItemType Directory -Path (Join-Path $PSScriptRoot 'results') -Force | Out-Null
