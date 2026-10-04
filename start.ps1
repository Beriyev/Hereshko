$ErrorActionPreference = "Stop"

Set-Location -LiteralPath $PSScriptRoot

$uvCache = Join-Path $env:TEMP "hereshko-uv-cache"
$env:UV_CACHE_DIR = $uvCache

Write-Host "Checking Docker..." -ForegroundColor Cyan
docker info *> $null
if ($LASTEXITCODE -ne 0) {
    throw "Docker Desktop is not running. Open Docker Desktop, wait for it to start, then run .\start.ps1 again."
}

Write-Host "Syncing Python dependencies..." -ForegroundColor Cyan
uv sync
if ($LASTEXITCODE -ne 0) {
    throw "Python dependency sync failed."
}

Write-Host "Starting Weaviate..." -ForegroundColor Cyan
docker compose up -d

$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

if (Test-Path -LiteralPath $venvPython) {
    $backendCommand = "& '$venvPython' -m uvicorn app.main:app --reload --port 8000"
    $mcpCommand = "& '$venvPython' -m app.mcp_server"
} else {
    $backendCommand = "`$env:UV_CACHE_DIR = '$uvCache'; uv run --project . uvicorn app.main:app --reload --port 8000"
    $mcpCommand = "`$env:UV_CACHE_DIR = '$uvCache'; uv run --project . python -m app.mcp_server"
}
$frontendCommand = "py -m http.server 4173 --directory frontend"

Write-Host "Starting MCP web tools on http://127.0.0.1:8765/mcp..." -ForegroundColor Cyan
Start-Process powershell.exe `
    -WorkingDirectory $PSScriptRoot `
    -ArgumentList @("-NoExit", "-Command", $mcpCommand)

Write-Host "Starting backend on http://localhost:8000..." -ForegroundColor Cyan
Start-Process powershell.exe `
    -WorkingDirectory $PSScriptRoot `
    -ArgumentList @("-NoExit", "-Command", $backendCommand)

Write-Host "Starting frontend on http://localhost:4173..." -ForegroundColor Cyan
Start-Process powershell.exe `
    -WorkingDirectory $PSScriptRoot `
    -ArgumentList @("-NoExit", "-Command", $frontendCommand)

Start-Sleep -Seconds 2
Start-Process "http://localhost:4173"

Write-Host "Hereshko is starting." -ForegroundColor Green
Write-Host "Frontend: http://localhost:4173"
Write-Host "API docs: http://localhost:8000/docs"
