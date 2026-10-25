# Kho Lưu Trữ Hồ Sơ Độc Lập Và Động Cơ Điều Phối Tác Vụ Hợp Nhất

## Ngữ Cảnh và Quyết Định
Trong quá trình phát triển nhanh các tính năng, hai phân hệ cốt lõi bị suy thoái kiến trúc thành các module nông (shallow modules):

1. **Hồ Sơ Cấu Hình (`auto_profile.json`) bị gắn chặt vào GUI**:
   - Toàn bộ logic trích xuất, xác thực và lưu trữ cấu hình hợp nhất (theo ADR-0006) nằm trực tiếp bên trong `linhvuong/dashboard.py` (`_collect_unified_profile` và `_apply_unified_profile`), cào dữ liệu trực tiếp từ các widget Tkinter (`Treeview`, `StringVar`, `Combobox`).
   - Phân hệ dòng lệnh (`cli.py`) hoàn toàn không thể nạp Hồ Sơ Cấu Hình hợp nhất mà phải sử dụng các file cấu hình rời rạc cũ (`build_plans.json`, `tech_plans.json`).
   - Bộ kiểm thử tự động (`test_dashboard_gui.py`) buộc phải khởi tạo cửa sổ Tkinter thật chỉ để kiểm tra việc lưu/nạp JSON.

2. **Các Runner chạy ngầm bị phân mảnh**:
   - `dashboard.py` định nghĩa 5 lớp runner nông (`BaseTaskRunner`, `GoiDanAutoRunner`, `BinhManAutoRunner`, `BuildingAutoRunner`, `ResearchAutoRunner`) với các vòng lặp và cờ kiểm soát luồng riêng biệt.
   - `ThaoPhatAutoRunner` lại nằm tách biệt trong `linhvuong/tasks/thao_phat.py`, không kế thừa `BaseTaskRunner`, tự cài đặt vòng lặp đếm lùi, jitter và quản lý trạng thái riêng.
   - Giao diện `dashboard.py` kiêm nhiệm vai trò giám sát viên đa luồng, quản lý thủ công 5 biến luồng khác nhau (`_tp_runner`, `_bld_runner`, `_res_runner`, `_gd_runner`, `_bm_runner`) dẫn đến rò rỉ seam và phình to lên hơn 4,500 dòng mã.

Để làm sâu kiến trúc (deep modules), tăng tính cục bộ (locality), tăng đòn bẩy (leverage) và tinh gọn bề mặt giao tiếp (interface), chúng tôi quyết định:

1. **Tách biệt Kho Lưu Trữ Hồ Sơ (`ProfileStore`) tại `linhvuong/profile.py`**:
   - Định nghĩa mô hình cấu hình hướng miền bằng các dataclass có kiểu dữ liệu rõ ràng (`Profile`, `BuildingProfile`, `ResearchProfile`, `ThaoPhatProfile`, `BinhManProfile`, `GoiDanProfile`, `CombatProfile`, `LogisticsProfile`, `ResourceProfile`).
   - Cung cấp giao diện tối giản: `load(path) -> Profile`, `save(profile, path)`, `default_for(username, server_id)`.
   - Cơ chế ghi file nguyên tử (`atomic write-and-replace`) qua file tạm `.tmp` chống hỏng dữ liệu khi tắt đột ngột.
   - Bảo toàn 100% khả năng tương thích ngược với cấu trúc file `auto_profile_{username}_{server_id}.json` hiện hành.

2. **Hợp nhất Động Cơ Điều Phối Tác Vụ (`AutomationEngine`) tại `linhvuong/engine.py`**:
   - Tạo seam chuẩn hóa `ExecutableTask` cho mọi tác vụ tự động hóa (`run_step() -> str`, `reset()`).
   - Hợp nhất toàn bộ việc quản lý luồng ngầm, Độ Trễ Ngẫu Nhiên (anti-bot jitter theo ADR-0011), nhật ký tác vụ và tự động tạm dừng khi gặp Captcha vào một module sâu duy nhất.
   - Giao diện điều phối chuẩn: `start(task_id, task, interval, jitter)`, `stop(task_id)`, `stop_all()`, `is_running(task_id)`, `get_status(task_id)`, `resume(task_id)`.

3. **Chuyển `dashboard.py` thành Adapter mỏng**:
   - `dashboard.py` chỉ làm nhiệm vụ đồng bộ hai chiều giữa `Profile` và các biến giao diện Tkinter.
   - Giao diện loại bỏ toàn bộ 5 lớp runner nông và điều khiển tác vụ thông qua duy nhất một thực thể `AutomationEngine`.

4. **Nâng cấp `cli.py`**:
   - Cho phép CLI nạp cấu hình trực tiếp từ `ProfileStore` qua tham số `--profile <path>`, dùng chung 100% cấu hình với GUI.

## Hệ Quả
- **Locality**: Toàn bộ lược đồ cấu hình và vòng lặp quản lý luồng/jitter/captcha tập trung tại đúng 2 module chuyên trách.
- **Leverage**: Một định dạng cấu hình và một engine điều phối phục vụ đồng thời cả GUI, CLI và test suites.
- **Testability**: Kiểm thử hồ sơ cấu hình và vòng lặp tác vụ hoàn toàn độc lập, không cần khởi tạo Tkinter, triệt tiêu cảnh báo `RuntimeError: main thread is not in main loop`.
- **Giao diện tinh gọn**: Giảm bớt hàng trăm dòng mã phân mảnh trong `dashboard.py` và loại bỏ các runner trùng lặp.
