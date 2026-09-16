param([switch]$NoBrowser, [ValidateRange(5,120)][int]$StartupTimeoutSeconds = 30)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$backend = Join-Path $root "backend"
$uvicorn = Join-Path $backend "venv\Scripts\uvicorn.exe"
if (-not (Test-Path $uvicorn)) { throw "Install backend requirements first; see RUN.md." }
$url = "http://127.0.0.1:8001"
$process = Start-Process -FilePath $uvicorn -ArgumentList "main:app --host 127.0.0.1 --port 8001" -WorkingDirectory $backend -PassThru
try { $deadline=(Get-Date).AddSeconds($StartupTimeoutSeconds); do { try { if ((Invoke-WebRequest "$url/health" -UseBasicParsing -TimeoutSec 2).StatusCode -eq 200) { break } } catch {}; Start-Sleep -Seconds 1 } while ((Get-Date) -lt $deadline); Write-Host "EvolveTrace is ready: $url"; if (-not $NoBrowser) { Start-Process $url }; [void][System.Console]::ReadKey($true) } finally { if (-not $process.HasExited) { Stop-Process -Id $process.Id -Force } }
