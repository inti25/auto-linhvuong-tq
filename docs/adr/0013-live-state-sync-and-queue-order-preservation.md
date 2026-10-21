# Tự Động Đồng Bộ Dữ Liệu Thực Tế và Bảo Toàn Thứ Tự Ưu Tiên

## Bối cảnh
Trước đây, trong các tác vụ Xây Dựng và Nghiên Cứu Viện Đại Học:
1. Khi người dùng bấm "Tải thực tế" (`_fetch_city_buildings`), giao diện duyệt lại danh sách theo thứ tự mảng trả về từ máy chủ (`City.ashx?id=5`), làm xóa sạch thứ tự ưu tiên mà người dùng đã sắp xếp bằng các nút Lên/Xuống.
2. Trong các chu kỳ thi công tự động (`BuildingTask.run_once` và `ResearchTask.run_once`), bot đã gửi yêu cầu truy vấn cấp độ thực tế (`City.ashx?id=5` và `Build.ashx?id=2`), nhưng dữ liệu này chỉ phục vụ tính toán nội bộ trong Task mà không đẩy ngược về giao diện Dashboard. Người dùng không thấy được `Cấp HT` (Cấp hiện tại) và các nhãn trạng thái nâng cấp/hạ cấp/hoàn thành thay đổi theo thời gian thực.

## Quyết định
1. **Bảo Toàn Thứ Tự Ưu Tiên (In-Place Queue Order Preservation)**:
   - Luôn sử dụng danh sách Hàng Đợi Quy Hoạch hiện hữu (trên `bld_tree` và trong bộ nhớ cache `_city_building_plans`) làm khung xương chuẩn.
   - Khi nhận dữ liệu thực tế từ máy chủ (dù nạp thủ công hay tự động theo chu kỳ), thực hiện ghép dữ liệu tại chỗ (in-place update): cập nhật trực tiếp `Cấp HT`, mã `gid`, tên công trình và nhãn màu (`upgrade`, `downgrade`, `completed`) cho từng ô đất (`pid`) và kỹ thuật (`tech_id`) mà không xóa bỏ hoặc sắp xếp lại cây Treeview.
   - Các ô đất mới phát hiện từ máy chủ mà chưa có trong quy hoạch sẽ được tự động gắn tiếp vào cuối danh sách ở trạng thái bỏ chọn (`enabled=False`) với `Cấp MT = Cấp HT`.
2. **Đồng Bộ Dữ Liệu Thực Tế Không Tốn Kém (Zero-Overhead Live State Sync)**:
   - Tận dụng ngay kết quả đọc dữ liệu từ `run_once()` thông qua callback sự kiện `on_sync_data(city_id, real_data)` chuyển tiếp an toàn qua `dashboard.after(0, ...)` lên luồng chính GUI.
   - Không tạo thêm bất kỳ HTTP request dư thừa nào ngoài vòng lặp thi công, loại bỏ hoàn toàn nguy cơ nghẽn mạng hoặc kích hoạt cơ chế phát hiện bot/Captcha từ máy chủ.
3. **Tách Biệt Thuật Toán Điều Phối và Thứ Tự Cấu Hình**:
   - Khi bật "Nâng đồng đều" (`even_upgrade`) hoặc "Nghiên cứu đồng đều" (`even_research`), thuật toán chỉ sắp xếp danh sách thi công tạm thời trong bộ nhớ của Task. Thứ tự hiển thị trên giao diện và trong Hồ Sơ Cấu Hình vẫn được bảo toàn nguyên vẹn 100%.
4. **Tối Ưu Ghi Đĩa**:
   - Dữ liệu thực tế được lưu trữ hoàn toàn trong bộ nhớ (`in-memory`) trong suốt phiên chạy và chỉ ghi ra file hồ sơ cấu hình khi người dùng bấm Lưu, khi dừng bot hoặc khi đóng ứng dụng.

## Hệ quả
- Giao diện người dùng phản hồi trực quan, tức thì sau mỗi chu kỳ nâng cấp thành công mà không gây giật lag hay mất vị trí con trỏ/cuộn chuột.
- Thứ tự ưu tiên xây dựng đa căn cứ và 29 kỹ thuật được giữ nguyên vẹn xuyên suốt quá trình vận hành tự động.
- Giảm thiểu tối đa lưu lượng mạng và tránh hao mòn I/O ổ đĩa.
