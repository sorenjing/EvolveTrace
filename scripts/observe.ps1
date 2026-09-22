[CmdletBinding()]
param(
    [string]$BaseUrl = "http://127.0.0.1:8001",
    [switch]$ExpectEvidence
)

$ErrorActionPreference = "Stop"
$base = $BaseUrl.TrimEnd("/")

function Invoke-ReadOnlyJson {
    param(
        [string]$Label,
        [string]$Path
    )

    Write-Host "`n== $Label =="
    $result = Invoke-RestMethod -Uri "$base$Path" -Method Get -TimeoutSec 5
    return $result
}

try {
    Write-Host "EvolveTrace observation"
    Write-Host "Base URL: $base"
    Write-Host "Mode: read-only"

    $health = Invoke-ReadOnlyJson -Label "Service health" -Path "/health"
    Write-Host "Health: $($health.status)"

    Write-Host "`n== Workbench =="
    $workbench = Invoke-WebRequest -Uri "$base/" -Method Get -UseBasicParsing -TimeoutSec 5
    Write-Host "HTTP status: $($workbench.StatusCode)"

    $sessions = @(Invoke-ReadOnlyJson -Label "Audit sessions" -Path "/api/audit/sessions")
    Write-Host "Session count: $($sessions.Count)"
    if ($sessions.Count -gt 0) {
        $latest = $sessions[0]
        Write-Host "Latest session: $($latest.session_id)"
        Write-Host "Latest event count: $($latest.event_count)"
        Write-Host "Latest risk count: $($latest.risk_count)"
    }

    $tasks = @(Invoke-ReadOnlyJson -Label "Harness tasks" -Path "/api/harness/tasks")
    Write-Host "Task count: $($tasks.Count)"

    $unboundRuns = @(Invoke-ReadOnlyJson -Label "Unbound runs" -Path "/api/harness/runs/unbound")
    Write-Host "Unbound run count: $($unboundRuns.Count)"
    if ($unboundRuns.Count -gt 0) {
        Write-Host "Attention: inspect repository-path matching and active task selection."
    }
} catch {
    Write-Error "Observation failed: $($_.Exception.Message)"
    exit 2
}

Write-Host "`n== Summary =="
if ($ExpectEvidence -and ($sessions.Count -eq 0)) {
    Write-Host "Service is healthy, but no Hook evidence is available yet."
    exit 1
}

Write-Host "Service and read-only observation endpoints are available."
exit 0
