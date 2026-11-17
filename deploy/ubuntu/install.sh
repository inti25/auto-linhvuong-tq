#!/usr/bin/env bash
set -euo pipefail

GITHUB_REPO="${GITHUB_REPO:-inti25/auto-linhvuong-tq}"
VERSION="${VERSION:-latest}"
BINARY_PATH="${BINARY_PATH:-}"
INSTALL_BIN="/usr/local/bin/LinhVuongWeb"
DATA_DIR="${DATA_DIR:-/var/lib/linhvuong}"
ENV_FILE="/etc/linhvuong/env"
SERVICE_FILE="/etc/systemd/system/linhvuong-web.service"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd || pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." 2>/dev/null && pwd || pwd)"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --binary)
      BINARY_PATH="${2:?Thiếu đường dẫn file binary}"
      shift 2
      ;;
    --version)
      VERSION="${2:?Thiếu tag phiên bản}"
      shift 2
      ;;
    --repo)
      GITHUB_REPO="${2:?Thiếu tên repo owner/name}"
      shift 2
      ;;
    --data-dir)
      DATA_DIR="${2:?Thiếu thư mục dữ liệu}"
      shift 2
      ;;
    -h|--help)
      cat <<'EOF'
Cài đặt Linh Vương Web Dashboard lên Ubuntu Server từ file binary (không cần Python/source).

Tùy chọn:
  --binary <path>     Cài trực tiếp từ file binary LinhVuongWeb có sẵn trên máy
  --version <tag>     Tải từ GitHub Release tag cụ thể (mặc định: latest)
  --repo <owner/repo> GitHub repository chứa release (mặc định: inti25/auto-linhvuong-tq)
  --data-dir <dir>    Thư mục lưu dữ liệu (mặc định: /var/lib/linhvuong)
EOF
      exit 0
      ;;
    *)
      echo "❌ Tham số không hợp lệ: $1" >&2
      exit 1
      ;;
  esac
done

SUDO=""
if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  SUDO="sudo"
fi

echo "=== Triển khai Linh Vương Web Dashboard (Binary) trên Ubuntu Server ==="

# 1. Xác định nguồn binary: ưu tiên --binary hoặc file có sẵn cạnh repo, ngược lại tải từ GitHub Releases
TMP_DIR=""
cleanup() {
  if [[ -n "$TMP_DIR" && -d "$TMP_DIR" ]]; then
    rm -rf "$TMP_DIR"
  fi
}
trap cleanup EXIT

if [[ -z "$BINARY_PATH" ]]; then
  for cand in "./LinhVuongWeb" "$REPO_ROOT/dist/linux/LinhVuongWeb" "$REPO_ROOT/dist/LinhVuongWeb"; do
    if [[ -f "$cand" ]]; then
      BINARY_PATH="$cand"
      break
    fi
  done
fi

if [[ -n "$BINARY_PATH" ]]; then
  if [[ ! -f "$BINARY_PATH" ]]; then
    echo "❌ Không tìm thấy file binary tại: $BINARY_PATH" >&2
    exit 1
  fi
  echo "📦 Cài đặt từ binary cục bộ: $BINARY_PATH"
else
  if ! command -v curl >/dev/null 2>&1; then
    $SUDO apt-get update -y
    $SUDO apt-get install -y curl ca-certificates
  fi
  TMP_DIR="$(mktemp -d)"
  if [[ "$VERSION" == "latest" ]]; then
    DL_URL="https://github.com/${GITHUB_REPO}/releases/latest/download/LinhVuongWeb"
  else
    DL_URL="https://github.com/${GITHUB_REPO}/releases/download/${VERSION}/LinhVuongWeb"
  fi
  echo "⬇️  Đang tải binary từ: $DL_URL"
  if ! curl -fsSL "$DL_URL" -o "$TMP_DIR/LinhVuongWeb"; then
    echo "❌ Tải binary thất bại từ $DL_URL." >&2
    echo "   Hãy kiểm tra tag release trên GitHub hoặc truyền --binary <duong_dan_LinhVuongWeb>." >&2
    exit 1
  fi
  BINARY_PATH="$TMP_DIR/LinhVuongWeb"
fi

# 2. Cài đặt binary vào /usr/local/bin/LinhVuongWeb
$SUDO install -m 0755 "$BINARY_PATH" "$INSTALL_BIN"

# 3. Tạo user hệ thống và thư mục dữ liệu
if ! id -u linhvuong >/dev/null 2>&1; then
  $SUDO useradd --system --home "$DATA_DIR" --shell /usr/sbin/nologin linhvuong
fi
$SUDO mkdir -p "$DATA_DIR" /etc/linhvuong
$SUDO chown -R linhvuong:linhvuong "$DATA_DIR"

# 4. Tạo tệp môi trường /etc/linhvuong/env nếu chưa có
if [[ ! -f "$ENV_FILE" ]]; then
  if [[ -f "$SCRIPT_DIR/env.example" ]]; then
    $SUDO cp "$SCRIPT_DIR/env.example" "$ENV_FILE"
  else
    $SUDO tee "$ENV_FILE" >/dev/null <<EOF
LINHVUONG_DATA_DIR=${DATA_DIR}
LINHVUONG_WEB_HOST=127.0.0.1
LINHVUONG_WEB_PORT=8000
LINHVUONG_WEB_USERNAME=admin
LINHVUONG_WEB_PASSWORD=thay_mat_khau_manh_tai_day
# LINHVUONG_VAULT_KEY=
EOF
  fi
  $SUDO sed -i "s|^LINHVUONG_DATA_DIR=.*|LINHVUONG_DATA_DIR=${DATA_DIR}|" "$ENV_FILE"
  $SUDO chmod 600 "$ENV_FILE"
  $SUDO chown root:linhvuong "$ENV_FILE"
  echo "📝 Đã tạo $ENV_FILE — hãy cập nhật LINHVUONG_WEB_PASSWORD trước khi mở cổng mạng ngoài."
fi

# 5. Cài đặt systemd unit trỏ thẳng tới binary
if [[ -f "$SCRIPT_DIR/linhvuong-web.service" ]]; then
  $SUDO cp "$SCRIPT_DIR/linhvuong-web.service" "$SERVICE_FILE"
else
  $SUDO tee "$SERVICE_FILE" >/dev/null <<'EOF'
[Unit]
Description=Linh Vuong Auto Bot & Web Dashboard
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=linhvuong
Group=linhvuong
WorkingDirectory=/var/lib/linhvuong
EnvironmentFile=-/etc/linhvuong/env
ExecStart=/usr/local/bin/LinhVuongWeb --host ${LINHVUONG_WEB_HOST:-127.0.0.1} --port ${LINHVUONG_WEB_PORT:-8000}
Restart=on-failure
RestartSec=5
KillSignal=SIGTERM
TimeoutStopSec=20

[Install]
WantedBy=multi-user.target
EOF
fi

$SUDO systemctl daemon-reload
$SUDO systemctl enable linhvuong-web
$SUDO systemctl restart linhvuong-web

echo "✅ Đã cài đặt và khởi chạy xong từ binary: $INSTALL_BIN"
echo "🔎 Kiểm tra trạng thái: sudo systemctl status linhvuong-web"
echo "📜 Xem nhật ký dịch vụ: sudo journalctl -u linhvuong-web -f"
