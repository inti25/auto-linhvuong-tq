# Phân Tách Hồ Sơ Đa Tài Khoản (Multi-Account Profile Isolation) Và Trình Chuyển Đổi Tài Khoản (Account Switcher)

Khi người chơi vận hành nhiều tài khoản Linh Vương cùng lúc trên một máy tính, nhu cầu phổ biến là chạy đồng thời nhiều cửa sổ ứng dụng (multi-instance) từ cùng một thư mục cài đặt duy nhất của `LinhVuong.exe`. Trước đây, hệ thống lưu cố định cấu hình đăng nhập trong `gui_settings.json` và hồ sơ quy hoạch trong `auto_profile.json`. Điều này dẫn đến hiện tượng ghi đè chéo cấu hình giữa các tài khoản, làm mất dữ liệu quy hoạch công trình/chiến dịch của tài khoản này khi tài khoản khác lưu cấu hình.

Các phương án khác đã cân nhắc:
- Yêu cầu người dùng tự nhân bản file `LinhVuong.exe` ra nhiều thư mục con riêng biệt (`Acc1/`, `Acc2/`): Hoạt động được nhưng tốn dung lượng ổ đĩa, gây phiền toái khi cập nhật phiên bản mới (phải copy đè thủ công nhiều nơi) và khó quản lý tập trung.
- Yêu cầu người dùng tự chọn file hồ sơ thủ công (`📁 Chọn Hồ Sơ`) mỗi lần đăng nhập: Dễ quên hoặc chọn nhầm file của tài khoản khác, gây áp dụng sai quy hoạch thành trì và điều chuyển quân giới nhầm lẫn.

Quyết định:
1. **Phân tách hồ sơ cấu hình theo định danh tài khoản (Account-Bound Profile Isolation)**:
   - Mỗi tài khoản khi đăng nhập thành công sẽ được gán tự động một tập tin hồ sơ quy hoạch riêng biệt theo cấu trúc: `auto_profile_{username}_{server_id}.json` (ví dụ: `auto_profile_quilia_53.json`).
   - Thứ tự nạp cấu hình khi mở Dashboard:
     1. Nếu file `auto_profile_{username}_{server_id}.json` đã tồn tại: tự động nạp cấu hình riêng của tài khoản này.
     2. Nếu chưa tồn tại (tài khoản mới): tự động nạp cấu hình mẫu từ `auto_profile.json` (nếu có) để kế thừa thiết lập ban đầu, nhưng đường dẫn lưu mặc định vẫn là file riêng của tài khoản.
   - Tránh hoàn toàn việc ghi đè chéo dữ liệu giữa các phiên chạy song song trong cùng một thư mục.

2. **Trình chuyển đổi tài khoản trên màn hình đăng nhập (Account Switcher)**:
   - Nâng cấp cấu trúc `gui_settings.json` để quản lý danh bạ tài khoản (`accounts: { "<user>@<server>": { server, username, proxy, proxy_user, proxy_pass } }`) song hành cùng cơ chế tương thích ngược cho cấu trúc file đơn cũ.
   - Bổ sung Combobox danh sách tài khoản đã lưu trên giao diện `LoginWindow`. Khi chọn một tài khoản trong danh sách, hệ thống tự động điền Server ID, Username và cấu hình Proxy tương ứng.
   - Hỗ trợ nút xóa nhanh tài khoản khỏi danh bạ khi không còn sử dụng.
   - Tự động ghi nhớ tài khoản đăng nhập thành công gần nhất (`last_account`).

3. **Phân biệt trực quan cửa sổ ứng dụng trên Taskbar (Visual Instance Identification)**:
   - Tiêu đề cửa sổ Dashboard hiển thị đầy đủ Server và Username: `LinhVuong - S{server_id} - [{username}]` (ví dụ: `LinhVuong - S53 - [quilia]`).
   - Giúp người chơi nhanh chóng nhận biết và chuyển đổi chính xác giữa các cửa sổ bot đang cắm ngầm trên thanh tác vụ Windows.
