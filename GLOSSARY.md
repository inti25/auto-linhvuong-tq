# LinhVuong

Công cụ tự động hóa (bot) cho game web Linh Vương, xây dựng và chuẩn hóa từ phân tích dịch ngược ZMan.exe và ZBuild.exe.
Phạm vi v1: Gọi Dân, Thảo Phạt, Bình Man, Xây Dựng, Nghiên Cứu Kỹ Thuật, Chuyển Quân Giới, An Dân.

## Language

**Thành**:
Căn cứ chính hoặc phân thành kiên cố của người chơi, có cấp độ, tài nguyên khoáng sản, kiến trúc nội thành và tường thành bảo vệ (ID dương).
_Avoid_: Thành trì (khi cần phân biệt với Doanh trại), base

**Doanh trại**:
Căn cứ dã ngoại hoặc đồn trú lưu động của người chơi trên bản đồ thế giới, có thể đóng quân, xuất kích đánh Man và di chuyển vị trí (ID âm hoặc định danh qua `lTentID`).
_Avoid_: Trại tạm, Trại Di Chuyển, camp, tent

**Võ tướng**:
Tướng chuyên về quân sự (loại 2), có chỉ số dũng võ, thể lực, sĩ khí; trực tiếp thống lĩnh binh mã xuất chinh dã ngoại, tham gia Thảo Phạt, Bình Man, Gọi Dân.
_Avoid_: Tướng võ, martial

**Văn quan**:
Tướng chuyên về mưu lược, nội chính và điều hành (loại 1), đảm nhiệm chức vụ Thái thú, nghiên cứu Kỹ Thuật Đại Học hoặc mưu sĩ hỗ trợ, không tham gia đánh ải Thảo Phạt.
_Avoid_: Văn tướng, mưu sĩ (khi chỉ chung văn chức)

**Di trại**:
Hành động dời Doanh trại dã ngoại từng bước trên bản đồ tọa độ về hướng mục tiêu trước khi xuất kích.
_Avoid_: Dời trại, di chuyển trại, relocate

**Tăng tốc**:
Hành động sử dụng đạo cụ (Lệnh bài tăng tốc / Vàng) để giảm thời gian hoặc hoàn tất tức thì một tiến trình nâng cấp công trình hoặc nghiên cứu.
_Avoid_: Speedup, cắn bùa tăng tốc

**Kích hoạt kiến trúc**:
Hành động kích hoạt hiệu ứng đặc quyền tăng 20% tốc độ xây dựng công trình trên toàn bộ các thành trong thời gian hiệu lực (`OPT.ashx?id=69, type=3`).
_Avoid_: Boost 20%, kích hoạt bonus

**Chuyển quân giới**:
Hoạt động điều chuyển binh lính (bộ binh, kỵ binh, cung binh) và khí tài giữa các Thành và Doanh trại của người chơi.
_Avoid_: Vận chuyển lính, gửi quân, logistics

**Man**:
Mục tiêu NPC trên bản đồ (trại quái) mà tướng xuất quân đánh, có loại (`man_type`) và `target_id`.
_Avoid_: Quái, monster

**Mục tiêu**:
Một Man cụ thể đang tồn tại trên bản đồ, định danh bằng `target_id`.
_Avoid_: Target (khi nói tiếng Việt), địch

**Gọi Dân**:
Hành động triệu hồi Man (gồm Dân thường `type=63` và Vong Linh `type=33`) về vị trí lân cận để đánh luyện tướng.
_Avoid_: Gọi man, summon

**Thảo Phạt**:
Chiến dịch tấn công các cứ điểm dã ngoại theo 8 cấp độ chiến dịch, chỉ sử dụng tối đa 5 Võ tướng.
_Avoid_: Đánh ải, càn quét

**Bình Man**:
Chế độ tự động quét và tấn công Man quanh Thành hoặc Doanh trại lưu động.

**Thiên Thành**:
Thành cấp 5 hoặc 6; vùng phụ cận quanh nó bị loại khỏi phạm vi quét đánh Man.

**Mid**:
Mã số định danh một ô trên bản đồ thế giới, tương ứng một tọa độ (x, y).
_Avoid_: Map ID, ô số

**Quét**:
Thu thập thông tin các Man và thực thể trong một vùng bản đồ ô lưới.
_Avoid_: Scan (khi nói tiếng Việt)

**Khóa mục tiêu**:
Đánh dấu tạm thời một Mục tiêu đã có nhiệm vụ nhận để nhiệm vụ khác không đánh trùng.
_Avoid_: Lock

**Trận hình**:
Thế trận xuất binh và giao chiến của đạo quân (Trùy hình, Câu hình, Kê hình, Hạc dực, Ngư lân) quyết định hiệu quả tương khắc ngũ hành.
_Avoid_: Đội hình

**Chiến trường**:
Không gian diễn ra trận giao chiến giữa quân ta và quân địch theo từng hiệp đấu.

**Bắt sống BOSS**:
Hành động giữ Tướng Chủ hoặc BOSS của quân địch (slot 19) sống đến cuối trận (sau khi tiêu diệt hết lính bảo vệ) để chiêu hàng hoặc bắt sống.

**An Dân**:
Hành động tế trời hoặc phát lương thực (`OPT.ashx?id=4`) khôi phục lòng dân và sĩ khí thành trì, triệt tiêu dân nộ để ngăn ngừa bạo loạn.
_Avoid_: Khuyên dân, vỗ về

**Kỹ Thuật Đại Học**:
29 công nghệ nâng cấp tại viện Đại Học quyết định sản lượng tài nguyên và năng lực tác chiến quân binh.
_Avoid_: Công nghệ, tech

**Binh Pháp**:
Đạo cụ tiêu hao giúp hoàn tất hoặc rút ngắn tức thì thời gian nghiên cứu Kỹ Thuật Đại Học (`OPT.ashx?id=180`).
_Avoid_: Sách tăng tốc

**Hàng Đợi Xây Dựng**:
Danh sách các công trình được người dùng tích chọn và sắp xếp thứ tự ưu tiên nâng cấp trong thành theo từng vị trí ô đất (`pid`).
_Avoid_: Queue xây, slot xây

**Hàng Đợi Nghiên Cứu**:
Danh sách các Kỹ Thuật Đại Học được tích chọn và xếp thứ tự ưu tiên nâng cấp tự động.

**Ngưỡng An Toàn**:
Ngưỡng thể lực hoặc quân số tối thiểu của Võ tướng; khi chạm ngưỡng này, đạo quân tự rút về thành mẹ để trị thương và bổ sung quân lực.
_Avoid_: Mức an toàn, return threshold

**Thời Gian Đóng Băng**:
Khoảng thời gian Doanh trại phải tạm dừng sau mỗi bước dời vị trí trước khi có thể dời tiếp hoặc xuất trận (`frozen_time`).
_Avoid_: Cooldown dời trại, frozen time

**Hồ Sơ Cấu Hình**:
File dữ liệu JSON duy nhất lưu trữ toàn bộ trạng thái thiết lập và quy hoạch tự động hóa của tất cả các phân hệ (Xây Dựng, Nghiên Cứu, Thảo Phạt, Bình Man, Gọi Dân, Hậu Cần).
_Avoid_: Config lẻ, file lưu cấu hình riêng, profile_settings

**Luyện Sĩ Khí**:
Hành động tăng điểm sĩ khí cho tướng tại Điểm Tướng Đài (`OPT.ashx?id=47`), mỗi lần tăng tối đa 10 điểm và có thời gian đếm ngược hoàn tất.
_Avoid_: Nâng sĩ khí, tăng morale, buff sĩ khí

**Biên Chế Quân Tự Động**:
Quy trình kiểm tra quân số tướng, tự động chiêu mộ tân binh và bổ sung binh lính theo loại quân chỉ định trước khi xuất kích.
_Avoid_: Bổ sung lính, refill lính, auto recruit

**Quy Hoạch Đa Căn Cứ**:
Thiết lập hàng đợi công trình độc lập cho từng Thành và Doanh trại, cho phép bot giám sát và tự động nâng cấp đồng thời nhiều căn cứ cùng lúc.
_Avoid_: Xây đa thành, multi-city queue

**Căn Cứ Thi Công**:
Thành hoặc Doanh trại được người chơi tích chọn tham gia tiến trình tự động nâng cấp công trình.
_Avoid_: Thành được chọn, active base

## Danh Mục Công Trình (Nhà)

Hệ thống tên kiến trúc song ngữ Trung - Việt chuẩn hóa theo ZBuild và ZMan:

| GID | Tên Kiến Trúc Chuẩn (ZBuild / ZMan) | Chức Năng |
|:---:|:---|:---|
| 1 | `官府 - Quan Phủ` | Trung tâm chỉ huy thành, mở khóa ô đất và công trình |
| 2 | `城墙 - Tường Thành` | Phòng thủ thành trì, xây cạm bẫy tên nỏ |
| 3 | `民房 - Nhà Dân` | Tăng trần dân số và sản lượng thuế |
| 4 | `仓库 - Kho` | Bảo vệ và dự trữ lương thực, tài nguyên |
| 5 | `鸿胪寺 - Hồng Lư Tự` | Thiết lập liên minh, bang hội và bang giao |
| 6 | `大学殿 - Đại Học Điện` | Nghiên cứu 29 Kỹ Thuật Đại Học |
| 7 | `客栈 - Quán Trọ` | Tiếp nhận và theo dõi tướng lang bạt |
| 8 | `酒馆 - Tửu Quán` | Chiêu mộ tướng tài bằng tiệc rượu |
| 9 | `聚贤楼 - Tụ Hiền Lâu` | Quản lý danh sách văn võ tướng của thành |
| 10 | `点将台 - Điểm Tướng Đài` | Điều binh phái tướng, biên chế đạo quân |
| 11 | `市场 - Chợ` | Mua bán tài nguyên, điều động xe buôn |
| 12 | `驿站 - Dịch Trạm` | Tăng tốc độ hành quân và chi viện |
| 13 | `兵器铺 - Xưởng Binh Khí` | Sản xuất vũ khí đao, thương, cung |
| 14 | `防具铺 - Xưởng Khôi Giáp` | Sản xuất áo giáp, khiên |
| 15 | `车马间 - Xưởng Ngựa` | Nuôi dưỡng và huấn luyện chiến mã |
| 16 | `校场 - Binh Trường` | Huấn luyện và mở rộng trần quân số |
| 17 | `营寨栅栏 - Tường` | Tường phòng thủ của Doanh trại |
| 18 | `中军大帐 - Trung Quân Đại Trướng` | Đầu não chỉ huy của Doanh trại |
| 19 | `营寨校场 - Binh Trường` | Doanh trại dã ngoại |
| 20 | `营寨驿站 - Dịch Trạm` | Trạm liên lạc của Doanh trại |
| 21 | `营寨仓库 - Kho` | Kho dã ngoại của Doanh trại |

