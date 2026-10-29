# Không Gian Đa Tài Khoản Hợp Nhất (Unified Multi-Account Workspace) Và Thanh Điều Hướng Tài Khoản

Trước đây, người chơi muốn vận hành nhiều tài khoản Linh Vương cùng lúc phải mở ứng dụng nhiều lần (chạy nhiều tiến trình `LinhVuong.exe` song song). Mỗi tiến trình mở một cửa sổ đăng nhập `LoginWindow` riêng và một cửa sổ `Dashboard` riêng, gây tốn tài nguyên hệ thống, thanh tác vụ Windows quá tải và khó quản lý tổng thể tình trạng của dàn bot.

Các phương án khác đã cân nhắc:
- Mở nhiều cửa sổ con (`Toplevel`) từ một cửa sổ cha: Vẫn tạo ra nhiều cửa sổ rải rác trên màn hình máy tính, không giải quyết được tính tập trung và khó theo dõi trạng thái đồng thời.
- Lưu tự động mật khẩu xuống đĩa để tự động đăng nhập hàng loạt: Tiện lợi nhưng vi phạm nguyên tắc bảo mật thông tin tài khoản của người dùng trên file JSON thô (`gui_settings.json`).

Quyết định:
1. **Kiến trúc Không Gian Đa Tài Khoản Hợp Nhất (Unified Multi-Account Workspace)**:
   - Chuyển đổi ứng dụng thành một cửa sổ duy nhất gồm 2 phân vùng chính:
     - **Thanh Điều Hướng Tài Khoản** (Sidebar bên trái): Quản lý danh sách Thẻ Tài Khoản (`AccountCard`), hiển thị chấm trạng thái kết nối trực quan (⚪ Chưa đăng nhập, 🟡 Đang kết nối, 🟢 Đã kết nối, 🔴 Lỗi, ⚠️ Cần Captcha), tóm tắt tác vụ đang chạy, nút `➕ Thêm tài khoản`, cùng các nút điều khiển hàng loạt `▶️ Bắt đầu tất cả` và `⏹️ Dừng tất cả` cho các tài khoản đang kết nối.
     - **Khung Làm Việc** (Workspace bên phải): Chứa nội dung điều khiển của tài khoản đang được chọn. Khi chuyển đổi giữa các tài khoản trên menu trái, hệ thống tráo đổi Frame hiển thị tức thì mà không hủy widget hay làm gián đoạn các luồng bot ngầm.

2. **Quy trình Đăng Nhập Cục Bộ Không Lưu Mật Khẩu Xuống Đĩa**:
   - `gui_settings.json` tiếp tục lưu trữ danh bạ tài khoản gồm Server ID, Username và cấu hình Proxy; **tuyệt đối không lưu mật khẩu game ra file trên đĩa**.
   - Khi chọn một tài khoản chưa đăng nhập, Khung Làm Việc hiển thị **Giao Diện Đăng Nhập Cục Bộ** (`AccountLoginView`) với các trường thông tin được điền sẵn, ô Mật khẩu để trống.
   - Khi người dùng nhập mật khẩu và bấm "Đăng nhập", nếu thành công Khung Làm Việc sẽ chuyển sang giao diện Dashboard đầy đủ 6 Tab của tài khoản đó. Mật khẩu chỉ được lưu tạm thời trong bộ nhớ RAM của phiên làm việc để phục vụ cơ chế tự động kết nối lại ngầm (`auto_relogin` khi hết hạn phiên - mã lỗi 198599), và sẽ tự động xóa sạch khi đăng xuất hoặc tắt app.

3. **Mô Hình Cách Ly Độc Lập Tuyệt Đối (Full Execution & State Isolation)**:
   - Mỗi tài khoản sở hữu một hệ sinh thái riêng biệt: `requests.Session`, `GatewayClient`, `ProxyPool`/Proxy riêng, `AutomationEngine` với các luồng nền riêng (Thảo Phạt, Bình Man, Xây Dựng, Sĩ Khí, Nghiên Cứu, Hậu Cần), `Roster`, `TargetLocks`, file cấu hình quy hoạch riêng (`auto_profile_{username}_{server_id}.json`) và file nhật ký riêng (`logs/linhvuong_{username}_{server_id}.log`).
   - Các luồng bot của từng tài khoản vận hành độc lập liên tục 24/7 kể cả khi người dùng đang chuyển sang xem tài khoản khác.

4. **Quản Lý Vòng Đời & Thoát An Toàn (Lifecycle & Graceful Teardown)**:
   - Hỗ trợ đầy đủ thao tác Thêm tài khoản mới, Đăng xuất (dừng bot, giải phóng session, xóa RAM password, quay về màn hình đăng nhập) và Xóa tài khoản khỏi danh bạ `gui_settings.json`.
   - Khi người dùng bấm tắt cửa sổ ứng dụng, nếu có tài khoản đang chạy bot ngầm, hệ thống sẽ bật hộp thoại xác nhận thoát để tránh thao tác nhầm, sau đó gửi tín hiệu dừng an toàn (`stop_all()`) cho toàn bộ các engine trước khi đóng tiến trình.

5. **Bảo Toàn Tính Tương Thích Ngược**:
   - Giữ nguyên chữ ký khởi tạo và API công khai của lớp `Dashboard` để 100% các bài kiểm thử tự động (tests) hiện có tiếp tục chạy độc lập bình thường mà không phát sinh hồi quy.

