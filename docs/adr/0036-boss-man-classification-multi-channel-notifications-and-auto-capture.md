# ADR 0036: Nhận Diện BOSS Thất Man, Thông Báo Đa Kênh Và Tự Động Cầm Hoạch Bằng Coin (Ngân Bảo)

## Ngữ Cảnh và Vấn Đề

1. **Sai lệch nhận diện BOSS chiến trường dã ngoại**:
   - Trước đây, hệ thống nhận diện BOSS dựa trên việc so khớp chuỗi từ khóa `BOSS_KEYWORDS`, trong đó chứa từ khóa chung `"大将"` (Đại tướng).
   - Qua khảo sát dữ liệu thực tế tại chiến trường Oa Quốc (`sg53.dipan.com/battle/1012`), các quái hộ vệ thông thường như `足轻大将` (Túc khinh đại tướng) và `侍大将` (Thị đại tướng) đều chứa chữ `"大将"` và mang cờ hiệu thường `flag = 16` (`0x10`). Việc gán nhãn chúng là BOSS khiến tính năng cô lập Boss (`leave_boss_last`) bị tê liệt và gây cảnh báo giả liên tục.
   - Ngược lại, BOSS thật sự của chiến trường là `卑弥呼` (Himiko) không chứa từ khóa chức danh nào trong tên nhưng sở hữu cờ hiệu độc quyền **`flag = 32` (`0x20`)**. Trong mã nguồn chính thức của Linh Vương webgame (`Dipan.SanGuo.Battle.js`), điều kiện `flag == 0x20` là tiêu chuẩn tiên quyết đại diện cho **七蛮 BOSS (BOSS Thất Man)** để có thể thi triển lệnh Cầm Hoạch (擒获 - Bắt sống).

2. **Thiếu cơ chế cảnh báo chủ động khi người chơi thu nhỏ ứng dụng**:
   - Khi treo bot tự động đánh dã ngoại hoặc bình man, người chơi thường thu nhỏ cửa sổ bot hoặc chuyển qua làm việc khác. Thông báo chỉ hiển thị trong log văn bản dễ bị trôi và bỏ lỡ thời cơ vàng để bắt Boss trước khi chiến trường kết thúc.

3. **Nhu cầu tự động hóa bắt sống Boss bằng Coin (Ngân bảo / 元宝)**:
   - Khi Boss đã bị cô lập và sĩ khí giảm sâu (< 60), người chơi muốn bot có khả năng tự động gửi lệnh bắt sống (`action = 5`) tiêu hao Coin mà không cần phải can thiệp thủ công bằng tay.

## Quyết Định Kiến Trúc

1. **Chuẩn Hóa Bộ Nhận Diện BOSS Thất Man (`linhvuong/battle.py`)**:
   - Loại bỏ hoàn toàn `"大将"` khỏi danh sách `BOSS_KEYWORDS`.
   - Đặt cờ `flag & 0x20` làm điều kiện tiên quyết cho BOSS Man có thể bắt sống, kết hợp cùng các danh xưng Boss tối cao (`大王`, `单于`, `可汗`, `洞主`, `大首领`).
   - Các quái thường dã ngoại mang cờ `16` (`0x10`) tuyệt đối không được coi là BOSS.

2. **Mô-đun Thông Báo Đa Kênh Bất Đồng Bộ (`linhvuong/notifications.py`)**:
   - Triển khai bộ phát thông báo đa kênh chạy trên luồng nền (`daemon Thread`) độc lập với timeout ngắn để không làm trễ nhịp điều khiển 10~15 giây cuối hiệp của chiến trường.
   - **Kênh Desktop**: Sử dụng giải pháp Windows Native (PowerShell Toast / Tooltip) kết hợp chuông hệ thống `winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)`, không phụ thuộc thư viện bên ngoài.
   - **Kênh Telegram**: Gửi HTTP POST tới Telegram Bot API (`sendMessage`) kèm thông tin: Tên Boss, Vị trí ô, Tọa độ/Thế lực dã ngoại và đường link trực tiếp vào chiến trường (`http://sg{server}.dipan.com/battle/{id}`).
   - **Chống Spam (Deduplication)**: Mỗi BOSS trên từng chiến trường `(battle_id, boss_pos)` chỉ kích hoạt thông báo đúng 1 lần duy nhất trong suốt thời gian diễn ra trận đánh.

3. **Cơ Chế Tự Động Bắt Sống BOSS Bằng Coin (`CombatConfig` & `BattleController`)**:
   - Bổ sung tùy chọn `auto_capture_boss: bool = False` và `capture_boss_max_morale: int = 60` vào cấu hình tác chiến.
   - Khi quái bảo vệ đã hết và sĩ khí của Boss `< 60`:
     - Gọi `Common.ashx?id=71` để kiểm tra chi phí Coin (`fee`) và tỷ lệ thành công (`ratio`).
     - Nếu không đủ Coin (mã lỗi 30): Tự động chuyển toàn quân sang Phòng ngự (`action = 3`) và gửi thông báo cảnh báo.
     - Nếu đủ điều kiện: Chỉ định đạo quân số 1 (chủ tướng) gửi lệnh Bắt sống `action = 5` qua `OPT.ashx?id=54`, đồng thời điều chuyển tất cả các đạo quân còn lại sang thế Phòng ngự (`action = 3`) để tránh đánh chết Boss.

4. **Hồ Sơ Cấu Hình & Giao Diện Popup Dashboard (`linhvuong/profile.py`, `linhvuong/dashboard.py`)**:
   - Bổ sung `NotificationProfile` vào `Profile` (lưu trữ độc lập cho từng tài khoản).
   - Bổ sung nút **`🔔 Cài Đặt Thông Báo & Bắt Sống BOSS`** trên Tab Chiến Trường. Khi bấm sẽ mở hộp thoại nổi (`tk.Toplevel`) cấu hình Desktop Toast, Chuông cảnh báo, Telegram Bot (kèm nút test trực tiếp) và tùy chọn Tự động bắt sống BOSS bằng Coin.

