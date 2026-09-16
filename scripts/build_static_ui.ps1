$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
npm ci
npm run build
$target = Join-Path $root "backend\static"
if (Test-Path $target) { Remove-Item -Recurse -Force $target }
New-Item -ItemType Directory -Path $target | Out-Null
Copy-Item -Path (Join-Path $root "out\*") -Destination $target -Recurse -Force
