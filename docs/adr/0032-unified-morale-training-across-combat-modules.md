# ADR 0032: Đồng Bộ Luyện Sĩ Khí Toàn Diện Chống Khóa Tài Khoản Cho Bình Man, Gọi Man Và Thảo Phạt

## Ngữ Cảnh và Vấn Đề
Trước đây, cơ chế **Luyện Sĩ Khí Quân Đội** đã được tối ưu hóa thành công tại Tab Tổng Quan ([ADR-0022](0022-concurrent-multi-city-morale-training.md), [ADR-0028](0028-tick-scheduler-for-multi-city-morale-training.md)) thông qua bộ điều phối `MoraleTrainer` sử dụng kiến trúc Vòng Lặp Chu Kỳ (Tick Scheduler), gom cụm truy vấn qua API `Common.ashx?id=76`, kích hoạt đồng thời không giới hạn số tướng và áp dụng khoảng nghỉ an toàn.

Tuy nhiên, trong các phân hệ tác chiến dã ngoại gồm **Bình Man**, **Gọi Man** và **Thảo Phạt**, logic luyện sĩ khí vẫn tồn tại nhiều nhược điểm nguy hiểm:
1. **Nâng tuần tự gây nghẽn tiến trình**: Trong chu kỳ `run_once()` của Bình Man và Gọi Man, vòng lặp kiểm tra tướng ngay khi phát hiện tướng đầu tiên thiếu sĩ khí đã gọi nâng và lập tức thoát `return "waiting_morale"`. Điều này khiến các tướng thứ 2, 3 hoàn toàn không được kích hoạt, dẫn đến việc luyện 3 tướng bị kéo dài gấp 3 lần và sinh ra hàng loạt chu kỳ polling vô ích.
2. **Nguy cơ khóa tài khoản do lỗi 40 (`ret=40`)**: Khi rút về Thành mẹ trị thương hoặc phục hồi tại chỗ, bot gọi `adjust_morale(..., current_morale=0)` mà không kiểm tra xem tướng có đang trong thời gian đếm ngược (`upgrading_time > 0`) hay không. Khi gửi lệnh `OPT.ashx?id=47` trong lúc đang đếm ngược, máy chủ trả về mã lỗi 40. Việc phát sinh lỗi 40 lặp lại là dấu hiệu nhận diện bot rõ ràng khiến tài khoản bị đưa vào danh sách đen hoặc khóa.
3. **Thiếu giãn cách vi mô (Micro-delay / Jitter)**: Các lệnh `adjust_morale` trong Thảo Phạt và các nút thủ công gửi đi dồn dập trong 0ms, dễ kích hoạt cơ chế phát hiện tần suất gói tin từ máy chủ.
4. **Xung đột điều chuyển tướng tại Doanh trại**: Khi rút về Thành mẹ, bot vừa kích hoạt nâng sĩ khí tại Thành mẹ đã lập tức gửi lệnh phái tướng quay lại Doanh trại (`OPT.ashx?id=50`) khi đếm ngược còn chạy dở, gây xung đột trạng thái giữa máy chủ và client.

## Quyết Định Kiến Trúc

1. **Chuẩn Hóa Lõi Miền Dùng Chung Trong [`MoraleTrainer`](../../linhvuong/tasks/morale.py)**:
   - **Chặn đứng mã lỗi 40**: Trước khi phát lệnh `OPT.ashx?id=47`, bắt buộc phải xác nhận qua thông tin API 76 rằng `upgrading_time == 0`. Tuyệt đối không gửi lệnh khi tướng đang đếm ngược.
   - **Giãn cách vi mô ngẫu nhiên (Micro-jitter)**: Áp dụng khoảng trễ ngẫu nhiên từ `100ms - 250ms` giữa các request `OPT.ashx?id=47` trong cùng một nhịp kích hoạt đồng loạt.
   - **Tích hợp tham số `travel_time: float = 0.0`**:
     - Mặc định `travel_time = 0.0` (dành cho Bình Man, Gọi Man, Tab Tổng Quan): Tướng chỉ được tính là hoàn tất khi đếm ngược về `0` và đạt `target_morale`.
     - Khi `travel_time > 0.0` (Thảo Phạt): Tướng được coi là sẵn sàng xuất quân ngay khi lượt nâng cuối cùng đảm bảo đạt ngưỡng (`current_morale + 10 >= target_morale`) và thời gian đếm ngược còn lại $0 < upgrading\_time \le travel\_time$.
   - **Xử lý tài nguyên an toàn**: Khi máy chủ phản hồi lỗi (ví dụ mã lỗi 15 do thiếu lúa), ghi log cảnh báo chi tiết và tạm dừng chu kỳ, không thử lại liên tục.

2. **Kích Hoạt Đồng Loạt Trong Chu Kỳ Tác Chiến Bình Man và Gọi Man**:
   - Trong `run_once()` của `BinhMan` và `GoiDan`, gom toàn bộ danh sách võ tướng xuất kích thiếu sĩ khí và chạy trực tiếp `MoraleTrainer.train_multiple_generals`.
   - Toàn bộ võ tướng được kích hoạt nâng sĩ khí đồng thời trên máy chủ, đếm ngược song song và cập nhật nhật ký thời gian thực qua `self.ctx.notify`.
   - Đảm bảo 100% võ tướng đạt chuẩn trước khi bước sang quét tìm Man hoặc gọi Man mới.

3. **Chiến Lược Luyện Sĩ Khí Tại Doanh Trại Cho Bình Man**:
   - Khi rút quân về Thành mẹ để phục hồi (`retreat_to_safety` hoặc `provision_camp_generals_with_parent_city`), tướng chỉ trị thương (`OPT.ashx?id=31`) và bổ sung quân số (`adjust_troops`), sau đó lập tức phái trở lại Doanh trại (`OPT.ashx?id=50`).
   - Việc Luyện Sĩ Khí không thực hiện tại Thành mẹ mà được thực hiện hoàn toàn tại Doanh trại thông qua `MoraleTrainer` khi tướng đã đóng quân ổn định tại Trại, loại trừ hoàn toàn rủi ro di chuyển tướng khi đang đếm ngược.

4. **Tái Cấu Trúc Thảo Phạt Và Giao Diện Thủ Công**:
   - Thay thế toàn bộ vòng lặp kiểm tra sĩ khí tự tạo trong `ThaoPhatAutoRunner` bằng `MoraleTrainer.train_multiple_generals` với tham số `travel_time`.
   - Thay thế các lời gọi `adjust_morale` đơn lẻ trong các nút "⚔️ Biên chế ngay" trên Tab Bình Man và Gọi Man bằng `MoraleTrainer` chạy trong luồng nền có báo cáo tiến độ mượt mà.

## Hệ Quả

- **An toàn tuyệt đối chống block**: Loại bỏ 100% lỗi `ret=40`, loại bỏ bão request nhờ micro-jitter ngẫu nhiên, không còn các request bất thường lên máy chủ.
- **Tốc độ chuẩn bị vượt trội**: Thời gian nâng sĩ khí cho đội 3 tướng trong Bình Man và Gọi Man giảm từ $3 \times T$ xuống chỉ còn $1 \times T$ do tất cả tướng cùng đếm ngược song song.
- **Tính nhất quán kiến trúc**: Tab Tổng Quan, Bình Man, Gọi Man và Thảo Phạt đều sử dụng chung một engine `MoraleTrainer` duy nhất, dễ dàng bảo trì và kiểm thử tự động.
