# Cường Hóa Trang Bị Và Hủy Trang Bị Trên Server 58+ (Tham Khảo ZFunction.exe)

Status: accepted

## Bối cảnh

Người chơi trên Server 58+ cần tự động hóa **Cường Hóa Trang Bị** (cấp 1→15) và **Hủy Trang Bị** hàng loạt dựa trên giao thức đã kiểm chứng (`Common.ashx?id=2/117`, `Optimization.ashx?action=equipment`, `OPT.ashx?id=154/188/17`). Trên Server 58+, endpoint cũ `Common.ashx?id=24` bị cắt ở 50 món trong khi `Optimization.ashx?action=equipment` phân trang đầy đủ theo `page`/`revision`, và chặng `OPT.ashx?id=188` (cấp 9→15 dùng **Pha Lê**) yêu cầu tài khoản đã gia nhập Liên Minh (trả `ret=27: 联盟编号不存在` nếu `ally_id=0`). Đồng thời `linhvuong/generals.py` trước đây đọc `max(1, int(row[7] or 1))` thay vì công thức 0-based `int(row[7] or 0) + 1`.

## Quyết định

1. **Lõi headless dùng chung (`linhvuong/enhance.py` + `AccountSession`) và Tab chính thứ 8 (`🔨 Cường Hóa`) trên Desktop & Web**:
   - Đặt toàn bộ logic giao thức và vòng lặp tại `linhvuong/enhance.py`, điều phối qua `AccountSession` (`linhvuong/runtime.py`) theo kiến trúc [ADR-0040](0040-headless-workspace-and-web-dashboard.md) và [ADR-0043](0043-web-desktop-parity-and-logistics-tribute.md).
   - Đặt thành Tab chính thứ 8 trên cả Desktop (`EnhanceMixin`, đồng bộ giao diện qua hàng đợi `queue.Queue`) và Web Dashboard SPA.

2. **Dùng `Optimization.ashx?action=equipment` cho kho trang bị & chuẩn hóa `parse_equipment_level`**:
   - Tái sử dụng `_fetch_all_equipment_rows(..., raise_on_captcha=True)` từ `linhvuong/generals.py` để tải đầy đủ trang bị chưa mặc (`general_id == 0`) vượt mốc 50 món và xử lý reset `ret=8102`.
   - Dùng chung `parse_equipment_level(row[7]) = max(1, int(row[7] or 0) + 1)` ở cả `linhvuong/generals.py` và `linhvuong/enhance.py`.

3. **Tách rời tham số mục tiêu, Búa Bảo Hộ và Phôi Cường Hóa xuyên suốt cấp 1→15**:
   - Tách `target_level` (2→15), `protect_from_level` (`None` hoặc `2..8`, gợi ý `7` khi đích ≥ 7) và `material_from_level` (`1..8`).
   - Tự động chuyển tiếp từ `OPT.ashx?id=154` (cấp `1→8`, dùng **Huyền Thiết** `341`, **Búa Bảo Hộ** `342`, tối đa 3 **Phôi Cường Hóa**) sang `OPT.ashx?id=188` (cấp `9→14`, dùng **Pha Lê** `354` theo bậc `5/10/20/30/40/50`, tự động bỏ qua kiểm tra/trừ Phôi).

4. **An toàn fail-closed, Giãn Cách Vi Mô, Captcha, diễn giải mã lỗi và vận hành on-demand**:
   - Dừng ngay khi hết Búa ở mốc bảo hộ, hết Phôi đã chọn hoặc thiếu Huyền Thiết/Pha Lê; khi mất mạng (`ret == -1`) hoàn trả bộ đếm phôi và đồng bộ cấp thật trước khi thử lại (tối đa 3 lần).
   - Chèn **Giãn Cách Vi Mô** `150–300ms`, dừng ngay khi gặp Captcha `110`, diễn giải rõ mã `ret=27` (`Tài khoản chưa gia nhập Liên Minh`) và `errMsg` máy chủ.
   - **Hủy Trang Bị** cấp ≥ 7 bắt buộc xác nhận tường minh ở cả UI và backend; không đưa phân hệ vào `RESUMABLE_TASKS`.

## Hệ quả

- **Tương thích hoàn toàn Server 58+**: Kho >50 món không bị cụt như `Common.ashx?id=24`, đồng bộ nhất quán giữa **Tự Động Trang Bị** và **Cường Hóa Trang Bị**.
- **Không đổi schema profile JSON**: Cấu hình cường hóa vận hành theo phiên on-demand.
