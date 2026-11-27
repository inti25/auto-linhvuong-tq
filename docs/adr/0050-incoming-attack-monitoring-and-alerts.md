# ADR 0050: Giám Sát Và Cảnh Báo Quân Tấn Công (Incoming Attack Alert)

Status: accepted

## Ngữ Cảnh và Vấn Đề

Người chơi cần nhận được cảnh báo kịp thời qua **Thông Báo Đa Kênh** khi có đạo quân địch (người chơi PvP hoặc NPC/Man như `鲜卑部队`) kéo tới đánh **Thành** hoặc **Doanh trại**, hoặc khi chiến trường phòng thủ vừa nổ ra tại **Căn Cứ**, mà không cần bật sẵn tác vụ Thảo Phạt/Bình Man hay mở trực tiếp game trên trình duyệt. Qua khảo sát thực tế trên máy chủ 53 và mã JS gốc (`Global.js`, `Page/alarm.js`, `Build/barracks_ot.js`), giao thức máy chủ có 3 điểm dễ gây lỗi nếu thiết kế ngây thơ:
1. `Common.ashx?id=40` (`battle`) trả cả các trận quân ta chủ động đi đánh Man bên ngoài (`p[1] != base_id`), dễ gây báo giả liên tục khi bot đang chạy Bình Man/Thảo Phạt.
2. Mục `come` trong `Common.ashx?id=40` không trả về `march_id` định danh duy nhất cho mỗi đợt hành quân (`p[13] = 0`).
3. Thăm dò `Common.ashx?id=40` cho từng Căn Cứ mỗi chu kỳ tốn $N$ request (với tài khoản 9–15 thành), trong khi `Common.ashx?id=41` (`lCityCampID=0`) trả tổng hợp toàn bộ Thành và Doanh trại chỉ trong 1 request.

## Quyết Định Kiến Trúc

1. **Quét Hai Tầng Kết Hợp Đánh Thức Đúng Mốc Khẩn (`linhvuong/attack_monitor.py`)**:
   - Chu kỳ nền mặc định **5 phút** (cấu hình tối thiểu 1 phút) chỉ gọi 1 request `Common.ashx?id=41` (`lCityCampID=0`). Chỉ gọi `Common.ashx?id=40` (`tid=<base_id>`) cho các Căn Cứ có `lai_pham_count > 0` hoặc cờ đang giao chiến.
   - Khi phát hiện có đạo quân tấn công đang hành quân tới, bộ đếm tự động hẹn đánh thức sớm đúng vào mốc cảnh báo khẩn (**≤ 5 phút** trước khi tới) và thời điểm chạm thành để không bỏ lỡ pha áp sát dù chu kỳ nền là 5 phút.

2. **Lọc Nghiêm Ngặt Đạo Tấn Công Và Trận Phòng Thủ Tại Căn Cứ**:
   - Trong `come`, chỉ nhận mục có `move_type == 1` (`攻击`), bỏ qua chi viện (`2`), điều phái (`5`), trinh sát (`6`), và hỗ trợ tùy chọn lọc `attack_alert_pvp_only` (`attacker_uid != 0`).
   - Trong `battle`, chỉ nhận trận diễn ra ngay tại căn cứ (`p[1] == base_id`), hoặc xác minh qua `Common.ashx?id=4` (`atside == 2` — Phòng thủ) khi `id=41` báo cờ chiến đấu; tuyệt đối bỏ qua các trận Bình Man/Thảo Phạt/Gọi Man ngoài dã ngoại.

3. **Chống Lặp Theo Chữ Ký Nguồn & Cửa Sổ Thời Gian Trong RAM**:
   - Do API không cấp `march_id`, mỗi đợt hành quân được theo dõi bằng chữ ký `(target_base_id, attacker_uid, source_id, source_x, source_y)` kết hợp khớp 1–1 theo `arrival_epoch` trong dung sai ±90 giây.
   - Phát cảnh báo theo 3 nấc rõ ràng: `initial` (khi mới phát hiện), `urgent` (khi tụt xuống ≤ 5 phút nếu ban đầu > 5 phút), và `battle` (khi chiến trường mở tại căn cứ). Bộ nhớ chống lặp lưu trong RAM theo phiên chạy để sau khi khởi động lại bot vẫn quét và báo lại các đợt đang tiến tới.

4. **Phạm Vi Giám Sát Thụ Động (Read-Only)**:
   - Mô-đun chỉ đọc trạng thái quân tình và phát **Thông Báo Đa Kênh** + hiển thị banner/huy hiệu cảnh báo trên cả Web Dashboard (`AccountSession`) và Desktop Tkinter; tuyệt đối không tự động điều tướng, đổi trận hay can thiệp vào chiến trường phòng thủ.

## Hệ Quả

- Khi bình yên, mỗi tài khoản chỉ tốn 1 request nhỏ mỗi 5 phút; khi bị tập kích vẫn nhận đủ chi tiết kẻ địch, quân lực (nếu lộ), đếm ngược thời gian và cảnh báo gấp trước 5 phút.
- Các tác vụ Bình Man, Thảo Phạt, Gọi Man chạy song song không bao giờ kích hoạt nhầm cảnh báo quân tấn công.
