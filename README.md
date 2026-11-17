# Auto Linh Vương

Công cụ tự động hóa cho game web Linh Vương, hỗ trợ vận hành đồng thời nhiều tài khoản trên **Windows Desktop (Tkinter)**, **Dòng lệnh (CLI)** và **Ubuntu Server kèm Bảng Điều Khiển Web (Web Dashboard)**.

## Auto dành cho Game Linh vương server Trung Quốc
- http://sg.dipan.com/

### [Tải về tại đây](https://github.com/inti25/auto-linhvuong-tq/releases)

### Phiên bản auto 1.x.x dành cho server 57 trở về trước

### Phiên bản auto 2.x.x dành cho server 58
- Từ server 58 Linh Vương Trung Quốc sử dụng nền tảng mới, có sẵn auto đính kèm, phiên bản auto này chỉ dùng để hỗ trợ thêm

## Tính năng chính

- **Không Gian Đa Tài Khoản**: Vận hành song song nhiều tài khoản, cô lập phiên (`Session`), `ProxyPool` (hỗ trợ HTTP/HTTPS/SOCKS5 & ProxyScrape JSON tự động hoán đổi), `Profile` (`auto_profile_{username}_{server_id}.json`) và nhật ký riêng.
- **Đầy đủ 7 phân hệ tự động hóa**:
  1. **Nội Chính & Nghiên Cứu**: Xây dựng đa căn cứ, nâng đồng đều, hạ/dỡ công trình, tự kích hoạt DS kiến trúc, mở rương khi thiếu, nghiên cứu 29 Kỹ Thuật Đại Học (Binh Pháp), giám sát ngưỡng tài nguyên, Thám bảo, Mở rương hàng loạt, Chuyển quân giới, An dân, Điểm danh và **Di Trại Độc Lập**.
  2. **Thảo Phạt**: 8 chiến dịch dã ngoại, tối đa 5 Võ tướng, tự biên chế & luyện sĩ khí xuất quân sớm.
  3. **Bình Man Đa Căn Cứ**: Chế độ Di Doanh trại (Mode 1) hoặc Xuất quân thẳng từ Thành (Mode 2), quét bản đồ đồng tâm & khóa mục tiêu ưu tiên căn cứ gần nhất.
  4. **Gọi Man & Vong Linh**: Triệu hồi Dân thường (`type=63`) và Vong Linh (`type=33` / bùa 268).
  5. **Tổng Quan & Quân Đội**: Roster thành/tướng, Ban thưởng toàn bộ, Luyện Sĩ Khí đa thành, Chế Tạo Quân Giới đa thành, Thiết lập Mưu Sĩ và Tự động Trang Bị Quan Văn & Võ Tướng.
  6. **Chiến Trường & Mưu Lược**: Tự đổi trận cuối hiệp, thích ứng binh chủng, cô lập & bắt sống BOSS (kèm tự bắt bằng Coin), giải hỗn loạn (96), rút lui khẩn cấp (92).
  7. **Sự Kiện Niên Thú**: Theo dõi kênh Thế Giới, tốc hành quân đi/về, dừng khi nhận 玉兔呈祥.
- **Thông Báo Đa Kênh**: Windows Desktop Toast/Sound (trên Desktop), Web Toast/Browser Notification/Web Audio (trên Web Dashboard), và Telegram Bot (cảnh báo BOSS, tạm dừng vì Captcha hoặc gián đoạn phiên).

---

## 1. Cài đặt nhanh trên máy cá nhân (Windows / Desktop & CLI)

Yêu cầu: Python `>= 3.10`.

```bash
git clone <repo-url>
cd auto-linhvuong-tq
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# Cài đặt bản cơ bản (Desktop Tkinter + CLI):
pip install -e .

# Hoặc cài kèm Web Server & Bảng Điều Khiển Web:
pip install -e ".[web]"
```

Chạy giao diện Desktop Tkinter:
```bash
python LinhVuong.py
```

Chạy Web Dashboard trên máy cá nhân:
```bash
linhvuong-web
# hoặc: linhvuong web
```
Mở trình duyệt tại `http://127.0.0.1:8000` (xem mật khẩu quản trị khởi tạo lần đầu in trên terminal nếu chưa đặt `LINHVUONG_WEB_PASSWORD`).

---

## 2. Triển khai trên Ubuntu Server (22.04 / 24.04 LTS)

### Cách A: Cài đặt trực tiếp bằng Binary + `systemd` (Khuyên dùng, không cần Python/mã nguồn)

**1. Chạy 1 lệnh trên Ubuntu Server** (tự tải binary `LinhVuongWeb` mới nhất từ GitHub Releases và cài đặt dịch vụ `systemd`):

```bash
curl -fsSL https://raw.githubusercontent.com/inti25/auto-linhvuong-tq/main/deploy/ubuntu/install.sh | sudo bash
```

Hoặc nếu bạn đã copy sẵn file binary `LinhVuongWeb` lên server:

```bash
bash deploy/ubuntu/install.sh --binary ./LinhVuongWeb
```

Script [deploy/ubuntu/install.sh](deploy/ubuntu/install.sh) sẽ:
1. Cài file binary vào `/usr/local/bin/LinhVuongWeb` (từ `--binary`, file cục bộ, hoặc tải từ GitHub Releases).
2. Tạo user hệ thống `linhvuong` và thư mục dữ liệu `/var/lib/linhvuong` (`LINHVUONG_DATA_DIR`).
3. Tạo `/etc/linhvuong/env` từ [deploy/ubuntu/env.example](deploy/ubuntu/env.example).
4. Cài và bật dịch vụ `systemd` ([deploy/ubuntu/linhvuong-web.service](deploy/ubuntu/linhvuong-web.service)).

Hoặc chạy nhanh trực tiếp bằng tay không cần `systemd`:
```bash
LINHVUONG_DATA_DIR=./data LINHVUONG_WEB_PASSWORD="mat_khau_manh" ./LinhVuongWeb --host 0.0.0.0 --port 8000
```

**2. Cấu hình mật khẩu Web & biến môi trường tại `/etc/linhvuong/env`**:

```bash
sudo nano /etc/linhvuong/env
```

Các biến quan trọng:
- `LINHVUONG_DATA_DIR=/var/lib/linhvuong`: nơi lưu `gui_settings.json`, `auto_profile_*.json`, `vault.enc`, `web_auth.json`, `logs/`.
- `LINHVUONG_WEB_HOST=127.0.0.1` (khuyên giữ `127.0.0.1` nếu đi qua SSH tunnel hoặc Nginx/Caddy; đổi thành `0.0.0.0` nếu mở cổng trực tiếp).
- `LINHVUONG_WEB_PORT=8000`
- `LINHVUONG_WEB_USERNAME=admin`
- `LINHVUONG_WEB_PASSWORD=<mat_khau_manh>`
- `LINHVUONG_VAULT_KEY=<chuoi_bi_mat>` *(tùy chọn)*: mở khóa **Két Mật Khẩu Mã Hóa** để server tự động đăng nhập lại và tiếp tục tác vụ sau khi reboot.

Khởi động lại dịch vụ sau khi sửa `/etc/linhvuong/env`:

```bash
sudo systemctl restart linhvuong-web
sudo journalctl -u linhvuong-web -f
```

#### Truy cập từ xa an toàn trên Ubuntu Server

- **Cách 1 — SSH Tunnel (không cần mở cổng firewall)**:
  ```bash
  ssh -L 8000:127.0.0.1:8000 user@<IP_UBUNTU_SERVER>
  ```
  Sau đó mở `http://127.0.0.1:8000` trên máy cá nhân.

- **Cách 2 — Nginx Reverse Proxy + HTTPS (Certbot)**:
  Dùng mẫu [deploy/ubuntu/nginx-linhvuong.conf](deploy/ubuntu/nginx-linhvuong.conf) (đã cấu hình sẵn `Upgrade`/`Connection` cho WebSocket `/ws`), rồi cấp SSL bằng `certbot --nginx`.

---

### Cách B: Triển khai bằng Docker & Docker Compose

```bash
# Đặt mật khẩu quản trị Web (và tùy chọn LINHVUONG_VAULT_KEY)
export LINHVUONG_WEB_PASSWORD="mat_khau_quan_tri_manh"
# export LINHVUONG_VAULT_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"

docker compose up -d --build
```

Mặc định [docker-compose.yml](docker-compose.yml) map cổng `127.0.0.1:8000:8000` và mount `./data` vào `/data` (`LINHVUONG_DATA_DIR=/data`) để bảo toàn cấu hình, hồ sơ và nhật ký khi nâng cấp image.

### Cách C: Tự build file Binary từ mã nguồn (PyInstaller)

- **Trên Ubuntu / Linux** (tạo `dist/linux/LinhVuongWeb`):
  ```bash
  bash deploy/ubuntu/build-binary.sh
  ```
- **Trên Windows** (tạo `dist/LinhVuongWeb.exe`):
  ```powershell
  pip install -e ".[web]" pyinstaller
  pyinstaller LinhVuongWeb.spec --clean --noconfirm
  ```
  (CI/CD tại [.github/workflows/release.yml](.github/workflows/release.yml) cũng tự động build sẵn cả `LinhVuong.exe`, `LinhVuongWeb.exe` và `LinhVuongWeb` cho Ubuntu `linux-amd64` khi tạo tag `v*`.)

---

## 3. Hướng dẫn sử dụng Web Dashboard

1. **Đăng nhập Phiên Quản Trị Web**: Nhập tài khoản/mật khẩu quản trị (`admin` + `LINHVUONG_WEB_PASSWORD`, hoặc mật khẩu ngẫu nhiên in trong log lần chạy đầu). Có thể đổi mật khẩu trực tiếp ở nút `🔐 Đổi mật khẩu Web` trên thanh trái.
2. **Thêm & Đăng nhập tài khoản Linh Vương**:
   - Bấm `➕ Thêm tài khoản`, nhập Server ID, tên tài khoản, mật khẩu game và cấu hình Proxy (hỗ trợ nút `⚡ Free` + `🔄 Test` kiểm tra nhanh ProxyScrape SOCKS5).
   - Nếu `LINHVUONG_VAULT_KEY` đã cấu hình, bạn có thể tích chọn **Lưu vào Két Mật Khẩu Mã Hóa** và **Tự chạy lại tác vụ khi reboot**.
3. **Điều hành 7 phân hệ**: Chuyển đổi giữa 7 tab trên thanh điều hướng; mọi chỉnh sửa quy hoạch được tự động lưu nguyên tử xuống `auto_profile_{username}_{server_id}.json` và đồng bộ tức thì tới mọi trình duyệt đang mở qua WebSocket.
4. **Xử lý khi gặp Captcha (`Cần giải Captcha`)**:
   - Hệ thống tạm dừng tác vụ gặp mã lỗi `110`, bật banner cảnh báo trên Web UI và gửi thông báo Telegram (nếu đã cấu hình).
   - Sau khi đăng nhập webgame giải mã hoặc đổi proxy, bấm **`▶️ Tiếp tục sau khi đã giải`** trên banner.
5. **Xem & Tải Log Server**: Bấm **`📄 Xem / Tải Logs Server`** ở góc dưới sidebar để đọc 500 dòng cuối hoặc tải về các tệp `logs/bot_*.log`.

---

## 4. Lưu ý vận hành & Bảo mật

- **Khóa chống chạy trùng (`DataDirLock`)**: Không thể chạy đồng thời hai tiến trình (`linhvuong-web` hoặc Desktop) trên cùng một `LINHVUONG_DATA_DIR`.
- **Mặc định an toàn khi bind `0.0.0.0`**: Hệ thống từ chối tắt xác thực quản trị khi bind ra địa chỉ mạng không phải loopback (`--no-auth` chỉ có hiệu lực trên `127.0.0.1` / `localhost`).
- **Tắt an toàn (`SIGTERM`)**: Khi chạy `systemctl stop linhvuong-web` hoặc `docker compose stop`, server lưu lại danh sách tác vụ đang chạy (`runtime_state.json`) và dừng toàn bộ luồng bot trước khi thoát.

---

## 5. Chạy bộ kiểm thử tự động (Tests)

```bash
pip install -e ".[web,dev]"
pytest -q
```
