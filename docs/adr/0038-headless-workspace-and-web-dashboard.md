# ADR 0038: Lõi Điều Phối Headless Dùng Chung Và Bảng Điều Khiển Web Song Hành

Status: accepted

## Ngữ Cảnh và Vấn Đề

1. **Phụ thuộc Tkinter và Windows khi muốn chạy 24/7 trên Ubuntu Server**:
   - Trước đây ([ADR-0021](0021-headless-profile-store-and-consolidated-automation-engine.md), [ADR-0033](0033-unified-multi-account-workspace-and-navigation.md)), `ProfileStore` (`linhvuong/profile.py`) và `AutomationEngine` (`linhvuong/engine.py`) đã tách khỏi Tkinter, nhưng tầng điều phối đa tài khoản (`MultiAccountApp` trong `linhvuong/gui.py`) và toàn bộ logic lắp ráp tác vụ, đồng bộ cấu hình, bộ đệm nhật ký vẫn nằm trực tiếp trong `linhvuong/dashboard/` gắn chặt với `tk.Frame`, `StringVar`, `self.after`.
   - `linhvuong/notifications.py` sử dụng Windows Toast qua PowerShell và `winsound`, không hỗ trợ cảnh báo cục bộ trên trình duyệt khi chạy trên máy chủ Linux không màn hình.
   - Các tệp cấu hình và nhật ký (`gui_settings.json`, `auto_profile_*.json`, `logs/`) mặc định ghi theo đường dẫn tương đối tại thư mục hiện tại, chưa hỗ trợ tách thư mục dữ liệu qua biến môi trường cho `systemd` và Docker.

2. **Nhu cầu vận hành trên Ubuntu Server qua trình duyệt mà không phá vỡ bản Desktop**:
   - Người dùng cần vận hành bot 24/7 trên Ubuntu Server (22.04/24.04 LTS) và điều khiển đầy đủ cả 7 phân hệ + đa tài khoản từ trình duyệt PC/điện thoại, đồng thời vẫn giữ nguyên ứng dụng Tkinter Desktop trên Windows và bộ kiểm thử hiện có.

## Quyết Định Kiến Trúc

1. **Tách Lõi Điều Phối Headless (`WorkspaceManager` & `AccountSession`)**:
   - Đưa toàn bộ quản lý danh bạ đa tài khoản, phiên `GatewayClient`/`ProxyPool`/`Roster`/`TargetLocks`, lắp ráp tác vụ, đồng bộ `ProfileStore`, hàng đợi nhật ký vòng (in-memory ring buffer) và phát sự kiện realtime vào module thuần Python không import `tkinter`.
   - Cả **Web Server** lẫn **Tkinter `Dashboard`** đều dùng chung lõi này (Tkinter giữ nguyên chữ ký công khai của `Dashboard` để bảo toàn 100% tương thích ngược và tests hiện tại).

2. **Ngăn Xếp Web: FastAPI + Uvicorn + WebSocket + Static No-Build SPA**:
   - Backend dùng `FastAPI` + `Uvicorn` + `WebSocket`, lấy `AccountSession` + `ProfileStore` làm nguồn chân lý duy nhất (Single Source of Truth): mọi thay đổi cấu hình được kiểm định, lưu nguyên tử trên server và broadcast tức thì tới mọi trình duyệt đang mở.
   - Frontend dùng **SPA tĩnh (HTML/CSS/JS hiện đại không cần bước build Node.js)** được FastAPI phục vụ trực tiếp, hỗ trợ responsive cho cả PC và điện thoại với đầy đủ chức năng tương đương 7 tab và các hộp thoại của Tkinter Dashboard.
   - Các thư viện Web Server được khai báo trong optional extra `.[web]` của `pyproject.toml` để giữ bản CLI và build Windows `.exe` (`LinhVuong.spec`) gọn nhẹ.

3. **Tương Thích Linux Headless, `LINHVUONG_DATA_DIR` & Thông Báo Đa Kênh Mở Rộng**:
   - Bổ sung biến môi trường/tham số `LINHVUONG_DATA_DIR` (mặc định `.` để giữ tương thích ngược) làm gốc lưu `gui_settings.json`, `auto_profile_*.json` và `logs/`.
   - Thêm khóa tiến trình (`file lock`) trên `LINHVUONG_DATA_DIR` để ngăn hai tiến trình chạy trùng cùng thư mục dữ liệu, kèm xử lý `SIGTERM`/`SIGINT` dừng tác vụ an toàn.
   - Mở rộng **Thông Báo Đa Kênh**: bổ sung Web Notification/Toast + âm thanh Web Audio qua WebSocket cho trình duyệt đang mở, mở rộng Telegram Bot cảnh báo cả khi tạm dừng vì `Captcha` (`CaptchaRequired`, giữ nguyên quy tắc tạm dừng chờ giải thủ công theo [ADR-0001](0001-no-license-gate-and-manual-captcha.md)) hoặc gián đoạn phiên, và thay nút mở thư mục log bằng trình xem/tải tệp `logs/*.log` trực tiếp trên Web UI.
   - Chuẩn hóa triển khai trên Ubuntu Server qua Python `venv` + `systemd` (+ mẫu Nginx/Caddy reverse proxy) và tùy chọn `Dockerfile` + `docker-compose.yml`.

## Các Phương Án Đã Cân Nhắc

- **Thay thế hoàn toàn Tkinter bằng Web Dashboard**: Bị từ chối vì người dùng Windows vẫn dùng bản desktop `.exe` không cần cài môi trường server, và sẽ phá vỡ bộ test Tkinter hiện tại.
- **Dùng React/Vite hoặc Next.js cho Frontend**: Bị từ chối vì đòi hỏi Node.js toolchain khi triển khai/build trên VPS, làm phức tạp quy trình cài đặt bằng `pip`/`systemd` của dự án Python thuần.
- **Nhân đôi logic lắp ráp tác vụ trực tiếp trong FastAPI routes**: Bị từ chối vì dễ lệch hành vi giữa Desktop và Web khi bảo trì; tách `WorkspaceManager`/`AccountSession` giải quyết triệt để vấn đề này.

## Hệ Quả

- Một nguồn nghiệp vụ duy nhất điều khiển cả Desktop lẫn Web Server, tránh phân mảnh logic.
- Cài đặt trên Ubuntu Server chỉ cần Python ≥ 3.10 với `pip install -e ".[web]"` (hoặc Docker), không cần Node.js hay X11/Tkinter.
- Không thể chạy đồng thời hai tiến trình (Web và Desktop) trên cùng một `LINHVUONG_DATA_DIR` do cơ chế khóa chống xung đột.
