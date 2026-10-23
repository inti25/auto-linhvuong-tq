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
Hành động dời Doanh trại dã ngoại từng bước trên bản đồ tọa độ về hướng mục tiêu trước khi xuất kích hoặc theo tọa độ chỉ định.
_Avoid_: Dời trại, di chuyển trại, relocate

**Di Trại Độc Lập**:
Hành động điều khiển Doanh trại dời vị trí tuần tự từng bước trên bản đồ tọa độ đến vị trí đích (X, Y) chỉ định mà không gắn liền với chu trình Bình Man.
_Avoid_: Dời trại thủ công, di chuyển trại tự do, camp navigation

**Lách Vật Cản**:
Cơ chế tự động dò tìm các ô phụ cận có cự ly Chebyshev gần đích nhất khi bước di chuyển thẳng của Doanh trại bị chặn bởi chướng ngại vật địa hình hoặc công trình (mã lỗi 39).
_Avoid_: Dò đường tránh vật cản, bypass obstacle, detour

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

**Hạ Cấp Công Trình**:
Hành động gửi lệnh giảm cấp độ công trình hoặc dỡ bỏ về cấp độ mong muốn (`OPT.ashx?id=65, type=2`).
_Avoid_: Giảm cấp, downgrade

**Dỡ Bỏ Công Trình**:
Quy trình hạ cấp công trình liên tục về cấp 0 để xóa bỏ hoàn toàn công trình khỏi ô đất (`pid`), giải phóng vị trí cho việc tái quy hoạch kiến trúc mới.
_Avoid_: Đập nhà, phá hủy, demolish

**Hoãn Kiểm Tra Công Trình**:
Cơ chế tự động đưa các công trình gặp mã lỗi 261 (bị chặn) hoặc 245 (chưa đủ điều kiện tiên quyết) xuống cuối hàng đợi duyệt trong các vòng lặp tiếp theo, ưu tiên thi công các công trình khác trước và tự động giải phóng khỏi danh sách hoãn ngay khi thi công thành công.
_Avoid_: Bỏ qua vĩnh viễn, skip queue, lặp lại lỗi đầu vòng

**Nâng Đồng Đều**:
Chế độ tự động điều phối thứ tự thi công công trình hoặc nghiên cứu kỹ thuật viện đại học ưu tiên các đối tượng có cấp độ hiện tại thấp nhất lên trước (`current_level` tăng dần), kết hợp sắp xếp ổn định (bảo toàn thứ tự hàng đợi khi bằng cấp độ) nhằm phát triển cân bằng hạ tầng công trình và năng lực công nghệ.
_Avoid_: Cân bằng cấp, level balance, round-robin



**Đạo Cụ Tài Nguyên**:
Vật phẩm dạng hòm/rương/đỉnh trong túi đồ của người chơi, khi mở sẽ cung cấp một lượng lớn tài nguyên xây dựng (Gỗ, Đá, Sắt, Lúa). Điển hình: Dân Sinh Bảo Đỉnh (ID: 24), Dân Sinh Chi Độc (ID: 16), Dân Sinh Chi Hạp (ID: 11), Dân Sinh Chi Nang (ID: 1), Bạch Kim Tài Nguyên Lễ Hộp (ID: 35).
_Avoid_: Hộp quà, bùa tài nguyên, resource chest

**Tự Động Mở Rương**:
Cơ chế tự động gửi lệnh mở đạo cụ tài nguyên qua API `Common.ashx?id=48` (`lBoxID`) ngay khi phát hiện căn cứ không đủ tài nguyên để tiến hành nâng cấp hoặc hạ cấp công trình.
_Avoid_: Cắn rương, auto open box

**Chu Kỳ Lặp**:
Khoảng thời gian nghỉ (đơn vị: Giây) giữa các lượt thực thi hoặc kiểm tra định kỳ của các tác vụ chạy nền (Thảo Phạt, Gọi Dân, Bình Man, Xây Dựng, Nghiên Cứu Kỹ Thuật), có ngưỡng sàn an toàn tối thiểu 3.0s.
_Avoid_: Tần suất, frequency, loop duration

**Độ Trễ Ngẫu Nhiên**:
Khoảng biến thiên thời gian ngẫu nhiên (± 1~2s) được cộng/trừ vào Chu Kỳ Lặp trước mỗi lượt chờ (`wait_cycle`), nhằm mô phỏng nhịp điệu thao tác của người thật và ngăn chặn các thuật toán phát hiện bot tự động từ phía máy chủ.
_Avoid_: Jitter, lag ngẫu nhiên, random sleep

**Hồ Sơ Tài Khoản Riêng Biệt**:
Tập tin cấu hình tổng hợp (`auto_profile_{username}_{server_id}.json`) được gắn định danh duy nhất cho từng tài khoản và máy chủ, lưu trữ toàn bộ trạng thái chọn căn cứ, hàng đợi quy hoạch công trình, kỹ thuật viện đại học và thiết lập chiến dịch riêng mà không bị ghi đè khi chạy song song nhiều tài khoản trong cùng một thư mục.
_Avoid_: Profile độc lập, file cấu hình riêng, isolated profile

**Trình Chuyển Đổi Tài Khoản**:
Tính năng trên giao diện đăng nhập cho phép lưu trữ và chuyển đổi nhanh giữa danh sách các tài khoản Linh Vương đã đăng nhập (kèm Server ID và Proxy riêng biệt tương ứng) mà không cần nhập lại thông tin thủ công.
_Avoid_: Account switcher, đổi acc, quản lý tài khoản

**Đồng Bộ Dữ Liệu Thực Tế**:
Tiến trình tự động cập nhật cấp độ và trạng thái kiến trúc, kỹ thuật từ phản hồi của máy chủ về bộ nhớ và giao diện bot sau mỗi chu kỳ thi công mà không phát sinh thêm lệnh truy vấn dư thừa.
_Avoid_: Refresh dữ liệu, reload thực tế, fetch lặp

**Bảo Toàn Thứ Tự Ưu Tiên**:
Nguyên tắc bất biến duy trì chính xác vị trí sắp xếp của các đối tượng trong Hàng Đợi Xây Dựng và Hàng Đợi Nghiên Cứu qua các lần nạp dữ liệu thực tế, chuyển đổi căn cứ hoặc nạp hồ sơ cấu hình.
_Avoid_: Reset thứ tự, xếp lại theo server, auto-sort mặc định

**Nhật Ký Tác Vụ**:
Bản ghi tuần tự các sự kiện, hành động và kết quả thực thi của các phân hệ tự động hóa (Thảo Phạt, Bình Man, Gọi Dân, Xây Dựng, Nghiên Cứu, Hậu Cần) theo mốc thời gian thực.
_Avoid_: File log thô, console output

**Vết Lỗi Thực Thi**:
Thông tin ngữ cảnh chi tiết (mã phản hồi máy chủ, tham số lệnh, vết ngăn xếp ngoại lệ) được ghi nhận khi phát sinh sự cố trong tiến trình tự động hóa nhằm phục vụ việc khoanh vùng nguyên nhân khi chạy dài hạn.
_Avoid_: Crash dump, log lỗi

**Quy Hoạch Theo Loại Công Trình**:
Cơ chế gom nhóm và điều phối thứ tự ưu tiên thi công theo từng chủng loại kiến trúc, cho phép thiết lập cấp mục tiêu chung và tự động nâng đồng đều các ô đất cùng loại.
_Avoid_: Gom nhóm nhà, group building, cây công trình

**Tự Động Kế Thừa Quy Hoạch Nhóm**:
Cơ chế tự động kết nạp các ô đất mới xây vào nhóm loại công trình tương ứng, tự động bật thi công và kế thừa cấp mục tiêu chung khi nhóm đó đang ở trạng thái chọn tất cả.
_Avoid_: Kế thừa cấp, auto inherit plot, tự add nhà

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
| 54 | `宫殿 - Cung Điện` | Đầu não chỉ huy Thiên Thành / Châu Thành (cấp cao của Quan Phủ) |
| 55 | `壁垒 - Bích Lũy` | Phòng thủ Thiên Thành (cấp cao của Tường Thành) |
| 56 | `高级民居 - Cao Cấp Dân Cư` | Nhà dân cao cấp (cấp cao của Nhà Dân) |
| 57 | `国库 - Quốc Khố` | Kho dự trữ cao cấp (cấp cao của Kho) |
| 58 | `使节殿 - Sứ Tiết Điện` | Sứ quán bang giao Thiên Thành (cấp cao của Hồng Lư Tự) |
| 59 | `太学殿 - Thái Học Điện` | Viện nghiên cứu 29 Kỹ Thuật Đại Học tại Thiên Thành / Châu Thành (cấp cao của Đại Học Điện) |
| 60 | `水镜庐 - Thủy Kính Lư` | Chiêu mộ và theo dõi danh tướng (cấp cao của Quán Trọ) |
| 61 | `酒肆 - Tửu Tứ` | Yến tiệc chiêu hiền đãi sĩ (cấp cao của Tửu Quán) |
| 62 | `幕僚邸 - Mạc Liêu Để` | Dinh thự quân sư, tướng lĩnh (cấp cao của Tụ Hiền Lâu) |
| 63 | `将帅府 - Tướng Soái Phủ` | Bộ chỉ huy quân sự (cấp cao của Điểm Tướng Đài) |
| 64 | `集市 - Tập Thị` | Chợ giao thương cao cấp (cấp cao của Chợ) |
| 65 | `中央驿所 - Trung Ương Dịch Sở` | Trung tâm trạm dịch cấp cao (cấp cao của Dịch Trạm) |
| 66 | `兵器司 - Binh Khí Ty` | Xưởng vũ khí cấp cao (cấp cao của Xưởng Binh Khí) |
| 67 | `防具司 - Phòng Cụ Ty` | Xưởng khôi giáp cấp cao (cấp cao của Xưởng Khôi Giáp) |
| 68 | `车马司 - Xa Mã Ty` | Trại ngựa chiến cấp cao (cấp cao của Xưởng Ngựa) |
| 69 | `督军场 - Đốc Quân Trường` | Doanh trại huấn luyện cao cấp (cấp cao của Binh Trường) |
