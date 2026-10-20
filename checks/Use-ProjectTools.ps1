$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
New-Item -ItemType Directory -Path (Join-Path $taskRoot '.local\logs'),(Join-Path $PSScriptRoot 'results') -Force | Out-Null
$env:CARGO_HOME = Join-Path $taskRoot '.local\cargo'
$env:RUSTUP_HOME = Join-Path $taskRoot '.local\rustup'
$env:CARGO_TARGET_DIR = Join-Path $taskRoot '.local\rust-target'
$env:CARGO_BUILD_JOBS = '4'
$env:npm_config_cache = Join-Path $taskRoot '.local\npm-cache'
$env:PATH = (Join-Path $env:CARGO_HOME 'bin') + ';' + $env:PATH
if ($env:BYR_MINGW_BIN -and (Test-Path -LiteralPath (Join-Path $env:BYR_MINGW_BIN 'gcc.exe'))) {
    $env:PATH = $env:BYR_MINGW_BIN + ';' + $env:PATH
} elseif (Test-Path -LiteralPath 'D:\mingw64\bin\gcc.exe') {
    $env:PATH = 'D:\mingw64\bin;' + $env:PATH
}
