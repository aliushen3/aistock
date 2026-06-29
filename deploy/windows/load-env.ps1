<#
.SYNOPSIS
  Load a KEY=VALUE .env file into the current PowerShell process environment.

.DESCRIPTION
  Parses an env file (default: deploy/aistock.env) and sets each variable via
  [Environment]::SetEnvironmentVariable(..., 'Process'). Lines starting with '#'
  and blank lines are ignored. Surrounding quotes around values are stripped.

  Dot-source this script so the variables stay in your session:
      . .\deploy\windows\load-env.ps1

.PARAMETER EnvFile
  Path to the env file. Defaults to <repo>\deploy\aistock.env
#>
param(
    [string]$EnvFile
)

if (-not $EnvFile) {
    $repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
    $EnvFile = Join-Path $repoRoot "deploy\aistock.env"
}

if (-not (Test-Path $EnvFile)) {
    Write-Error "Env file not found: $EnvFile (copy deploy/aistock.env.example first)"
    return
}

$count = 0
Get-Content -LiteralPath $EnvFile -Encoding UTF8 | ForEach-Object {
    $line = $_.Trim()
    if ($line -eq "" -or $line.StartsWith("#")) { return }

    $idx = $line.IndexOf("=")
    if ($idx -lt 1) { return }

    $key = $line.Substring(0, $idx).Trim()
    $val = $line.Substring($idx + 1).Trim()

    # strip matching surrounding quotes
    if (($val.StartsWith('"') -and $val.EndsWith('"')) -or
        ($val.StartsWith("'") -and $val.EndsWith("'"))) {
        $val = $val.Substring(1, $val.Length - 2)
    }

    [Environment]::SetEnvironmentVariable($key, $val, "Process")
    $count++
}

Write-Host "[load-env] loaded $count variables from $EnvFile" -ForegroundColor Green
