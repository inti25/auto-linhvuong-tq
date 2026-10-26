# Bể Proxy Động, Tự Động Tải Qua URL, Kiểm Tra Trạng Thái và Hoán Đổi Nóng

## Ngữ Cảnh và Vấn Đề
Trước đây ([ADR-0002](0002-proxy-support-and-remote-dns.md)), Linh Vương Auto Bot chỉ hỗ trợ cấu hình một địa chỉ Proxy đơn lẻ (`ip:port` hoặc `ip:port:user:pass`) tại màn hình đăng nhập. Khi chạy tự động 24/7, các vấn đề thực tế nảy sinh:
1. Proxy bị nhà mạng hoặc dịch vụ proxy ngắt kết nối, hết hạn hoặc die đột ngột (`ProxyError`, `ConnectTimeout`).
2. Bot bị dừng toàn bộ các tác vụ nền do không thể kết nối tới máy chủ game và yêu cầu người dùng phải can thiệp thủ công.
3. Người chơi thường thuê các gói proxy xoay hoặc proxy list từ nhà cung cấp (được cấp một liên kết API/URL trả về danh sách các proxy có dạng `ip:port:user:pass`).

Do đó, bot cần một cơ chế tự động nạp danh sách proxy từ URL, kiểm định tính sẵn sàng kết nối tới máy chủ game (Health Check), và tự động hoán đổi sang proxy sống khác (Failover) khi proxy đang dùng gặp sự cố.

## Quyết Định Kiến Trúc

1. **Kiến Trúc Module Bể Proxy Độc Lập (`ProxyPool`)**:
   - Xây dựng module `linhvuong/proxy.py` gồm 2 thực thể cốt lõi:
     - `ProxyEndpoint`: Đại diện cho một điểm cầu proxy (`host`, `port`, `username`, `password`, `protocol`, `is_alive`, `latency`). Hỗ trợ xuất ra URL chuẩn hóa (`http://...` hoặc `socks5h://...`).
     - `ProxyPool`: Quản lý danh sách `ProxyEndpoint`, nạp từ URL hoặc text thô, thực hiện kiểm tra trạng thái song song, cấp phát proxy an toàn luồng và xử lý hoán đổi khi có sự cố.

2. **Cơ Chế Phân Tích Dữ Liệu Tải Về (Lenient Parser)**:
   - Tải file danh sách dạng `text/plain` từ URL do người dùng cung cấp.
   - Hỗ trợ phân tích từng dòng linh hoạt:
     - Dạng 4 thành phần: `ip:port:username:password` (tự động trích xuất thông tin xác thực).
     - Dạng 2 thành phần: `ip:port` (proxy không cần mật khẩu).
     - Bỏ qua các dòng trống, dòng chú thích `#` hoặc định dạng sai.
   - Giao thức mặc định khi không chỉ định scheme là `http://`. Nếu có tiền tố `socks5://` sẽ tự động chuyển thành `socks5h://` để phân giải DNS từ xa.

3. **Kiểm Tra Trạng Thái Kết Nối Đa Luồng (`ProxyHealthCheck`)**:
   - Sử dụng `concurrent.futures.ThreadPoolExecutor` để kiểm tra song song nhiều proxy cùng lúc, không làm nghẽn luồng giao diện chính.
   - Endpoint kiểm tra: Gửi yêu cầu kiểm tra trực tiếp tới cổng đăng nhập game (`http://pass.dipan.com/` hoặc `http://sg{server_id}.dipan.com/`) với timeout ngắn (3 - 5 giây).
   - Chỉ giữ lại và ưu tiên các proxy thực sự kết nối thông suốt tới máy chủ game, loại bỏ các proxy bị tường lửa máy chủ game chặn.

4. **Cơ Chế Hoán Đổi Nóng và Thử Lại Yêu Cầu (`ProxyFailover`)**:
   - Tích hợp trực tiếp vào `GatewayClient.call` và `requests.Session`:
     - Khi phát hiện các ngoại lệ mạng liên quan đến Proxy (`requests.exceptions.ProxyError`, `requests.exceptions.ConnectTimeout`, `requests.exceptions.ConnectionError`), Gateway sẽ đánh dấu proxy hiện tại là lỗi (`mark_dead`).
     - Lấy proxy sống tiếp theo từ `ProxyPool` và gán lại `session.proxies`.
     - Thông báo log hệ thống thời gian thực tới tất cả các tab trên giao diện (`_log_global`).
     - Tự động lặp lại yêu cầu API đang thực thi dở dang với proxy mới mà không làm gián đoạn luồng nhiệm vụ.
   - **Tự động làm mới khi cạn kiệt (Auto-Refetch)**: Nếu toàn bộ proxy trong pool đều bị đánh dấu chết, `ProxyPool` tự động gửi request tải lại URL nguồn để lấy danh sách proxy mới nhất từ nhà cung cấp.

5. **Tích Hợp Giao Diện Đăng Nhập và Lưu Trữ Cấu Hình**:
   - Màn hình đăng nhập (`linhvuong/gui.py`): Bổ sung trường "URL Proxy List" kèm nút "🔄 Tải & Test".
   - Tự động lưu `proxy_url` vào cấu hình tài khoản trong `gui_settings.json` (tương thích hoàn toàn với Account Switcher).
   - Giao diện Dashboard: Hiển thị thông tin proxy hiện tại và cung cấp nút chuyển đổi proxy thủ công khi người dùng có nhu cầu.

## Đánh Đổi và Hệ Quả

- **Đạt được**:
  - Khả năng hoạt động liên tục 24/7 bền bỉ, miễn nhiễm với sự cố die proxy bất ngờ.
  - Tương thích tốt với các dịch vụ proxy xoay và proxy list thương mại phổ biến tại Việt Nam.
  - Kiểm tra sống/chết đa luồng nhanh chóng, chính xác vì trỏ thẳng vào endpoint của game.
- **Hạn chế và Đánh đổi**:
  - Khi proxy chết, yêu cầu API hiện tại sẽ mất một khoảng thời gian chờ (timeout) trước khi phát hiện và chuyển đổi sang proxy mới.
  - Cần bảo mật an toàn URL proxy trong `gui_settings.json` (không chia sẻ file settings có chứa link proxy riêng tư).
