# Gọi Man Bằng Tài Khoản Gọi Hộ (Helper Account Man Calling)

Status: accepted

## Bối cảnh

Trong chế độ **Gọi Man**, người chơi thường muốn dùng một **Tài Khoản Gọi Hộ** (cùng máy chủ) để tiêu thụ đạo cụ kéo **Man Thường** (Cấp 1–10) về sát thành của tài khoản chính, sau đó tài khoản chính xuất quân tiêu diệt, hồi phục quân số và luyện sĩ khí rồi lặp lại chu kỳ.

Hai ràng buộc giao thức và vận hành khiến thiết kế phải có ranh giới rõ ràng:
1. Giao thức kéo **Man Thường** (`OPT.ashx?id=69`, `type=63`) nhận `param1=target_id` và `param2=dest_mid`, cho phép tài khoản gọi hộ kéo Man từ bản đồ về ô đất trống sát thành của tài khoản chính mà không cần chuyển thành hiện tại sang thành tài khoản chính (thực tế tài khoản gọi hộ không sở hữu `city_id` đó). Ngược lại, **Vong Linh** (`301`, `type=33`, `param2=0`) luôn triệu hồi quanh thành đang kích hoạt của chính người gọi, nên tài khoản gọi hộ sẽ gọi nhầm về thành của chính mình.
2. Hệ thống tuân thủ quy tắc không lưu mật khẩu plaintext vào `auto_profile_*.json` / `gui_settings.json` (ADR-0033, ADR-0041) và hỗ trợ đa tài khoản đồng thời trên Web Dashboard (ADR-0038). Nếu tài khoản gọi hộ đã có phiên đăng nhập trong `WorkspaceManager`, việc tự đăng nhập lại cùng tài khoản sẽ đá cookie phiên đang chạy.

## Quyết định

1. **Ranh giới loại Man**:
   - Chế độ **Tài Khoản Gọi Hộ** chỉ áp dụng cho **Man Thường** (Cấp 1–10, `type=63`). Nếu cấu hình bật Tài Khoản Gọi Hộ nhưng danh sách mục tiêu chứa **Vong Linh (`301`)**, hệ thống chặn và báo lỗi cấu hình rõ ràng trước khi chạy.
   - Tài khoản chính vẫn thực hiện kiểm tra rảnh, đổi mưu sĩ, trị thương/biên chế, luyện sĩ khí và kiểm tra Man sẵn có sát thành (`<= 6 ô`) trước khi yêu cầu Tài Khoản Gọi Hộ tiêu thụ đạo cụ.
2. **Abstraction & vòng đời phiên (`linhvuong/helper_caller.py`)**:
   - Đóng gói việc cung cấp `GatewayClient` gọi hộ qua `HelperCallerSession`, nhận tùy chọn `session_lookup` để tái sử dụng phiên đã đăng nhập cùng `(server_id, username)` trong `WorkspaceManager` (tránh double-login đá cookie) hoặc tự mở phiên `requests.Session` + `GatewayClient` độc lập có `auto_relogin` và kế thừa cấu hình Proxy của tài khoản chính.
   - Khi tác vụ kết thúc (`AutomationEngine`, `GoiDanAutoRunner`, hoặc chạy 1 lượt), `GoiDan.close()` chỉ đóng phiên độc lập do nó mở, tuyệt đối không đóng phiên tái sử dụng của workspace.
   - Không gọi `set_current_city(main_city_id)` lên gateway của Tài Khoản Gọi Hộ.
3. **Bảo mật thông tin đăng nhập (ADR-0041)**:
   - `GoiDanProfile` chỉ lưu `caller_enabled` và `caller_username` trong `auto_profile_*.json`, loại bỏ mọi khóa mật khẩu plaintext khi đọc/ghi.
   - Mật khẩu Tài Khoản Gọi Hộ chỉ giữ trong RAM của phiên chạy, và tùy chọn lưu mã hóa vào `CredentialVault` dưới khóa chuẩn `{caller_username} @ S{server_id}`. Khi lưu từ Gọi Man cho tài khoản chưa có trong `accounts`, đặt `auto_resume=False` để tránh tự động khởi chạy như một phiên tài khoản độc lập khi khởi động lại server.
4. **Chính sách xử lý lỗi không fallback**:
   - Khi Tài Khoản Gọi Hộ gặp hết đạo cụ (`ret=90`), Captcha (`ret=110/73` → `caller_captcha`), hoặc lỗi đăng nhập (`caller_login_failed`), vòng lặp Gọi Man dừng ngay và phát thông báo rõ tên Tài Khoản Gọi Hộ; tuyệt đối không fallback sang tiêu thụ đạo cụ của tài khoản chính và không khóa `captcha_required` toàn cục của tài khoản chính.
5. **Đồng bộ Desktop Tkinter & Web Dashboard (ADR-0043)**:
   - Cung cấp cấu hình Tài Khoản Gọi Hộ đồng nhất trên cả tab Gọi Man của Desktop Tkinter (`linhvuong/dashboard/goidan.py`) và Web Dashboard (`linhvuong/web/static/app.js` + endpoints `/tasks/goidan/caller/credentials`, `/tasks/goidan/caller/test`).

## Hệ quả

- Tài khoản chính và Tài Khoản Gọi Hộ phối hợp khép kín chu trình kéo Man – đánh – biên chế – luyện sĩ khí trên cùng một máy chủ mà không làm lộ mật khẩu plaintext hay đá phiên cookie đang mở.
- Giao diện trừu tượng `caller_gateway` / `caller_provider` tách biệt việc lấy phiên gọi hộ khỏi logic `GoiDan`, cho phép mở rộng sang danh sách nhiều Tài Khoản Gọi Hộ xoay vòng về sau mà không phải viết lại lõi tác vụ.
