# Chuẩn Hóa Bình Man Hai Chế Độ Tác Chiến Và Tách Biệt Phân Hệ Gọi Man

## Ngữ Cảnh và Vấn Đề
Trước đây, nhiệm vụ Bình Man được thiết kế dựa trên một hàm thực thi chung nhưng chưa phân định ranh giới rõ ràng giữa việc di dời Doanh trại dã ngoại áp sát mục tiêu và việc xuất quân viễn chinh trực tiếp từ Thành kiên cố. Đồng thời, tính năng triệu hồi quái (trước đây gọi là Gọi Dân / Gọi Vong Linh) bị nhầm lẫn hoặc có xu hướng gộp chung vào phân hệ Bình Man, dẫn đến việc xử lý lỗi, quản lý hồi quân và giao diện cấu hình bị chồng chéo.

Người chơi có 2 nhu cầu tác chiến Man hoang dã rõ rệt:
1. **Dời Doanh trại áp sát**: Đóng quân tại Doanh trại dã ngoại, di chuyển Doanh trại từng bước tiếp cận mục tiêu trong cự ly gần ($\le 2$ ô) rồi mới xuất kích, giúp đánh liên tục các Man cấp cao ở xa mà không phải đi về Thành mẹ.
2. **Xuất quân thẳng từ Thành**: Tướng đồn trú trong Thành chính, chỉ xuất kích đánh các Man xuất hiện trong cự ly ngắn xung quanh Thành và tự động hồi thành sau trận đánh.

Bên cạnh đó, nhu cầu luyện tướng thông qua việc dùng bùa triệu hồi Man tại chỗ đòi hỏi sự linh hoạt trong việc lựa chọn cấp độ Man cụ thể (từ Cấp 1 Uy Quốc đến Cấp 10 Hổ Báo Kỵ, hoặc Vong Linh 301).

## Quyết Định Kiến Trúc

1. **Phân Tách Rõ Ràng Ranh Giới Giữa Bình Man và Gọi Man**:
   - **Bình Man (`BinhMan`)**: Chuyên trách quét và tiêu diệt các Man hoang dã tự nhiên phân bố trên bản đồ thế giới, hỗ trợ đúng 2 chế độ tác chiến:
     - `MODE_CAMP = 1` (Sử dụng Doanh trại di chuyển đến cạnh Man).
     - `MODE_CITY = 2` (Xuất quân thẳng từ Thành).
   - **Gọi Man (`GoiMan`)**: Giữ nguyên là một phân hệ độc lập, chuyên trách việc sử dụng đạo cụ (bùa) triệu hồi mục tiêu xuất hiện cạnh Thành rồi tiêu diệt. Bổ sung bộ chọn cấp độ Man linh hoạt (Cấp 1 đến Cấp 10 và Vong Linh ID 301).

2. **Quy Trình Tác Chiến Hai Chế Độ Trong `BinhMan`**:
   - **Chế Độ 1 (Doanh Trại Di Chuyển)**:
     - Yêu cầu cấu hình `camp_id` và `parent_city_id` (Thành mẹ).
     - Áp dụng thuật toán [ADR-0014](0014-server-feedback-driven-camp-relocation.md) (`DiTrai`): di chuyển Doanh trại từng bước (Chebyshev $\le 2$, lách vật cản, đếm lùi `frozen_time`) đến khi cự ly tới Man $\le 2$ ô thì xuất kích (`OPT.ashx?id=53`).
     - Khi mục tiêu bị người khác đánh mất giữa đường (`ret=230`) hoặc hết mục tiêu trong bán kính: Doanh trại giữ nguyên vị trí hiện tại và chờ chu kỳ quét kế tiếp, không quay đầu.
     - Khi binh lực/thể lực rơi xuống dưới Ngưỡng An Toàn: Tướng rút về Thành mẹ (`OPT.ashx?id=50`), trị thương (`OPT.ashx?id=31`), mua tân binh (`OPT.ashx?id=41`), biên chế (`OPT.ashx?id=6`), rồi tái xuất sang Doanh trại (`OPT.ashx?id=50`).
   - **Chế Độ 2 (Xuất Quân Thẳng Từ Thành)**:
     - Tướng đồn trú tại Thành (ID dương).
     - Quét tìm Man trong bán kính ngắn quanh Thành.
     - **Cơ chế Idle Check**: Trước khi quét và xuất quân, bot kiểm tra trạng thái của các Võ tướng. Chỉ xuất kích khi toàn bộ tướng trong đạo rảnh rỗi (`status == 0`). Nếu tướng đang hành quân trên đường, bot tạm dừng và đợi tướng hồi thành.
     - Phục hồi tại chỗ: Khi dưới Ngưỡng An Toàn, bot trị thương và bù lính ngay tại Thành mà không phát sinh lệnh chuyển căn cứ.

3. **Mở Rộng Hồ Sơ Cấu Hình (`ProfileStore`)**:
   - `BinhManProfile`: Bổ sung trường `mode: int = 1` (1: Doanh trại, 2: Thành), `target_types: list[int]` đồng bộ với `mantypes`.
   - `GoiManProfile` (tương thích khóa `goi_dan` trong JSON): Bổ sung `target_types: list[int] = [301]`, tự động tương thích ngược với trường `target_type: int`.

4. **Đồng Bộ Giao Diện Người Dùng (`Dashboard`)**:
   - Widget **`MultiSelectDropdown`**: Dùng chung cho cả 2 tab (Bình Man và Gọi Man) với danh mục chuẩn 11 mục: Vong Linh (ID 301) và 10 cấp độ Man tộc (Cấp 1 Uy Quốc đến Cấp 10 Hổ Báo Kỵ).
   - Menu checkbuttons kèm thao tác nhanh "Chọn tất cả" và "Bỏ chọn tất cả", tóm tắt nhãn hiển thị trực quan.
   - Tab Bình Man: Bổ sung RadioButton chọn Chế độ 1 hoặc Chế độ 2. Tự động vô hiệu hóa (disabled) ô nhập Doanh trại ID và Thành mẹ khi chọn Chế độ 2.
   - Tab Gọi Man: Thay combobox đơn bằng dropdown chọn nhiều loại Man.

5. **Cơ Chế Gọi Man Tuần Tự (Round-Robin) & Fallback Khi Thiếu Đạo Cụ**:
   - Khi chọn nhiều loại Man mục tiêu, task `GoiMan` thực hiện gọi xoay vòng tuần tự qua từng loại đã chọn.
   - Nếu gọi một loại thất bại (do hết lệnh bài trong kho hoặc mã lỗi khác), bot tự động thử loại kế tiếp trong danh sách để duy trì tiến trình luyện tướng không bị ngắt quãng.

6. **Chủ Động Chọn Võ Tướng Xuất Kích Cho Bình Man và Gọi Man**:
   - **Giao diện bảng danh sách võ tướng (`Treeview`)**: Bổ sung `Treeview` hiển thị đầy đủ thông tin chi tiết (`Tên võ tướng`, `Chọn [x]`, `Cấp`, `Thể lực`, `Sĩ khí`, `Bộ binh`, `Kỵ binh`, `Cung binh`, `Tổng quân`) được bố trí trực quan ngay phía trên khung nhật ký log cho cả Tab Gọi Man và Tab Bình Man.
   - **Thao tác nhanh**: Cung cấp 2 nút "✅ Chọn tất cả" và "❌ Bỏ chọn tất cả" cùng khả năng nhấp chuột trực tiếp vào từng dòng để bật/tắt (toggle) chọn tướng xuất kích.
   - **Quy tắc chọn mặc định khi đổi căn cứ**:
     - *Gọi Man*: Mặc định chọn 3 võ tướng đầu tiên trong Thành (hoặc toàn bộ nếu ít hơn 3).
     - *Bình Man*: Mặc định chọn tất cả võ tướng có trong căn cứ (Doanh trại hoặc Thành), đáp ứng nhu cầu huy động toàn lực không giới hạn số lượng tướng viễn chinh.
   - **Lưu trữ hồ sơ (`ProfileStore`)**:
     - Bổ sung trường `generals: list[int] = field(default_factory=list)` vào cả `BinhManProfile` và `GoiDanProfile`.
     - Tự động xuất/nạp trạng thái tích chọn võ tướng xuất kích khi lưu và mở hồ sơ cấu hình tài khoản.

## Đánh Đổi và Hệ Quả

- **Đạt được**:
  - Trải nghiệm đồng nhất giữa Bình Man và Gọi Man, hiển thị đầy đủ cấp độ và tên gọi chuẩn.
  - Người chơi chủ động quyết định đạo quân xuất kích thay vì bị ép cứng vào 3 tướng đầu danh sách.
  - Bình Man có khả năng huy động không giới hạn số lượng võ tướng tham chiến tùy ý người chơi.
  - Cho phép người chơi kết hợp nhiều loại lệnh bài triệu hồi cùng lúc mà không lo hết loại này làm dừng bot.
  - Tối ưu hóa lưu lượng mạng và thời gian đóng băng Doanh trại.
  - Giao diện trực quan, thân thiện, ngăn ngừa sai sót cấu hình từ người dùng.
- **Chấp nhận**:
  - Cần duy trì cơ chế tương thích ngược cho các file cấu hình cũ chưa có trường `mode`, `target_types`, hoặc `generals`.

