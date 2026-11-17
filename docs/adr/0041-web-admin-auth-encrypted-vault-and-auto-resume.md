# ADR 0041: Phiên Quản Trị Web, Két Mật Khẩu Mã Hóa Tùy Chọn Và Tự Phục Hồi Trên Máy Chủ

Status: accepted

## Ngữ Cảnh và Vấn Đề

1. **Bảo vệ Bảng Điều Khiển Web khi mở cổng mạng trên Ubuntu Server**:
   - Khi triển khai trên VPS/Ubuntu Server, người dùng truy cập Web Dashboard từ xa qua trình duyệt PC hoặc điện thoại. Mở cổng HTTP không xác thực có nguy cơ bị người ngoài chiếm quyền điều khiển dàn tài khoản game và đọc cấu hình proxy/Telegram token.

2. **Đánh đổi với quy tắc không lưu mật khẩu của ADR-0033 khi server khởi động lại**:
   - [ADR-0033](0033-unified-multi-account-workspace-and-navigation.md) quy định `gui_settings.json` tuyệt đối không lưu mật khẩu tài khoản game xuống đĩa (chỉ giữ trong RAM để `auto_relogin`).
   - Trên ứng dụng desktop mở tay, việc nhập lại mật khẩu mỗi lần bật app là hợp lý. Tuy nhiên trên Ubuntu Server chạy dịch vụ nền (`systemd` / Docker) 24/7, mỗi lần máy chủ reboot hoặc cập nhật dịch vụ, toàn bộ tài khoản sẽ mất phiên nếu không có cơ chế lưu thông tin đăng nhập an toàn để tự khôi phục.

## Quyết Định Kiến Trúc

1. **Phiên Quản Trị Web (Single-Admin) & Mặc Định Bind An Toàn**:
   - Bảng Điều Khiển Web vận hành theo mô hình **1 chủ sở hữu duy nhất (Single-Admin)**, bảo vệ bằng màn hình đăng nhập riêng cấp cookie phiên HTTP-only, tách biệt với phiên đăng nhập game.
   - Mặc định server chỉ bind **`127.0.0.1:8000`** (an toàn khi truy cập qua SSH tunnel hoặc reverse proxy nội bộ). Khi người dùng bind ra mạng ngoài (`0.0.0.0`), hệ thống **bắt buộc** phải bật xác thực quản trị; nếu chưa cấu hình mật khẩu (`LINHVUONG_WEB_PASSWORD` hoặc tệp cấu hình auth đã băm), server tự sinh mật khẩu quản trị ngẫu nhiên in ra log khởi động lần đầu thay vì mở trắng.

2. **Két Mật Khẩu Mã Hóa Tùy Chọn (`Encrypted Credential Vault`)**:
   - Giữ nguyên mặc định an toàn của [ADR-0033](0033-unified-multi-account-workspace-and-navigation.md): `gui_settings.json` **không** lưu mật khẩu game; khi không bật két, sau mỗi lần restart server tài khoản ở trạng thái chờ người dùng nhập mật khẩu đăng nhập lại qua Web UI.
   - Bổ sung tùy chọn **Két Mật Khẩu Mã Hóa** tách tệp riêng trong `LINHVUONG_DATA_DIR`, mã hóa mật khẩu game bằng khóa đối xứng (`cryptography`) mở khóa qua biến môi trường `LINHVUONG_VAULT_KEY` (khóa chủ đặt trong cấu hình `systemd`/Docker secret, không ghi chung vào tệp két).

3. **Tự Động Khôi Phục Tác Vụ Sau Khởi Động Lại (`auto_resume`)**:
   - Khi bật **Két Mật Khẩu Mã Hóa** và máy chủ tắt an toàn (`SIGTERM`/`SIGINT`) hoặc khởi động lại, hệ thống lưu danh sách tác vụ đang hoạt động trước lúc tắt vào trạng thái phục hồi.
   - Khi dịch vụ khởi động lại với `LINHVUONG_VAULT_KEY` hợp lệ, hệ thống tự động đăng nhập lại từng tài khoản và tự kích hoạt lại các tác vụ đang chạy trước đó (có tùy chọn tắt `auto_resume` riêng cho từng tài khoản).

## Các Phương Án Đã Cân Nhắc

- **Hệ thống phân quyền đa người dùng (Multi-tenant RBAC + Database)**: Bị từ chối vì làm phức tạp quá mức nhu cầu cá nhân/nhóm nhỏ; khi cần tách người dùng có thể chạy nhiều instance với `LINHVUONG_DATA_DIR` và cổng riêng.
- **Giữ cứng quy tắc cấm lưu mật khẩu trong mọi trường hợp**: Bị từ chối vì khiến bot trên Ubuntu Server không thể tự hồi phục sau reboot VPS ban đêm.
- **Lưu mật khẩu game dạng plain text hoặc base64 trong `gui_settings.json`**: Bị từ chối vì rủi ro lộ mật khẩu nếu tệp cấu hình bị sao lưu hoặc chia sẻ nhầm.

## Hệ Quả

- Làm rõ ngoại lệ có kiểm soát đối với [ADR-0033](0033-unified-multi-account-workspace-and-navigation.md): mật khẩu chỉ được phép lưu xuống đĩa khi người dùng chủ động bật Két Mật Khẩu Mã Hóa và cung cấp `LINHVUONG_VAULT_KEY`.
- Người vận hành trên VPS được bảo vệ mặc định khỏi lỗi quên đặt mật khẩu khi mở cổng `0.0.0.0`.
- Việc kích hoạt `Két Mật Khẩu Mã Hóa` yêu cầu người dùng quản lý an toàn biến môi trường `LINHVUONG_VAULT_KEY` trên `systemd`/Docker; nếu mất khóa chủ, người dùng chỉ cần nhập lại mật khẩu game trên Web UI để tạo lại két mới.
