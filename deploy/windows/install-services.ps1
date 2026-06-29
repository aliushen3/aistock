<#
.SYNOPSIS
  Register AiStock backend processes as Windows services via NSSM (production).

.DESCRIPTION
  Creates three Windows services (equivalent to Linux systemd units):
    aistock-api             FastAPI / uvicorn :8000
    aistock-celery-worker   Celery worker (eventlet pool)
    aistock-celery-beat     Celery beat scheduler

  Each service:
    - runs backend\.venv\Scripts\python.exe
    - starts in the backend directory
    - loads every KEY=VALUE from deploy\aistock.env as service environment
    - writes stdout/stderr to deploy\windows\logs\<service>.log

  Requires NSSM (https://nssm.cc). Install via:  choco install nssm
  Must be run from an ELEVATED (Administrator) PowerShell.

.PARAMETER Action
  install | uninstall | restart | status   (default: install)

.PARAMETER Nssm
  Path to nssm.exe. Defaults to "nssm" on PATH.

.PARAMETER WorkerPool
  Celery pool for the worker service: eventlet (default) or solo.
#>
param(
    [ValidateSet("install", "uninstall", "restart", "status")]
    [string]$Action = "install",
    [string]$Nssm = "nssm",
    [ValidateSet("eventlet", "solo")]
    [string]$WorkerPool = "eventlet"
)

$ErrorActionPreference = "Stop"

# --- elevation check ---
$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Run this script from an elevated (Administrator) PowerShell."
}

if (-not (Get-Command $Nssm -ErrorAction SilentlyContinue)) {
    throw "nssm not found. Install with 'choco install nssm' or pass -Nssm <path\nssm.exe>."
}

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$backend  = Join-Path $repoRoot "backend"
$venvPy   = Join-Path $backend ".venv\Scripts\python.exe"
$envFile  = Join-Path $repoRoot "deploy\aistock.env"
$logDir   = Join-Path $PSScriptRoot "logs"

$services = @(
    @{ Name = "aistock-api";           Args = "-m uvicorn app.main:app --host 0.0.0.0 --port 8000" },
    @{ Name = "aistock-celery-worker"; Args = "-m celery -A app.celery_app.celery_app worker -l info -P $WorkerPool" },
    @{ Name = "aistock-celery-beat";   Args = "-m celery -A app.celery_app.celery_app beat -l info" }
)

function Get-EnvBlock {
    # Build NSSM AppEnvironmentExtra value: KEY=VALUE entries separated by NUL? 
    # NSSM accepts repeated "set AppEnvironmentExtra KEY=VALUE"; we collect KEY=VALUE lines.
    if (-not (Test-Path $envFile)) {
        Write-Warning "Env file not found: $envFile (services will start with empty config)"
        return @()
    }
    $pairs = @()
    Get-Content -LiteralPath $envFile -Encoding UTF8 | ForEach-Object {
        $line = $_.Trim()
        if ($line -eq "" -or $line.StartsWith("#")) { return }
        $idx = $line.IndexOf("=")
        if ($idx -lt 1) { return }
        $k = $line.Substring(0, $idx).Trim()
        $v = $line.Substring($idx + 1).Trim()
        if (($v.StartsWith('"') -and $v.EndsWith('"')) -or ($v.StartsWith("'") -and $v.EndsWith("'"))) {
            $v = $v.Substring(1, $v.Length - 2)
        }
        $pairs += "$k=$v"
    }
    return $pairs
}

function Install-Services {
    if (-not (Test-Path $venvPy)) { throw "venv python not found at $venvPy. Run setup-backend.ps1 first." }
    if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
    $envPairs = Get-EnvBlock

    foreach ($svc in $services) {
        $name = $svc.Name
        Write-Host "[install] $name" -ForegroundColor Cyan

        & $Nssm install $name $venvPy | Out-Null
        & $Nssm set $name AppParameters $svc.Args | Out-Null
        & $Nssm set $name AppDirectory $backend | Out-Null
        & $Nssm set $name Start SERVICE_AUTO_START | Out-Null
        & $Nssm set $name AppStdout (Join-Path $logDir "$name.log") | Out-Null
        & $Nssm set $name AppStderr (Join-Path $logDir "$name.log") | Out-Null
        & $Nssm set $name AppRotateFiles 1 | Out-Null
        & $Nssm set $name AppRotateBytes 10485760 | Out-Null

        if ($envPairs.Count -gt 0) {
            # AppEnvironmentExtra expects entries; pass them as one multi-arg set.
            & $Nssm set $name AppEnvironmentExtra @envPairs | Out-Null
        }
    }

    Write-Host "[install] starting services..." -ForegroundColor Cyan
    & $Nssm start aistock-api
    Start-Sleep -Seconds 3
    & $Nssm start aistock-celery-worker
    & $Nssm start aistock-celery-beat
    Write-Host "[install] done. Logs in $logDir" -ForegroundColor Green
}

function Uninstall-Services {
    foreach ($svc in $services) {
        $name = $svc.Name
        Write-Host "[uninstall] $name" -ForegroundColor Yellow
        & $Nssm stop $name confirm 2>$null | Out-Null
        & $Nssm remove $name confirm | Out-Null
    }
    Write-Host "[uninstall] done." -ForegroundColor Green
}

function Restart-Services {
    foreach ($svc in $services) {
        & $Nssm restart $svc.Name
        Write-Host "[restart] $($svc.Name)" -ForegroundColor Green
    }
}

function Show-Status {
    foreach ($svc in $services) {
        $state = (& $Nssm status $svc.Name) 2>$null
        Write-Host ("{0,-26} {1}" -f $svc.Name, $state)
    }
}

switch ($Action) {
    "install"   { Install-Services }
    "uninstall" { Uninstall-Services }
    "restart"   { Restart-Services }
    "status"    { Show-Status }
}
