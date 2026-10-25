# Luyện Sĩ Khí Đồng Thời Đa Thành Cho Tướng Có Quân Đội

## Ngữ Cảnh và Vấn Đề
Trước đây, người chơi phải truy cập từng thành hoặc doanh trại, chọn từng võ tướng rồi nâng sĩ khí từng nhịp 10 điểm thủ công, hoặc phụ thuộc vào chu trình kiểm tra sĩ khí trước khi xuất kích của phân hệ Thảo Phạt. Khi người chơi chuẩn bị chiến dịch lớn hoặc tổng động viên quân đội đóng rải rác trên nhiều thành trì và doanh trại dã ngoại, quy trình này gây tốn nhiều thời gian và thao tác lặp lại.

Đồng thời, danh sách tướng hiển thị ở Tab Tổng quan chỉ hiển thị theo từng thành đơn lẻ, không hỗ trợ xem gộp toàn bộ lực lượng có quân ngũ hoặc điều phối tác vụ đồng thời trên quy mô toàn quân.

## Quyết Định Kiến Trúc

1. **Phân hệ Luyện Sĩ Khí Độc Lập (`MoraleTrainer`) tại `linhvuong/tasks/morale.py`**:
   - Tách biệt hoàn toàn logic luyện sĩ khí ra khỏi Tkinter, tuân thủ nguyên lý deep module:
     - `train_general_morale(city_id, general_id, current_morale, target_morale=100, stop_event, on_step)`:
       * Tự động kiểm tra thông tin thực tế từ `Common.ashx?id=76` gồm sĩ khí hiện tại và `upgrading_time` (thời gian đếm ngược lượt nâng đang chạy dở).
       * **Xử lý tướng đang luyện dở**: Nếu `upgrading_time > 0`, bot tự động chuyển sang trạng thái chờ, hiển thị đếm ngược thời gian thực trên giao diện, đợi lượt luyện dở hoàn tất rồi đọc lại sĩ khí cập nhật từ máy chủ.
       * Tiếp tục lặp các nhịp tăng tối đa 10 điểm qua API `OPT.ashx?id=47` (`lAddPoint`, `lGeneralID`, `tid`), chờ đếm ngược giữa các đợt cho đến khi chạm đích `target_morale` hoặc bị hủy bởi `stop_event`.
     - `train_multiple_generals(targets, target_morale=100, max_workers=3, stop_event, on_progress, on_step)`: Điều phối song song qua `ThreadPoolExecutor` (giới hạn 3-4 workers để vừa đạt tốc độ cao vừa tránh nghẽn socket hoặc kích hoạt rate-limit máy chủ), báo cáo tiến độ và đếm ngược từng tướng thread-safe qua callbacks `on_progress` và `on_step`.

2. **Giao Diện Bố Cục Hai Tầng tại Tab Tổng Quan (`linhvuong/dashboard.py`)**:
   - **Tầng trên**: Bảo toàn nguyên vẹn 3 cột Thành & Doanh trại, Tướng đồn trú, Chi tiết biên chế.
   - **Tầng dưới**: Bổ sung khung điều khiển `⚔️ Luyện Sĩ Khí Quân Đội (Đa Thành)` gồm:
     - Thanh điều khiển: Combobox lọc theo căn cứ ("🌟 Tất cả các thành" hoặc từng căn cứ cụ thể), nút "☑ Chọn tất cả", nút "☐ Bỏ chọn", Combobox "Sĩ khí đích" (100, 95, 90, 85), nút "⚔️ Luyện Sĩ Khí", nút "⏹️ Dừng", và nhãn tiến độ.
     - Bảng Treeview chuyên biệt hiển thị các tướng có quân ngũ (`army.total > 0`), gồm các cột: Chọn (`☑`/`☐`), Tên tướng, Thành đồn trú, Sĩ khí hiện tại (`x/100`), Quân số, Chi tiết binh chủng (B/K/C), và Trạng thái luyện thời gian thực.

3. **Cơ Chế Lọc Tướng và Điều Hướng Trực Quan**:
   - Bảng tướng chỉ hiển thị các tướng sở hữu quân đội (`army.total > 0`), loại bỏ văn quan và tướng nhàn rỗi không có quân.
   - Khi nạp ban đầu, toàn bộ tướng có quân đội được tự động đánh dấu chọn sẵn giúp người chơi có thể kích hoạt ngay chỉ với 1 cú nhấp chuột.
   - Hỗ trợ thao tác click chuột hoặc bấm phím Cách (`Space`) để bật/tắt chọn tướng linh hoạt.

4. **An Toàn Đa Luồng & Thu Dọn Tài Nguyên**:
   - Toàn bộ giao tiếp giữa luồng worker và giao diện Tkinter được truyền qua `self.after(0, ...)` có bọc ngoại lệ `(RuntimeError, tk.TclError)`.
   - Quản lý cờ dừng `threading.Event` độc lập và tự động kích hoạt `stop()` trong hàm `destroy()` của `Dashboard` khi người dùng đóng ứng dụng.

## Hệ Quả
- **Tiện dụng & Hiệu quả**: Rút ngắn thời gian chuẩn bị sĩ khí cho toàn quân từ vài phút xuống vài giây.
- **Tính độc lập & Khả năng kiểm thử (Testability)**:
  - `MoraleTrainer` có thể kiểm thử 100% độc lập mà không cần môi trường đồ họa (`tests/test_morale.py`).
  - Toàn bộ hành vi GUI (render, lọc theo thành, chọn/bỏ chọn, chạy đa luồng mock) được kiểm thử chặt chẽ tại `tests/test_dashboard_gui.py`.
