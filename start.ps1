$ErrorActionPreference = "Stop"

$PROJECT_ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path
$BACKEND_DIR = Join-Path $PROJECT_ROOT "backend"
$VENV_DIR = Join-Path $BACKEND_DIR "venv"
$VENV_PYTHON = Join-Path $VENV_DIR "Scripts\python.exe"
$VENV_UVICORN = Join-Path $VENV_DIR "Scripts\uvicorn.exe"
$NODE_MODULES = Join-Path $PROJECT_ROOT "node_modules"

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

Write-Step "Checking environment..."

$backendReady = $true
if (-not (Test-Path $VENV_DIR)) {
    Write-Warn "Backend virtual environment not found at: $VENV_DIR"
    Write-Warn "Please run the following commands first:"
    Write-Host ""
    Write-Host "  cd backend"
    Write-Host "  python -m venv venv"
    Write-Host "  .\venv\Scripts\pip install -r requirements.txt"
    Write-Host "  copy .env.example .env   (then edit .env with your LLM_API_KEY)"
    Write-Host ""
    $backendReady = $false
} elseif (-not (Test-Path $VENV_UVICORN)) {
    Write-Warn "uvicorn not found in venv. Installing dependencies..."
    Write-Host "  cd backend; .\venv\Scripts\pip install -r requirements.txt"
    Write-Host ""
    $backendReady = $false
}

$frontendReady = $true
if (-not (Test-Path $NODE_MODULES)) {
    Write-Warn "node_modules not found. Installing frontend dependencies first:"
    Write-Host ""
    Write-Host "  npm install"
    Write-Host ""
    $frontendReady = $false
}

if (-not $backendReady -and -not $frontendReady) {
    Write-Fail "Neither backend nor frontend is ready. Please follow RUN.md to set up first."
    exit 1
}

$backendProcess = $null
$frontendProcess = $null

try {
    if ($backendReady) {
        $backendWorkDir = $BACKEND_DIR
        $backendArgs = "main:app --host 127.0.0.1 --port 8001 --reload"
        $backendCmdLine = "-NoExit -Command `"Set-Location '$backendWorkDir'; & '$VENV_UVICORN' $backendArgs`""

        Write-Step "Starting backend on http://localhost:8001 ..."
        $backendProcess = Start-Process powershell -ArgumentList $backendCmdLine -PassThru
        Write-OK "Backend started (PID: $($backendProcess.Id))"
    } else {
        Write-Warn "Skipping backend (not ready)"
    }

    if ($frontendReady) {
        $frontendWorkDir = $PROJECT_ROOT
        $frontendCmdLine = "-NoExit -Command `"Set-Location '$frontendWorkDir'; npm run dev`""

        Write-Step "Starting frontend on http://localhost:3000 ..."
        $frontendProcess = Start-Process powershell -ArgumentList $frontendCmdLine -PassThru
        Write-OK "Frontend started (PID: $($frontendProcess.Id))"
    } else {
        Write-Warn "Skipping frontend (not ready)"
    }

    Write-Host ""
    Write-OK "All services launched."
    if ($backendReady)  { Write-Host "  Backend : http://localhost:8001" }
    if ($frontendReady) { Write-Host "  Frontend: http://localhost:3000" }
    Write-Host ""
    Write-Host "Press any key to stop all services and exit..." -ForegroundColor DarkGray
    try {
        [void][System.Console]::ReadKey($true)
    } catch {
        Write-Host "(Non-interactive mode detected. Services are running in separate windows.)" -ForegroundColor DarkGray
        Write-Host "Close the spawned PowerShell windows manually to stop services." -ForegroundColor DarkGray
        Start-Sleep -Seconds 2
    }
}
finally {
    Write-Host ""
    Write-Step "Stopping services..."

    if ($null -ne $backendProcess -and !$backendProcess.HasExited) {
        try {
            Stop-Process -Id $backendProcess.Id -Force -ErrorAction SilentlyContinue
            Write-OK "Backend stopped (PID: $($backendProcess.Id))"
        } catch {
            Write-Warn "Could not stop backend process (PID: $($backendProcess.Id))"
        }
    }

    if ($null -ne $frontendProcess -and !$frontendProcess.HasExited) {
        try {
            Stop-Process -Id $frontendProcess.Id -Force -ErrorAction SilentlyContinue
            Write-OK "Frontend stopped (PID: $($frontendProcess.Id))"
        } catch {
            Write-Warn "Could not stop frontend process (PID: $($frontendProcess.Id))"
        }
    }

    Write-OK "Done."
}
