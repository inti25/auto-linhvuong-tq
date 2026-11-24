# San Đều Quân giữa các Võ Tướng xuất kích (Even Troop Distribution)

Status: accepted

## Bối cảnh

Trong quá trình chạy **Bình Man** và **Gọi Man**, các **Võ tướng xuất kích** trong cùng một **Căn Cứ** thường chịu tổn thất binh lực không đồng đều sau giao chiến (ví dụ tướng đánh trước/hàng đầu hao hụt nhiều hơn, hoặc tướng mới điều động mang lệch quân số giữa các binh chủng). Khi người chơi không đủ tân binh/vũ khí để bù đầy ngay lên **Định Mức Biên Chế**, hoặc muốn tận dụng đều tổng quân số hiện có trước khi chiêu mộ bổ sung và **Luyện Sĩ Khí**, hệ thống cần một bước cân bằng lại binh lực giữa các tướng đang sẵn sàng xuất kích.

Nếu thực hiện cân bằng bằng cách rút quân thừa về kho qua `OPT.ashx?id=6` (`lAmount < 0`) rồi biên chế lại (`lAmount > 0`), trò chơi sẽ làm suy giảm **Sĩ khí** của đạo quân vừa nhận quân mới, gây lãng phí **Thể lực**, thời gian **Đếm Ngược Luyện Sĩ Khí** và nguy cơ kẹt quân trong kho khi thiếu vũ khí. Qua phân tích mã nguồn client (`barracks.js` cho Thành và `barracks1.js` cho Doanh trại), Binh trường hỗ trợ API điều động quân trực tiếp giữa hai tướng (`OPT.ashx?id=39`) giúp chuyển lính trực tiếp từ tướng này sang tướng khác mà vẫn bảo toàn **Sĩ khí**.

## Quyết định

1. **Giao thức điều động trực tiếp (`OPT.ashx?id=39`)**:
   - Thêm `ArmyProvisioner.transfer_troops_between_generals()` gọi `POST /GateWay/OPT.ashx?id=39` với các tham số đã xác minh trên cả Thành (`tid > 0`, `barracks.js`) và Doanh trại (`tid < 0`, `barracks1.js`): `lFromGeneralID`, `lToGeneralID`, `infantry`, `cavalry`, `bowman`, `mangonel` (`"0"`), `tid`, `_`.
   - Tuyệt đối không dùng `OPT.ashx?id=6` với `lAmount < 0` để rút quân về kho khi thực hiện **San Đều Quân**.
   - Bắt buộc kiểm tra mã Captcha (`ret == 110` hoặc `ret == 73`) và ném `CaptchaRequired` tương tự các tác vụ khác.

2. **Phạm vi & điều kiện Võ tướng tham gia (`ArmyProvisioner.balance_troops`)**:
   - Chỉ cân bằng trong tập **Võ tướng xuất kích** được tích chọn (`general_ids`) đang có mặt tại cùng **Căn Cứ** (`origin_id`), có vai trò Võ tướng (`role == "vo"`), đang rảnh rỗi (`status == 0`) và không đang **Đếm Ngược Luyện Sĩ Khí** (`upgrading_time <= 0`).
   - Nếu số tướng đủ điều kiện `< 2`, bỏ qua bước san đều quân.

3. **Thuật toán cân bằng độc lập theo từng binh chủng & tối ưu Sĩ khí**:
   - Xử lý độc lập 3 binh chủng: Bộ binh (`infantry`), Kỵ binh (`cavalry`), Cung binh (`archers`).
   - Bỏ qua binh chủng nếu `max - min <= 1` (đã cân bằng).
   - Với `total = sum(counts)`, `base = total // N`, `rem = total % N`: sắp xếp các tướng đủ điều kiện giảm dần theo quân số hiện có (ưu tiên sĩ khí cao hơn khi quân số bằng nhau, sau đó giữ nguyên thứ tự chọn) và phân bổ `base + 1` cho `rem` tướng đầu bảng, `base` cho các tướng còn lại nhằm tối thiểu hóa số lượng quân phải dịch chuyển.
   - **Tối ưu Sĩ khí trong phạm vi chuyển 1 nhịp (`surplus → deficit`)**:
     - Mô phỏng sĩ khí sau nhận theo quy tắc trung bình có trọng số theo quân số của trò chơi:
       $$M_R^{\text{new}} = \frac{n_R M_R + x M_D}{n_R + x}$$
     - Xác định trần sàn cố định $F_{\text{fixed}}$ là mức sĩ khí nhỏ nhất của các tướng không còn thiếu quân sau phần xuất thừa (do chuyển 1 nhịp không thể nâng sĩ khí của tướng cho), sau đó dùng tìm kiếm nhị phân (water-filling) tìm sàn sĩ khí tối đa khả thi $L^* \in [0, F_{\text{fixed}}]$ cho toàn đội.
     - **Pha A**: Cứu các tướng nhận dưới sàn $L^*$ bằng lượng quân vừa đủ từ tướng cho có sĩ khí cao nhất để toàn bộ tướng đạt ít nhất $L^*$ (giảm số nhịp chờ **Luyện Sĩ Khí** song song).
     - **Pha B**: Với phần thừa/thiếu an toàn còn lại, ghép đồng hạng (`sĩ khí cao → cao`, `thấp → thấp`) để bảo toàn các tướng đang sẵn sĩ khí cao (`100`) và tránh làm loãng sĩ khí vô ích. Khi mọi tướng cho đồng nhất sĩ khí (hoặc không có `base_gens`), tự động quy về ghép thừa lớn nhất → thiếu lớn nhất để tối thiểu hóa số request.
   - Gộp các binh chủng cùng cặp `(from_gid, to_gid)` vào một lần gọi `OPT.ashx?id=39`.
   - Khi lệnh gộp thất bại (không phải Captcha, ví dụ `ret=43` vượt giới hạn thống lĩnh hoặc `ret=42` thiếu vũ khí), tự động thử tách từng binh chủng riêng lẻ; nếu binh chủng nào vẫn lỗi ở tướng nhận, ghi nhật ký cảnh báo, đánh dấu bỏ qua tướng nhận đó cho binh chủng tương ứng và lập tức lập lại kế hoạch cho phần còn lại.

4. **Thứ tự chuẩn bị đội hình & trạng thái đồng bộ**:
   - Chu trình chuẩn bị trước khi kiểm tra ngưỡng an toàn và xuất kích:
     `Trị thương (OPT.ashx?id=31)` → **San Đều Quân (`OPT.ashx?id=39`)** → `Biên Chế Quân Tự Động (OPT.ashx?id=6 / id=41)` → `Luyện Sĩ Khí (OPT.ashx?id=47)`.
   - Kết quả quân số cập nhật trong bộ nhớ (`current_armies`) từ `balance_troops()` phải được truyền thẳng sang `adjust_troops()`, tính toán nhu cầu tân binh, hồi quân Thành mẹ và kiểm tra **Ngưỡng An Toàn** để tránh dùng dữ liệu roster cũ gây chiêu mộ/biên chế dư thừa.
   - Khi có ít nhất một lượt chuyển quân xảy ra (`troops_balanced == True`), `MoraleTrainer` bắt buộc làm mới sĩ khí từ máy chủ (`refresh_from_server=True`).
   - Cổng `needs_army_prep` trong `BinhMan.run_once()` và `GoiDan.run_once()` bao gồm cả `even_troops`, đảm bảo San Đều Quân vẫn hoạt động ngay cả khi **Định Mức Biên Chế** đặt `0 / 0 / 0` hoặc tắt tự động bổ sung lính.

5. **Lưu trữ & đồng bộ Desktop / Web Dashboard (ADR-0042)**:
   - Thêm tùy chọn `even_troops: bool = False` (mặc định tắt) vào `GoiDanProfile`, `BaseBinhManConfig` (cấu hình riêng từng Căn Cứ), và `BinhManProfile`.
   - Áp dụng đồng nhất trong cả vòng lặp tự động (`run_once()` / `recover_*`) lẫn nút thao tác thủ công `⚔️ Biên chế ngay` và `⚔️ Biên chế TẤT CẢ căn cứ` trên Desktop Tkinter và Web Dashboard.

## Hệ quả

- Bảo toàn tối đa **Sĩ khí** và **Thể lực** của **Võ tướng xuất kích** khi phân bổ lại lực lượng hiện có giữa các tướng trước khi bổ sung thêm quân mới.
- Hoạt động đồng bộ trên cả **Thành** và **Doanh trại**, hỗ trợ đầy đủ **Bình Man Đa Căn Cứ** (ADR-0029) và giao diện Web/Desktop (ADR-0042).
- Người dùng giữ nguyên hành vi cũ cho đến khi chủ động tích chọn checkbox **San đều quân**.
