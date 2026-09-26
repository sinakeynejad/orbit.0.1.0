$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
if (-not (Test-Path .venv/Scripts/python.exe)) { py -3.12 -m venv .venv }
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-desktop.txt
if ($LASTEXITCODE -ne 0) { throw "Install failed" }
.\.venv\Scripts\python.exe backend/desktop.py
