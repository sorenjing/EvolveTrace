param(
    [switch]$NoBrowser,
    [ValidateRange(5, 120)]
    [int]$StartupTimeoutSeconds = 30
)

$ErrorActionPreference = "Stop"

$PROJECT_ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path
$BACKEND_DIR = Join-Path $PROJECT_ROOT "backend"
$VENV_DIR = Join-Path $BACKEND_DIR "venv"
$VENV_UVICORN = Join-Path $VENV_DIR "Scripts\uvicorn.exe"
$NODE_MODULES = Join-Path $PROJECT_ROOT "node_modules"
$BACKEND_URL = "http://127.0.0.1:8001/health"
$DASHBOARD_URL = "http://127.0.0.1:3000"

function Write-Step {
    param([string]$Msg)
    Write-Host "[*] $Msg" -ForegroundColor Cyan
}
function Write-OK {
    param([string]$Msg)
    Write-Host "[+] $Msg" -ForegroundColor Green
}
function Write-Warn {
    param([string]$Msg)
    Write-Host "[!] $Msg" -ForegroundColor Yellow
}
function Write-Fail {
    param([string]$Msg)
    Write-Host "[X] $Msg" -ForegroundColor Red
}
function Wait-ForHttp {
    param(
        [string]$Url,
        [int]$TimeoutSeconds
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
                return $true
            }
        } catch {
            Start-Sleep -Seconds 1
        }
    }
    return $false
}

Write-Step "Checking environment..."

$backendReady = $true
if (-not (Test-Path $VENV_DIR)) {
    Write-Warn "Backend virtual environment not found at: $VENV_DIR"
    Write-Warn "Run the one-time backend setup described in RUN.md."
    $backendReady = $false
} elseif (-not (Test-Path $VENV_UVICORN)) {
    Write-Warn "uvicorn not found in the backend virtual environment."
    Write-Warn "Run the one-time dependency installation described in RUN.md."
    $backendReady = $false
}

$frontendReady = $true
if (-not (Test-Path $NODE_MODULES)) {
    Write-Warn "node_modules not found. Run the one-time npm install described in RUN.md."
    $frontendReady = $false
}

if (-not $backendReady -or -not $frontendReady) {
    Write-Fail "EvolveTrace needs both local services. Complete the one-time setup, then run this script again."
    exit 1
}

$backendProcess = $null
$frontendProcess = $null

try {
    Write-Step "Starting audit service..."
    $backendProcess = Start-Process -FilePath $VENV_UVICORN -ArgumentList "main:app --host 127.0.0.1 --port 8001 --reload" -WorkingDirectory $BACKEND_DIR -PassThru

    Write-Step "Starting review workbench..."
    $frontendProcess = Start-Process -FilePath "npm.cmd" -ArgumentList "run", "dev" -WorkingDirectory $PROJECT_ROOT -PassThru

    if (-not (Wait-ForHttp -Url $BACKEND_URL -TimeoutSeconds $StartupTimeoutSeconds)) {
        throw "The audit service did not become ready within $StartupTimeoutSeconds seconds."
    }
    if (-not (Wait-ForHttp -Url $DASHBOARD_URL -TimeoutSeconds $StartupTimeoutSeconds)) {
        throw "The review workbench did not become ready within $StartupTimeoutSeconds seconds."
    }

    Write-OK "EvolveTrace is ready: $DASHBOARD_URL"
    if ($NoBrowser) {
        Write-Host "  In ChatGPT desktop Codex, use @Browser to open: $DASHBOARD_URL" -ForegroundColor DarkGray
    } else {
        Write-Step "Opening the dashboard in your default browser..."
        Start-Process $DASHBOARD_URL
    }

    Write-Host ""
    Write-Host "Press any key to stop EvolveTrace..." -ForegroundColor DarkGray
    [void][System.Console]::ReadKey($true)
}
finally {
    Write-Host ""
    Write-Step "Stopping EvolveTrace..."

    if ($null -ne $frontendProcess -and -not $frontendProcess.HasExited) {
        Stop-Process -Id $frontendProcess.Id -Force -ErrorAction SilentlyContinue
    }
    if ($null -ne $backendProcess -and -not $backendProcess.HasExited) {
        Stop-Process -Id $backendProcess.Id -Force -ErrorAction SilentlyContinue
    }

    Write-OK "Stopped."
}
