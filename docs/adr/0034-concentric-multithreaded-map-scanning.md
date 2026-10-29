# ADR 0034: Tối Ưu Tốc Độ Quét Bản Đồ (Step 7 Và Quét Song Song 3 Luồng)

## Ngữ Cảnh và Vấn Đề
Trước đây, bộ quét bản đồ `Scanner` ([ADR-0029](0029-multi-base-independent-binh-man-and-target-locking.md)) sử dụng bước nhảy cố định `step = 5` và vận hành hoàn toàn tuần tự (single-threaded).
Khi người chơi thiết lập bán kính quét lớn (ví dụ bán kính 50 hoặc 60 để tìm kiếm Man hiếm hoặc dã ngoại):
1. **Số lượng request bùng nổ**: Bán kính 50 tạo ra 317 điểm quét; bán kính 60 tạo ra 441 điểm quét.
2. **Độ trễ tích lũy quá lớn**: Khi sử dụng proxy (đặc biệt là proxy SOCKS5), độ trễ mỗi request khoảng 250ms - 350ms. Việc quét tuần tự 441 điểm tốn tới hơn **2 phút rưỡi** (150 giây) cho một lượt quét nếu không có Man hoặc Man ở rìa ngoài.
3. **Chồng lấn tầm nhìn lãng phí**: Đo đạc thực tế từ gói tin `Map.ashx?id=6` của máy chủ Linh Vương cho thấy tầm nhìn hiệu dụng của 1 gói tin bao phủ lưới $13 \times 13$ ô (offset $\pm 6$ cả trục X và Y). Với `step = 5`, độ chồng lấn lên tới 8 ô, khiến nhiều vị trí bản đồ bị truy vấn lặp lại 2-4 lần trong cùng một lượt.

## Quyết Định Kiến Trúc

1. **Nâng Bước Nhảy Quét Mặc Định Từ `step = 5` Lên `step = 7`**:
   - Dựa trên tầm nhìn $\pm 6$ ô của máy chủ, bước nhảy `step = 7` đảm bảo hai điểm quét liền kề có độ giao thoa là $13 - 7 = 6$ ô.
   - Chứng minh thực nghiệm hình học: `step = 7` bảo đảm **100% độ phủ (0 điểm mù)** trên mọi bán kính quét từ $R = 10$ đến $R = 60$.
   - Tại $R = 60$, số lượng điểm quét giảm từ **441 xuống còn 233 điểm** (giảm gần 50% số lượng request cần gửi).

2. **Cơ Chế Quét Song Song 3 Luồng Theo Lô Đồng Tâm (Concentric Batching with 3 Workers)**:
   - `Scanner` được bổ sung tham số `workers: int = 3` (mặc định 3 luồng song song, có thể cấu hình).
   - Tận dụng `ThreadPoolExecutor(max_workers=self.workers)` và connection pool sẵn có trong `GatewayClient` (`pool_maxsize=32`).
   - Các điểm quét được sắp xếp tăng dần theo khoảng cách Euclid từ gốc $O(ox, oy)$ và chia thành từng lô (batch) có kích thước bằng `workers`.
   - Ba luồng gửi đồng thời 3 request `map_view` qua `executor.map`, duy trì ổn định 3 kết nối song song và giảm thời gian quét thực tế xuống gấp 3 lần mà không gây quá tải hay kích hoạt cơ chế chống spam của máy chủ game.

3. **Thuật Toán Ngắt Sớm Dựa Trên Bất Đẳng Thức Tam Giác (Triangle Inequality Early-Exit)**:
   - Để bảo toàn nguyên tắc bắt buộc: **luôn trả về mục tiêu hợp lệ gần nhất**, thuật toán không ngắt ẩu ngay khi một luồng bất kỳ tìm thấy Man.
   - Khi tìm thấy các mục tiêu ứng viên, hệ thống xác định cự ly của mục tiêu gần nhất $D_{min} = \min(dist)$.
   - Theo bất đẳng thức tam giác: Một điểm quét $P$ tại khoảng cách $d_{next}$ chỉ có thể quan sát các mục tiêu trong phạm vi bán kính tối đa 6 ô quanh $P$. Do đó, mọi mục tiêu $T$ nhìn thấy từ $P$ đều thỏa mãn:
     $$\|T - O\| \ge \|P - O\| - \|T - P\| \ge d_{next} - 6$$
   - Ngay khi cự ly của lô điểm quét tiếp theo thỏa mãn $d_{next} \ge D_{min} + 6$, hệ thống khẳng định chắc chắn 100% không còn bất kỳ điểm nào phía sau có thể chứa mục tiêu gần hơn $D_{min}$. Lúc này, bot lập tức khóa và trả về mục tiêu chiến thắng, hủy toàn bộ các lô quét còn lại.

4. **Tương Thích Ngược Và Dự Phòng Tuần Tự (Sequential Fallback)**:
   - Khi cấu hình `workers <= 1`, `Scanner` tự động chuyển về luồng quét tuần tự đơn giản, loại bỏ hoàn toàn chi phí điều phối luồng trong các môi trường kiểm thử hoặc thiết bị cấu hình thấp.

## Hệ Quả

- **Hiệu năng vượt trội**:
  - Thời gian quét trọn vẹn bán kính 60 giảm từ **~150 giây xuống còn ~19 giây** (tăng tốc độ gấp **~8 lần**).
  - Với các mục tiêu ở khoảng cách gần và trung bình (bán kính 10 - 25), thời gian phản hồi chỉ còn từ **1 - 3 giây**.
- **An toàn máy chủ**: Mức tải 3 luồng song song qua kết nối SOCKS5 hoàn toàn nằm trong ngưỡng an toàn của game server Linh Vương.
