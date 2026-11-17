# Đồng Bộ Bảng Điều Khiển Web Theo Chuẩn Desktop Và Thực Thi Hậu Cần / Cống Quận

Status: accepted

## Bối cảnh

Sau [ADR-0040](0040-headless-workspace-and-web-dashboard.md) và [ADR-0041](0041-web-admin-auth-encrypted-vault-and-auto-resume.md), **Bảng Điều Khiển Web** đã vận hành ổn định trên môi trường máy chủ nhưng vẫn tồn tại nhiều sai lệch so với ứng dụng Desktop Tkinter (thiếu **Đồng Bộ Quân Giới**, **Đổi Tên Tướng**, một số bộ lọc/nút chọn nhanh/cột bảng, sai khác bố cục và lệch ánh xạ chỉ số `Mưu kế Hiệp 1`), đồng thời một số điều khiển trên Desktop chỉ là khung tĩnh chưa gắn vòng chạy thực tế (`Cống quận`, bảng lặp `Chuyển quân giới`).

## Quyết định

1. **Lấy bản Desktop làm chuẩn giao diện & nghiệp vụ game, giữ lại hạ tầng vận hành Web/Server**:
   - Bố cục, phân khu, cột bảng, thứ tự nút, thanh chọn nhanh và toàn bộ các hộp thoại chức năng của 7 tab trên Web được đồng bộ theo bản Desktop (có co giãn responsive cho màn hình nhỏ và chuẩn hóa nhãn hiển thị theo `GLOSSARY.md`).
   - Giữ nguyên toàn bộ tính năng hạ tầng đặc thù của Web/Server (`Phiên Quản Trị Web`, `Két Mật Khẩu Mã Hóa`, `auto_resume` / `auto_start`, Xem/Tải Logs Server, `Chạy tất cả` / `Dừng tất cả`, `⚡ Free` / `🔄 Test` proxy, `💾 Lưu cấu hình`, thông báo trình duyệt + âm thanh Web Audio, banner Captcha, và báo Captcha/Mất kết nối qua Telegram) cùng các điều khiển tác vụ đã hoạt động thực tế (`Slots`, `Chu kỳ` xây dựng/nghiên cứu, `Nâng đồng đều`, `Tải công trình`/`Tải kỹ thuật`, sửa `Cấp MT` trực tiếp).
   - Bỏ qua các điều khiển tĩnh chưa gắn logic ở Desktop (`Nâng nhà cấp cao nhất`).

2. **Chuẩn hóa ánh xạ `stratagem_combo_idx` dùng chung với Desktop**:
   - Sửa `AccountSession._build_combat_config()` và Web UI từ mảng `[0, 92, 93, 94, 95]` về đúng thứ tự của Desktop (`0. Không dùng`, `93. Phản khách vi chủ`, `95. Cầm tặc cầm vương`, `94. Quan môn tróc tặc`), bảo đảm **Hồ Sơ Cấu Hình** đồng nhất giữa Desktop và Web.

3. **Mở rộng `LogisticsProfile` và quy tắc dừng khi thiếu quân cho `Chuyển quân giới` & `Cống quận`**:
   - Bổ sung danh sách hàng đợi `transfer_orders` và `transfer_interval` vào `LogisticsProfile` để bảng **Chuyển quân giới** chạy lặp lại thực tế trong tác vụ nền (hỗ trợ `auto_resume` và kèm nút chuyển ngay một lần). Khi phát hiện **Thành** xuất phát không đủ **Quân Giới** cho bất kỳ lệnh nào trong lượt, vòng lặp **dừng ngay** thay vì bỏ qua chờ lượt sau nhằm tránh lặp lỗi/hao tổn tài nguyên khi nguồn cung đã cạn.
   - Bổ sung `tribute_enabled` và `tribute_building_gid` (`1` = Quan Phủ, `2` = Tường Thành) để **Cống quận** tự động chạy tối đa 1 lần/ngày trên các **Thành** đang bật (bỏ qua **Doanh trại**), kèm nút thực thi ngay cho Thành đang chọn.

## Các phương án đã cân nhắc

- **Giữ bảng `Chuyển quân giới` chỉ là UI tĩnh như Desktop hoặc bỏ hẳn để chỉ giữ nút chuyển 1 lần**: Bị từ chối vì người dùng cần khả năng điều chuyển định kỳ thật trên VPS mà vẫn giữ trải nghiệm quen thuộc từ Desktop.
- **Tiếp tục bỏ qua lệnh thiếu quân và giữ vòng lặp chạy tiếp**: Bị từ chối theo yêu cầu vận hành; khi nguồn xuất phát đã thiếu quân, dừng vòng lặp ngay để người dùng chủ động bổ sung hoặc điều phối lại.

## Hệ quả

- **Hồ Sơ Cấu Hình** (`auto_profile_{user}_{server}.json`) vẫn tương thích ngược hoàn toàn với bản Desktop (các trường mới trên `LogisticsProfile` đều có giá trị mặc định an toàn).
- Toàn bộ nghiệp vụ mới (**Đồng Bộ Quân Giới**, **Đổi Tên Tướng**, vòng lặp **Chuyển quân giới**, **Cống quận**) được đặt trong `AccountSession` (`linhvuong/runtime.py`) và API FastAPI (`linhvuong/web/app.py`) theo đúng kiến trúc một lõi điều phối của [ADR-0040](0040-headless-workspace-and-web-dashboard.md).
