# Cường Hóa Trang Bị Và Hủy Trang Bị Đồng Bộ Desktop – Web (Tham Khảo ZFunction.exe)

Status: accepted

## Bối cảnh

Người chơi cần tự động hóa việc **Cường Hóa Trang Bị** (cấp 1→15) và **Hủy Trang Bị** hàng loạt dựa trên giao thức thực tế được phân tích từ `ZFunction.exe` (`Common.ashx?id=2/24/117`, `OPT.ashx?id=154/188/17`). Triển khai gốc trong `ZFunction.exe` gắn chặt logic nghiệp vụ vào Tkinter, gộp cứng cấp đích và mốc búa thành chuỗi tĩnh (`"5 búa 7"`), không hỗ trợ chuyển tiếp liền mạch qua mốc cấp 9, không bắt Captcha `110`, không có **Giãn Cách Vi Mô**, và hiểu đúng cấp 0-based `row[7] + 1` trong khi `linhvuong/generals.py` trước đây đọc `max(1, row[7])`.

## Quyết định

1. **Lõi headless dùng chung (`linhvuong/enhance.py` + `AccountSession`) và Tab chính thứ 8 (`🔨 Cường Hóa`) trên cả Desktop & Web**:
   - Đặt toàn bộ logic giao thức và vòng lặp cường hóa/hủy đồ ở `linhvuong/enhance.py`, điều phối qua `AccountSession` (`linhvuong/runtime.py`) theo kiến trúc [ADR-0038](0038-headless-workspace-and-web-dashboard.md) và [ADR-0042](0042-web-desktop-parity-and-logistics-tribute.md).
   - Đặt làm Tab chính thứ 8 thay vì modal popup để đủ không gian cho 2 bảng Võ/Văn, bộ lọc, 3 ô Phôi Cường Hóa, tồn kho, thanh tiến độ và nhật ký trực tiếp.

2. **Tách rời tham số mục tiêu, kẹp Búa Bảo Hộ và Phôi Cường Hóa xuyên suốt cấp 1→15**:
   - Tách thành `target_level` (2→15), `protect_from_level` (`None` hoặc `2..8`, gợi ý mặc định `7` khi đích ≥ 7) và `material_from_level` (`1..8`).
   - Tự động nối liền hai giai đoạn: `OPT.ashx?id=154` cho cấp `1→8` (dùng **Huyền Thiết** `341`, **Búa Bảo Hộ** `342`, tối đa 3 **Phôi Cường Hóa**) và `OPT.ashx?id=188` cho cấp `9→14` (chỉ dùng **Pha Lê** `354` theo bậc `5/10/20/30/40/50`, tự động bỏ qua kiểm tra/trừ Phôi).

3. **Chuẩn hóa công thức cấp trang bị `int(row[7]) + 1`**:
   - Dùng chung hàm `parse_equipment_level(row[7])` ở cả `linhvuong/generals.py` và `linhvuong/enhance.py` để cấp hiển thị nhất quán tuyệt đối giữa **Tự Động Trang Bị** và **Cường Hóa Trang Bị**.

4. **Bảo vệ fail-closed, Giãn Cách Vi Mô, Captcha và vận hành on-demand**:
   - Dừng ngay lập tức khi hết **Búa Bảo Hộ** ở mốc cần bảo hộ (không ép trần gây tụt cấp), hết **Phôi Cường Hóa** đã chọn, hoặc cạn **Huyền Thiết**/**Pha Lê**. Khi lỗi mạng (`ret == -1`), đồng bộ lại cấp thực tế từ `Common.ashx?id=24` trước khi thử lại (tối đa 3 lần liên tiếp).
   - Chèn **Giãn Cách Vi Mô** `150–300ms` giữa mỗi lượt gọi `OPT.ashx`; gặp `ret == 110` dừng ngay và kích hoạt luồng cảnh báo Captcha + **Thông Báo Đa Kênh**.
   - Chọn món tiếp theo khi ép hàng loạt chỉ lấy món chưa mặc cùng loại còn `cấp < cấp mục tiêu` (ưu tiên đúng cấp ban đầu), và **Hủy Trang Bị** cấp ≥ 7 bắt buộc xác nhận tường minh cả ở UI lẫn backend.
   - Xếp cả **Cường Hóa Trang Bị** và **Hủy Trang Bị** vào nhóm tác vụ **on-demand**, không đưa vào `RESUMABLE_TASKS` / `auto_resume` để tránh tự động đốt nguyên liệu hay hủy đồ khi khởi động lại máy chủ.

## Hệ quả

- **Tương thích ngược**: `auto_profile_{user}_{server}.json` không bị thay đổi cấu trúc.
- **Nhất quán hiển thị**: Trang bị cấp 1 (`row[7]=0`) và cấp 2 (`row[7]=1`) được phân biệt chính xác trên toàn hệ thống thay vì gộp chung `Lv.1`.
