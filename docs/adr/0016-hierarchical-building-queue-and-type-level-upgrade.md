# Quy Hoạch Công Trình Phân Cấp Dạng Cây Và Nâng Đồng Đều Theo Loại

## Bối cảnh

Trong các phiên bản trước:
1. **Hàng đợi phẳng gây khó khăn khi thao tác số lượng lớn**: Giao diện hiển thị phẳng toàn bộ 32 ô đất (`pid 1` đến `pid 32`). Khi người chơi muốn ưu tiên các loại công trình có nhiều ô đất (như Nhà Dân có 10 ô, Ruộng có nhiều ô), họ phải dùng nút Lên/Xuống di chuyển thủ công từng ô riêng lẻ rất mất thời gian.
2. **Cơ chế Nâng Đồng Đều cũ thiếu phân tầng**: Chế độ `even_upgrade` cũ so sánh cấp độ giữa tất cả các công trình trong toàn thành, làm xáo trộn thứ tự ưu tiên chiến lược (ví dụ: Quan Phủ và Kho bị trì hoãn nếu có một ô Nhà Dân cấp thấp hơn).
3. **Ô đất mới xây không tự động kết nạp**: Khi nâng cấp Quan Phủ mở thêm ô đất mới hoặc khi người chơi xây mới một công trình, ô đất đó được nạp vào ở trạng thái bỏ chọn (`enabled=False`), buộc người chơi phải tự tìm và cấu hình lại.

## Quyết định

1. **Hiển Thị Phân Cấp Dạng Cây Theo Loại Công Trình (Hierarchical Treeview by Type)**:
   - Các công trình đơn chiếc (chỉ có 1 ô trong thành như Quan Phủ, Tường Thành, Đại Học Điện, Chợ...): Hiển thị trực tiếp ở dòng gốc mà không có nhánh con, hiển thị đầy đủ thông số ô đất, cấp hiện tại và mục tiêu.
   - Các công trình có nhiều ô đất (Nhà Dân, Kho, Ruộng, Mỏ...): Dòng cha đại diện cho Loại công trình (`民房 - Nhà Dân (x ô)`), hiển thị dải cấp độ tóm tắt `min - max`, cấp mục tiêu chung và trạng thái chọn (`☑` chọn tất cả, `▣` chọn lẻ, `☐` bỏ chọn). Các dòng con thụt lề biểu diễn từng ô đất cụ thể `Ô {pid}`.

2. **Thứ Tự Ưu Tiên Theo Loại Công Trình (Type-Level Priority Queue)**:
   - Thứ tự ưu tiên thi công được quyết định theo vị trí của các Loại công trình từ trên xuống dưới trên cây.
   - Nút **"⬆️ Lên"** và **"⬇️ Xuống"** tác động trực tiếp lên dòng Loại công trình (dòng cha), di chuyển toàn bộ nhóm công trình đó trong danh sách ưu tiên.
   - Bot thi công hoàn tất mục tiêu của Loại công trình đứng trước rồi mới chuyển sang Loại công trình đứng sau.

3. **Thuật Toán Nâng Đồng Đều Nội Bộ Loại & Chọn Lẻ (Intra-Type Even Upgrade)**:
   - Khi thi công một nhóm Loại công trình có nhiều ô được chọn, bot luôn tự động ưu tiên nâng các ô có cấp độ hiện tại thấp nhất trong nhóm đó lên trước (nâng cân bằng dàn trải).
   - Cho phép chọn lẻ: Người chơi có thể bỏ chọn riêng từng ô con hoặc đặt Cấp Mục Tiêu riêng cho từng ô con. Bot chỉ thi công các ô được bật chọn và dừng lại khi từng ô đạt đúng cấp mục tiêu riêng lẻ.

4. **Tự Động Kế Thừa Quy Hoạch Nhóm (Auto-Inherit on New Plots)**:
   - Khi phát hiện ô đất mới cùng loại (qua nút *"Tải thực tế"* hoặc chu kỳ đồng bộ `run_once`):
     - Nếu nhóm công trình đó đang ở trạng thái **chọn tất cả** (`all` / `☑`): Ô đất mới sẽ tự động được bật chọn (`enabled=True`) và tự động kế thừa Cấp Mục Tiêu chung của nhóm để lập tức tham gia vào chu trình nâng đồng đều.
     - Nếu nhóm công trình đó đang ở trạng thái **chọn lẻ** (`▣`) hoặc **bỏ chọn** (`☐`): Ô đất mới sẽ ở trạng thái bỏ chọn (`enabled=False`) với `Cấp MT = Cấp HT`.

5. **Bảo Toàn Tương Thích Ngược Cấu Hình**:
   - Dữ liệu lưu trữ trong `build_plans.json` và `auto_profile_{username}_{server_id}.json` vẫn duy trì mảng phẳng `plans: [{pid, gid, name, target_level, enabled}, ...]`, được sắp xếp tuần tự theo thứ tự nhóm loại công trình.
   - Đảm bảo tương thích ngược 100% với giao diện dòng lệnh (CLI), các bản sao lưu cũ và test suite.

6. **Gỡ Bỏ Checkbox Nâng Đồng Đều Toàn Cục Ở Xây Dựng**:
   - Do cơ chế quy hoạch mới đã tự động nâng đồng đều nội bộ loại (`_order_plans_by_type_even`), nút kiểm `⚖️ Nâng đồng đều` trên giao diện Tab Xây Dựng được gỡ bỏ hoàn toàn để tránh xáo trộn thứ tự ưu tiên vĩ mô giữa các loại công trình.
   - Nút `⚖️ Nâng đồng đều` tại Tab Viện Đại Học vẫn được giữ nguyên độc lập.

## Hệ quả

- Người dùng dễ dàng quy hoạch thành phố ở tầm vĩ mô (Quan Phủ > Kho > Nhà Dân) chỉ với vài thao tác.
- Toàn bộ các công trình giống nhau tự động phát triển cân bằng mà không cần can thiệp thủ công.
- Loại bỏ hoàn toàn checkbox thừa trên giao diện Xây Dựng, giảm thiểu cấu hình nhầm lẫn.
- Các ô đất mới xây tự động hòa nhập vào kế hoạch phát triển của thành phố mà không phát sinh thêm bước cấu hình rườm rà.
