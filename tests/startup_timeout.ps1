$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$probeRoot = Join-Path $root ("runtime\startup-timeout-" + (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
$probeBackend = Join-Path $probeRoot 'backend'
$probeVenv = Join-Path $probeBackend 'venv'
New-Item -ItemType Directory -Path (Join-Path $probeVenv 'Scripts') -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $root 'start.ps1') -Destination (Join-Path $probeRoot 'start.ps1')
Copy-Item -LiteralPath (Join-Path $root 'backend/venv/Scripts/python.exe') -Destination (Join-Path $probeVenv 'Scripts/python.exe')
Copy-Item -LiteralPath (Join-Path $root 'backend/venv/pyvenv.cfg') -Destination (Join-Path $probeVenv 'pyvenv.cfg')
"import time`ntime.sleep(30)`n" | Set-Content -LiteralPath (Join-Path $probeBackend 'main.py') -Encoding utf8
$previousPythonPath = $env:PYTHONPATH
$env:PYTHONPATH = Join-Path $root 'backend/venv/Lib/site-packages'
# Simulate an unreachable health/status API while an actual copied venv
# launcher and its Python child wait inside a slow module import.
function Invoke-RestMethod { throw 'Synthetic startup probe: not ready.' }
$timedOut = $false
try {
    & (Join-Path $probeRoot 'start.ps1') -NoBrowser -Detached -StartupTimeoutSeconds 5
} catch {
    if ($_.Exception.Message -notlike '*did not become healthy*') { throw }
    $timedOut = $true
} finally { $env:PYTHONPATH = $previousPythonPath }
if (-not $timedOut) { throw 'Expected startup timeout did not occur.' }
Start-Sleep -Milliseconds 800
$leftovers = @(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and $_.CommandLine.Contains((Join-Path $probeVenv 'Scripts\python.exe')) })
if ($leftovers.Count) { throw "Startup timeout left $($leftovers.Count) Python processes." }
Write-Host 'PASS: slow startup timed out and both venv launcher and Python child were cleaned up.'
