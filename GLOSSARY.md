# LinhVuong

Công cụ tự động hóa (bot) cho game web Linh Vương, xây lại từ phân tích ZMan.exe. Phạm vi v1: Gọi Dân, Thảo Phạt, Bình Man.

## Language

**Man**:
Mục tiêu NPC trên bản đồ (trại quái) mà tướng xuất quân đánh, có loại (`man_type`) và `target_id`.
_Avoid_: Quái, monster

**Mục tiêu**:
Một Man cụ thể đang tồn tại trên bản đồ, định danh bằng `target_id`.
_Avoid_: Target (khi nói tiếng Việt), địch

**Gọi Dân**:
Hành động triệu hồi Man (gồm Vong Linh) về vị trí để đánh.
_Avoid_: Gọi man, summon

**Thảo Phạt**:
Chiến dịch tấn công các cứ điểm/quân cướp theo cấp độ.

**Bình Man**:
Chế độ tự động quét và tấn công Man quanh thành hoặc Trại Di Chuyển.

**Trại Di Chuyển**:
Doanh trại lưu động của người chơi, dời từng bước tới Mục tiêu trước khi tấn công.
_Avoid_: Trại tạm

**Thiên Thành**:
Thành cấp 5 hoặc 6; vùng quanh nó bị loại khỏi phạm vi đánh Man.

**Mid**:
Mã số một ô trên bản đồ, tương ứng một tọa độ (x, y).
_Avoid_: Map ID, ô số

**Quét**:
Thu thập các Man và thực thể trong một vùng bản đồ.
_Avoid_: Scan (khi nói tiếng Việt)

**Khóa mục tiêu**:
Đánh dấu tạm một Mục tiêu đã có nhiệm vụ nhận để nhiệm vụ khác không đánh trùng.
_Avoid_: Lock

**Trận hình**:
Thế trận xuất binh và giao chiến của đạo quân (Trùy hình, Câu hình, Kê hình, Hạc dực, Ngư lân) quyết định hiệu quả tương khắc lẫn nhau.
_Avoid_: Đội hình (khi nói về trận pháp tương khắc ngũ hành)

**Chiến trường**:
Không gian diễn ra trận giao chiến giữa quân ta và quân địch theo từng hiệp đấu.

**Bắt sống BOSS**:
Hành động giữ Tướng Chủ hoặc BOSS của quân địch sống đến cuối trận (sau khi tiêu diệt hết quân lính) để chiêu hàng hoặc bắt sống.
