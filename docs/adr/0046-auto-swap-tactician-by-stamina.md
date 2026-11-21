# Tự Động Đổi Mưu Sĩ Theo Ngưỡng Thể Lực Cho Bình Man Và Gọi Man

Status: accepted

## Bối cảnh

Trong tác chiến dã ngoại (**Bình Man**, **Gọi Man**), **Mưu sĩ** đi theo **Võ tướng xuất kích** cũng tiêu hao thể lực qua từng trận đánh và khi thể lực cạn sẽ làm giảm hiệu quả hỗ trợ (trong khi việc tháo trắng Mưu sĩ khiến Võ tướng mất quyền sử dụng chiêu thức binh chủng trong chiến trường). Trước đây người chơi phải mở hộp thoại Thiết lập Mưu sĩ trên Tổng quan để tháo và gán lại thủ công.

Ngoài ra, giao thức gán/tháo Mưu sĩ (`OPT.ashx?id=5`) yêu cầu **Văn quan** và **Võ tướng** phải nằm trong cùng căn cứ (`lCityID`), nếu khác sẽ trả mã lỗi `10023`.

## Quyết định

1. **Cặp cấu hình độc lập theo từng phân hệ và từng căn cứ trên cả Desktop & Web**:
   - Bổ sung `auto_swap_tactician: bool = False` (mặc định tắt để giữ nguyên hành vi hồ sơ cũ) và `min_tactician_stamina: str = "30"` vào `GoiDanProfile`, `BaseBinhManConfig` và `BinhManProfile`, đồng bộ hai chiều Desktop Tkinter và **Bảng Điều Khiển Web** theo [ADR-0043](0043-web-desktop-parity-and-logistics-tribute.md).
   - Khi tùy chọn được bật, nếu **Võ tướng xuất kích** rảnh (`status == 0`) đang chưa có Mưu sĩ (`tactician_id == 0`), hệ thống cũng tự động gán một **Văn quan** đạt ngưỡng thay vì chỉ xử lý trường hợp đã có Mưu sĩ yếu thể lực.

2. **Giới hạn phạm vi đổi trong căn cứ xuất kích `origin_id` (không tự điều tướng qua Thành mẹ)**:
   - Lọc ứng viên thay thế chỉ từ các **Văn quan** đang ở sẵn trong cùng `origin_id` (`camp_id` ở Bình Man Chế độ 1; `city_id` ở Bình Man Chế độ 2 và Gọi Man), rảnh rỗi (`status == 0`), không giữ chức **Thái thú** (`special_status != 1`), chưa biên chế cho Võ tướng khác (`special_status == 0` và không thuộc `roster.active_tactician_ids()`), và đạt `% thể lực >= ngưỡng` (`stamina_max <= 0` coi là `100%`).
   - Sắp xếp ghép cặp theo cấp độ giảm dần (`Cao → Thấp`) cho cả danh sách Võ tướng cần đổi/gán lẫn danh sách Văn quan đạt ngưỡng.
   - Không tự điều chuyển Văn quan qua lại giữa **Thành mẹ** và **Doanh trại** bằng `OPT.ashx?id=50`, và không thực hiện đổi ngầm trong `retreat_to_safety()` để tránh sai lệch trạng thái vị trí tướng giữa Thành và Trại.

3. **Fallback không chặn và giao dịch 2 bước có hoàn tác (rollback)**:
   - Nếu Mưu sĩ hiện tại dưới ngưỡng nhưng trong căn cứ không có Văn quan thay thế đủ thể lực, giữ nguyên Mưu sĩ hiện tại, ghi cảnh báo vào **Nhật Ký Tác Vụ** và vẫn tiếp tục xuất quân để không làm gián đoạn vòng lặp hay mất chiêu thức chiến trường.
   - Chỉ gửi lệnh tháo Mưu sĩ cũ (`lType=0`) sau khi đã xác nhận có ứng viên đạt ngưỡng; nếu lệnh gán Văn quan mới (`lType=3`) thất bại, tự động thử gán lại Mưu sĩ cũ trước khi ghi lỗi (và phát `CaptchaRequired` ngay nếu gặp mã `110`/`73`).

4. **Điểm kích hoạt thống nhất**:
   - Tự động kiểm tra và đổi Mưu sĩ trong pha chuẩn bị trước xuất kích của `BinhMan.run_once()` / `GoiDan.run_once()` (cùng lúc kiểm tra quân lực & sĩ khí, kể cả khi không đặt định mức lính hay không bật luyện sĩ khí) và khi người dùng bấm nút **⚔️ Biên chế ngay** thủ công.

## Các phương án đã cân nhắc

- **Tự động điều Văn quan từ Thành mẹ ra Doanh trại bằng `OPT.ashx?id=50` ở Bình Man Chế độ 1 (hoặc đổi ngầm lúc `retreat_to_safety()`)**: Bị từ chối để tránh phát sinh lệnh điều tướng ngoài ý muốn và rủi ro lệch vị trí Mưu sĩ giữa Thành mẹ và Doanh trại.
- **Tạm dừng xuất quân (`waiting_tactician_stamina`) hoặc tháo Mưu sĩ yếu khi hết Văn quan dự bị**: Bị từ chối vì làm kẹt tiến trình farm dài hạn hoặc làm mất chiêu thức chiến trường của Võ tướng.

## Hệ quả

- **Tương thích ngược**: Hồ sơ JSON cũ không chứa `auto_swap_tactician` / `min_tactician_stamina` mặc định tắt (`False`, ngưỡng `30%`), không làm thay đổi hành vi các tác vụ đang chạy.
- **Tối ưu truy vấn Roster**: `BinhMan` và `GoiDan` chỉ nạp `include_civil=True` khi `auto_swap_tactician=True`, tránh tăng tải gọi `/api/city/pageofficial?heroType=1` và `Common.ashx?id=14` khi người dùng không bật tùy chọn này.
