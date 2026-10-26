# Xuất Quân Đa Đợt (Tối Đa 3 Đạo / Đợt) Cho Phân Hệ Bình Man Và Gọi Man

## Ngữ Cảnh và Vấn Đề
Trong cơ chế game Linh Vương, mỗi lệnh xuất quân (`OPT.ashx?id=53`) chỉ cho phép tối đa 3 đạo quân (3 võ tướng: Tiền quân, Trung quân, Hậu quân). Trước đây, hệ thống gửi toàn bộ danh sách võ tướng đã chọn trong một request duy nhất (`"generals": ",".join(...)`). Khi người dùng chọn nhiều hơn 3 võ tướng (ví dụ 4, 5, 6 tướng hoặc "Chọn tất cả"), server Linh Vương sẽ từ chối hoặc chỉ ghi nhận một phần, dẫn đến sai lệch đội hình và lãng phí quân lực.

Ngoài ra:
- Chưa có cơ chế chia nhỏ thành các đợt xuất quân liền nhau tới cùng một mục tiêu Man/Vong Linh.
- Thiếu khoảng trễ an toàn giữa các đợt xuất kích liên tiếp, tiềm ẩn nguy cơ bị server nhận diện là spam hoặc nghẽn request.
- Phân hệ Gọi Man chưa có cơ chế kiểm tra tướng rảnh rỗi (Idle Check), khiến việc xuất quân có thể phát sinh lỗi nếu có tướng đang bận hoặc hành quân trên đường.
- Giao diện chưa hiển thị số lượng đạo quân và số đợt xuất kích dự kiến khi người dùng tích chọn tướng.

## Quyết Định Kiến Trúc

1. **Chuẩn Hóa Xuất Quân Đa Đợt Trong `attack()` (`linhvuong/tasks/base.py`)**:
   - Tham số hóa `batch_size: int = 3`, `batch_delay: float = 0.5`, `sleep_fn: Callable[[float], None] = time.sleep`.
   - Danh sách võ tướng `generals` được chia thành các lô (chunks) có kích thước tối đa 3 tướng:
     - $N \le 3$: Giữ nguyên hành vi 1 đợt xuất kích duy nhất (không trễ, tương thích ngược tuyệt đối).
     - $N > 3$: Xuất kích tuần tự theo lô: Lô 1 $\rightarrow$ nghỉ `batch_delay` ($0.5$ giây) $\rightarrow$ Lô 2 $\rightarrow$ ...
   - Tất cả các đợt xuất quân trong cùng lượt đều nhắm tới **cùng một mục tiêu** (`target.target_id` tại tọa độ `target.x, target.y`).
   - Ghi nhận thông báo tiến độ từng đợt xuất kích qua `ctx.notify`.

2. **Cơ Chế Ngắt Lỗi Tức Thì (Short-Circuit Error Handling)**:
   - Nếu bất kỳ đợt xuất kích nào gặp sự cố (Captcha `ret=73`, Hết hạn phiên `198599`, Bị người khác chiếm `ret=230`, hoặc lỗi mạng), chuỗi xuất kích lập tức dừng lại và trả về lỗi tương ứng mà không gửi các đợt tiếp theo.

3. **Đồng Bộ Cơ Chế Idle Check Cho Cả Bình Man và Gọi Man**:
   - `GoiDan` (`linhvuong/tasks/goi_dan.py`): Bổ sung phương thức `check_generals_idle()` thông qua `Common.ashx?id=32 (type=2)`.
   - Cả `BinhMan` và `GoiDan` đều kiểm tra: Chỉ khi **tất cả** các tướng được chọn đều đang ở trạng thái rảnh rỗi (`status == 0`) thì mới kích hoạt chuỗi xuất quân. Nếu có tướng bận/hành quân, lượt chạy trả về `"generals_busy"` và chờ hồi thành.

4. **Hiển Thị Trực Quan Trạng Thái Phân Đợt Trên Giao Diện (`Dashboard`)**:
   - Bổ sung nhãn trạng thái `self.gd_gen_count_lbl` và `self.bm_gen_count_lbl` ngay trên thanh công cụ bảng chọn võ tướng:
     `Đã chọn: X tướng (Y đợt xuất kích)`
   - Tự động cập nhật đồng bộ khi:
     - Người dùng nhấn "✅ Chọn tất cả" hoặc "❌ Bỏ chọn tất cả".
     - Người dùng nhấp chuột tick chọn/bỏ chọn từng võ tướng trên Treeview.
     - Người dùng chuyển đổi thành phố hoặc căn cứ.
     - Hệ thống tự động nạp cấu hình tài khoản (`_load_unified_profile`).

## Đánh Đổi và Hệ Quả

- **Đạt được**:
  - Tuân thủ chính xác quy tắc game Linh Vương (tối đa 3 đạo/lần xuất quân).
  - Cho phép người chơi tự do huy động bất kỳ số lượng tướng nào (4, 5, 6, 9 tướng...) và hệ thống sẽ tự động phối hợp nhiều đợt tấn công liên tiếp vào mục tiêu.
  - Bảo đảm an toàn kết nối qua khoảng nghỉ $0.5$ giây giữa các đợt xuất kích.
  - Ngăn ngừa xuất quân khi đội hình chưa hồi đủ tướng nhờ cơ chế Idle Check đồng bộ.
  - Giao diện trực quan, rõ ràng số đợt xuất kích dự kiến.
- **Tương thích ngược**:
  - Toàn bộ 290 bài kiểm thử tự động đều vượt qua, các trường hợp $\le 3$ tướng hoàn toàn không bị ảnh hưởng.
