# Builds installer/Output/VisualCommand-Setup-<version>.exe
#   1. model + icon   2. tests   3. PyInstaller (dist/VisualCommand)   4. Inno Setup
# Usage:  powershell -ExecutionPolicy Bypass -File scripts\build.ps1
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$py = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path $py)) { throw 'No .venv found. Run: uv venv -p 3.11 .venv ; uv pip install --python .venv\Scripts\python.exe -e ".[dev]"' }

& $py scripts\fetch_model.py; if ($LASTEXITCODE) { throw 'model download failed' }
& $py scripts\make_icon.py;   if ($LASTEXITCODE) { throw 'icon failed' }

& $py -m pytest -q;           if ($LASTEXITCODE) { throw 'tests failed' }

& $py -m PyInstaller --noconfirm --clean VisualCommand.spec
if ($LASTEXITCODE) { throw 'PyInstaller failed' }

$version = (& $py -c "import visualcommand; print(visualcommand.__version__)").Trim()
$iscc = @(
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { throw 'Inno Setup 6 not found. Install it with: winget install JRSoftware.InnoSetup' }

& $iscc "/DMyAppVersion=$version" installer\VisualCommand.iss
if ($LASTEXITCODE) { throw 'Inno Setup failed' }
Write-Host "`nInstaller: $root\installer\Output\VisualCommand-Setup-$version.exe" -ForegroundColor Green
