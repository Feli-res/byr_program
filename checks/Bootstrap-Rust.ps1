$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Use-ProjectTools.ps1')
$taskRoot = Split-Path -Parent $PSScriptRoot
$downloads = Join-Path $taskRoot '.local\downloads'
New-Item -ItemType Directory -Path $downloads,(Join-Path $taskRoot '.local\logs') -Force | Out-Null
$installer = Join-Path $downloads 'rustup-init.exe'
$checksum = $installer + '.sha256'
$url = 'https://static.rust-lang.org/rustup/dist/x86_64-pc-windows-gnu/rustup-init.exe'
& curl.exe --fail --location --silent --show-error --connect-timeout 20 --max-time 180 $url --output $installer
if ($LASTEXITCODE -ne 0) { throw 'Rust installer download failed.' }
& curl.exe --fail --location --silent --show-error --connect-timeout 20 --max-time 60 ($url+'.sha256') --output $checksum
if ($LASTEXITCODE -ne 0) { throw 'Rust checksum download failed.' }
$expected = ((Get-Content -Raw -LiteralPath $checksum).Trim() -split '\s+')[0]
if ((Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash -ne $expected) { throw 'Rust checksum mismatch.' }
& $installer -y --no-modify-path --profile minimal --default-host x86_64-pc-windows-gnu --default-toolchain 1.99.1
if ($LASTEXITCODE -ne 0) { throw 'Rust installation failed.' }
& cargo --version
& rustc --version
