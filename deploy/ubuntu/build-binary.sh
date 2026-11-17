#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

BUILD_VENV="${BUILD_VENV:-/tmp/linhvuong-web-build-venv}"
python3 -m venv "$BUILD_VENV"
"$BUILD_VENV/bin/pip" install --upgrade pip
"$BUILD_VENV/bin/pip" install -e ".[web]" pyinstaller

"$BUILD_VENV/bin/pyinstaller" LinhVuongWeb.spec --clean --noconfirm --distpath dist/linux --workpath build/linux
chmod +x dist/linux/LinhVuongWeb

echo "✅ Đã build binary Linux tại: $ROOT_DIR/dist/linux/LinhVuongWeb"
