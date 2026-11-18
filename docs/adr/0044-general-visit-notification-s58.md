# ADR 0044: Thông Báo Danh Tướng Viếng Thăm Tại Tửu Quán & Quán Trọ (Server 58)

- **Status**: accepted

## Bối Cảnh & Vấn Đề

Trong Linh Vương, khi xuất hiện **Danh Tướng Viếng Thăm** (danh tướng võ tại Tửu Quán `gid=8` hoặc danh sỹ văn tại Quán Trọ `gid=7`), server trả về trường `rumor` (ví dụ `[265, 228, 83, '张嶷']`) thông qua `Build.ashx?id=2` (`tab=2`, `pid=-1`, `tid=0`) theo ngữ cảnh thành đang chọn.

Kiểm chứng trực tiếp trên `sg58.dipan.com` cho thấy:
1. Danh sách `rumor` viếng thăm được dùng chung toàn tài khoản ở tất cả các **Thành** (không cần quét lặp lại từng thành).
2. Nếu một thành chưa xây Tửu Quán / Quán Trọ thì kết quả trống, trong khi thành có xây công trình đó trả về ngay thông tin `rumor`.
3. Cách chuyển ngữ cảnh thành trên S58 (`POST /api/city/current`) khác với S1–S57 (`City.ashx?id=50`) và hiện chưa có cơ sở kiểm chứng trực tiếp trên S1–S57 nên tính năng này chỉ áp dụng cho nhánh `s58`.

## Quyết Định Kiến Trúc

1. **Chỉ kiểm tra một Thành chính duy nhất**:
   - Lọc các **Thành** (bỏ qua **Doanh trại**), ưu tiên chọn Thành đầu tiên có Tửu Quán (`gid=8`/`61`) hoặc Quán Trọ (`gid=7`/`60`), fallback về Thành đầu tiên nếu không kiểm tra được danh sách công trình.
   - Chạy định kỳ mỗi 60 giây trong vòng lặp phụ trợ (`_aux_loop` trên runtime Web/CLI và bộ đếm chu kỳ phụ trợ trên Desktop) dưới khóa `gateway_city_context`, kiểm tra độc lập cả `gid=8` (Tửu Quán) lẫn `gid=7` (Quán Trọ) thay vì `if/else` như client cũ để không bỏ sót khi cả hai cùng có khách.
2. **Thông Báo Đa Kênh & Chống lặp theo phiên viếng thăm**:
   - Tái sử dụng `NotificationConfig` (**Thông Báo Đa Kênh**: Log + Web Toast/Sound + Desktop Toast/Sound + Telegram Bot với cờ `telegram_alert_general_visit`).
   - Chống lặp theo cặp khóa `(account_key, gid)` gắn với tên tướng hiện tại: chỉ phát cảnh báo 1 lần khi danh tướng bắt đầu xuất hiện, và tự xóa trạng thái ngay khi `rumor` trống hoặc đổi sang tướng khác để các lần viếng thăm sau (dù trùng tên) vẫn được báo lại.
3. **Đồng bộ Web & Desktop trên Tab Nội Chính**:
   - Bổ sung checkbox bật/tắt `notify_general_visit` (lưu trong `LogisticsProfile`, mặc định bật) cùng nhãn hiển thị danh tướng đang viếng thăm ở cả **Tab Nội Chính** Web và Desktop.
