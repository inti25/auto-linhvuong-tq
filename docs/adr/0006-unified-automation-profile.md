# Hợp nhất cấu hình các tính năng tự động thành một Hồ Sơ Cấu Hình duy nhất

LinhVuong hợp nhất việc lưu và nạp cấu hình của tất cả các phân hệ tự động (Xây Dựng, Nghiên Cứu Viện Đại Học, Thảo Phạt, Bình Man, Gọi Dân, Hậu Cần) thành một file Hồ Sơ Cấu Hình JSON duy nhất (`auto_profile.json` hoặc file do người dùng chỉ định), được quản lý tập trung tại Tab Tổng Quan & Quân Đội. Đồng thời loại bỏ các nút Lưu/Nạp riêng lẻ tại từng tab con.

Các phương án khác đã cân nhắc:
- Giữ các nút Lưu/Nạp riêng lẻ tại từng tab (như `build_plans.json` ở Tab Xây Dựng, `tech_plans.json` ở Tab Đại Học): Gây phân mảnh dữ liệu, người chơi phải lưu và nạp thủ công nhiều file khi chuyển đổi giữa các tài khoản hoặc chia sẻ bộ thiết lập cho nhau, giao diện các tab con bị chật chội.
- Tự động đồng bộ vào `gui_settings.json`: Dễ gây xung đột và làm lộ thông tin tài khoản / proxy khi chia sẻ file quy hoạch chiến lược cho người chơi khác.

Quyết định:
- Cung cấp tính năng Lưu/Nạp một file duy nhất cho toàn bộ cấu hình bot tại Tab 1 (Tổng Quan).
- Tự động nạp file `auto_profile.json` mặc định khi khởi động ứng dụng nếu file tồn tại.
- Hỗ trợ tương thích ngược thông minh: Nếu người dùng nạp file cấu hình cũ chỉ chứa quy hoạch công trình hoặc kỹ thuật, hệ thống tự động nhận diện và cập nhật đúng phân hệ tương ứng mà không báo lỗi.
