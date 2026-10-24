# Chiến Lược Mở Rương Khi Toàn Bộ Thiếu Tài Nguyên Và Mặc Định Bỏ Chọn Hàng Đợi

## Ngữ Cảnh và Quyết Định
Trước đây, khi nạp mới hoặc đồng bộ danh sách kiến trúc và kỹ thuật, các ô kiểm `Chạy` mặc định được chọn (`enabled=True`), khiến bot tự động thi công toàn bộ nếu người chơi chưa kịp tùy chỉnh. Đồng thời, khi một công trình bị thiếu tài nguyên (mã 32 hoặc 37), cơ chế cũ lập tức mở liên tiếp nhiều rương tài nguyên (`_try_open_box_and_retry`) để phục vụ riêng công trình đó, gây lãng phí rương quý giá trong khi các công trình khác trong hàng đợi có thể đủ điều kiện xây ngay bằng tài nguyên hiện có.

Chúng tôi quyết định:
1. **Trạng thái thi công mặc định**: Tất cả công trình và kỹ thuật khi khởi tạo mới hoặc đồng bộ lần đầu từ máy chủ sẽ ở trạng thái chưa chọn (`☐` / uncheck / `enabled=False`). Trạng thái này chỉ được bật khi người chơi chủ động tích chọn hoặc khi nạp từ file cấu hình / hồ sơ hợp nhất đã lưu.
2. **Xoay vòng bỏ qua khi thiếu tài nguyên**: Khi lệnh thi công một công trình gặp lỗi thiếu tài nguyên (mã 32 hoặc 37), bot không mở rương ngay mà tạm hoãn công trình đó trong lượt hiện tại và thử tiếp các công trình kế tiếp trong hàng đợi.
3. **Mở 1 rương khi toàn bộ đều thiếu và quay lại từ đầu**: Chỉ khi toàn bộ các công trình hợp lệ trong hàng đợi đều báo thiếu tài nguyên và tùy chọn `Mở khi thiếu lúc xây dựng` đang bật, bot mới mở đúng **1 rương** tài nguyên theo danh mục ưu tiên, sau đó lập tức quay lại đầu hàng đợi để thử lại theo đúng thứ tự ưu tiên ban đầu. Quá trình này lặp lại tối đa theo trần an toàn `max_boxes_per_round` hoặc khi kho đầy.

## Hệ Quả
- Tiết kiệm tối đa tài nguyên rương đạo cụ bằng cách tận dụng tài nguyên sẵn có trong kho cho các công trình tiêu hao thấp hoặc khác loại tài nguyên trước.
- Tuyệt đối bảo toàn thứ tự ưu tiên: Sau khi mở rương, công trình ưu tiên cao nhất luôn được trao cơ hội thi công đầu tiên.
- Người chơi nắm toàn quyền kiểm soát danh sách thi công mà không bị tự động chạy hàng loạt ngoài ý muốn.
