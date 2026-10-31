#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
python="$root/.venv/bin/python"
core="$root/desktop/src-tauri/core"

(cd "$root/ui" && npm ci && npm run build)
"$python" -m PyInstaller "$root/packaging/everything_agent.spec" --noconfirm \
    --distpath "$core" --workpath "$root/build/pyinstaller"
"$python" "$root/packaging/third_party_licenses.py" "$core/THIRD_PARTY_LICENSES.txt"
cp "$root/LICENSE" "$root/NOTICE" "$core/"
"$python" "$root/packaging/smoke_test.py" "$core/Everything Agent Core/Everything Agent Core"
(cd "$root/desktop" && npm ci && npx tauri build --config src-tauri/tauri.core.conf.json)

echo "App: desktop/src-tauri/target/release/bundle/"
