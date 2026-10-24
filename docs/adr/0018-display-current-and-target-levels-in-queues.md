# Hiển Thị Cấp Hiện Tại (Cấp HT) và Cấp Mục Tiêu (Cấp MT) Trong Hàng Đợi Nội Chính

## Bối cảnh

Trong quy hoạch giao diện hợp nhất Nội Chính & Nghiên Cứu (ADR-0017), hai bảng điều khiển chính ở Cột 2 gồm **Quản lý nhà** (`bld_tree`) và **Nâng cấp kỹ thuật** (`res_tree`) chỉ hiển thị 2 cột dữ liệu: `Cấp` (đại diện cho Cấp mục tiêu) và `Chạy` (checkbox chọn thi công).

Điều này dẫn đến các hạn chế về trải nghiệm người dùng:
1. **Mù thông tin cấp độ thực tế**: Người chơi không thể quan sát được cấp độ hiện tại thực tế trên máy chủ game (`cur_lvl`) của từng công trình và kỹ thuật ngay trên bảng điều khiển, mà phải mở cửa sổ game hoặc suy đoán qua màu sắc.
2. **Khó theo dõi tiến độ nhóm công trình đa ô đất**: Các công trình nhiều ô đất như Nhà Dân, Kho thường có cấp độ các ô lệch nhau (ví dụ ô cấp 5, ô cấp 8), người dùng không nắm được biên độ phát triển của nhóm khi dòng cha đang thu gọn (*collapsed*).
3. **Thiếu sự nhất quán về nhận diện trực quan**: Bảng Quản lý nhà đã có hệ thống đổi màu theo trạng thái (Xanh lá = nâng cấp, Xám = hoàn tất, Đỏ = hạ cấp), nhưng bảng Nâng cấp kỹ thuật Viện Đại Học trước đó chưa áp dụng cùng bộ màu này.

## Quyết định

1. **Chuẩn Hóa 4 Cột Hiển Thị Độc Lập Cho Cả Hai Bảng**:
   - Tách cột `Cấp` thành 2 cột riêng biệt: **`Cấp HT`** (Cấp hiện tại) và **`Cấp MT`** (Cấp mục tiêu).
   - Cấu trúc cột mới của `bld_tree` và `res_tree`:
     - Cột `#0` (Tree header): Tên kiến trúc / Kỹ thuật (độ rộng ~125-135px).
     - Cột `#1` (`current_lvl`): `Cấp HT` (độ rộng ~45px, căn giữa).
     - Cột `#2` (`target_lvl`): `Cấp MT` (độ rộng ~45px, căn giữa).
     - Cột `#3` (`select`): `Chạy` (độ rộng ~40px, căn giữa, hiển thị ký hiệu `☑`/`☐`/`▣`).
   - Tổng độ rộng ~260px, tối ưu hoàn hảo cho độ rộng tối thiểu 320px của Cột 2.

2. **Quy Tắc Hiển Thị Cấp HT Đối Với Nhóm Đa Ô Đất**:
   - Khi dòng nhóm (dòng cha) ở trạng thái thu gọn (*collapsed*): Cột `Cấp HT` hiển thị dải cấp `min - max` (ví dụ `5 - 8`, hoặc `5` nếu các ô bằng cấp nhau), cột `Cấp MT` hiển thị cấp mục tiêu chung của nhóm.
   - Khi dòng nhóm được mở rộng (*expanded*): Từng dòng con hiển thị cụ thể `↳ Ô <pid>` kèm đúng Cấp HT và Cấp MT của riêng ô đó.

3. **Đồng Bộ Hệ Thống Tag Màu Trực Quan (Color Tagging) Sang Bảng Kỹ Thuật**:
   - Áp dụng bộ màu tiêu chuẩn cho cả `res_tree`:
     - 🟢 **Xanh lá (`upgrade`)**: `Cấp HT < Cấp MT` (đang có nhu cầu nghiên cứu/nâng cấp).
     - ⚪ **Màu xám mờ (`completed`)**: `Cấp HT >= Cấp MT` (đã đạt mục tiêu quy hoạch).
     - 🔴 **Đỏ nhạt (`downgrade`)**: `Cấp HT > Cấp MT` (dành cho công trình hạ cấp/dỡ bỏ).

4. **Trạng Thái Khởi Đầu Khi Chưa Đồng Bộ Server**:
   - Trước khi bot nạp dữ liệu thực tế từ API server game, cột `Cấp HT` của bảng Kỹ Thuật hiển thị ký hiệu `-` (chưa nạp) và chuyển sang cấp thực tế (0..30) ngay khi đồng bộ xong.

5. **Cập Nhật Tương Tác Click**:
   - Nhận diện cột click: Click vào cột `Chạy` (cột hiển thị thứ 3 - `#3`) sẽ đảo trạng thái checkbox chọn chạy (`☑`/`☐`). Click vào các cột khác sẽ kích hoạt chọn dòng và cập nhật Cấp MT lên ô nhập liệu phía trên.

## Hệ quả

- Người dùng theo dõi trực tiếp, rõ ràng và tức thời chênh lệch giữa thực tế và quy hoạch cho toàn bộ hệ thống công trình và kỹ thuật.
- Trải nghiệm thị giác và tương tác click hoàn toàn đồng bộ, nhất quán giữa hai bảng điều khiển trung tâm của Cột 2.
