# Tự Động Hạ Cấp và Dỡ Bỏ Công Trình Thành Trì

Trong quá trình phát triển căn cứ trong Linh Vương, người chơi thường xuyên có nhu cầu tái quy hoạch lại cơ cấu ô đất (`pid`) — ví dụ: dỡ bỏ bớt Nhà Dân hoặc Xưởng Binh Khí để lấy ô đất xây thêm Binh Trường hoặc Kho. LinhVuong tích hợp khả năng tự động hạ cấp và dỡ bỏ hoàn toàn công trình về cấp 0 vào Tab 5 (Xây Dựng).

Các phương án khác đã cân nhắc:
- Tạo cột chọn chế độ "Nâng" / "Hạ" thủ công riêng biệt: Khiến bảng công trình bị chật chội, người chơi phải thiết lập qua 2 bước (vừa đổi chế độ vừa nhập cấp độ).
- Khóa bảo vệ không cho phép hạ Quan Phủ hoặc Trung Quân Đại Trướng về 0: Mặc dù an toàn nhưng làm hạn chế quyền tự do quy hoạch tối đa của người chơi chuyên nghiệp khi muốn xóa bỏ hoàn toàn một doanh trại dã ngoại hoặc tái cấu trúc phân thành.
- Chỉ cho phép Tăng tốc cho Nâng cấp, không tăng tốc khi Hạ cấp: Khiến tiến trình dỡ bỏ giải phóng ô đất bị kéo dài không cần thiết.

Quyết định:
- Nhận diện hành động thông minh dựa trên so sánh giữa Cấp Mục Tiêu (`target_level`) và Cấp Hiện Tại (`current_level`):
  - Mở rộng dải Cấp MT từ `[0..33]` (cấp 0 tương ứng dỡ bỏ hoàn toàn công trình khỏi ô đất).
  - Nếu `target_level < current_level`: Tự động gửi lệnh Hạ cấp (`OPT.ashx?id=65, type=2`).
  - Nếu `target_level > current_level`: Tự động gửi lệnh Nâng cấp (`OPT.ashx?id=65, type=1`).
  - Nếu `target_level == current_level`: Đánh dấu đã hoàn thành quy hoạch cho ô đất đó.
- Cho phép hạ cấp tự do về cấp 0 cho toàn bộ tất cả công trình (kể cả Quan Phủ và Trung Quân Đại Trướng) theo đúng yêu cầu người dùng.
- Thứ tự thực hiện các lệnh Nâng và Hạ cấp tuân thủ tuyệt đối theo thứ tự sắp xếp ưu tiên từ trên xuống dưới trong Hàng Đợi Quy Hoạch của căn cứ.
- Cơ chế Tăng tốc (Speedup) và hiệu ứng Boost 20% áp dụng đồng bộ cho cả tiến trình Nâng cấp và Hạ cấp.
- Xử lý mã phản hồi đặc thù từ server đối với hạ cấp: mã `ret=36` ("Không thể hạ cấp do đã đạt cấp tối thiểu").
