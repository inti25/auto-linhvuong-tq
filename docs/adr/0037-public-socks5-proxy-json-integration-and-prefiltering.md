# ADR 0037: Tích Hợp Nguồn ProxyScrape SOCKS5 JSON Và Cơ Chế Tiền Lọc Proxy Công Cộng

## Ngữ Cảnh và Vấn Đề

1. **Nhu cầu sử dụng Proxy miễn phí khi chưa có Proxy riêng**:
   - Trước đây ([ADR-0025](0025-dynamic-proxy-pool-and-failover.md)), `ProxyPool` chỉ hỗ trợ phân tích dữ liệu dạng text thuần dòng (`ip:port:user:pass` hoặc `ip:port`) thường được cấp bởi các dịch vụ proxy xoay thương mại có trả phí.
   - Khi người chơi mới hoặc người chơi chạy nhiều tài khoản phụ muốn nhanh chóng kích hoạt proxy ẩn danh mà chưa kịp mua gói proxy cá nhân, họ cần một nguồn proxy SOCKS5 miễn phí, sẵn có và ổn định.
   - Nguồn dữ liệu SOCKS5 công cộng từ ProxyScrape (`https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/refs/heads/main/proxies/protocols/socks5/data.json`) được cập nhật liên tục với hàng ngàn proxy trên toàn cầu. Tuy nhiên dữ liệu này trả về dưới định dạng mảng JSON (`[{"ip": "...", "port": ..., "protocol": "socks5", "latency_ms": ..., "uptime_percent": ...}, ...]`), khiến `load_from_text` trước đây không thể phân tích cú pháp.

2. **Thách thức về độ trễ và tải kiểm định khi nạp danh sách lớn (1.300+ proxy)**:
   - Danh sách ProxyScrape chứa hơn 1.300 proxy. Nếu đưa toàn bộ vào tiến trình `check_all` (ProxyHealthCheck) tới máy chủ game (`http://pass.dipan.com/`), quá trình sẽ mất hàng phút và gửi một lượng lớn request vô nghĩa tới cổng xác thực.
   - Proxy công cộng miễn phí có chất lượng biến thiên lớn: nhiều proxy có độ trễ cao hàng ngàn ms hoặc uptime rất thấp. Cần có giải thuật tiền lọc để chọn ra các ứng viên sáng giá nhất.

## Quyết Định Kiến Trúc

1. **Bộ Phân Tích Đa Định Dạng Tự Động Trong `ProxyPool` (`linhvuong/proxy.py`)**:
   - Nâng cấp `ProxyPool.load_from_text` và bổ sung `ProxyPool.load_from_json`:
     - Tự động nhận diện dữ liệu đầu vào: nếu chuỗi bắt đầu bằng `[` hoặc `{`, chuyển sang giải mã JSON.
     - Hỗ trợ cả định dạng mảng object của ProxyScrape (`ip`, `port`, `protocol`, `latency_ms`, `uptime_percent`) lẫn cấu trúc danh sách URL/dòng văn bản thông thường.
     - Tự động chuẩn hóa giao thức: `socks5` -> `socks5h` để ủy quyền phân giải DNS từ xa cho proxy theo [ADR-0002](0002-proxy-support-and-remote-dns.md).

2. **Cơ Chế Tiền Lọc Thông Minh (Pre-filtering & Candidate Ranking)**:
   - Trước khi nạp vào bể kiểm tra, lọc và xếp hạng các endpoint theo 2 tiêu chí:
     - Ưu tiên 1: Độ trễ ước tính (`latency_ms`) thấp nhất.
     - Ưu tiên 2: Tỷ lệ hoạt động (`uptime_percent`) cao nhất.
   - Giới hạn lấy **Top 50** ứng viên tiềm năng nhất (`max_candidates = 50`) để chuyển vào `ProxyHealthCheck`. Việc này rút ngắn thời gian khởi động kiểm tra chỉ còn khoảng 2-4 giây trên mạng thực tế.

3. **Hằng Số Nguồn Mặc Định & Nút Chọn Nhanh Trên Giao Diện (`linhvuong/gui.py`)**:
   - Khai báo hằng số chuẩn hóa:
     `DEFAULT_FREE_PROXY_URL = "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/refs/heads/main/proxies/protocols/socks5/data.json"`
   - Bổ sung nút tiện ích **`⚡ Free`** cạnh ô nhập *URL Proxy List* trên cả hai giao diện `AccountLoginFrame` (chuyển đổi tài khoản) và `LoginWindow` (màn hình đăng nhập độc lập).
   - Khi bấm, tự động điền URL ProxyScrape vào cấu hình và thông báo hướng dẫn người dùng nhấn *🔄 Test* hoặc trực tiếp đăng nhập.

4. **Kế Thừa Hoán Đổi và Tự Động Làm Mới (Failover & Auto-Refetch)**:
   - Khi tất cả proxy sống trong top 50 bị hỏng trong quá trình bot chạy tự động, cơ chế `failover` của `ProxyPool` sẽ tự động tải lại JSON mới nhất từ ProxyScrape để lấy mẻ proxy sống mới mà không làm gián đoạn bot.

## Đánh Đổi và Hệ Quả

- **Tích cực**:
  - Người dùng có thể chạy proxy SOCKS5 hoàn toàn miễn phí chỉ với 1 cú click chuột.
  - Tương thích ngược 100%: các URL trả về text dòng truyền thống hoặc cấu hình proxy cá nhân trước đây vẫn hoạt động hoàn hảo.
  - Tối ưu hiệu năng: không làm nghẽn mạng do chỉ kiểm định Top 50 proxy chất lượng nhất.
- **Hạn chế**:
  - Proxy công cộng miễn phí có thể bị nghẽn mạng hoặc chết bất chợt nhanh hơn proxy trả phí, đòi hỏi bot phải failover thường xuyên hơn.

