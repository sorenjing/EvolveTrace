param(
    [switch]$NoBrowser,
    [switch]$Detached,
    [string]$Workspace,
    [ValidateRange(5,120)][int]$StartupTimeoutSeconds = 30
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$backend = Join-Path $root "backend"
$python = Join-Path $backend "venv\Scripts\python.exe"
$url = "http://127.0.0.1:8001"
$process = $null
$ownedServerId = $null
$keepRunning = $false

function Get-CaptureStatus {
    $status = Invoke-RestMethod "$url/api/activity/status" -TimeoutSec 2
    if ($status.schema_version -ne "activity-status/v1") { throw "Port 8001 is not serving a compatible EvolveTrace instance." }
    return $status
}

# Locate the configured workspace without reading other projects' memory.
if ($Workspace) {
    $workspaceRoot = (Resolve-Path -LiteralPath $Workspace).Path
    if (-not (Test-Path -LiteralPath (Join-Path $workspaceRoot ".aictx.toml"))) { throw "Workspace must contain .aictx.toml." }
} else {
    $workspaceRoot = $root
    while ($workspaceRoot -and -not (Test-Path -LiteralPath (Join-Path $workspaceRoot ".aictx.toml"))) {
        $workspaceRoot = Split-Path -Parent $workspaceRoot
    }
}

$healthy = $false
try { $healthy = (Invoke-RestMethod "$url/health" -TimeoutSec 2).status -eq "ok" } catch {}
if ($healthy) {
    # Never take ownership of, or stop, an existing service.
    $status = Get-CaptureStatus
    Write-Host "Reusing EvolveTrace (PID $($status.process_id))."
} else {
    if (-not (Test-Path -LiteralPath $python)) { throw "Install backend requirements first; see RUN.md." }
    $logRoot = Join-Path $root "runtime\local-service"
    New-Item -ItemType Directory -Path $logRoot -Force | Out-Null
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss-fff"
    $process = Start-Process -FilePath $python -ArgumentList "-m uvicorn main:app --host 127.0.0.1 --port 8001" -WorkingDirectory $backend -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logRoot "$stamp.log") -RedirectStandardError (Join-Path $logRoot "$stamp-error.log")
}

try {
    if ($process) {
        $deadline = (Get-Date).AddSeconds($StartupTimeoutSeconds)
        $status = $null
        do {
            $process.Refresh()
            if ($process.HasExited) { throw "Backend exited during startup. See runtime/local-service logs." }
            try { $status = Get-CaptureStatus } catch {}
            if ($status) { break }
            Start-Sleep -Milliseconds 500
        } while ((Get-Date) -lt $deadline)
        if (-not $status) { throw "EvolveTrace did not become healthy within $StartupTimeoutSeconds seconds. See runtime/local-service logs." }
        # Windows venv launchers may create a child Python process. Verify that
        # the responding server belongs to this launch before managing its PID.
        $server = Get-CimInstance Win32_Process -Filter "ProcessId=$([int]$status.process_id)"
        if ($server.ProcessId -ne $process.Id -and $server.ParentProcessId -ne $process.Id) { throw "Responding service does not belong to this launch." }
        $ownedServerId = [int]$status.process_id
        @{ ProcessId = $ownedServerId; LauncherId = $process.Id; BaseUrl = $url; StartedAt = $status.started_at } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $logRoot "process.json") -Encoding utf8
    }
    if ($workspaceRoot) {
        try {
            if (-not (Get-Command aictx -ErrorAction SilentlyContinue)) { throw "aictx is not on PATH." }
            $registration = & aictx audit sync --workspace $workspaceRoot --evolvetrace-url $url
            if ($LASTEXITCODE -ne 0) { throw "aictx audit sync failed." }
            $registered = $registration | ConvertFrom-Json
            Write-Host "Registered $(@($registered.projects).Count) project directories."
        } catch { Write-Warning "Project registration unavailable: $($_.Exception.Message) Use aictx audit sync after fixing the Context CLI." }
    } else { Write-Warning "No ancestor .aictx.toml found. Use -Workspace to register project directories." }
    Write-Host "EvolveTrace is ready: $url"
    if (-not $NoBrowser) { Start-Process $url }
    $keepRunning = $Detached -or [Console]::IsInputRedirected -or -not $process
    if ($keepRunning) {
        Write-Host "Backend remains running (PID $($status.process_id)). Collection status: $url/api/activity/status"
    } else {
        Write-Host "Press any key to stop this backend. Use -Detached to keep it running."
        [void][Console]::ReadKey($true)
    }
} finally {
    if ($process -and -not $keepRunning) {
        # A timeout can happen before the API reveals its PID. Discover only
        # Python children from this launch so a slow import cannot survive it.
        $children = @(Get-CimInstance Win32_Process -Filter "ParentProcessId=$($process.Id)" -ErrorAction SilentlyContinue | Where-Object {
            $_.Name -eq "python.exe" -and $_.CommandLine -like '*-m uvicorn main:app --host 127.0.0.1 --port 8001*'
        })
        foreach ($child in $children) { Stop-Process -Id $child.ProcessId -ErrorAction SilentlyContinue }
        if ($ownedServerId -and $ownedServerId -ne $process.Id -and $ownedServerId -notin $children.ProcessId) {
            Write-Warning "Server process no longer belongs to the launcher; leaving it untouched."
        }
        $process.Refresh()
        if (-not $process.HasExited) { Stop-Process -Id $process.Id -ErrorAction SilentlyContinue }
    }
}
