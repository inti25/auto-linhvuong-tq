# Đồng Bộ và Thanh Lọc Danh Sách Căn Cứ trong Hồ Sơ Cấu Hình

## Bối cảnh
Hồ Sơ Tài Khoản Riêng Biệt (`auto_profile_{username}_{server_id}.json`) lưu cấu hình theo ID **Căn Cứ** tại nhiều phân hệ (`building.cities`, `resource.resource_cities`, `research.city_id`, `binh_man.bases`, `crafting.cities`, `thao_phat.city_id`, `goi_dan.city_id`, `nien_thu.city_id`). Trước đây, khi một **Thành** bị chiếm/bỏ hoặc một **Doanh trại** bị giải thể trên máy chủ, thao tác tải lại `roster` chỉ thêm lúc rỗng hoặc chỉ cập nhật giao diện danh sách mà không thanh lọc bộ nhớ/JSON, khiến tác vụ **Xây Dựng** và **Giám Sát Tài Nguyên** tiếp tục chạy trên các căn cứ không còn tồn tại.

## Các phương án đã cân nhắc
- **Giữ cấu hình căn cứ cũ trong JSON và chỉ ép `enabled = False`**: Dễ giữ lại cấu hình nếu người chơi vô tình lỗi mạng, nhưng để lại dữ liệu rác (`name: ""`) vĩnh viễn trong hồ sơ và vẫn có nguy cơ chạy nhầm nếu một phân hệ đọc thiếu cờ `enabled`.
- **Chỉ lọc tại lúc bấm chạy Auto mà không sửa JSON**: Ngăn được gửi lệnh thừa trong phiên hiện tại nhưng file JSON vẫn lệch với thực tế và giao diện/hồ sơ xuất ra vẫn chứa căn cứ ma.

## Quyết định
1. **Xóa hẳn (prune) các Căn Cứ không còn tồn tại khỏi Hồ Sơ & bộ nhớ** và cập nhật tên mới nhất / thêm căn cứ mới (ở Trạng Thái Thi Công Mặc Định `enabled=False`) ngay khi tải `roster` thành công hoặc khi nạp/import hồ sơ lúc đã có `roster`.
2. **Điều kiện an toàn bắt buộc trước khi prune**: Chỉ thực hiện thanh lọc khi danh sách `roster.bases` trả về từ máy chủ **hợp lệ và khác rỗng**, tuyệt đối không xóa dữ liệu hồ sơ khi API lỗi mạng, hết phiên (401/198599) hoặc trả danh sách rỗng bất thường.
3. **Phân tách đúng Thành và Doanh trại**: Các phân hệ đa căn cứ nội chính và Bình Man (`building.cities`, `resource.resource_cities`, `binh_man.bases`, `binh_man.current_base_id`) đối chiếu theo toàn bộ `roster.bases`; các phân hệ đặc thù của Thành (`crafting.cities`, `research.city_id`, `thao_phat.city_id`, `goi_dan.city_id`, `nien_thu.city_id`, `parent_city_id`) đối chiếu theo `roster.cities` và tự động fallback về Thành hợp lệ đầu tiên khi ID cũ biến mất.
4. **Chốt chặn thực thi ở cả Task & Runner**: Tại lúc khởi chạy tác vụ luôn lọc theo `roster.bases` hiện hành; trong `BuildingTask`, không bao giờ suy diễn công trình ở cấp `0` khi đọc `/api/building/list` thất bại hoặc rỗng, và tự động loại căn cứ khỏi vòng chạy + kích hoạt đồng bộ lại nếu căn cứ biến mất giữa chừng.
