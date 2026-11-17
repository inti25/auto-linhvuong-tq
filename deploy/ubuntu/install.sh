#!/usr/bin/env bash
set -euo pipefail

GITHUB_REPO="${GITHUB_REPO:-inti25/auto-linhvuong-tq}"
VERSION="${VERSION:-latest}"
WEB_HOST="${WEB_HOST:-${LINHVUONG_WEB_HOST:-0.0.0.0}}"
WEB_PORT="${WEB_PORT:-${LINHVUONG_WEB_PORT:-8080}}"
WEB_USERNAME="${WEB_USERNAME:-${LINHVUONG_WEB_USERNAME:-admin}}"
WEB_PASSWORD="${WEB_PASSWORD:-${LINHVUONG_WEB_PASSWORD:-admin}}"
BINARY_PATH="${BINARY_PATH:-}"
INSTALL_BIN="/usr/local/bin/LinhVuongWeb"
DATA_DIR="${DATA_DIR:-/var/lib/linhvuong}"
ENV_FILE="/etc/linhvuong/env"
SERVICE_FILE="/etc/systemd/system/linhvuong-web.service"
NON_INTERACTIVE="${NON_INTERACTIVE:-0}"

HAS_VERSION=0
HAS_HOST=0
HAS_PORT=0
HAS_PASSWORD=0

SCRIPT_SOURCE="${BASH_SOURCE[0]:-}"
if [[ -n "$SCRIPT_SOURCE" ]]; then
  SCRIPT_DIR="$(cd "$(dirname "$SCRIPT_SOURCE")" 2>/dev/null && pwd || pwd)"
  REPO_ROOT="$(cd "$SCRIPT_DIR/../.." 2>/dev/null && pwd || pwd)"
else
  SCRIPT_DIR=""
  REPO_ROOT=""
fi

while [[ $# -gt 0 ]]; do
  case "$1" in
    --binary)
      BINARY_PATH="${2:?Thiếu đường dẫn file binary}"
      shift 2
      ;;
    --version)
      VERSION="${2:?Thiếu tag phiên bản}"
      HAS_VERSION=1
      shift 2
      ;;
    --host)
      WEB_HOST="${2:?Thiếu địa chỉ host}"
      HAS_HOST=1
      shift 2
      ;;
    --port)
      WEB_PORT="${2:?Thiếu cổng port}"
      HAS_PORT=1
      shift 2
      ;;
    --web-password)
      WEB_PASSWORD="${2:?Thiếu mật khẩu web_password}"
      HAS_PASSWORD=1
      shift 2
      ;;
    --repo)
      GITHUB_REPO="${2:?Thiếu tên repo owner/repo}"
      shift 2
      ;;
    --data-dir)
      DATA_DIR="${2:?Thiếu thư mục dữ liệu}"
      shift 2
      ;;
    -y|--yes|--non-interactive)
      NON_INTERACTIVE=1
      shift
      ;;
    -h|--help)
      cat <<'EOF'
Cài đặt Linh Vương Web Dashboard lên Ubuntu Server từ file binary (không cần Python/source).

Tùy chọn:
  --version <tag>        Tag phiên bản Release (mặc định: latest; ví dụ: v1.0.5, v2.0.0)
  --host <ip>            Địa chỉ IP lắng nghe (mặc định: 0.0.0.0)
  --port <port>          Cổng HTTP/WebSocket (mặc định: 8080)
  --web-password <pass>  Mật khẩu Phiên Quản Trị Web (mặc định: admin)
  --binary <path>        Cài trực tiếp từ file binary LinhVuongWeb có sẵn trên máy
  --repo <owner/repo>    GitHub repository chứa release (mặc định: inti25/auto-linhvuong-tq)
  --data-dir <dir>       Thư mục lưu dữ liệu (mặc định: /var/lib/linhvuong)
  -y, --non-interactive  Không hỏi nhập tương tác, dùng trực tiếp tham số/mặc định
EOF
      exit 0
      ;;
    *)
      echo "❌ Tham số không hợp lệ: $1" >&2
      exit 1
      ;;
  esac
done

prompt_if_needed() {
  local label="$1"
  local default_val="$2"
  local var_name="$3"
  local input_val=""
  printf "%s [%s]: " "$label" "$default_val" >/dev/tty
  if IFS= read -r input_val <&3; then
    input_val="${input_val#"${input_val%%[![:space:]]*}"}"
    input_val="${input_val%"${input_val##*[![:space:]]}"}"
    if [[ -n "$input_val" ]]; then
      printf -v "$var_name" '%s' "$input_val"
    fi
  fi
}

if [[ "$NON_INTERACTIVE" != "1" ]] && (( HAS_VERSION == 0 || HAS_HOST == 0 || HAS_PORT == 0 || HAS_PASSWORD == 0 )); then
  if exec 3</dev/tty 2>/dev/null && [[ -w /dev/tty ]]; then
    echo "⚙️  Cấu hình cài đặt (nhấn Enter để giữ giá trị mặc định):" >/dev/tty
    [[ "$HAS_VERSION" -eq 0 ]] && prompt_if_needed "Phiên bản (latest, v1.0.5, v2.0.0...)" "$VERSION" VERSION
    [[ "$HAS_HOST" -eq 0 ]] && prompt_if_needed "Host lắng nghe" "$WEB_HOST" WEB_HOST
    [[ "$HAS_PORT" -eq 0 ]] && prompt_if_needed "Port Web Dashboard" "$WEB_PORT" WEB_PORT
    [[ "$HAS_PASSWORD" -eq 0 ]] && prompt_if_needed "Mật khẩu Web Admin (web_password)" "$WEB_PASSWORD" WEB_PASSWORD
    exec 3<&-
  fi
fi

if ! [[ "$WEB_PORT" =~ ^[0-9]+$ ]] || (( WEB_PORT < 1 || WEB_PORT > 65535 )); then
  echo "❌ Port không hợp lệ: '$WEB_PORT' (phải là số nguyên 1..65535)." >&2
  exit 1
fi
if [[ -z "$WEB_HOST" || -z "$WEB_PASSWORD" || -z "$VERSION" ]]; then
  echo "❌ version, host và web_password không được để trống." >&2
  exit 1
fi

SUDO=""
if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  SUDO="sudo"
fi

echo "=== Triển khai Linh Vương Web Dashboard (Binary) trên Ubuntu Server ==="
echo "📌 Cấu hình: version=${VERSION} | host=${WEB_HOST} | port=${WEB_PORT} | data_dir=${DATA_DIR}"

# 1. Xác định nguồn binary: ưu tiên --binary hoặc file có sẵn cạnh repo, ngược lại tải từ GitHub Releases
TMP_DIR=""
cleanup() {
  if [[ -n "$TMP_DIR" && -d "$TMP_DIR" ]]; then
    rm -rf "$TMP_DIR"
  fi
}
trap cleanup EXIT

if [[ -z "$BINARY_PATH" ]]; then
  for cand in "./LinhVuongWeb" ${REPO_ROOT:+"$REPO_ROOT/dist/linux/LinhVuongWeb"} ${REPO_ROOT:+"$REPO_ROOT/dist/LinhVuongWeb"}; do
    if [[ -n "$cand" && -f "$cand" ]]; then
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
if [[ "$(readlink -f "$BINARY_PATH")" != "$(readlink -f "$INSTALL_BIN" 2>/dev/null || echo "$INSTALL_BIN")" ]]; then
  $SUDO install -m 0755 "$BINARY_PATH" "$INSTALL_BIN"
else
  $SUDO chmod 0755 "$INSTALL_BIN"
fi

# 3. Tạo user hệ thống và thư mục dữ liệu
if ! id -u linhvuong >/dev/null 2>&1; then
  $SUDO useradd --system --home "$DATA_DIR" --shell /usr/sbin/nologin linhvuong
fi
$SUDO mkdir -p "$DATA_DIR" /etc/linhvuong
$SUDO chown -R linhvuong:linhvuong "$DATA_DIR"

# 4. Tạo hoặc cập nhật tệp môi trường /etc/linhvuong/env
upsert_env_var() {
  local file="$1" key="$2" val="$3" tmp
  tmp="$(mktemp)"
  if $SUDO test -f "$file"; then
    $SUDO cat "$file" | LV_KEY="$key" LV_VAL="$val" awk '
      BEGIN { k = ENVIRON["LV_KEY"]; v = ENVIRON["LV_VAL"]; found = 0 }
      $0 ~ "^" k "=" { print k "=" v; found = 1; next }
      { print }
      END { if (!found) print k "=" v }
    ' > "$tmp"
  else
    printf '%s=%s\n' "$key" "$val" > "$tmp"
  fi
  $SUDO install -m 0600 -o root -g linhvuong "$tmp" "$file"
  rm -f "$tmp"
}

if ! $SUDO test -f "$ENV_FILE"; then
  if [[ -n "$SCRIPT_DIR" && -f "$SCRIPT_DIR/env.example" ]]; then
    $SUDO cp "$SCRIPT_DIR/env.example" "$ENV_FILE"
  else
    $SUDO tee "$ENV_FILE" >/dev/null <<EOF
LINHVUONG_DATA_DIR=${DATA_DIR}
LINHVUONG_WEB_HOST=${WEB_HOST}
LINHVUONG_WEB_PORT=${WEB_PORT}
LINHVUONG_WEB_USERNAME=${WEB_USERNAME}
LINHVUONG_WEB_PASSWORD=${WEB_PASSWORD}
# LINHVUONG_VAULT_KEY=
EOF
  fi
fi

upsert_env_var "$ENV_FILE" "LINHVUONG_DATA_DIR" "$DATA_DIR"
upsert_env_var "$ENV_FILE" "LINHVUONG_WEB_HOST" "$WEB_HOST"
upsert_env_var "$ENV_FILE" "LINHVUONG_WEB_PORT" "$WEB_PORT"
upsert_env_var "$ENV_FILE" "LINHVUONG_WEB_USERNAME" "$WEB_USERNAME"
upsert_env_var "$ENV_FILE" "LINHVUONG_WEB_PASSWORD" "$WEB_PASSWORD"
echo "📝 Đã cấu hình $ENV_FILE (host=${WEB_HOST}, port=${WEB_PORT}, user=${WEB_USERNAME})."

# 5. Cài đặt systemd unit trỏ thẳng tới binary
if [[ -n "$SCRIPT_DIR" && -f "$SCRIPT_DIR/linhvuong-web.service" ]]; then
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
ExecStart=/usr/local/bin/LinhVuongWeb
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
echo "🌐 Truy cập Web Dashboard: http://${WEB_HOST}:${WEB_PORT} (Tài khoản: ${WEB_USERNAME})"
echo "🔎 Kiểm tra trạng thái: sudo systemctl status linhvuong-web"
echo "📜 Xem nhật ký dịch vụ: sudo journalctl -u linhvuong-web -f"
