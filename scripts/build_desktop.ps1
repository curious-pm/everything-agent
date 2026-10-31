$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"
$core = Join-Path $root "desktop\src-tauri\core"

Push-Location (Join-Path $root "ui")
npm ci
npm run build
Pop-Location

& $python -m PyInstaller (Join-Path $root "packaging\everything_agent.spec") --noconfirm `
    --distpath $core --workpath (Join-Path $root "build\pyinstaller")
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }
& $python (Join-Path $root "packaging\third_party_licenses.py") (Join-Path $core "THIRD_PARTY_LICENSES.txt")
if ($LASTEXITCODE -ne 0) { throw "Couldn't collect the third-party licenses" }
Copy-Item (Join-Path $root "LICENSE"), (Join-Path $root "NOTICE") $core
& $python (Join-Path $root "packaging\smoke_test.py") (Join-Path $core "Everything Agent Core\Everything Agent Core.exe")
if ($LASTEXITCODE -ne 0) { throw "The packaged core failed its smoke test" }

Push-Location (Join-Path $root "desktop")
npm ci
npx tauri build --config src-tauri/tauri.core.conf.json
if ($LASTEXITCODE -ne 0) { Pop-Location; throw "Tauri build failed" }
Pop-Location

Write-Host "Installer: desktop\src-tauri\target\release\bundle\nsis\"
