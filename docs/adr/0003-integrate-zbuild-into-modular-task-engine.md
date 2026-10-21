# Hợp nhất phân hệ ZBuild vào kiến trúc Task độc lập của LinhVuong

LinhVuong mở rộng phạm vi v1 để tích hợp toàn bộ các tính năng nội chính từ ZBuild.exe (xây dựng công trình, nghiên cứu viện Đại Học, an dân tự động và chuyển quân liên thành) thành các Task độc lập trong `linhvuong/tasks/` chạy song song với các Task quân sự của ZMan.exe.

Các phương án khác đã cân nhắc:
- Duy trì hai ứng dụng / repository riêng biệt như tác giả Zee: Tốn tài nguyên, phân mảnh HTTP Session, phải đăng nhập hai lần và khó đồng bộ dữ liệu thành trì giữa hai bên.
- Gộp chung toàn bộ luồng xây dựng vào một loop khổng lồ: Khó bảo trì, khó viết unit test và không cho phép người chơi bật/tắt từng tính năng độc lập.
