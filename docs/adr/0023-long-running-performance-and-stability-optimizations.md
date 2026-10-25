# Tối Ưu Hiệu Năng và Độ Ổn Định Khi Chạy Dài Hạn (24/7)

## Ngữ Cảnh và Vấn Đề
Linh Vương Bot được thiết kế để vận hành nền tự động liên tục trong thời gian dài (hàng ngày, 24/7). Sau đợt review hiệu năng chuyên sâu, phát hiện một số điểm nghẽn và nguy cơ suy giảm độ ổn định khi chạy lâu:

1. **Rò rỉ nhân bản Timer chu kỳ trong giao diện**: `_schedule_periodic_boost_check` trong `dashboard.py` tự kích hoạt định kỳ 60s, nhưng lại được gọi thêm mỗi lần nạp danh sách căn cứ (reload hoặc sau mỗi đợt luyện sĩ khí). Điều này tạo ra chuỗi nhân bản timer tăng dần theo thời gian, làm bùng nổ các luồng kiểm tra ngầm.
2. **Bão Polling Roster trong Thảo Phạt**: `ThaoPhatAutoRunner` gọi hàm toàn cục `fetch_roster` trong các vòng lặp chờ (chờ tướng về, chờ nâng sĩ khí, chờ về sau trận). Với tài khoản có 10 thành/trại, mỗi lần gọi phát sinh 14 HTTP requests, dẫn tới hàng nghìn request nhàn rỗi trong 30 phút, gây nghẽn và tăng nguy cơ bị máy chủ chặn.
3. **Gọi lặp trùng API kiểm tra thi công**: Trong `BuildingTask`, mỗi chu kỳ cho từng thành gọi cả `check_and_activate_boost()` và `get_active_upgrade_slots()`, cả hai đều bắn request `Common.ashx?id=77` riêng biệt dù cùng một dữ liệu.
4. **Polling dày đặc khi nâng sĩ khí**: `MoraleTrainer` kiểm tra `Common.ashx?id=76` mỗi 2 giây kể cả khi tướng đang có thời gian nâng dở dang (`up_t`) kéo dài hàng trăm giây.
5. **Rò rỉ bộ nhớ khóa mục tiêu**: `TargetLocks` trong `locks.py` lưu trữ `_expiry` vô hạn mà không có cơ chế dọn dẹp các mục tiêu đã hết hạn sau hàng ngày quét bản đồ.
6. **Mở socket liên tục do Connection Pool mặc định nhỏ**: `requests.Session` mặc định giữ pool 10 kết nối, trong khi bot có thể chạy đồng thời 5-8 luồng dẫn đến socket bị đóng và mở lại liên tục.

## Quyết Định Kiến Trúc

1. **Kiểm soát Timer Tkinter có định danh và hủy chuỗi cũ**:
   - Lưu `_boost_after_id` trong `Dashboard`.
   - Trước khi lập lịch chu kỳ 60s mới, kiểm tra và gọi `after_cancel` nếu timer trước đó đang chờ thực thi.

2. **Truy vấn Roster có định hướng căn cứ (`only_base_ids`)**:
   - Bổ sung tham số `only_base_ids: Optional[Iterable[int]]` vào hàm `fetch_roster(gateway, only_base_ids)`.
   - Khi lọc, chỉ các căn cứ nằm trong danh sách mới được truy vấn API 76 (chi tiết binh lực & sĩ khí).
   - `ThaoPhatAutoRunner` truyền `only_base_ids=[self.city_id]`, giảm ~85% số request trong toàn bộ vòng lặp Thảo Phạt.

3. **Bộ nhớ đệm chu kỳ ngắn cho trạng thái thi công (`_fetch_c77`)**:
   - `BuildingTask` cache kết quả `Common.ashx?id=77` trong thời gian ngắn (3 giây) trong cùng một chu kỳ `run_once()`.
   - Cả `check_and_activate_boost()` và `get_active_upgrade_slots()` tái sử dụng cùng kết quả phản hồi. Cache tự động xóa sạch khi kích hoạt boost hoặc tăng tốc.

4. **Chờ thích ứng (Adaptive Waiting) trong `MoraleTrainer`**:
   - Khi `up_t > 0`, thời gian chờ được điều chỉnh động theo công thức: `min(up_t, max(poll_interval, min(up_t / 2.0, 30.0)))`.
   - Tích hợp `sleep_fn` kế thừa từ `GatewayClient` để kiểm thử độc lập mà không tốn thời gian thực.

5. **Tự động dọn dẹp khóa hết hạn (Eviction / Pruning) trong `TargetLocks`**:
   - Thêm phương thức `_prune_locked(now)` kích hoạt khi kích thước từ điển vượt quá ngưỡng 256 phần tử, giải phóng toàn bộ khóa đã quá hạn.

6. **Tối ưu Connection Pool cho `GatewayClient`**:
   - Gắn `HTTPAdapter(pool_connections=4, pool_maxsize=32)` vào `requests.Session` khi khởi tạo gateway client.

7. **Đồng bộ hóa dọn dẹp toàn diện trong `Dashboard.destroy()`**:
   - Phát tín hiệu dừng `stop()` cho toàn bộ các runner (`_tp_runner`, `_gd_runner`, `_bm_runner`, `_bld_runner`, `_res_runner`).
   - Hủy cờ `_res_monitor_running = False`, giải phóng timer `after_cancel`.

## Hệ Quả
- **Tiết kiệm tài nguyên mạng**: Giảm từ 60% đến 85% lưu lượng HTTP nhàn rỗi trong các tác vụ dài ngày.
- **Tiêu thụ RAM ổn định**: Bộ nhớ duy trì ở mức phẳng, không phình to theo thời gian chạy.
- **Độ tin cậy cao**: Loại bỏ rủi ro văng ứng dụng do Tcl thread desync hoặc cạn kiệt socket.
