<#
.SYNOPSIS
  Create the backend Python virtualenv and install dependencies (Windows).

.DESCRIPTION
  - Verifies Python 3.11+ is available.
  - Creates backend\.venv if missing.
  - Upgrades pip and installs backend\requirements.txt.
  - Installs eventlet so Celery can run with a concurrent pool on Windows.

.PARAMETER Python
  Python launcher/executable to use, e.g. "py -3.11" or "python".
  Auto-detected when omitted.
#>
param(
    [string]$Python = ""
)

$ErrorActionPreference = "Stop"
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$backend  = Join-Path $repoRoot "backend"
$venv     = Join-Path $backend ".venv"

function Resolve-Python {
    param([string]$Preferred)
    if ($Preferred) { return $Preferred }
    foreach ($cand in @("py -3.11", "py -3.12", "py -3.13", "python")) {
        $exe = $cand.Split(" ")[0]
        if (Get-Command $exe -ErrorAction SilentlyContinue) { return $cand }
    }
    throw "No Python found. Install Python 3.11+ from https://www.python.org/downloads/windows/"
}

$pythonCmd = Resolve-Python -Preferred $Python
$parts = $pythonCmd.Split(" ")
$exe = $parts[0]
$baseArgs = @()
if ($parts.Length -gt 1) { $baseArgs = $parts[1..($parts.Length - 1)] }

Write-Host "[setup] using Python launcher: $pythonCmd" -ForegroundColor Cyan

# Check version >= 3.11
$pyver = & $exe @baseArgs -c "import sys;print('%d.%d'%sys.version_info[:2])"
Write-Host "[setup] detected Python $pyver" -ForegroundColor Cyan
$major, $minor = $pyver.Split(".")
if ([int]$major -lt 3 -or ([int]$major -eq 3 -and [int]$minor -lt 11)) {
    throw "Python $pyver is too old. Need 3.11+."
}

if (-not (Test-Path $venv)) {
    Write-Host "[setup] creating venv at $venv" -ForegroundColor Cyan
    & $exe @baseArgs -m venv $venv
} else {
    Write-Host "[setup] venv already exists, reusing" -ForegroundColor Yellow
}

$venvPy = Join-Path $venv "Scripts\python.exe"
if (-not (Test-Path $venvPy)) { throw "venv python not found at $venvPy (venv creation failed)" }

Write-Host "[setup] upgrading pip" -ForegroundColor Cyan
& $venvPy -m pip install --upgrade pip

Write-Host "[setup] installing requirements.txt" -ForegroundColor Cyan
& $venvPy -m pip install -r (Join-Path $backend "requirements.txt")

Write-Host "[setup] installing eventlet (Celery pool on Windows)" -ForegroundColor Cyan
& $venvPy -m pip install eventlet

Write-Host "[setup] done. venv = $venv" -ForegroundColor Green
