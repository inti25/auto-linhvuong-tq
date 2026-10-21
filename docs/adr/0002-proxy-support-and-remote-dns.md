# Hỗ trợ Proxy xuyên suốt phiên và ưu tiên phân giải DNS từ xa cho SOCKS5

Ứng dụng hỗ trợ cấu hình proxy HTTP, HTTPS và SOCKS5 từ màn hình đăng nhập (và tùy chọn qua file cấu hình CLI). Proxy được gắn trực tiếp vào `requests.Session` xuyên suốt toàn bộ vòng đời (từ bước xác thực đăng nhập đến toàn bộ lệnh gọi API trong game) để tránh rò rỉ địa chỉ IP gốc. Khi cấu hình SOCKS5 (`socks5://`), hệ thống tự động chuyển đổi sang giao thức `socks5h://` để ủy quyền toàn bộ việc phân giải DNS cho proxy server xử lý.

Đồng thời, hệ thống hỗ trợ xác thực Proxy (Proxy Authentication) linh hoạt:
- Cung cấp 2 trường tùy chọn "Proxy User" và "Proxy Pass" trên giao diện (và lưu vào `gui_settings.json`).
- Tự động nhận diện và phân tích cú pháp dán nhanh phổ biến tại thị trường proxy: `ip:port:user:pass` hoặc `protocol://ip:port:user:pass`.
- Hỗ trợ mã hóa URL an toàn (`urllib.parse.quote`) khi mật khẩu proxy chứa ký tự đặc biệt (`@`, `:`, v.v.).

Các phương án khác đã cân nhắc:
- Chỉ áp dụng proxy cho bước đăng nhập: bị loại bỏ vì khi vào game, bot sẽ gọi trực tiếp bằng IP thật, làm lộ danh tính người chơi.
- Giữ nguyên `socks5://` (phân giải DNS cục bộ tại máy người dùng): bị loại bỏ vì tên miền game (`pass.dipan.com`, `sg*.dipan.com`) có thể bị nhà mạng địa phương chặn hoặc làm rò rỉ truy vấn DNS ngoài đường hầm proxy.
- Bắt buộc người dùng tự gõ `user:pass@host:port`: gây khó khăn cho người dùng khi các trang bán proxy thường cấp chuỗi `ip:port:user:pass`. Giải pháp kết hợp ô nhập riêng và tự động phân tách khi dán mang lại trải nghiệm tối ưu nhất.
