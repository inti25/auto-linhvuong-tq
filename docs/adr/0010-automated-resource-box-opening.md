# Tự Động Mở Đạo Cụ Tài Nguyên Khi Thiếu Hụt Trong Tab Xây Dựng

Khi tiến hành nâng cấp hoặc hạ cấp công trình trong Linh Vương, các công trình cấp cao đòi hỏi lượng lớn tài nguyên (Gỗ, Đá, Sắt, Lúa). Nếu tài nguyên tại thành không đủ, server phản hồi mã lỗi `ret=32` hoặc `ret=37`, khiến toàn bộ tiến trình thi công bị tạm dừng. Người chơi sở hữu số lượng lớn đạo cụ tài nguyên dân sinh trong túi đồ (đặc biệt là Dân Sinh Bảo Đỉnh) có nhu cầu tự động mở các rương này để quá trình xây dựng diễn ra liên tục, không bị ngắt quãng.

Các phương án khác đã cân nhắc:
- Thăm dò tài nguyên kho trước khi thi công (Pre-check qua `City.ashx?id=20`): Tăng số lượng request lên server không cần thiết trước mỗi lệnh xây dựng và khó ước lượng chính xác lượng tài nguyên cần cho từng công trình ở mọi cấp.
- Cố định chỉ mở một loại rương duy nhất (Dân Sinh Bảo Đỉnh): Nếu tài khoản người chơi hết Bảo Đỉnh nhưng còn nhiều Hạp/Độc/Nang thì bot sẽ bị kẹt không thể tự phục hồi.
- Mở rương không giới hạn cho đến khi đủ tài nguyên: Tiềm ẩn rủi ro lãng phí đạo cụ quý khi sức chứa kho của thành đã đạt giới hạn trần (`max_storage`).

Quyết định:
- Kích hoạt theo cơ chế phản xạ (Reactive Trigger): Bot chỉ can thiệp mở đạo cụ khi lệnh nâng/hạ cấp (`OPT.ashx?id=65`) trả về mã lỗi thiếu tài nguyên `ret in (32, 37)`.
- Quy trình tự động mở rương và tái thử nghiệm:
  1. Chuyển ngữ cảnh về thành trì đang thi công (`City.ashx?id=50`).
  2. Gửi lệnh mở đạo cụ tài nguyên qua `Common.ashx?id=48` (`lBoxID={box_id}`).
  3. Sau mỗi lần mở thành công (`ret=0`), thử gửi lại lệnh nâng/hạ cấp công trình.
  4. Nếu lệnh thi công thành công (`ret=0`), kết thúc vòng lặp mở đạo cụ và ghi log xác nhận.
- Cơ chế bảo vệ và giới hạn an toàn:
  - Giới hạn số lần mở tối đa cấu hình trong một đợt (mặc định: `5` cái/đợt) để tránh vòng lặp vô tận.
  - Tự động dừng ngay lập tức nếu kho chứa đã chạm trần (`current >= max_storage`).
  - Tự động fallback: nếu loại rương đang chọn đã hết trong túi đồ (`ret=10014`), tự động chuyển xuống bậc rương nhỏ hơn theo thứ tự ưu tiên: `24: Dân Sinh Bảo Đỉnh -> 16: Dân Sinh Chi Độc -> 11: Dân Sinh Chi Hạp -> 1: Dân Sinh Chi Nang`.
- Tích hợp giao diện: Bổ sung thanh điều khiển chung trên Tab 5 (Xây Dựng) với Checkbox kích hoạt, Combobox chọn loại đạo cụ mặc định, Checkbox tự động fallback và ô nhập số lượng mở tối đa.
