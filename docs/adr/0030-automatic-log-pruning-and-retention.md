# ADR 0030: Cắt Tỉa Nhật Ký Tự Động và Chính Sách Lưu Giữ

## Ngữ Cảnh và Vấn Đề
Khi bot Linh Vương hoạt động liên tục trong thời gian dài (treo máy nhiều ngày, nhiều tuần):
1. **Quá tải giao diện đồ họa (GUI Memory & Lag)**:
   - Các khung hiển thị văn bản (`tk.Text`) trong các tab nghiệp vụ tích tụ hàng nghìn dòng văn bản. Hàm `_append_text_buffer` trước đây đặt ngưỡng `max_lines = 1000` và cắt tỉa đơn lẻ từng dòng một (`diff = 1`). Việc liên tục xóa 1 dòng đầu tiên mỗi khi ghi dòng mới buộc bộ máy Tkinter phải tính toán lại chỉ mục vị trí (`index`) liên tục, gây tụt hiệu năng (frame drops, giật lag giao diện).
   - Riêng tab Chiến Trường (`bt_log_text`) trước đây chèn trực tiếp văn bản mà hoàn toàn không áp dụng giới hạn dòng, dẫn đến việc các trận đánh lớn kéo dài hàng trăm hiệp có thể làm phình to bộ nhớ RAM không kiểm soát.
   - Các tab Thảo Phạt, Gọi Man, Bình Man thiếu nút bấm xóa trắng nhật ký thủ công (`🗑️ Xóa`), gây bất tiện cho người dùng khi muốn dọn sạch khung nhìn.
2. **Chiếm dụng dung lượng lưu trữ ổ đĩa (Disk Storage Bloat)**:
   - Cấu hình xoay vòng tệp log trước đây trong `linhvuong/logger.py` sử dụng `max_bytes = 10MB` và `backup_count = 5` (tương đương ~50MB/tài khoản).
   - Chưa có cơ chế tự động dọn dẹp các tệp log lịch sử của các tài khoản hoặc máy chủ cũ đã ngừng sử dụng, khiến thư mục `logs/` tích lũy theo thời gian.

## Quyết Định Kiến Trúc

### 1. Cắt Tỉa Nhật Ký Giao Diện Theo Khối (GUI Batch Pruning)
Trong [`linhvuong/dashboard.py`](../../linhvuong/dashboard.py):
- Xác lập các hằng số cấu hình chuẩn:
  - `DEFAULT_MAX_LOG_LINES = 500`: Ngưỡng dòng tối đa cho các tab tác vụ thường (`tp_log_text`, `gd_log_text`, `bm_log_text`, `bld_log_text`, `logis_log_text`, `_open_log_window`).
  - `BATCH_TRIM_LINES = 100`: Số dòng cắt tỉa theo khối cho các tab tác vụ thường.
  - `COMBAT_MAX_LOG_LINES = 300`: Ngưỡng dòng tối đa cho tab Chiến Trường (`bt_log_text`).
  - `COMBAT_TRIM_LINES = 60`: Số dòng cắt tỉa theo khối cho tab Chiến Trường.
- Tái cấu trúc hàm `_append_text_buffer`:
  - Kiểm tra số lượng dòng hiện tại `line_count = int(widget.index("end-1c").split(".")[0])`.
  - Khi `line_count > max_lines`, thực hiện cắt tỉa theo khối:
    `target_lines = max(1, max_lines - trim_batch)`
    `lines_to_delete = line_count - target_lines`
    `widget.delete("1.0", f"{lines_to_delete + 1}.0")`
  - Nhờ cơ chế này, sau mỗi lần cắt tỉa, widget sẽ có khoảng trống đệm (100 dòng với tác vụ thường, 60 dòng với chiến trường) để tiếp nhận các dòng log mới tiếp theo mà **không cần thực hiện phép xóa hay tính toán lại chỉ mục nào**, giải phóng áp lực cho luồng giao diện Tkinter.
  - Tự động cuộn đến cuối dòng (`widget.see("end")`).
  - Đảm bảo an toàn đa luồng: Tự động điều phối qua `self.after(0, ...)` nếu cuộc gọi xuất phát từ luồng nền (background thread).
- Chuyển hàm `_append_bt_log` sang sử dụng `_append_text_buffer` với ngưỡng riêng của Chiến Trường (`COMBAT_MAX_LOG_LINES` và `COMBAT_TRIM_LINES`).

### 2. Bổ Sung Nút Xóa Thủ Công Trên Giao Diện
- Trang bị thêm nút bấm `🗑️ Xóa` trên thanh tiêu đề của khung nhật ký tại:
  - Tab Thảo Phạt (`_tp_clear_log`)
  - Tab Gọi Man (`_gd_clear_log`)
  - Tab Bình Man (`_bm_clear_log`)
- Đảm bảo tính nhất quán với nút xóa đã có sẵn ở cửa sổ Nhật ký Nội chính (`_open_log_window`) và tab Chiến trường (`_bt_clear_log`).

### 3. Tối Ưu Xoay Vòng và Thanh Lý Nhật Ký Ổ Đĩa
Trong [`linhvuong/logger.py`](../../linhvuong/logger.py):
- Giảm dung lượng tệp xoay vòng mặc định xuống `max_bytes = 2 * 1024 * 1024` (2MB/tệp) và `backup_count = 3` (tối đa ~6MB trên mỗi tài khoản).
- Triển khai hàm `clean_old_logs(log_dir: Optional[Path] = None, max_age_days: int = 7) -> int`:
  - Quét toàn bộ các tệp `.log` và tệp log xoay vòng trong thư mục `logs/`.
  - Kiểm tra thời điểm sửa đổi lần cuối (`mtime`). Nếu tệp đã tồn tại quá `max_age_days` (mặc định 7 ngày), tiến hành xóa an toàn.
  - Bọc khối `try/except` để không làm gián đoạn ứng dụng nếu một tệp đang bị tiến trình khác giữ khóa.
- Tự động gọi `clean_old_logs` mỗi khi `setup_logger` được thực thi lúc khởi tạo bot.

## Hệ Quả
- **Hiệu năng và độ mượt (UI Responsiveness)**: Giảm 99% số lần kích hoạt hàm xóa chỉ mục của Tkinter nhờ cơ chế cắt tỉa theo khối; chấm dứt tình trạng giật lag hoặc đơ giao diện khi chạy thời gian dài.
- **Kiểm soát bộ nhớ RAM**: Giới hạn cố định số dòng trong mọi widget nhật ký (kể cả Chiến Trường), đảm bảo mức tiêu thụ RAM luôn ổn định.
- **Tiết kiệm tài nguyên đĩa**: Hạn chế dung lượng log ở mức gọn gàng (~6MB/acc) và tự động dọn sạch các tệp log cũ sau 7 ngày mà không cần người dùng can thiệp thủ công.
- **Tiện ích người dùng**: Giao diện trực quan, rõ ràng, hỗ trợ nút xóa thủ công nhanh chóng trên từng phân hệ.

