# Tự Động Bổ Sung Binh Lực và Luyện Sĩ Khí Trong Thảo Phạt

Chiến dịch Thảo Phạt yêu cầu các võ tướng liên tục xuất quân chinh chiến, dẫn đến hao hụt quân số và suy giảm sĩ khí sau mỗi trận đánh. LinhVuong tích hợp cơ chế tự động biên chế binh lực và luyện sĩ khí trước mỗi lượt xuất trận, kết hợp thuật toán tối ưu hóa thời gian hành quân.

Các phương án khác đã cân nhắc:
- Để người dùng tự biên chế và luyện sĩ khí bằng tay trên giao diện web/game: Gây gián đoạn chu kỳ tự động, giảm hiệu suất cày ải và dễ khiến tướng xuất kích với quân số thiếu hụt dẫn đến thất bại.
- Luôn chờ thời gian luyện sĩ khí về 0 mới xuất quân: Gây lãng phí thời gian chờ đợi vì trong thời gian tướng hành quân đến mục tiêu (1 chiều từ 300s đến 1800s), sĩ khí vẫn tiếp tục đếm ngược và sẽ hoàn tất trước khi trận chiến diễn ra.

Quyết định:
- Bố cục giao diện Tab Thảo Phạt theo hàng dọc (Row layout): Hàng trên dành cho bảng danh sách võ tướng với đầy đủ 8 cột chỉ số (Chọn, Cấp, Thể lực, Sĩ khí, Bộ binh, Kỵ binh, Cung binh, Tổng quân); Hàng dưới dành cho khung nhật ký log chiến dịch có thanh cuộn.
- Cho phép người dùng thiết lập trực tiếp quân số mục tiêu cho cả 3 binh chủng (`Bộ MT`, `Kỵ MT`, `Cung MT`), hỗ trợ cả đội hình thuần chủng và hỗn hợp.
- Bổ sung nút bấm **"⚔️ Biên chế ngay"** để người chơi có thể cân bằng và bổ sung lính tức thời cho các tướng được chọn mà không cần kích hoạt vòng lặp Thảo Phạt.
- Tự động kiểm tra tân binh trong kho và chiêu mộ bổ sung (`OPT.ashx?id=41`), kết hợp an dân tăng nhân khẩu (`OPT.ashx?id=4, lType=4`) nếu thiếu dân rảnh rỗi.
- Tự động luyện sĩ khí nhiều đợt (+10 điểm/đợt qua `OPT.ashx?id=47`) cho đến khi đạt ngưỡng cấu hình (`min_morale`, mặc định 95).
- Cho phép xuất quân sớm nếu đợt luyện sĩ khí cuối cùng thỏa mãn điều kiện thời gian còn lại nhỏ hơn hoặc bằng thời gian hành quân (`upgrading_time <= travel_time`).
- Đồng bộ toàn bộ các tham số này vào Hồ Sơ Cấu Hình Tổng Hợp (`auto_profile.json`).

