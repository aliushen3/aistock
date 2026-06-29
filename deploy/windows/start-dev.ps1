<#
.SYNOPSIS
  Start AiStock backend (API + Celery worker + beat) and frontend for dev/verification.

.DESCRIPTION
  Loads deploy\aistock.env, then launches each process in its own PowerShell window:
    1. FastAPI (uvicorn)            :8000
    2. Celery worker (eventlet)
    3. Celery beat (scheduler)
    4. Frontend (vite dev server)  :5173

  This is for development / smoke testing. For production use install-services.ps1
  (NSSM Windows services) + a static web server (Nginx for Windows / Caddy).

.PARAMETER NoFrontend
  Skip launching the frontend dev server.

.PARAMETER WorkerPool
  Celery pool: "eventlet" (concurrent, recommended) or "solo" (single task).
#>
param(
    [switch]$NoFrontend,
    [ValidateSet("eventlet", "solo")]
    [string]$WorkerPool = "eventlet"
)

$ErrorActionPreference = "Stop"
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$backend  = Join-Path $repoRoot "backend"
$frontend = Join-Path $repoRoot "frontend"
$venvPy   = Join-Path $backend ".venv\Scripts\python.exe"
$loadEnv  = Join-Path $PSScriptRoot "load-env.ps1"

if (-not (Test-Path $venvPy)) {
    throw "venv not found. Run deploy\windows\setup-backend.ps1 first."
}

# Common preamble each child window runs: load env + cd backend.
$preamble = ". `"$loadEnv`"; Set-Location `"$backend`";"

function Start-InWindow {
    param([string]$Title, [string]$Command)
    $full = "$preamble `$host.UI.RawUI.WindowTitle='$Title'; $Command"
    Start-Process -FilePath "powershell.exe" `
        -ArgumentList @("-NoExit", "-NoProfile", "-Command", $full)
    Write-Host "[start] launched: $Title" -ForegroundColor Green
}

Write-Host "[start] repo = $repoRoot" -ForegroundColor Cyan

Start-InWindow -Title "aistock-api" `
    -Command "& `"$venvPy`" -m uvicorn app.main:app --host 0.0.0.0 --port 8000"

Start-Sleep -Seconds 2

Start-InWindow -Title "aistock-celery-worker" `
    -Command "& `"$venvPy`" -m celery -A app.celery_app.celery_app worker -l info -P $WorkerPool"

Start-InWindow -Title "aistock-celery-beat" `
    -Command "& `"$venvPy`" -m celery -A app.celery_app.celery_app beat -l info"

if (-not $NoFrontend) {
    $feCmd = "Set-Location `"$frontend`"; if (-not (Test-Path node_modules)) { npm install }; npm run dev"
    Start-Process -FilePath "powershell.exe" `
        -ArgumentList @("-NoExit", "-NoProfile", "-Command", "`$host.UI.RawUI.WindowTitle='aistock-frontend'; $feCmd")
    Write-Host "[start] launched: aistock-frontend" -ForegroundColor Green
}

Write-Host ""
Write-Host "API:      http://127.0.0.1:8000/api/v1/health" -ForegroundColor Yellow
if (-not $NoFrontend) {
    Write-Host "Frontend: http://127.0.0.1:5173" -ForegroundColor Yellow
}
