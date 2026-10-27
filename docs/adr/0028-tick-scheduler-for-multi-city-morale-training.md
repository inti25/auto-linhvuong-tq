# ADR 0028: Tick Scheduler cho Luyện Sĩ Khí Quân Đội Đa Thành

## Ngữ Cảnh và Vấn Đề
Trước đây, tính năng **Luyện Sĩ Khí Quân Đội (Đa Thành)** ([ADR-0022](0022-concurrent-multi-city-morale-training.md)) sử dụng `ThreadPoolExecutor` với giới hạn cứng `max_workers = 3`. Mô hình luồng ban đầu gán mỗi worker cho 1 võ tướng, và worker đó chạy vòng lặp ngủ chặn (`sleep`) chờ đếm ngược lượt luyện dở (`upgrading_time`) cho đến khi hoàn tất mục tiêu.

Hạn chế nghiêm trọng:
1. **Nghẽn luồng đồng thời**: 3 tướng đầu tiên chiếm trọn 3 luồng worker và ngủ chờ đếm ngược (thời gian đếm ngược thường từ 60s đến 300s). Các tướng từ thứ 4 trở đi bị kẹt trong hàng đợi (`queue`), hoàn toàn chưa được gửi lệnh kích hoạt nâng sĩ khí nào lên máy chủ.
2. **Lãng phí thời gian**: Máy chủ Linh Vương cho phép nhiều tướng (thậm chí toàn bộ danh tướng trong thành và đa thành) cùng trong trạng thái đếm ngược luyện sĩ khí cùng một lúc. Giới hạn 3 luồng khiến việc chuẩn bị sĩ khí cho 10-20 tướng kéo dài gấp nhiều lần không cần thiết.
3. **Thừa thãi request API 76**: Mỗi worker thăm dò `Common.ashx?id=76` riêng lẻ cho từng tướng, thay vì gom cụm theo thành (`cid`) để lấy thông tin toàn bộ tướng chỉ trong 1 request.

## Quyết Định Kiến Trúc

1. **Chuyển sang kiến trúc Vòng Lặp Chu Kỳ (Tick Scheduler)** trong [`MoraleTrainer.train_multiple_generals`](../../linhvuong/tasks/morale.py):
   - Xóa bỏ sự phụ thuộc vào việc giữ luồng worker chờ đếm ngược.
   - Quản lý trạng thái tiến trình của tất cả các tướng được chọn trong một bảng trạng thái trung tâm (`GeneralMoraleState`).
   - Sử dụng một luồng điều phối duy nhất chạy theo nhịp chu kỳ (tick interval 1.0s - 2.0s).

2. **Gom cụm truy vấn sĩ khí theo Thành (Batch Query per City)**:
   - Triển khai hàm `get_city_generals_morale_info(city_id)`: Chỉ gọi `Common.ashx?id=76` đúng 1 lần cho mỗi thành có tướng đang hoạt động trong chu kỳ, lấy đồng thời `current_morale` và `upgrading_time` của toàn bộ tướng trong thành đó.
   - Thăm dò API 76 có chọn lọc: Chỉ gọi khi thành chưa sync, hoặc có tướng đã đếm ngược về 0, hoặc đã qua chu kỳ `poll_interval`.

3. **Kích hoạt đồng loạt không giới hạn số tướng**:
   - Ở mỗi nhịp tick, duyệt qua toàn bộ các tướng chưa hoàn tất:
     - Tướng nào `upgrading_time == 0` và `morale < target_morale`: Gửi ngay lệnh `OPT.ashx?id=47` (`lAddPoint=min(10, target - current)`).
     - Giữa các lượt gọi lệnh nâng sĩ khí có khoảng nghỉ vi mô (micro-delay 50-100ms) để giữ an toàn cho socket/proxy và tránh bão request đột ngột.
   - Giúp toàn bộ 10, 20 hay 50 tướng được chọn đều có thể **đồng loạt đếm ngược luyện sĩ khí song song trên máy chủ**.

4. **Đếm ngược cục bộ thời gian thực cho giao diện**:
   - Mỗi giây trôi qua, bộ điều phối tự động giảm `upgrading_time` cục bộ và phát sự kiện `on_step` để bảng Treeview hiển thị đếm ngược thời gian thực mượt mà cho tất cả các dòng tướng.
   - Khi `upgrading_time` chạm 0, nhịp tick tiếp theo tự động đồng bộ lại từ máy chủ và tiếp tục lượt nâng kế tiếp.

5. **Bảo toàn giao diện và khả năng tương thích ngược**:
   - Giữ nguyên chữ ký hàm `train_multiple_generals(targets, target_morale, max_workers, stop_event, on_progress, on_step)` để tương thích hoàn toàn với các lời gọi hiện tại.
   - `train_general_morale` đơn lẻ vẫn được duy trì cho các trường hợp kiểm thử hoặc gọi độc lập.

## Hệ Quả
- **Hiệu năng vượt trội**: Toàn bộ tướng được chọn đều bắt đầu luyện sĩ khí cùng lúc, rút ngắn tổng thời gian luyện của 10-20 tướng xuống bằng thời gian của 1 đợt tướng.
- **Tiết kiệm tài nguyên**: Giảm 70-80% số lượng request `Common.ashx?id=76` nhờ cơ chế gom cụm theo thành.
- **An toàn mạng**: Duy trì nhịp gọi có giãn cách vi mô, không kích hoạt cơ chế chống spam của máy chủ game.
- **Trải nghiệm trực quan**: Bảng Treeview phản ánh tiến độ đếm ngược đồng thời của toàn bộ danh sách tướng, không còn hiện tượng chỉ 3 dòng chạy còn các dòng khác đứng yên.

