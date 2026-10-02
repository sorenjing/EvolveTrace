[CmdletBinding()]
param(
    [string]$Workspace = (Get-Location).Path
)

$ErrorActionPreference = "Stop"

try {
    $workspacePath = (Resolve-Path -LiteralPath $Workspace).Path
} catch {
    Write-Error "Workspace does not exist: $Workspace"
    exit 2
}

if (-not (Test-Path -LiteralPath (Join-Path $workspacePath ".aictx.toml"))) {
    Write-Error "Not an AI Context Kit workspace: $workspacePath"
    exit 2
}

$aictxCommand = Get-Command "aictx" -ErrorAction SilentlyContinue
if ($null -eq $aictxCommand) {
    Write-Error "aictx is not available on PATH."
    exit 2
}

function Invoke-AictxReadOnly {
    param(
        [string]$Label,
        [string[]]$Arguments
    )

    Write-Host "`n== $Label =="
    $output = & $aictxCommand.Source @Arguments 2>&1
    $exitCode = $LASTEXITCODE
    if ($null -ne $output) {
        $output | ForEach-Object { Write-Host $_ }
    }

    return $exitCode
}

Write-Host "AI Context Kit self-check"
Write-Host "Workspace: $workspacePath"
Write-Host "Mode: read-only"

$versionExit = Invoke-AictxReadOnly -Label "CLI version" -Arguments @("--version")
if ($versionExit -ne 0) {
    Write-Error "Unable to run aictx."
    exit 2
}

$scanExit = Invoke-AictxReadOnly -Label "Project discovery" -Arguments @(
    "scan", "--workspace", $workspacePath
)
if ($scanExit -ne 0) {
    Write-Error "Project discovery failed. Review the configuration and command output."
    exit 2
}

$statusExit = Invoke-AictxReadOnly -Label "Freshness" -Arguments @(
    "status", "--workspace", $workspacePath
)
$checkExit = Invoke-AictxReadOnly -Label "Workspace integrity" -Arguments @(
    "check", "--workspace", $workspacePath
)

Write-Host "`n== Summary =="
if (($statusExit -eq 0) -and ($checkExit -eq 0)) {
    Write-Host "Healthy: discovery, freshness, and workspace integrity checks passed."
    exit 0
}

Write-Host "Maintenance required: review new, stale, or missing projects and integrity findings above."
Write-Host "This script made no changes. Follow the reviewed dry-run workflow in docs/zh-CN/usage.md."
exit 1
