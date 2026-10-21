# Bỏ kiểm tra giấy phép từ xa và không tự động giải captcha

LinhVuong là ứng dụng mới, không dựng lại lớp kiểm tra giấy phép Supabase của ZMan (dùng khóa và backend của tác giả gốc). Khi gặp captcha, nhiệm vụ dừng và cảnh báo người dùng giải thủ công thay vì chọn ngẫu nhiên như ZMan.

Các phương án khác đã cân nhắc: giữ gọi Supabase của tác giả gốc (phụ thuộc hạ tầng và khóa của người khác); tự dựng backend giấy phép (chưa cần cho dùng cá nhân); chọn captcha ngẫu nhiên (tỷ lệ đúng khoảng 25%, dễ bị phát hiện).
