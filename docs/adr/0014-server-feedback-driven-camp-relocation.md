# Di Trại Từng Bước Dựa Trên Phản Hồi Máy Chủ Thay Vì Tìm Đường Toàn Cục

## Bối cảnh và Quyết định

Tính năng Di Trại cho phép người chơi dời Doanh trại dã ngoại trên bản đồ thế giới đến một tọa độ chỉ định hoặc hướng tới mục tiêu Man. Bản đồ thế giới trong Linh Vương rất rộng lớn (hàng chục nghìn ô tọa độ). Việc triển khai thuật toán tìm đường toàn cục (như A* hoặc Dijkstra) đòi hỏi phải nạp trước toàn bộ dữ liệu địa hình (núi, sông, rừng, thành trì, cứ điểm NPC) giữa điểm xuất phát và điểm đích thông qua hàng chục lượt gọi API `Map.ashx?id=6` liên tiếp. Điều này gây lãng phí băng thông lớn và làm tăng nguy cơ bị máy chủ nhận diện hành vi tự động hóa bất thường.

Chúng tôi quyết định áp dụng giải pháp **Di Trại Từng Bước Dựa Trên Phản Hồi Máy Chủ (Server-Feedback-Driven Relocation)** kết hợp thuật toán tham lam cục bộ (Greedy Local Search với cơ chế Lách Vật Cản). Bot luôn ưu tiên dời trại thẳng về hướng đích theo cự ly Chebyshev lớn nhất (`max_step = 2`). Chỉ khi máy chủ phản hồi mã lỗi chướng ngại vật (`ret=39`), bot mới thăm dò các ô lân cận (bước nhảy 1 ô hoặc các ô láng giềng kề cận có cự ly Chebyshev nhỏ nhất tới đích) mà không cần quét trước bản đồ diện rộng. Sau mỗi bước thành công (`ret=0`), bot đếm lùi thời gian đóng băng (`frozen`) và cập nhật tọa độ mới tức thì vào bộ nhớ `Roster`.

## Đánh đổi và Lý do chọn

- **Chấp nhận**: Có thể không tìm ra đường đi tối ưu tuyệt đối trong các mê cung địa hình quá phức tạp (cần cơ chế ngắt an toàn sau 5 lần thử lách thất bại).
- **Đạt được**: 
  - Hoàn toàn không phát sinh thêm bất kỳ request quét bản đồ dư thừa nào.
  - Phù hợp và mô phỏng 100% cơ chế dịch ngược từ `ZMan.exe`.
  - Tối ưu hóa tính độc lập giữa phân hệ Di Trại và phân hệ Quét Man / Bình Man.
