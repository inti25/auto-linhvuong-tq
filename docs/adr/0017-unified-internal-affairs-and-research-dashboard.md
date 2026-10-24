# Quy Hoạch Giao Diện Hợp Nhất Nội Chính & Nghiên Cứu 3 Cột

## Bối cảnh

Trong kiến trúc ban đầu của Bot:
1. **Chia cắt các tính năng nội chính**: Tab Xây Dựng (Tab 5) và Tab Đại Học & Hậu Cần (Tab 6) nằm riêng biệt. Người chơi phải chuyển đổi qua lại liên tục giữa các tab để vừa theo dõi xây nhà, vừa nghiên cứu kỹ thuật và điều phối tài nguyên/quân giới.
2. **Khó kiểm soát tài nguyên đa thành**: Tính năng mở rương tài nguyên trước đây chỉ kích hoạt bị động khi nâng cấp công trình thiếu tài nguyên (`ret=32/37`), chưa hỗ trợ chủ động duy trì ngưỡng tài nguyên (Vàng, Gỗ, Sắt, Đá, Thực) theo % trên nhiều thành khác nhau.
3. **Thiếu thông tin trực quan về đặc quyền DS Kiến Trúc**: Hiệu ứng mở rộng 3 hàng đợi thi công (`OPT.ashx?id=69, type=3`) không hiển thị thời gian còn lại (`plus_finish`), khiến người chơi không biết bùa xây dựng khi nào hết hạn để duy trì.
4. **Thứ tự Tab chưa tối ưu**: Tab Tổng Quan nằm ở đầu nhưng người dùng chủ yếu thao tác điều khiển nội chính và viễn chinh, cần ưu tiên Tab Nội Chính & Nghiên Cứu lên đầu.

## Quyết định

1. **Tái Cấu Trúc Hệ Thống Tab Notebook**:
   - Gộp Tab Xây Dựng và Tab Đại Học & Hậu Cần thành một Tab hợp nhất quy mô lớn: **`🏛️ Nội Chính & Nghiên Cứu`**.
   - Chuyển `🏛️ Nội Chính & Nghiên Cứu` lên vị trí **Tab 1** mặc định.
   - Thứ tự mới của 5 Tab trên Notebook:
     1. `🏛️ Nội Chính & Nghiên Cứu`
     2. `⚔️ Thảo Phạt`
     3. `🏕️ Bình Man` (tách riêng phần Di trại để quy hoạch độc lập sau)
     4. `🧛 Vong Linh`
     5. `🏰 Tổng quan`

2. **Bố Cục 3 Cột Theo Chuẩn ZBuild / AutoLV**:
   - **Cột 1 (Điều khiển chung & Danh sách thành)**:
     - Các nút chức năng chính: `Làm Mới`, `Xem Log`.
     - 3 nút trạng thái dạng công tắc bật/tắt (Toggle buttons): `Xây`, `Nghiên Cứu`, `Tài Nguyên`.
     - Bộ nút chọn nhanh: `Chọn`, `Bỏ Chọn`, `Chọn Tất Cả`, `Bỏ Tất Cả`, `★ Chọn NC`, `✖ Bỏ NC`.
     - Bảng **Danh sách thành**: Cột `Thành`, `Chọn` (tham gia xây dựng), `Tài nguyên` (giám sát bù tài nguyên theo ngưỡng), `NC` (chỉ định thành nghiên cứu).
     - Khung **Tăng tốc xây dựng**: Tự động dùng đạo cụ tăng tốc (Ngân bảo/Lệnh bài) khi thời gian thi công dưới ngưỡng giờ cài đặt.
   - **Cột 2 (Quản lý nhà & Kỹ thuật nghiên cứu)**:
     - **Quản lý nhà**:
       - Điều khiển: `Cấp mục tiêu: [ N ]`, `[Nâng]`, `[Hạ]`, `[ ↑ ]`, `[ ↓ ]` (đổi thứ tự ưu tiên nhóm), Checkbox `Nâng nhà cấp cao nhất`.
       - Bảng Treeview công trình: Kế thừa mô hình phân cấp dạng cây (ADR-0016), mặc định ở trạng thái thu gọn (collapsed) hiển thị tóm tắt `Nhà | Cấp | Chạy`. Khi click đúp có thể mở rộng xem từng ô `pid`.
     - **Nâng cấp kỹ thuật**:
       - Điều khiển: `Cấp mục tiêu: [ N ]`, `[OK]`, `[ ↑ ]`, `[ ↓ ]`.
       - Checkbox `Mặc Tử (đến dưới 24h)` và Checkbox `Nâng đồng đều`.
       - Bảng danh sách kỹ thuật: `Kỹ Thuật`, `Cấp`, `Chạy`.
   - **Cột 3 (Ngưỡng tài nguyên, Phụ trợ & Chuyển quân giới)**:
     - **Thiết lập ngưỡng tài nguyên và rương**:
       - Cài đặt ngưỡng: Vàng, % Gỗ, % Sắt, % Đá, % Thực.
       - Lựa chọn loại Rương Vàng và Rương Tài Nguyên tự động cắn mở.
       - Nút `[Áp Dụng Thiết Lập]`.
       - Tích hợp 2 chế độ: Mở khi thiếu lúc xây dựng (bị động) và Mở theo ngưỡng định kỳ (chủ động qua nút `Tài Nguyên`).
     - **Chức năng phụ trợ**:
       - `Thưởng hàng ngày` (nhận điểm danh chuyên cần).
       - `Tự an ủi` (An dân khi sĩ khí < 90% hoặc dân nộ > 0).
       - `DS kiến trúc` (tự động kích hoạt duy trì 3 hàng đợi thi công) kèm nhãn hiển thị thời gian còn lại từ `plus_finish` (Common.ashx?id=77).
       - `Cống quận` (cống nạp cho Quan Phủ).
     - **Chuyển Quân Giới**:
       - Thiết lập tuyến vận chuyển: Từ thành -> Đến thành, Loại quân giới, Số lượng, Chu kỳ lặp lại (giây).
       - Nút `Add` và `Xóa`, bảng danh sách các lệnh vận chuyển.
     - **Hàng nút đáy**: `[Re-Login]`, `[💾 Lưu]` và `[📂 Load]` cấu hình tổng hợp.

3. **Tách Rời Di Trại Ra Khỏi Tab 4**:
   - Loại bỏ tính năng Di trại khỏi Tab 4 và không đưa vào Cột 1, giữ lại để thiết kế thành module độc lập kết hợp với Bình Man trong các phiên bản tiếp theo.

## Hệ quả

- Người dùng quản lý trọn vẹn toàn bộ hoạt động nội chính của đế chế (xây thành, nghiên cứu, cân đối khoáng sản, quân giới) trên một màn hình duy nhất mà không cần chuyển tab.
- Cơ chế giám sát tài nguyên chủ động giúp các thành luôn duy trì đủ khoáng sản và vàng cho mọi hoạt động mà không lo bị kẹt thiếu tài nguyên.
- Trực quan hóa chính xác thời hạn của hiệu ứng DS Kiến Trúc và tự động gia hạn 3 slot xây dựng.
- Hệ thống Tab được sắp xếp logic theo thứ tự tần suất sử dụng thực tế của người chơi.
