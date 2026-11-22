# Tự Động Mua Và Bán Tài Nguyên Qua Chợ

Status: accepted

## Bối cảnh

Trong giai đoạn phát triển thành trì hoặc vận hành dài hạn, một số Thành dư thừa lớn khoáng sản (chạm ngưỡng 90%–100% sức chứa kho gây lãng phí sản lượng) trong khi các Thành khác lại thiếu hụt tài nguyên hoặc cần giữ lại Rương Tài Nguyên. Máy chủ Linh Vương cung cấp sàn giao dịch tài nguyên tại **Chợ** (`gid=11`) và **Tập Thị** (`gid=64`, ở Thiên Thành/Châu Thành) theo đơn vị **Đản** (`1 đản = 1.000` tài nguyên):

- Đọc bảng chào bán: `Common.ashx?id=38` (`stab=1`, `type=1..4`, `tid`), tuy nhiên máy chủ vẫn trả bảng chào bán ngay cả khi truyền `tid` của Thành chưa xây Chợ và chỉ chặn khi gửi lệnh giao dịch (`ret=232`).
- Đọc giá trung bình hôm qua: `OPT.ashx?id=29` (`type=1..4`) trả số nguyên thô (không phải JSON object).
- Mua ngay bằng Vàng của Thành: `OPT.ashx?id=9` (cộng tài nguyên và trừ Vàng tức thì).
- **Treo Đơn Bán** lên sàn: `OPT.ashx?id=49` (trừ tài nguyên khỏi kho ngay khi treo, không thể hủy đơn, giới hạn số đơn treo tối đa `ret=249` và giới hạn biên độ giá `ret=74` theo giá TB hôm qua và khung giờ: `±10%` từ 8h–24h, `±5%` từ 0h–8h giờ máy chủ UTC+8, kẹp trong `[50%..200%]` giá gốc).

## Quyết định

1. **Module lõi dùng chung (`linhvuong/market.py`) & phạm vi áp dụng**:
   - Đóng gói toàn bộ logic giao dịch Chợ và chu kỳ giám sát tài nguyên của một Thành (`process_city_resource_cycle`) trong `linhvuong/market.py` để cả Desktop Tkinter và Web/Headless (`AccountSession`) dùng chung một hành vi.
   - Tính năng **Ưu Tiên Mua Chợ** và **Treo Đơn Bán** chỉ áp dụng trong luồng Giám sát tài nguyên định kỳ (`Tài Nguyên` / `resource_monitor`). Luồng `Mở khi thiếu lúc xây dựng` trong `BuildingTask` giữ nguyên chiến lược mở rương phản xạ theo [ADR-0019](0019-deferred-box-opening-and-default-uncheck-queue.md) vì mã lỗi `ret=32/37` không chỉ rõ loại tài nguyên thiếu.

2. **Nhận diện Thành có Chợ và kiểm tra lười**:
   - Xác định Thành có Chợ bằng `City.ashx?id=5` (`gid in {11, 64}` và `level > 0`) qua `CityMarketCache` có TTL và tự vô hiệu hóa sang `False` nếu lệnh mua/bán trả về `ret=232`; Doanh trại (`id <= 0`) luôn trả về `False`.
   - Chỉ truy vấn `City.ashx?id=5` khi thực sự có nhu cầu bán hoặc nhu cầu mua Chợ, không phát sinh thêm request khi hai tùy chọn Chợ đều tắt.
   - Các Căn Cứ không có Chợ bỏ qua bước mua Chợ và fallback về mở Rương Tài Nguyên mặc định.

3. **Thứ tự thực thi trong 1 chu kỳ (Bán dư → Vàng → Mua Chợ → Fallback Rương)**:
   - **Bước 1 (Bán dư)**: Tại Thành có Chợ, nếu bật **Treo Đơn Bán** khi vượt **Ngưỡng Bán Tài Nguyên** (`> S%`, hoặc `>= 100%` khi `S == 100`), bán gộp **1 đơn duy nhất** đưa tồn kho về `max(S - 10%, ngưỡng_mua)` nhằm giải phóng sức chứa kho trước và tránh spam đơn nhỏ gây `ret=249`. Tự bỏ qua bán đối với loại tài nguyên có `ngưỡng_mua >= ngưỡng_bán` để ngăn vòng lặp mua–bán lỗ thuế. Không tự động sửa giá đơn treo cũ (`OPT.ashx?id=68`).
   - **Bước 2 (Vàng)**: Nếu Vàng dưới `gold_threshold`, mở 1 Rương Vàng trước và đọc lại số Vàng mới để sẵn sàng cho bước mua Chợ.
   - **Bước 3 (Bù thiếu & Fallback)**: Nếu bật **Ưu Tiên Mua Chợ** và Thành có Chợ, gom mua lần lượt các loại đang thiếu (`>= 1 đản`) từ đơn giá rẻ nhất trong top 10 (không vượt sức chứa kho). Chỉ khi sau khi thử mua Chợ vẫn còn loại thiếu (sàn hết hàng hoặc thiếu Vàng) hoặc Căn Cứ không có Chợ mới fallback mở đúng **1 Rương Tài Nguyên**.

4. **Định giá treo bán an toàn**:
   - Lấy giá rẻ nhất đang rao trên sàn (`Common.ashx?id=38`), hoặc giá TB hôm qua (`OPT.ashx?id=29`) nếu sàn trống, sau đó kẹp vào biên độ giá hợp lệ hiện hành; nếu máy chủ vẫn trả `ret=74`, thử lại 1 lần ở đúng giá TB hôm qua.

## Các phương án đã cân nhắc

- **Bán vừa đúng về ngưỡng `S%` thay vì lùi về `max(S - 10%, ngưỡng_mua)`**: Bị từ chối vì sản lượng khai thác mỗi 30 giây sẽ đẩy kho vượt lại `S%` liên tục, tạo hàng loạt đơn nhỏ và nhanh chóng đụng giới hạn số đơn treo `ret=249`.
- **Chỉ dựa vào phản hồi `Common.ashx?id=38` để biết Thành có Chợ hay không**: Bị từ chối sau khi kiểm chứng thực tế trên Server 57 cho thấy `Common.ashx?id=38` vẫn trả danh sách bán với Thành không có Chợ.
- **Tự động hạ giá đơn cũ qua `OPT.ashx?id=68` khi gặp `ret=249`**: Bị từ chối để tránh sửa nhầm đơn người chơi chủ động treo giá cao thủ công.

## Hệ quả

- `ResourceProfile` bổ sung `prefer_market_buy`, `auto_sell_resource`, `sell_threshold_pct` (mặc định `False`, `False`, `"90"`), tương thích ngược hoàn toàn với **Hồ Sơ Cấu Hình** hiện có.
- Nhãn nút trên **Bảng Điều Khiển Web** được chuẩn hóa thành `Tài Nguyên` đồng bộ với Desktop Tkinter để phản ánh đúng cả hai cơ chế Chợ và Rương.
