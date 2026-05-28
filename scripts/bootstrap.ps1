#Requires -Version 5.1

<#
.SYNOPSIS
    Bootstrap script for Marcin Włoch Kiro Swarm demo (Windows PowerShell)

.DESCRIPTION
    Installs uv (if needed), runs uv sync in mcp-server/, and smoke-tests the setup.

.EXAMPLE
    .\scripts\bootstrap.ps1

#>

Write-Host "=== Marcin Włoch Kiro Swarm Demo Bootstrap ===" -ForegroundColor Cyan

# Step 1: Check uv
Write-Host "`n[1/3] Checking uv..." -ForegroundColor Blue
$uv = Get-Command uv -ErrorAction SilentlyContinue
if (-not $uv) {
    Write-Host "  uv not found. Installing..." -ForegroundColor Yellow
    irm https://astral.sh/uv/install.ps1 | iex
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
    Write-Host "  uv installed." -ForegroundColor Green
} else {
    Write-Host "  uv $(uv --version)" -ForegroundColor Green
}

# Step 2: Sync mcp-server
Write-Host "`n[2/3] Running 'uv sync' in mcp-server/..." -ForegroundColor Blue
cd "$PSScriptRoot/../mcp-server"
uv sync --python 3.12 --frozen --no-dev
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ERROR: uv sync failed" -ForegroundColor Red
    exit 1
}
Write-Host "  uv sync OK" -ForegroundColor Green

# Step 3: Smoke test (load aws-endpoints.env, same vars as .kiro/settings/mcp.json)
Write-Host "`n[3/3] Running smoke test..." -ForegroundColor Blue
$envFile = Join-Path $PSScriptRoot "..\aws-endpoints.env"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        $line = $_.Trim()
        if ($line -eq "" -or $line.StartsWith("#")) { return }
        $eq = $line.IndexOf("=")
        if ($eq -gt 0) {
            $name = $line.Substring(0, $eq).Trim()
            $value = $line.Substring($eq + 1).Trim()
            Set-Item -Path "env:$name" -Value $value
        }
    }
    Write-Host "  Loaded aws-endpoints.env" -ForegroundColor Green
} else {
    Write-Host "  WARNING: aws-endpoints.env not found - smoke test may fail" -ForegroundColor Yellow
}
uv run python -m swarm_mcp.server --self-test
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ERROR: smoke test failed" -ForegroundColor Red
    exit 1
}
Write-Host "  Smoke test OK" -ForegroundColor Green

Write-Host "`n=== Bootstrap Complete ===" -ForegroundColor Green
Write-Host "`nNext steps:" -ForegroundColor Cyan
Write-Host "  1. Set AWS credentials: aws configure --profile nortal-swarm"
Write-Host "  2. Open this folder in Kiro IDE"
Write-Host "  3. Reload MCP servers (if needed) and see 'nortal-swarm' with 8 tools"
Write-Host "  4. Check README.md for demo instructions"
