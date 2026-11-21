# Đào Tạo Tướng Hàng Ngày Tại Điểm Tướng Đài Và Tụ Hiền Lâu (Server 58+)

Status: accepted

## Bối cảnh

Trên **Linh Vương Server 58+** (`sg58.dipan.com`), người chơi có thể đào tạo nhận điểm kinh nghiệm định kỳ cho **Võ tướng** tại **Điểm Tướng Đài** (`点将台` / **Tướng Soái Phủ** `将帅府`, `lType=2`) và cho **Văn quan** tại **Tụ Hiền Lâu** (`聚贤楼` / **Mạc Liêu Để** `幕僚邸`, `lType=1`). Mỗi phân hệ có tối đa 5 ô đào tạo cấp tài khoản (`lPos = 1..5`).

Kiểm chứng trực tiếp từ `adapter.js` (`_p_marketPassthrough`), `Build/officialgeneral.js` trên CDN S58 và tài khoản thực tế `quilia @ S58`:
- **Truy vấn trạng thái**: `POST /GateWay/Common.ashx?id=141` với tham số `lType` (`1` hoặc `2`) và `tid` (ID Thành dương `> 0`; `adapter.js` điền mặc định `_cid()` nếu thiếu `tid`). Phản hồi trả về `slots` (`0..5`, tài khoản test S58 có `slots=2` cho Điểm Tướng Đài và `slots=1` cho Tụ Hiền Lâu), `hero` theo `tid`, và `list` (`[[pos, remaining_seconds, hero_id, img_id, hero_name], ...]`) dùng chung toàn tài khoản.
- **Thực thi đào tạo**: `POST /GateWay/OPT.ashx?id=178` với `lType`, `lPos`, `lHeroID` và `tid` (`> 0`). Hoạt động xuyên thành và ngay cả khi tướng đang bận (`status != 0`), không cần chuyển thành (`/api/city/current`); khi thành công (`ret=0`) trả về `exp` ngay lập tức và đặt ô vào thời gian hồi **24 giờ trượt (86.400 giây)** (rolling cooldown, không reset theo mốc 00:00). Lỗi trên S58 kèm trường `errMsg` (ví dụ `{"ret":20,"errMsg":"人物ID不存在"}`, `{"ret":1,"errMsg":"操作失败，请稍后再试"}`).

## Quyết định

1. **Module miền độc lập (`linhvuong/tasks/training.py`)**:
   - Đóng gói truy vấn (`fetch_training_state` truyền `tid`), thực thi (`start_general_training` truyền `tid` tùy chọn và định dạng `errMsg` từ S58), điều phối chu kỳ (`run_training_cycle`) và tính thời điểm đánh thức kế tiếp (`compute_next_training_check_seconds`) không phụ thuộc UI.
   - Tuyệt đối **không** tự động gọi `OPT.ashx?id=177` (mở khóa ô bằng `slots * 50` Nguyên bảo); chỉ sử dụng các ô đã mở (`1..slots`).
   - Hỗ trợ **thứ tự ưu tiên có dự phòng (fallback)**: khi một tướng trong danh sách ưu tiên gặp lỗi theo tướng (`ret` thuộc `{315, 316, 40, 20}`), hệ thống tự động chuyển sang tướng kế tiếp trong danh sách ưu tiên cho ô trống đó.

2. **Lặp lại tự động mỗi 24 giờ không spam API**:
   - Không dùng kiểm tra theo ngày lịch (`YYYY-MM-DD`) vì thời gian hồi 24 giờ tính trượt theo từng ô.
   - Tích hợp vào vòng lặp phụ trợ `AccountSession.start_aux_loop()` trên Web/Runtime và `_schedule_periodic_boost_check()` trên Desktop bằng lịch `remaining_seconds + 2` giây (giới hạn đồng bộ tối đa 1 giờ/lần khi còn xa, retry `300s` khi gặp lỗi tạm thời `316`/`40`).
   - Khi số ô đã mở lớn hơn số tướng người dùng chọn và mọi tướng chọn đều đang nằm trong ô đếm ngược, vẫn chờ theo `min_active_remaining` thay vì lặp 0 giây.

3. **Lưu trữ hồ sơ & đồng bộ Desktop / Web Dashboard**:
   - Bổ sung `TrainingProfile(enabled: bool, vo_general_ids: list[int], van_general_ids: list[int])` vào `Profile` trong `linhvuong/profile.py`, tương thích ngược hoàn toàn với các tệp JSON cũ.
   - Cung cấp cửa sổ **🎓 Đào Tạo Tướng** trên cả Desktop Tkinter (`TrainingDialogMixin`, nút đặt trên Tab 1 Overview giữ nguyên 8 tab chính và tích hợp vào khối Phụ trợ trong `linhvuong/dashboard/building.py`) và **Bảng Điều Khiển Web** (`openTrainingModal()` + `GET /api/accounts/{key}/training/status`, `POST /api/accounts/{key}/training/run`) cùng công tắc bật/tắt nhanh ở khối Phụ trợ Nội Chính.

## Hệ quả

- Người chơi chỉ cần chọn danh sách tướng ưu tiên cho Điểm Tướng Đài và Tụ Hiền Lâu một lần và bật tự động; hệ thống tự đào tạo lặp lại mỗi khi hết hồi 24 giờ trên Server 58+.
- Không làm phát sinh chi phí Nguyên bảo ngoài ý muốn (`OPT.ashx?id=177`) và không làm tăng tải gọi API thừa trong thời gian chờ.
