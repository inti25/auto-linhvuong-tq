# ADR 0035: Điều Phối Bình Man Đa Căn Cứ Đa Luồng Song Song (Concurrent Multi-Base Binh Man)

## Ngữ Cảnh và Vấn Đề

Tại [ADR-0029](0029-multi-base-independent-binh-man-and-target-locking.md), phân hệ **Bình Man Đa Căn Cứ** đã được xây dựng để cho phép quản lý cấu hình độc lập và khóa mục tiêu tập trung (`TargetLocks`) giữa các Thành và Doanh trại. Tuy nhiên, kiến trúc điều phối lúc đó vận hành theo mô hình vòng lặp tuần tự đơn luồng (`Multi-Base Round-Robin Coordinator` trong một Thread duy nhất):

```python
for t in self.tasks:
    res = t.run_once()
```

### Triệu Chứng và Sự Cố Thực Tế
1. **Một thành xuất quân làm tắc nghẽn toàn bộ các thành khác**:
   Khi một căn cứ xuất kích tấn công mục tiêu dã ngoại (`attack()`), hoặc khi võ tướng đang trên đường hành quân / trong chiến trường, `BinhMan.run_once()` sẽ gọi `_track_active_battle()`. Hàm này chạy đồng bộ và liên tục thăm dò, chờ đợi hành quân (mất 20 - 60 giây) và theo dõi từng hiệp giao tranh trong chiến trường (có thể kéo dài 2 - 5 phút).
2. **Các thành khác bị đóng băng hoàn toàn**:
   Do toàn bộ các căn cứ chạy chung một luồng tuần tự, trong suốt thời gian căn cứ đầu tiên đang xuất quân và đánh quái, vòng lặp bị chặn đứng tại căn cứ đó. Các căn cứ còn lại không được gọi `run_once()` để quét quái, dời trại, phục hồi quân hay xuất kích, làm giảm nghiêm trọng hiệu suất cày quái và tài nguyên.

## Quyết Định Kiến Trúc

1. **Điều Phối Đa Luồng Độc Lập Cho Từng Căn Cứ (`BinhManAutoRunner`)**:
   - Khi khởi động nhiệm vụ Bình Man, `BinhManAutoRunner` khởi tạo và quản lý một danh sách các luồng worker độc lập (`BMWorker-<base_name>`), mỗi căn cứ sở hữu một worker thread riêng:
     ```python
     for t in self.tasks:
         w = threading.Thread(
             target=self._run_base_worker,
             args=(t,),
             name=f"BMWorker-{base_label}",
             daemon=True,
         )
         self.worker_threads.append(w)
         w.start()
     ```
   - Mỗi worker thread thực thi vòng lặp tác chiến khép kín độc lập:
     - Tự động gọi `task.run_once()`.
     - Nếu có hành động (xuất quân, theo dõi trận đánh, dời trại, hồi quân), sau khi hoàn tất nhịp sẽ chỉ chờ ngắn 1.0s để duy trì nhịp tác chiến liên tục.
     - Nếu không có quái (`no_target`), võ tướng bận hoặc đang đợi sĩ khí/hồi lính, worker tự động chờ chu kỳ `interval` giây (kèm Jitter ngẫu nhiên $\pm 1 \sim 2$s).

2. **Chia Sẻ Tài Nguyên An Toàn Luồng (Thread-Safety)**:
   - **GatewayClient**: Sử dụng connection pool (`pool_connections=4, pool_maxsize=32`) qua `requests.adapters.HTTPAdapter` để các thread gửi yêu cầu HTTP đồng thời mà không bị nghẽn socket hoặc xung đột kết nối.
   - **TargetLocks**: Bộ khóa mục tiêu dùng chung đã được bảo vệ bằng `threading.Lock()`, đảm bảo khi 2 căn cứ cùng quét thấy một Man tại cùng một thời điểm, chỉ căn cứ ưu tiên cự ly gần nhất mới khóa thành công.
   - **Tkinter Thread Marshalling**: Mọi thông báo nhật ký (`log_cb`) và sự kiện giao diện (`on_battle_found`, `on_battle_state`) từ các worker thread đều được điều phối qua `self.after(0, ...)` về main thread của Tkinter.

3. **Cập Nhật Tọa Độ Đồng Đội Động Theo Thời Gian Thực (`peers_fn`)**:
   - Thay vì truyền danh sách tọa độ căn cứ tĩnh tại thời điểm khởi tạo, hệ thống liên kết hàm callback động `peers_fn` cho từng task.
   - Khi bất kỳ Doanh trại nào dời vị trí (`advance_camp_one_step`), các căn cứ khác ngay lập tức nhận diện được tọa độ mới nhất của trại đó để áp dụng chính xác Quy Tắc Ưu Tiên Căn Cứ Gần Nhất (ADR-0029).

4. **Đa Luồng Cho Thao Tác Chạy 1 Lượt (`_run_binhman_once`)**:
   - Nâng cấp nút "Chạy 1 lượt" trên giao diện để kích hoạt các worker song song cho tất cả các căn cứ được chọn thay vì duyệt tuần tự.

5. **Đồng Bộ Dừng Khẩn Cấp Và Xử Lý Captcha**:
   - Chia sẻ cờ `self.stop_event` giữa runner và tất cả các worker threads.
   - Khi người dùng bấm nút "Dừng" hoặc khi **bất kỳ căn cứ nào** gặp `CaptchaRequired`, cờ `stop_event` lập tức được kích hoạt. Toàn bộ các worker đang chờ `wait_cycle()` hoặc đang ngủ đếm lùi trong `sleep_fn()` lập tức thức giấc và kết thúc an toàn trong vòng dưới 1 giây.

## Hệ Quả

- **Đạt được**:
  - Các căn cứ hoạt động hoàn toàn song song: Thành A đang xuất quân đánh Man thì Thành B vẫn liên tục quét quái, dời trại hoặc xuất trận độc lập.
  - Tối đa hóa sản lượng săn Man và kinh nghiệm danh tướng khi vận hành nhiều thành/trại cùng lúc.
  - Tương thích ngược 100% với trường hợp người dùng chỉ chạy 1 căn cứ duy nhất.
  - Dừng nhiệm vụ nhanh chóng, dứt điểm, không treo giao diện hay rò rỉ luồng.

