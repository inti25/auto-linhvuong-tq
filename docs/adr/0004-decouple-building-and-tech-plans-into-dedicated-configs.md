# Tách biệt file cấu hình tài khoản và file quy hoạch công trình / kỹ thuật

LinhVuong tách biệt cấu hình hệ thống (tài khoản, server, proxy) trong `config.json` khỏi cấu hình quy hoạch công trình (`build_plans.json`) và thứ tự nghiên cứu kỹ thuật (`tech_plans.json`).

Các phương án khác đã cân nhắc:
- Gộp chung toàn bộ vào `config.json`: Cây cấu hình quy hoạch nhà của nhiều thành rất dài, làm file cấu hình chung cồng kềnh, dễ gây lỗi cú pháp khi người dùng chỉnh sửa thông tin đăng nhập hoặc proxy.
- Lưu cấu hình vào cơ sở dữ liệu SQLite: Phức tạp hóa việc triển khai cho người dùng thông thường, khó sao chép hoặc chia sẻ kế hoạch quy hoạch mẫu giữa các người chơi.
