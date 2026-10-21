# Hợp nhất Thành - Doanh Trại và Hàng Đợi Ưu Tiên Tương Tác Trực Quan

LinhVuong hợp nhất việc quản lý cả Thành (ID dương) và Doanh trại (ID âm hoặc camp_id) trong `Roster`, đồng thời chuyển đổi mô hình nạp file cấu hình tĩnh sang Hàng Đợi Ưu Tiên tương tác trực tiếp (Interactive Priority Queue) với checkbox chọn và nút đẩy thứ tự ưu tiên trên giao diện GUI.

Các phương án khác đã cân nhắc:
- Tách riêng màn hình quản lý Thành và Doanh trại: Khiến giao diện bị phân mảnh, người chơi phải chuyển qua lại giữa nhiều tab chỉ để xem tướng hoặc điều chuyển binh lực giữa thành và trại.
- Chỉ đọc kế hoạch nâng cấp và kỹ thuật từ file JSON tĩnh: Buộc người dùng phải tra cứu thủ công mã `pid`, `gid`, `tech_id` để gõ vào file JSON, trải nghiệm kém trực quan so với cơ chế chọn trực tiếp qua bảng kiểm (checkbox) và nút dịch chuyển ưu tiên (Up/Down) của ZBuild.
- Cho phép cả Văn quan xuất kích Thảo phạt: Vi phạm quy tắc chiến đấu của game Linh Vương, dẫn đến việc server phản hồi lỗi hoặc gây lãng phí thể lực của mưu sĩ.
