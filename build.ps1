$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
pnpm --dir frontend install --frozen-lockfile --ignore-scripts
if ($LASTEXITCODE -ne 0) { throw "Frontend dependency install failed" }
pnpm --dir frontend build
if ($LASTEXITCODE -ne 0) { throw "Frontend build failed" }
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-desktop.txt
if ($LASTEXITCODE -ne 0) { throw "Python dependency install failed" }
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm --onedir --windowed --name Orbit --paths backend --add-data "frontend/dist;frontend/dist" --collect-all webview backend/desktop.py
if ($LASTEXITCODE -ne 0) { throw "Desktop build failed" }
