# Động Cơ Tác Chiến Hợp Nhất, Ma Trận Tương Khắc Ngũ Hành Và Phân Tầng Mưu Lược

## Ngữ Cảnh và Quyết Định
Trước đây, module `linhvuong/battle.py` chỉ được thiết kế phục vụ riêng cho phụ bản Thảo Phạt (`battle_id=0`) với nhiều hạn chế nghiêm trọng:
1. Nhận diện phe Ta/Địch dựa trên vị trí cứng (`pos <= 10`), dẫn đến nhầm lẫn hoàn toàn phe ta thành địch khi người chơi ở vị thế Phòng thủ (`pos 11..20`).
2. Hoàn toàn thiếu API tác chiến `OPT.ashx?id=54`, khiến quân ta đánh thụ động theo mặc định server, không thể dồn mục tiêu hay chọn phương thức tấn công đặc thù cho từng binh chủng.
3. Đổi trận hình `OPT.ashx?id=57` bị hardcode ép đơn đấu PK 100% (`RatioPK=100`), gửi lệnh ngay đầu hiệp khiến đối phương dễ dàng phản khắc, và thuật toán chọn trận hình chỉ nhìn phiến diện 1 mục tiêu đối diện thay vì tương quan toàn cục.
4. Thiếu hoàn toàn API mưu kế chiến trường `OPT.ashx?id=70`, khiến quân ta bất lực khi bị dính hiệu ứng Hỗn loạn hoặc khi cần rút lui khẩn cấp.

Tham khảo thiết kế từ module `AUTOFIGHTING.cs` và `WarFunc.cs` trong `LVClientCode`, chúng tôi quyết định:

1. **Chuẩn hóa Động cơ Tác chiến (BattleEngine) dùng chung**:
   - Xây dựng một engine tác chiến trung tâm, tiếp nhận `battle_id` linh hoạt để phục vụ đồng thời Thảo Phạt (`battle_id=0`), Bình Man / Gọi Dân (`battle_id > 0` từ bản đồ `Map.ashx?id=6`), và Tab Chiến Trường thủ công.
   - Nhận diện quân ta thông qua `UserID == current_uid` của tài khoản đang đăng nhập kết hợp xác định thế trận (Công hay Thủ) qua tổng số quân hai phe.

2. **Lệnh Tác chiến & Mục tiêu Thông minh (`OPT.ashx?id=54`)**:
   - **Thích ứng binh chủng**: Mặc định tự động chọn phương thức tấn công tối ưu theo loại quân chiếm ưu thế của tướng: Cung thủ dùng `Hỏa tiễn (13)`, Kỵ binh dùng `Đột kích (10)`, Bộ binh/Xe dùng `Mãnh công (11)` hoặc `Phổ thông (1)`, có hỗ trợ ghi đè thủ công.
   - **Chọn mục tiêu**: Sắp xếp quân địch theo trọng số (Quân số × Sĩ khí × Trạng thái), hỗ trợ dồn hỏa lực (1&1, 2&1, 3&1).
   - **Tự động bỏ qua quân hỗn loạn**: Khi một đạo quân địch đã bị dính hiệu ứng Hỗn loạn (`TrangThaiQuanDoi == 1`), bot tự động chuyển mục tiêu sang đạo quân địch khác còn nguyên vẹn.
   - **Cô lập BOSS**: Khi bật chế độ bắt sống (`leave_boss_last=True`), bot không tấn công BOSS khi còn lính bảo vệ. Ngay khi chỉ còn duy nhất BOSS trên chiến trường, bot tự động đưa toàn bộ quân ta về thế `Phòng ngự (3)` và dừng tấn công để người chơi vào chiêu hàng.

3. **Điều chỉnh Trận hình Ma trận Ngũ hành Toàn cục (`OPT.ashx?id=57`)**:
   - Áp dụng ma trận tương khắc ngũ hành 5×5 (`ArrayValue[5, 5]` của Trùy, Câu, Kê, Hạc, Ngư) nhân trọng số với quân số, sĩ khí và trạng thái toàn bộ quân địch để chọn ra trận hình có lợi thế áp đảo nhất toàn trận.
   - Bảo toàn tỷ lệ năng lực gốc của tướng (`RatioAttack`, `RatioPK`, `RatioStra`), tuyệt đối không ép PK liều mạng.
   - **Cửa sổ đổi trận cuối hiệp**: Chỉ gửi lệnh `OPT 57` ở 10~15 giây cuối của hiệp (`bout_left <= 15s`) và khi thỏa mãn đủ 3 điều kiện an toàn (tổng tỷ lệ = 100, có mục tiêu xác định, trận hình mới khác trận hình hiện tại).

4. **Phân tầng Mưu lược Chiến trường (`OPT.ashx?id=70`)**:
   - **Tầng phản xạ**: Tự động kích hoạt mưu kế `96 - Hủy bỏ trạng thái` ngay khi đạo quân ta bị rơi vào trạng thái Hỗn loạn.
   - **Tầng khẩn cấp**: Tự động kích hoạt mưu kế `92 - Kim thiền thoát xác` khi quân số hoặc thể lực rơi xuống dưới Ngưỡng An Toàn để bảo toàn 100% sĩ khí và quân lực.
   - **Tầng chủ động**: Hỗ trợ gán mưu kế ưu tiên (`93 - Phản khách vi chủ`, `95 - Cầm tặc cầm vương`, `94 - Quan môn tróc tặc`) ở hiệp mở màn hoặc hiệp chỉ định.

5. **Lưu trữ Cấu hình & Trực quan hóa**:
   - Bổ sung section `"combat"` vào Hồ Sơ Cấu Hình hợp nhất (`auto_profile_{username}_{server_id}.json`) theo chuẩn ADR 0006.
   - Bổ sung Tab "Chiến Trường" trên giao diện chính GUI để hiển thị cục diện hai phe, đếm ngược hiệp đấu và các nút can thiệp trực tiếp.
   - Ghi nhật ký từng hiệp có cấu trúc theo chuẩn ADR 0015 (`logs/combat_{username}_{date}.log`).

## Hệ Quả
- Tối ưu hóa tối đa sát thương và tỷ lệ chiến thắng, bảo toàn tối đa quân số và sĩ khí tướng sau mỗi trận chiến.
- Khắc phục triệt để lỗi nhận diện ngược phe Công/Thủ và lỗi spam request đổi trận sai quy tắc.
- Đảm bảo an toàn tuyệt đối cho các mục tiêu bắt sống danh tướng/BOSS.
- Cho phép người chơi vừa có thể tự động hóa toàn bộ, vừa có thể theo dõi và can thiệp thủ công linh hoạt qua GUI.
