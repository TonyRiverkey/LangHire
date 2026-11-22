$ErrorActionPreference = 'Stop'
$projectDir = Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $projectDir

foreach ($port in @(8743, 1420)) {
    if (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) {
        throw "Port $port is already in use. Stop the existing app before starting LangHire."
    }
}

$python = Join-Path $projectDir '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    throw 'Run uv sync --python 3.13 before starting LangHire.'
}
if (-not (Test-Path -LiteralPath (Join-Path $projectDir 'node_modules'))) {
    throw 'Run npm ci before starting LangHire.'
}

# UTF-8 is needed for the agent logs on Windows; disable browser-use telemetry locally.
$env:PYTHONUTF8 = '1'
$env:ANONYMIZED_TELEMETRY = 'false'
New-Item -ItemType Directory -Path logs -Force | Out-Null
$backend = Start-Process -FilePath $python -ArgumentList 'backend/main.py' -WorkingDirectory $projectDir -WindowStyle Hidden -PassThru -RedirectStandardOutput 'logs\backend-stdout.log' -RedirectStandardError 'logs\backend-stderr.log'
try {
    Write-Host 'Open http://127.0.0.1:1420 when Vite is ready. Press Ctrl+C to stop.'
    & npm.cmd run dev
} finally {
    if (-not $backend.HasExited) { Stop-Process -Id $backend.Id }
}
