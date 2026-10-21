# Tùy Chỉnh Chu Kỳ Chạy (Interval) Và Độ Trễ Ngẫu Nhiên (Jitter) Cho Các Tính Năng Tự Động

Trong hệ thống tự động hóa LinhVuong, các tác vụ chạy nền (Thảo Phạt, Gọi Dân, Bình Man, Xây Dựng, Nghiên Cứu Đại Học) trước đây được gán chu kỳ kiểm tra lặp cứng (hardcoded intervals: 10s, 15s, 20s, 30s). Người chơi có nhu cầu tối ưu hóa tốc độ chạy linh hoạt theo giai đoạn phát triển (ví dụ: cần xây dựng nhanh hơn khi đang kích hoạt bùa tăng tốc hoặc kéo dài chu kỳ khi tài nguyên cạn kiệt), đồng thời hạn chế nguy cơ bị phát hiện bot do gửi request tuần hoàn với khoảng thời gian cố định tuyệt đối.

Các phương án khác đã cân nhắc:
- Giữ nguyên chu kỳ hardcoded trong mã nguồn: Không đáp ứng được tính linh hoạt khi nhu cầu của người chơi thay đổi theo từng chiến thuật hoặc tốc độ mạng.
- Cho phép người dùng nhập chu kỳ tùy ý không giới hạn (kể cả 0s hoặc mili-giây): Rất nguy hiểm vì có thể gây bão request (gateway spam), dẫn đến bị chặn IP tạm thời hoặc kích hoạt hệ thống Captcha của server game.
- Gửi request hoàn toàn ngẫu nhiên không có chu kỳ cơ sở: Khiến thời gian chờ không thể dự đoán và gây khó khăn cho người dùng khi giám sát tiến trình.

Quyết định:
- Chuẩn hóa đơn vị đo lường: Toàn bộ cấu hình chu kỳ trên giao diện người dùng (GUI) được hiển thị và thiết lập thống nhất theo đơn vị **Giây (s)** (`tp_interval`, `gd_interval`, `bm_interval`, `bld_interval`, `res_interval`).
- Giới hạn an toàn tối thiểu (Safety Floor): Bắt buộc giá trị chu kỳ có hiệu lực luôn `>= 3.0s` (`max(3.0, interval)`) để bảo vệ tài khoản người dùng khỏi nguy cơ spam gateway.
- Cơ chế giãn cách ngẫu nhiên nhẹ (Jitter / Anti-bot delay):
  - Bổ sung phương thức `wait_cycle(seconds: float, jitter: float = 2.0) -> bool` vào `BaseTaskRunner` và `ThaoPhatAutoRunner`.
  - Nếu `seconds <= 3.0`, giữ nguyên độ trễ an toàn tối thiểu 1.0s.
  - Nếu `seconds > 3.0`, áp dụng độ lệch ngẫu nhiên nhẹ `actual_wait = max(3.0, seconds + random.uniform(-jitter, jitter))` nhằm mô phỏng hành vi tự nhiên của con người, phá vỡ tính tuần hoàn cứng nhắc của các lượt quét.
- Tích hợp giao diện & Lưu/Nạp cấu hình:
  - Bổ sung các ô nhập chu kỳ tương ứng trên cả 5 Tab chức năng của GUI Dashboard.
  - Đồng bộ hóa toàn diện vào Hồ Sơ Cấu Hình Tổng Hợp (`auto_profile.json`) với đầy đủ khả năng tương thích ngược (fallback về giá trị mặc định chuẩn nếu hồ sơ cũ chưa có trường `interval`).
