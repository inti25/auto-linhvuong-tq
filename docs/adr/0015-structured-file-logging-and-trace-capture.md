# Ghi Log Vào File Có Cấu Trúc và Thu Thập Vết Lỗi Chạy Dài Hạn

## Bối cảnh

Khi bot tự động hóa Linh Vương vận hành liên tục trong thời gian dài (treo máy 24/7):
1. **Mất dấu vết khi xảy ra sự cố**: Trước đây, các tác vụ chạy ngầm (`BaseTaskRunner`, `ThaoPhatAutoRunner`, `BuildingAutoRunner`, v.v.) chỉ bắt ngoại lệ chung `except Exception as e` và in ra chuỗi `str(e)` lên widget `tk.Text` của giao diện. Khi xảy ra lỗi logic, lỗi parse dữ liệu máy chủ hoặc sự cố mạng, toàn bộ thông tin ngăn xếp (`traceback`), tên file và số dòng bị mất sạch, khiến việc điều tra nguyên nhân sau nhiều giờ chạy là bất khả thi.
2. **Nuốt lỗi âm thầm ở tầng mạng**: `GatewayClient.call` bắt ngoại lệ `except Exception: continue` và trả về `None` mà không ghi nhận lý do (timeout, đứt proxy, HTTP 503, phản hồi HTML thay vì JSON).
3. **Nguy cơ rò rỉ bộ nhớ giao diện**: Widget `tk.Text` trên Tkinter không có giới hạn dòng. Khi chạy qua hàng vạn chu kỳ lặp, widget tích tụ lượng lớn chuỗi ký tự gây phình RAM và làm đơ giao diện đồ họa.
4. **Không có lưu trữ bền vững**: Nhật ký chỉ tồn tại tạm thời trong bộ nhớ tiến trình; nếu ứng dụng bị đóng, mất điện hoặc crash, toàn bộ lịch sử biến mất.

## Quyết định

1. **Phân Tách Thư Mục và Xoay Vòng File Log Bền Vững (Isolated Rotating Logs)**:
   - Toàn bộ log được ghi vào thư mục `logs/`.
   - Tên file log được phân tách theo từng tài khoản và máy chủ: `logs/bot_{username}_S{server_id}.log`, đảm bảo tính độc lập tuyệt đối giữa các phiên chạy đồng thời (tuân thủ nguyên tắc cách ly của ADR-0012).
   - Áp dụng `RotatingFileHandler` với dung lượng tối đa 10 MB mỗi file và lưu trữ 5 bản sao xoay vòng (`.log.1` đến `.log.5`), bảo đảm dung lượng lưu trữ trên đĩa không vượt quá 50 MB mỗi tài khoản.

2. **Ghi Toàn Bộ Vết Ngăn Xếp Khi Gặp Ngoại Lệ (Full Traceback Capture)**:
   - Khi phát sinh ngoại lệ trong các luồng chạy ngầm, hệ thống bắt buộc ghi lại đầy đủ Exception Type, Message và Full Stack Traceback (`logger.exception` / `exc_info=True`) vào file log trên đĩa.
   - Giao diện UI chỉ hiển thị thông báo tóm tắt ngắn gọn kèm biểu tượng cảnh báo (`❌ Lỗi: ...`) để giữ không gian trực quan.

3. **Ghi Vết Mạng và Phản Hồi Gateway Có Chọn Lọc (Selective Network Tracing)**:
   - Ở mức thông thường (`INFO`), `GatewayClient` chỉ ghi log chi tiết khi phát sinh bất thường: lỗi kết nối, quá thời gian chờ (timeout), các lượt thử lại (retry), mã trạng thái HTTP khác 200, phản hồi không parse được JSON, hoặc máy chủ trả mã lỗi (`ret != 0`). Bản ghi bao gồm: endpoint, api_id, tham số gửi đi và phản hồi thô.
   - Khi bật cờ gỡ lỗi (`DEBUG`), hệ thống mới ghi vết toàn bộ mọi gói tin gửi/nhận thành công.
   - Tích hợp bộ lọc `SanitizingFilter` tự động che mờ các thông tin nhạy cảm (mật khẩu game, thông tin xác thực proxy) thành `***` trước khi xuất bản ghi ra đĩa hoặc màn hình.

4. **Bảo Vệ Bộ Nhớ Giao Diện và Phân Tuyến Log Đa Luồng (UI Decoupling & Buffer Limiting)**:
   - Giới hạn tối đa 1.000 dòng gần nhất cho mỗi ô nhật ký `tk.Text` trên UI. Khi vượt quá ngưỡng, hệ thống tự động cắt tỉa các dòng cũ nhất ở đầu.
   - Bổ sung nút bấm `"📂 Mở thư mục Log"` trên thanh Header của Dashboard để người dùng có thể mở nhanh thư mục `logs/` trong File Explorer.
   - Định tuyến log thông minh dựa theo tên logger phân hệ (`linhvuong.tasks.<name>`), vừa ghi vào file log tập trung vừa hiển thị đúng vào tab tương ứng trên giao diện.

5. **Module Cấu Hình Logging Tập Trung (Centralized Logging Module)**:
   - Xây dựng module `linhvuong/logger.py` chuẩn hóa toàn bộ việc khởi tạo handlers, formatters, sanitizers dùng chung cho cả chế độ Giao diện (`GUI`) và Dòng lệnh (`CLI`).
   - Bổ sung tham số `--debug` (hoặc `-v`) trong `linhvuong/cli.py` để thuận tiện kích hoạt mức DEBUG trong môi trường terminal.

## Hệ quả

- **Khả năng điều tra sự cố**: Khi bot gặp lỗi sau nhiều ngày chạy liên tục, người phát triển và người dùng có thể mở ngay file log để truy nguyên chính xác dòng lệnh, ngữ cảnh tham số và phản hồi của máy chủ gây ra lỗi.
- **Độ tin cậy và hiệu năng**: Bộ nhớ RAM của GUI không bị rò rỉ, đĩa cứng không bao giờ bị tràn, và bảo mật thông tin đăng nhập/proxy của người dùng được đảm bảo.
- **Tính nhất quán**: Hành vi ghi nhật ký đồng nhất trên cả 2 chế độ GUI và CLI.
