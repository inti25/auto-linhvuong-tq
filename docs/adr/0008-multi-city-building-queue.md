# Quy Hoạch Đa Căn Cứ và Xây Dựng Nhiều Thành Đồng Thời

Người chơi trong Linh Vương thường sở hữu nhiều Thành trì và Doanh trại với mục tiêu phát triển khác nhau (ví dụ: Thành chính tập trung nâng Viện Đại Học và Quan Phủ, các phân thành tập trung sản xuất tài nguyên và khoáng sản, Doanh trại dã ngoại tập trung Binh Trường và Kho). LinhVuong bổ sung cơ chế Quy Hoạch Đa Căn Cứ, cho phép người chơi cấu hình độc lập danh sách công trình cho từng căn cứ và tự động nâng cấp nhiều căn cứ song song.

Các phương án khác đã cân nhắc:
- Giữ combobox chọn một thành đơn lẻ và chỉ nâng cấp một thành tại một thời điểm: Khiến người chơi phải tốn nhiều công sức theo dõi, chuyển thành thủ công và không tối ưu hóa được hàng đợi nâng cấp của đế chế nhiều thành.
- Mở mỗi thành trên một luồng Thread riêng: Dễ gây xung đột gateway, gửi quá nhiều gói tin đồng thời tới máy chủ dẫn đến nguy cơ bị chặn IP hoặc server từ chối kết nối.

Quyết định:
- Bố cục giao diện Tab Xây Dựng thành 3 cột trực quan:
  - Cột 1 (Trái): Bảng danh sách toàn bộ Thành & Doanh trại với cột checkbox tích chọn `☑/☐`, loại căn cứ và tên căn cứ. Kèm 2 nút tiện ích `☑ Tất cả` và `☐ Bỏ chọn`.
  - Cột 2 (Giữa): Bảng Hàng Đợi Quy Hoạch Công Trình của riêng căn cứ đang được chọn focus. Cho phép bật/tắt ô đất, tùy chỉnh Cấp MT, sắp xếp thứ tự ưu tiên và nút tải công trình thực tế.
  - Cột 3 (Phải): Khung Nhật ký Nâng Cấp Công Trình theo dõi tiến độ thi công của toàn bộ các căn cứ.
- Quản lý cấu hình trong bộ nhớ độc lập theo từng `city_id` (`self._city_building_plans: dict[int, list[BuildingPlan]]`). Khi người dùng chọn căn cứ khác, bảng công trình tự động lưu và chuyển đổi tương ứng mà không làm xáo trộn thiết lập của các căn cứ khác.
- Runner thực thi theo cơ chế xoay vòng tuần tự (Round-robin): Trong mỗi chu kỳ, lần lượt kiểm tra và gửi lệnh nâng cấp cho từng căn cứ được tích chọn `☑`, tự động kích hoạt Tăng tốc 20% và An Dân nếu cần. Nếu một căn cứ hết slot hoặc thiếu tài nguyên, Runner lập tức chuyển sang căn cứ tiếp theo.
- Tích hợp vào Hồ Sơ Cấu Hình duy nhất (`auto_profile.json`) dưới dạng `cities: {city_id: {"enabled": bool, "name": str, "plans": [...]}}`, đồng thời đảm bảo tương thích ngược hoàn hảo với định dạng `plans: [...]` cũ.
