# Đào Tạo Tướng Hàng Ngày Tại Điểm Tướng Đài Và Tụ Hiền Lâu

Status: accepted

## Bối cảnh

Trong Linh Vương, người chơi có thể đào tạo nhận điểm kinh nghiệm định kỳ cho **Võ tướng** tại **Điểm Tướng Đài** (`点将台` / **Tướng Soái Phủ** `将帅府`, `lType=2`) và cho **Văn quan** tại **Tụ Hiền Lâu** (`聚贤楼` / **Mạc Liêu Để** `幕僚邸`, `lType=1`). Mỗi phân hệ có tối đa 5 ô đào tạo cấp tài khoản (`lPos = 1..5`):
- Truy vấn trạng thái: `Common.ashx?id=141` với `lType` (`1` hoặc `2`) và `lCityID` (bắt buộc là ID Thành dương `> 0`; truyền `0` hoặc ID Doanh trại `< 0` trả về `ret=4`). Phản hồi trả về `slots` (số ô đã mở) và `list` (các ô đang hồi với thời gian đếm ngược tính bằng giây).
- Thực thi đào tạo: `OPT.ashx?id=178` với `lType`, `lPos`, `lHeroID`. Khi thành công (`ret=0`), tướng nhận `exp` ngay lập tức, không chuyển sang trạng thái bận, và ô đào tạo đó bước vào thời gian hồi **24 giờ (86.400 giây)** tính từ thời điểm bấm (rolling 24h cooldown, không reset theo mốc 00:00 lịch ngày).

## Quyết định

1. **Module miền độc lập (`linhvuong/tasks/training.py`)**:
   - Đóng gói truy vấn (`fetch_training_state`), thực thi (`start_general_training`), điều phối chu kỳ (`run_training_cycle`) và tính thời điểm đánh thức kế tiếp (`compute_next_training_check_seconds`) không phụ thuộc UI.
   - Tuyệt đối **không** tự động gọi `OPT.ashx?id=177` (mở khóa ô bằng Nguyên bảo); chỉ sử dụng các ô đã mở (`1..slots`).
   - Hỗ trợ **thứ tự ưu tiên có dự phòng (fallback)**: khi một tướng trong danh sách ưu tiên gặp lỗi theo tướng như đã đạt cấp tối đa (`ret=315`), đang trọng thương/dưỡng thương/đấu giá/phụ thể (`ret=316`) hoặc bận (`ret=40`), hệ thống tự động chuyển sang tướng kế tiếp trong danh sách ưu tiên cho ô trống đó.

2. **Lặp lại tự động mỗi 24 giờ không spam API**:
   - Không dùng kiểm tra theo ngày lịch (`YYYY-MM-DD`) vì thời gian hồi 24 giờ tính trượt theo từng ô.
   - Tích hợp vào vòng lặp phụ trợ `AccountSession.start_aux_loop()` trên Web/Runtime và `_schedule_periodic_boost_check()` trên Desktop bằng lịch `remaining_seconds + 2` giây (giới hạn đồng bộ tối đa 1 giờ/lần khi còn xa, retry `300s` khi gặp lỗi tạm thời `316`/`40`).
   - Khi số ô đã mở lớn hơn số tướng người dùng chọn và mọi tướng chọn đều đang nằm trong ô đếm ngược, vẫn chờ theo `min_active_remaining` thay vì lặp 0 giây.

3. **Lưu trữ hồ sơ & đồng bộ Desktop / Web Dashboard**:
   - Bổ sung `TrainingProfile(enabled: bool, vo_general_ids: list[int], van_general_ids: list[int])` vào `Profile` trong `linhvuong/profile.py`, tương thích ngược hoàn toàn với các tệp JSON cũ.
   - Cung cấp cửa sổ **🎓 Đào Tạo Tướng** trên cả Desktop Tkinter (`TrainingDialogMixin`) và **Bảng Điều Khiển Web** (`openTrainingModal()` + `GET /api/accounts/{key}/training/status`, `POST /api/accounts/{key}/training/run`) cùng công tắc bật/tắt nhanh ở khối Phụ trợ Nội Chính.

## Hệ quả

- Người chơi chỉ cần chọn danh sách tướng ưu tiên cho Điểm Tướng Đài và Tụ Hiền Lâu một lần và bật tự động; hệ thống tự đào tạo lặp lại mỗi khi hết hồi 24 giờ.
- Không làm phát sinh chi phí Nguyên bảo ngoài ý muốn và không làm tăng tải gọi API thừa trong thời gian chờ.
