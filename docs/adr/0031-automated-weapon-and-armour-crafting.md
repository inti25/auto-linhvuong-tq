# ADR 0031: Tự Động Hóa Chế Tạo Quân Giới Đa Thành

## Ngữ Cảnh và Vấn Đề
Để duy trì quân lực cho các chiến dịch viễn chinh quy mô lớn (Thảo Phạt, Bình Man, Gọi Man, Chiến Trường), người chơi Linh Vương luôn cần một lượng quân nhu khổng lồ gồm vũ khí, giáp trụ, chiến mã và xe công thành.
1. **Thao tác thủ công rườm rà**: Trong giao diện web, người chơi phải bấm chuyển qua từng thành, tìm thủ công ô đất của từng xưởng (Xưởng Binh Khí, Xưởng Khôi Giáp, Xưởng Ngựa), chọn chủng loại trang bị, nhập số lượng và bấm chế tạo. Thao tác này lặp đi lặp lại hàng trăm lần mỗi ngày.
2. **Quy hoạch thành chuyên môn hóa**: Trong chiến thuật thực tế, mỗi thành thường được xây dựng chuyên môn hóa: một thành chuyên rèn Cung nỗ cấp cao, một thành chuyên đúc Áo giáp, một thành chuyên nuôi Ngựa chiến. Chưa có cơ chế tự động hóa nào điều phối độc lập lịch sản xuất theo từng thành.
3. **Thiếu vắng trên Tab Tổng Quan**: Tab Tổng quan (Tab 5) hiện mới chỉ có phần kiểm tra đồn trú và Luyện sĩ khí, chưa tích hợp mắt xích đầu tiên và quan trọng nhất của chuỗi hậu cần quân sự: **Chế Tạo Quân Giới**.

## Quyết Định Kiến Trúc

### 1. Chuẩn Hóa Danh Mục Quân Giới và Nhận Diện Công Xưởng Tự Động
Trong module [`linhvuong/tasks/crafting.py`](../../linhvuong/tasks/crafting.py):
- Chuẩn hóa danh mục 68 loại quân giới nguyên bản của Linh Vương thành từ điển dữ liệu cấu trúc:
  - **Binh Khí** (`101` - `152`): Thấu giáp thương, Hậu bối đao, Hổ bí đao, v.v.
  - **Cung Nỗ** (`201` - `251`): Thiết thai cung, Bá vương nỗ, Phá phong cung, v.v.
  - **Khôi Giáp** (`301` - `350`): Ngư lân giáp, Tinh cương giáp, Minh quang chiến giáp, v.v.
  - **Chiến Mã** (`401` - `450`): Tuyệt địa mã, Phiên vũ mã, Thiết kị mã, v.v.
  - **Xe Ném Đá** (`501` - `531`): Xe ném đá loại nhẹ, vừa, nặng, hỏa diêm.
- Cơ chế tự động truy vấn danh sách công trình trong thành qua `City.ashx?id=5` để tìm vị trí ô đất (`pid`) phù hợp:
  - Binh Khí & Cung Nỗ: tìm `gid = 13` (Xưởng Binh Khí) hoặc `gid = 66` (Binh Khí Ty).
  - Khôi Giáp: tìm `gid = 14` (Xưởng Khôi Giáp) hoặc `gid = 67` (Phòng Cụ Ty).
  - Chiến Mã & Xe Ném Đá: tìm `gid = 15` (Xưởng Ngựa) hoặc `gid = 68` (Xa Mã Ty).
- Người dùng chỉ cần chọn loại quân giới, hệ thống tự động tìm đúng công xưởng để phát lệnh.

### 2. Giao Thức Lệnh Chế Tạo và Cơ Chế An Toàn Tài Nguyên
- Thực thi lệnh chế tạo qua API chuẩn của máy chủ Linh Vương: `OPT.ashx?id=38` với các tham số:
  - `count`: Số lượng sản xuất trong một mẻ (Batch size).
  - `gid`: Mã ID loại quân giới.
  - `lFaster`: Cấp độ đẩy nhanh tiến độ (mặc định `0`).
  - `pos`: Vị trí ô đất (`pid`) của xưởng tương ứng.
  - `tid`: ID thành trì đích (kèm gọi `City.ashx?id=50` để chuyển tiêu điểm thành nếu cần).
- Cơ chế an toàn (Safety Guard):
  - Khi máy chủ phản hồi `ret = 32` (Thiếu tài nguyên Gỗ/Đá/Sắt/Lúa) hoặc xưởng đang bận sản xuất mẻ trước, bot ghi nhận nhật ký và tự động chờ đến chu kỳ tiếp theo, tuyệt đối không spam request lỗi lên máy chủ.

### 3. Mô Hình Cấu Hình Đa Thành & Đa Loại Quân Giới (Multi-City & Multi-Weapon Matrix)
Trong [`linhvuong/profile.py`](../../linhvuong/profile.py) và [`linhvuong/dashboard.py`](../../linhvuong/dashboard.py):
- Mỗi thành trì được gán một cấu hình riêng biệt (`CityCraftConfig`):
  - `city_id`: ID thành trì.
  - `weapon_ids`: Danh sách các mã quân giới được chọn chế tạo đồng thời tại thành này (hỗ trợ chọn nhiều loại qua `MultiSelectDropdown` có phân nhóm danh mục: Binh khí, Cung nỗ, Khôi giáp, Chiến mã, Xe ném đá).
  - `weapon_id`: Mã quân giới đầu tiên (giữ tính tương thích ngược tuyệt đối).
  - `amount`: Số lượng chế tạo mỗi mẻ.
  - `interval`: Chu kỳ lặp lại (giây).
  - `enabled`: Trạng thái kích hoạt.
- Tích hợp trực quan tại tầng dưới của Tab Tổng quan (Tab 5):
  - Bố cục **2 cột song song**:
    - **Cột trái**: Luyện Sĩ Khí Quân Đội (Đa Thành) - Bảng chọn tướng và mức sĩ khí đích.
    - **Cột phải**: Chế Tạo Quân Giới (Đa Thành) - Dropdown đa chọn 67 loại quân giới theo nhóm danh mục, số lượng/mẻ, chu kỳ, nút Chế tạo ngay, Bắt đầu / Dừng và Treeview đa thành.
  - Tự động thực thi chế tạo tuần tự từng loại quân giới đã chọn trong chu kỳ; dừng an toàn nếu thành thiếu tài nguyên (`ret=32`).
- Toàn bộ cấu hình được lưu và nạp tự động thông qua hồ sơ tổng hợp (`auto_profile_<user>_<server>.json`).

## Hệ Quả
- **Khép kín chuỗi quân sự**: Hoàn thiện mắt xích cung ứng: Chế tạo quân giới -> Chuyển quân giới liên thành -> Chiêu mộ tân binh -> Biên chế quân ngũ -> Luyện sĩ khí -> Xuất kích viễn chinh.
- **Tiết kiệm tối đa thời gian**: Người chơi không còn phải click chuột rải rác ở hàng chục thành mỗi giờ để chế tạo vũ khí.
- **An toàn và ổn định**: Cơ chế kiểm tra điều kiện tài nguyên và giãn cách chu kỳ loại bỏ nguy cơ tài khoản bị khóa hoặc giật lag hệ thống.

