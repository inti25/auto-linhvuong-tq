# Đồng Bộ Biên Chế Quân Tự Động Bất Đối Xứng Thành - Doanh Trại Cho Bình Man Và Gọi Man

Trước đây, chỉ phân hệ Thảo Phạt sở hữu cơ chế **Biên Chế Quân Tự Động** theo **Định Mức Biên Chế** (`Bộ MT / Kỵ MT / Cung MT`) kèm Luyện Sĩ Khí ([ADR-0007](0007-thao-phat-auto-refill-and-morale-threshold.md)), trong khi Bình Man và Gọi Man chỉ bù cứng `+500` hoặc `+1000` lính sau trận. Chúng tôi quyết định trích xuất một dịch vụ miền dùng chung để đồng bộ toàn bộ bộ công cụ biên chế và Luyện Sĩ Khí sang Bình Man và Gọi Man, nhưng áp dụng **chiến lược bất đối xứng giữa Thành và Doanh trại** cùng quy tắc chờ sĩ khí hoàn tất trước khi xuất kích.

## Các phương án đã cân nhắc

- **Áp dụng nguyên xi chu trình Thảo Phạt cho Doanh trại ở mỗi lượt Bình Man**: Bị loại bỏ vì Doanh trại dã ngoại không thể chiêu mộ tân binh trực tiếp (`OPT.ashx?id=41`), còn nếu sau mỗi trận hao hụt nhỏ đều điều tướng khứ hồi về Thành mẹ (`OPT.ashx?id=50`) sẽ phát sinh 2 lượt hành quân đường dài trên bản đồ thế giới và làm tê liệt tốc độ Bình Man.
- **Cho phép xuất quân sớm khi đang đếm ngược Luyện Sĩ Khí như Thảo Phạt**: Bị loại bỏ cho Bình Man và Gọi Man vì cự ly tới mục tiêu ở Gọi Man và Doanh trại áp sát rất ngắn (chỉ vài giây), khiến quân vào Chiến trường trước khi sĩ khí kịp nhảy điểm; đồng thời ở Gọi Man nếu gọi mục tiêu ra bản đồ trước khi đủ sĩ khí sẽ dễ bị người chơi khác cướp mục tiêu.
- **Đặt mặc định `Bộ MT = 5000` giống Thảo Phạt**: Bị loại bỏ cho Bình Man và Gọi Man vì người chơi thường vận hành đạo quân thuần Kỵ binh hoặc Cung thủ đã biên chế sẵn; mặc định `Bộ MT > 0` khi nâng cấp từ Hồ Sơ Cấu Hình cũ sẽ vô tình pha trộn Bộ binh, làm chậm tốc độ hành quân và sai lệch Thích Ứng Binh Chủng.

## Quyết định

- **Dịch vụ miền dùng chung, lưu trữ hồ sơ độc lập theo tab**: Trích xuất nghiệp vụ Biên Chế Quân Tự Động (trị thương, kiểm tra kho tân binh, chiêu mộ kèm An Dân khi thiếu nhân khẩu, biên chế phần thiếu hụt `target - current > 0` không tước quân dư, và Luyện Sĩ Khí) thành module dùng chung cho Thảo Phạt, Bình Man và Gọi Man; `ThaoPhatProfile`, `BinhManProfile` và `GoiDanProfile` lưu độc lập các trường định mức và sĩ khí riêng.
- **Mặc định an toàn binh chủng `0 / 0 / 0`**: `BinhManProfile` và `GoiDanProfile` khởi tạo mặc định `Bộ MT = 0`, `Kỵ MT = 0`, `Cung MT = 0` (khi cả ba bằng `0`, hệ thống giữ nguyên biên chế hiện có của tướng và chỉ trị thương/giữ sĩ khí).
- **Bất đối xứng Thành vs Doanh trại**:
  - **Tại Thành** (Gọi Man và Bình Man Chế độ 2): Trước mỗi lượt xuất kích khi Võ tướng xuất kích rảnh rỗi, tự động trị thương, chiêu mộ tân binh tại chỗ bù đủ Định Mức Biên Chế và Luyện Sĩ Khí.
  - **Tại Doanh trại** (Bình Man Chế độ 1): Ở mỗi lượt thường chỉ bù từ quân đồn trú sẵn có tại Doanh trại (không gọi chiêu mộ tại trại và không hồi thành khi thiếu nhẹ). Chỉ khi **bất kỳ Võ tướng xuất kích nào** rơi xuống dưới **Ngưỡng An Toàn (%)** (xét cả tỷ lệ quân số trên `Tổng MT` và tỷ lệ thể lực) mới rút **đồng bộ toàn bộ đội Võ tướng xuất kích** về Thành mẹ để trị thương, chiêu mộ, biên chế đủ định mức, Luyện Sĩ Khí rồi điều ngược ra Doanh trại.
  - **Nút `⚔️ Biên chế ngay` tại Doanh trại**: Ưu tiên rút dự trữ tại trại trước; nếu vẫn thiếu so với Định Mức Biên Chế và đã chọn Thành mẹ thì tự động điều tướng khứ hồi về Thành mẹ biên chế đủ rồi quay lại Doanh trại.
- **Chờ hoàn tất Luyện Sĩ Khí trước khi quét/gọi mục tiêu**: Ở Bình Man và Gọi Man, khi bật `Tự động nâng sĩ khí`, hệ thống chờ đếm ngược Luyện Sĩ Khí về `0` và đạt `min_morale` rồi mới tiến hành gọi Man / quét Man và xuất kích.

