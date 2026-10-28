# ADR 0029: Bình Man Đa Căn Cứ Độc Lập Và Khóa Mục Tiêu Ưu Tiên Căn Cứ Gần Nhất

## Ngữ Cảnh và Vấn Đề
Trước đây, phân hệ **Bình Man** ([ADR-0024](0024-binh-man-two-modes-and-isolated-goi-man.md), [ADR-0026](0026-multi-wave-expeditions-for-binh-man-and-goi-man.md), [ADR-0027](0027-unified-army-provisioning-for-binh-man-and-goi-man.md)) được cấu hình dưới dạng một bản ghi phẳng duy nhất trong `BinhManProfile`. Mọi thông số (chế độ tác chiến, bán kính quét, loại Man, định mức lính, danh sách võ tướng xuất kích) đều là các biến toàn cục áp dụng chung cho một căn cứ duy nhất đang được chọn qua Combobox.

Hạn chế nghiêm trọng:
1. **Ghi đè cấu hình giữa các căn cứ**: Người chơi thường có chiến lược tác chiến phân hóa rõ rệt giữa các cứ điểm:
   - Thành chính hoặc phân thành: Xuất kích Chế độ 2 diệt Man cấp 1-4 trong bán kính ngắn quanh thành để thu thập trang bị và nguyên liệu.
   - Doanh trại dã ngoại A: Di chuyển Chế độ 1 áp sát săn Man cấp 10 (Hổ Báo Kỵ) ở các vùng biên ải xa xôi.
   - Doanh trại dã ngoại B: Di chuyển săn Man cấp 7-8 (Hung Nô, Đột Quyết).
   Khi chuyển đổi căn cứ trên giao diện, bot không lưu được cấu hình riêng, khiến người chơi phải nhập lại toàn bộ thông số và tích chọn lại võ tướng thủ công mỗi lần chuyển đổi.
2. **Thiếu khả năng tự động hóa đa căn cứ**: Bot chỉ có thể chạy cho đúng 1 căn cứ tại một thời điểm, người chơi phải túc trực đổi căn cứ bằng tay thay vì bot tự động quán xuyến toàn bộ các căn cứ.
3. **Nguy cơ tranh chấp và xuất quân trùng lặp**: Khi vận hành nhiều căn cứ gần nhau hoặc có vùng quét chồng lấn, hai căn cứ có thể cùng quét thấy một Man và cùng gửi quân xuất kích (hoặc cùng dời trại về một điểm), dẫn đến lãng phí lương thực, hao tổn thời gian hành quân và phát sinh lỗi máy chủ chiếm cứ điểm (`ret=230`).

## Quyết Định Kiến Trúc

1. **Chuẩn Hóa Mô Hình Dữ Liệu Độc Lập Theo Từng Căn Cứ (`ProfileStore`)**:
   - Mở rộng [`BinhManProfile`](../../linhvuong/profile.py) trong Hồ Sơ Cấu Hình (`auto_profile_{username}_{server_id}.json`) bổ sung danh điển căn cứ:
     `bases: dict[str, BaseBinhManConfig] = field(default_factory=dict)`
   - Mỗi thực thể `BaseBinhManConfig` đại diện cho một Căn Cứ (Thành hoặc Doanh trại), quản lý độc lập:
     - `enabled: bool = False`: Trạng thái bật/tắt tham gia chiến dịch Bình Man.
     - `mode: int`: 1 (Doanh trại di chuyển) hoặc 2 (Xuất quân từ Thành).
     - `radius: str`, `threshold: str`: Bán kính quét và Ngưỡng An Toàn (%).
     - `target_types: list[int]`, `mantypes: str`: Danh mục Man mục tiêu.
     - `generals: list[int]`: Danh sách ID võ tướng xuất kích riêng của căn cứ đó.
     - `target_infantry: str`, `target_cavalry: str`, `target_archers: str`: Định Mức Biên Chế riêng.
     - `auto_recruit: bool`, `auto_morale: bool`, `min_morale: str`: Thiết lập phục hồi quân và sĩ khí.
     - `camp_id: str`, `parent_city_id: str`: Định danh trại và Thành mẹ hồi quân.
   - **Tương thích ngược tuyệt đối**: Khi nạp tệp hồ sơ cũ chưa có trường `bases`, hệ thống tự động ánh xạ các giá trị phẳng hiện tại vào căn cứ đang hoạt động hoặc căn cứ đầu tiên, bảo toàn toàn vẹn dữ liệu người dùng.

2. **Bộ Điều Phối Vòng Lặp Đa Căn Cứ Tuần Tự (Multi-Base Round-Robin Coordinator)**:
   - Vận hành một tiến trình điều phối duy nhất tuần tự duyệt qua danh sách các Căn Cứ Bình Man có `enabled == True`.
   - **Cơ chế chuyển lượt không chặn (Non-blocking)**:
     - Nếu một căn cứ có võ tướng đang bận (đang hành quân hoặc trong Chiến trường) hoặc Doanh trại đang trong Thời Gian Đóng Băng (`frozen_time`), bộ điều phối không ngủ chờ mà lập tức chuyển lượt sang căn cứ hợp lệ kế tiếp.
     - Chỉ khi toàn bộ các căn cứ được bật đều không có hành động nào khả dụng hoặc không tìm thấy mục tiêu (`no_target`), bot mới nghỉ trọn vẹn `interval` giây (kèm Độ Trễ Ngẫu Nhiên $\pm 1 \sim 2$s) trước khi lặp lại vòng quét mới.

3. **Khóa Mục Tiêu Tập Trung Và Quy Tắc Ưu Tiên Căn Cứ Gần Nhất (Nearest Base Priority)**:
   - **Bộ quản lý khóa dùng chung (`Shared TargetLocks`)**: Tất cả các căn cứ trong cùng tài khoản chia sẻ một thể hiện `TargetLocks` duy nhất.
   - **Giải quyết tranh chấp theo khoảng cách**: Khi một Man mục tiêu nằm trong tầm quét của nhiều Căn Cứ cùng lúc:
     - Hệ thống tính toán cự ly (khoảng cách Chebyshev/Euclid) từ các Căn Cứ hợp lệ tới Man đó.
     - Quyền khóa (`try_lock`) và xuất kích được **ưu tiên tuyệt đối cho Căn Cứ có cự ly gần Man nhất**.
     - Căn Cứ ở xa hơn sẽ tự động bỏ qua Man này và tìm mục tiêu tiếp theo trong bán kính của mình.
   - **Chốt chặn trước khi xuất quân (Pre-flight Verification)**: Ngay trước khi gửi lệnh xuất kích `OPT.ashx?id=53`, bot kiểm tra lại trạng thái khóa: nếu mục tiêu đã bị căn cứ khác nhắm tới hoặc bị chiếm, lập tức hủy lệnh xuất quân và chuyển sang quét mục tiêu khác.

4. **Tái Cấu Trúc Giao Diện Người Dùng (2-Pane Layout)**:
   - **Bảng Căn Cứ (Trái / Treeview)**: Hiển thị toàn bộ Thành và Doanh trại với các cột: `[x] Chạy`, `Tên căn cứ`, `Loại` (Thành/Trại), `Tọa độ`, `Số tướng chọn`. Đi kèm các nút thao tác nhanh "Chọn tất cả", "Bỏ tất cả".
   - **Khung Chi Tiết (Phải / Dưới)**: Hiển thị và chỉnh sửa độc lập các thông số (Chế độ, Bán kính, Loại Man, Định mức lính, Bảng danh sách võ tướng xuất kích) của căn cứ đang được chọn trên Treeview. Chuyển đổi căn cứ tự động lưu cấu hình căn cứ cũ và nạp cấu hình căn cứ mới mà không làm mất dữ liệu.
   - **Hành vi nút biên chế**:
     - Nút `⚔️ Biên chế ngay`: Kích hoạt bổ sung lính và luyện sĩ khí cho duy nhất căn cứ đang được nhấp chọn.
     - Nút `⚔️ Biên chế tất cả`: Kích hoạt tiến trình biên chế quân tự động tuần tự cho toàn bộ các Căn Cứ đang bật `[x] Chạy`.

5. **Bộ Quy Tắc An Toàn Mặc Định Cho Căn Cứ Mới**:
   - Trạng thái thi công mặc định: `enabled = False` (chưa chọn chạy).
   - Danh sách võ tướng: Mặc định chọn tất cả võ tướng có trong căn cứ đó.
   - Định mức lính: Mặc định `0 / 0 / 0` (giữ nguyên quân lực sẵn có, không tự ý đổi binh chủng).

## Hệ Quả

- **Đạt được**:
  - Người chơi tự do thiết lập chiến thuật riêng cho từng Thành và Doanh trại mà không lo bị ghi đè.
  - Tự động hóa hoàn toàn việc Bình Man đa căn cứ song song/luân phiên, gia tăng tối đa sản lượng tài nguyên, kinh nghiệm tướng và trang bị.
  - Triệt tiêu 100% rủi ro xung đột hoặc xuất quân trùng một Man nhờ cơ chế Khóa tập trung và Quy tắc Ưu tiên Căn cứ gần nhất.
  - Luồng chạy mượt mà, không bị nghẽn khi một căn cứ rơi vào thời gian đóng băng hoặc đợi tướng hồi thành.
- **Đánh đổi**:
  - Cần nâng cấp mô hình dữ liệu `Profile` và các bài kiểm thử tự động để bảo đảm tính tương thích ngược với các file `auto_profile.json` cũ.
