# Đồng Bộ Quân Giới Cho Võ Tướng Từ Một Tướng Mẫu Độc Lập

Status: accepted

Trong Linh Vương, cấu hình **Quân Giới** cho binh chủng của **Võ tướng** (`Common.ashx?id=12`, `OPT.ashx?id=56`: Bộ/Kỵ/Cung mỗi loại 3 ô, Xe ném đá 1 ô; cùng **Trận hình** qua `OPT.ashx?id=57`) là khái niệm tách biệt hoàn toàn với **Tự Động Trang Bị** cá nhân (`OPT.ashx?id=58`) và **Chuyển quân giới** liên thành (`OPT.ashx?id=52`). Vì `OPT.ashx?id=56` cho phép gán trước cấu hình quân giới khi tướng chưa có quân (không tiêu hao kho ngay) và việc phối hợp các ô phụ 2–3 mang tính chiến thuật chủ quan của người chơi, tự động chọn đồ theo tồn kho không phản ánh đúng đội hình mong muốn.

Chúng tôi quyết định xây dựng **Đồng Bộ Quân Giới** như một công cụ thao tác độc lập theo yêu cầu trên Tab Tổng Quan: người chơi chọn trực tiếp một **Võ tướng** làm mẫu mỗi lần chạy, tích chọn từng binh chủng (và tùy chọn **Trận hình**) rồi nhân bản sang các **Võ tướng** đích được chọn. Service đọc trước cấu hình hiện tại qua `Common.ashx?id=12` để giữ nguyên các binh chủng không tích chọn khi gửi `OPT.ashx?id=56` (và giữ nguyên tỷ lệ đánh/ngưỡng rút quân khi gửi `OPT.ashx?id=57`), không lưu vào `Profile` và không gắn hook vào **Biên Chế Quân Tự Động** hay các tác vụ Thảo Phạt, Bình Man, Gọi Man.

- **Considered Options**:
  - *Tự động chọn Quân Giới tốt nhất từ kho Thành (`Auto-Best`)*: Bị loại vì cấu hình ô 2–3 đa binh chủng phụ thuộc ý đồ người chơi và dễ lệch so với tướng chủ lực khi kho các Thành khác nhau.
  - *Lưu tướng mẫu vào Hồ Sơ và tự đồng bộ trước `OPT.ashx?id=6` (`ArmyProvisioner`)*: Bị loại để giữ **Đồng Bộ Quân Giới** đơn giản, an toàn, không can thiệp ngoài ý muốn vào Thảo Phạt, Bình Man hay Gọi Man.
- **Consequences**:
  - Không thay đổi lược đồ `Profile` (`ProfileStore`) hay logic `ArmyProvisioner`, `ThaoPhat`, `BinhMan`, `GoiDan`.
  - Hỗ trợ đồng bộ từng phần (chỉ ghi những binh chủng/trận hình được chọn và có khác biệt), bỏ qua tướng bận (`status != 0`) và chính tướng mẫu, đồng thời ghi log rõ lỗi thiếu kho (`ret=42`) hoặc thiếu quân giới chính khi đã có lính (`ret=71`).
