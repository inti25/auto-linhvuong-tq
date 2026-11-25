# Tăng Nhân Khẩu & Biên Chế Từng Phần khi thiếu dân (Partial Troop Provisioning)

Status: accepted

## Bối cảnh

Trước đây, trong quy trình **Biên Chế Quân Tự Động** tại **Thành** (`ArmyProvisioner.buy_recruits` và `ArmyProvisioner.adjust_troops`), khi kho thiếu tân binh (`OPT.ashx?id=6` trả về `ret=53`) và dân số rảnh rỗi không đủ để chiêu mộ toàn bộ phần thiếu (`OPT.ashx?id=41` trả về `ret=34`), hệ thống chỉ gọi **Tăng Nhân Khẩu** (`OPT.ashx?id=4, lType=4`) rồi thử mua lại đúng toàn bộ số lượng thiếu ban đầu:

- Nếu **Tăng Nhân Khẩu** đang trong thời gian hồi ~15 phút (`ret=55`) hoặc sau khi gọi dân nhàn rỗi vẫn nhỏ hơn toàn bộ số quân thiếu, lệnh chiêu mộ `OPT.ashx?id=41` tiếp tục thất bại (`ret=34`) → **0 tân binh được mua và 0 quân được biên chế**, dù trong kho và dân nhàn rỗi vẫn còn hàng trăm/hàng nghìn dân.
- Vì không biên chế được quân nào mới, đội hình bỏ lỡ khoảng thời gian hồi Quan Phủ để **Luyện Sĩ Khí** trước cho số quân khả dụng. Ngoài ra, trong Thảo Phạt, cờ `recruit_failed` còn `continue` sớm và bỏ qua luôn bước Luyện Sĩ Khí.
- Ở chiều ngược lại, trong Bình Man và Gọi Man tại Thành, nếu biên chế từng phần xong mà không giữ lại chờ đủ 100% **Định Mức Biên Chế** (chỉ xét **Ngưỡng An Toàn** `30%` hoặc `0%`), tướng sẽ xuất quân luôn khi quân số còn thiếu.

Qua kiểm chứng trực tiếp trên hai phiên bản máy chủ game:
- Nhánh `main` (`server < 58`): `City.ashx?id=6` trả về mảng `population`, trong đó `population[4]` là số **dân nhàn rỗi** (`m_lpopulation_idle_man`).
- Nhánh `s58` (`server >= 58`): `GET /api/city/info` trả về trường `data.m_lpopulation_idle_man` là số **dân nhàn rỗi**.

## Quyết định

1. **Truy vấn dân nhàn rỗi (`ArmyProvisioner.check_idle_population`)**:
   - Đọc `population[4]` từ `City.ashx?id=6` trên `main` (hoặc `data.m_lpopulation_idle_man` từ `/api/city/info` trên `s58`, fallback `population[4]` nếu gặp mảng), kẹp tối thiểu về `0` và bắt buộc kiểm tra Captcha (`ret in (110, 73)` → ném `CaptchaRequired`).

2. **Chiêu mộ tận dụng 100% dân nhàn rỗi & Biên Chế Từng Phần (`buy_recruits_partial` / `adjust_troops`)**:
   - Khi `OPT.ashx?id=6` thiếu tân binh (`ret=53`, `auto_recruit=True`, `base_id > 0`), kiểm tra tồn kho `check_recruits(city_id)` để chỉ mua phần chênh lệch `missing = diff - avail` (giữ tương thích `missing = diff` nếu `check_recruits` trả `None` hoặc `>= diff`).
   - Khi `OPT.ashx?id=41` gặp `ret=34` (thiếu dân), gọi `OPT.ashx?id=4, lType=4` tối đa 1 lần cho mỗi Thành trong cùng lượt chuẩn bị (`comfort_attempted`).
   - Nếu sau khi gọi (hoặc đang cooldown `ret=55`) dân vẫn chưa đủ `missing`, truy vấn `check_idle_population(city_id)` và chiêu mộ hết 100% dân nhàn rỗi hiện có (`min(missing, idle_pop)`), sau đó biên chế phần khả dụng `assignable = min(diff, known_avail + bought)` qua `OPT.ashx?id=6`.
   - Khi thiếu trang bị (`OPT.ashx?id=6` trả về `ret=42`), tự động đọc kho trang bị qua `GET /api/city/pagearmament`, ước lượng phần quân tối đa đáp ứng được cho từng binh chủng (`_estimate_equipment_caps`) và biên chế từng phần theo mức trang bị khả dụng.
   - `adjust_troops` giữ phân bổ **tuần tự từng tướng** (lấp đầy tướng trước để không làm loãng sĩ khí lặp lại trên nhiều tướng mỗi đợt gọi dân; tương thích với **San Đều Quân** khi bật) và trả kết quả tách biệt phần đã biên chế (`(stype, assignable, True, 0)`) cùng phần còn thiếu do dân/tân binh (`(stype, remaining, False, shortage_ret)` với `shortage_ret in {34, 53, 55}`).

3. **Chống spam Quan Phủ & chống biên chế lắt nhắt**:
   - Ghi nhớ thời điểm cho phép gọi lại `OPT.ashx?id=4, lType=4` theo từng `city_id`: **900 giây** sau `ret=0` và **60 giây** sau `ret=55`. Không xóa bộ đếm cooldown này ngay cả khi một lượt biên chế sau đó đủ quân.
   - Khi Thành đang ở trạng thái chờ dân (`_waiting_population[city_id] == True`) và không vừa Tăng Nhân Khẩu thành công trong lượt, các vòng lặp tự động chỉ mua/biên chế tiếp khi tổng `tân_binh_kho + dân_nhàn_rỗi >= min(số_thiếu, 50)` để tránh biên chế nhỏ giọt vài lính mỗi 10 giây làm tụt sĩ khí liên tục (vẫn hoàn tất ngay nếu phần thiếu cuối cùng `< 50`; tắt ngưỡng này ở thao tác thủ công `⚔️ Biên chế ngay`).

4. **Luyện Sĩ Khí trước, giữ quân tới khi đủ 100% Định Mức Biên Chế tại Thành**:
   - Helper `has_population_shortage(results)` chỉ nhận diện thiếu dân/tân binh (`ret in {34, 53, 55}`), không giữ kẹt đối với lỗi cấu hình/trang bị như `ret=42` (thiếu vũ khí) hoặc `ret=43` (vượt sức chứa thống lĩnh).
   - Tại **Bình Man (Chế độ 2 - Thành)**, **Gọi Man** và **Thảo Phạt**: sau **Biên Chế Từng Phần**, luôn chạy **Luyện Sĩ Khí** (`OPT.ashx?id=47`) cho phần quân vừa biên chế trước; nếu vẫn còn thiếu dân/tân binh (`has_population_shortage` / `recruit_failed`), giữ đội hình tại Thành (`"waiting_troops"` trong Bình Man/Gọi Man; chờ 30 giây và lặp lại trong Thảo Phạt) cho tới khi đạt đủ 100% **Định Mức Biên Chế** và Sĩ Khí đạt ngưỡng mới xuất quân.
   - Tách **Ngưỡng An Toàn** trong Bình Man thành `stamina_threshold` (Thể lực an toàn `%`) và `army_threshold` (Ngưỡng quân an toàn `%`), giữ tương thích ngược `return_threshold` / `threshold`.

## Hệ quả

- Tối ưu hóa thời gian chuẩn bị quân lực: ngay trong 15 phút chờ hồi Quan Phủ, số dân nhàn rỗi hiện có đã được chuyển thành quân số thực tế và luyện sẵn sĩ khí.
- Khóa biên chế theo căn cứ (`TargetLocks.base_provision_lock`), chặn retry đối với các lệnh không idempotent (`OPT.ashx` ids `6`, `39`, `41`) và bỏ qua biên chế khi đọc quân số thất bại (`Roster.has_reliable_armies`) giúp ngăn biên chế vượt định mức.
