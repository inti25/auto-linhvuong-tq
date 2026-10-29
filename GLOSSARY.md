# LinhVuong

Công cụ tự động hóa (bot) cho game web Linh Vương, xây dựng và chuẩn hóa từ phân tích dịch ngược ZMan.exe và ZBuild.exe.
Phạm vi v1: Gọi Man, Thảo Phạt, Bình Man, Xây Dựng, Nghiên Cứu Kỹ Thuật, Chuyển Quân Giới, An Dân.

## Language

**Thành**:
Căn cứ chính hoặc phân thành kiên cố của người chơi, có cấp độ, tài nguyên khoáng sản, kiến trúc nội thành và tường thành bảo vệ (ID dương).
_Avoid_: Thành trì (khi cần phân biệt với Doanh trại), base

**Doanh trại**:
Căn cứ dã ngoại hoặc đồn trú lưu động của người chơi trên bản đồ thế giới, có thể đóng quân, xuất kích đánh Man và di chuyển vị trí (ID âm hoặc định danh qua `lTentID`).
_Avoid_: Trại tạm, Trại Di Chuyển, camp, tent

**Võ tướng**:
Tướng chuyên về quân sự (loại 2), có chỉ số dũng võ, thể lực, sĩ khí; trực tiếp thống lĩnh binh mã xuất chinh dã ngoại, tham gia Thảo Phạt, Bình Man, Gọi Man.
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

**DS kiến trúc** (Đại Sư Kiến Trúc / Kích hoạt kiến trúc):
Đặc quyền đạo cụ mở rộng hàng đợi thi công từ 1 công trình mặc định lên tối đa 3 công trình xây dựng cùng lúc (`OPT.ashx?id=69, type=3`), đồng thời tăng 20% tốc độ xây dựng. Thời hạn hiệu lực được kiểm tra qua trường `plus_finish` từ `Common.ashx?id=77`.
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

**Gọi Man**:
Hành động triệu hồi Man (gồm Dân thường `type=63` và Vong Linh `type=33`) về vị trí lân cận để đánh luyện tướng.
_Avoid_: Gọi dân, summon

**Võ tướng xuất kích**:
Các Võ tướng có vai trò võ quan (`role == "vo"`) được người chơi tích chọn tham gia đạo quân viễn chinh đánh Man, Gọi Man hoặc Thảo Phạt.
_Avoid_: Tướng đánh, active general, selected general

**Đợt xuất quân**:
Một lệnh xuất kích tấn công mục tiêu dã ngoại (`OPT.ashx?id=53`), mang tối đa 3 đạo quân (3 Võ tướng). Khi danh sách Võ tướng xuất kích vượt quá 3, hệ thống tự động chia thành nhiều đợt xuất quân liền nhau tới cùng một mục tiêu.
_Avoid_: Attack wave, đợt đánh

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

**Ưu Tiên Căn Cứ Gần Nhất**:
Quy tắc giải quyết xung đột mục tiêu trong Bình Man Đa Căn Cứ: Khi một Mục tiêu Man nằm trong phạm vi quét của nhiều Căn Cứ cùng lúc, quyền khóa và xuất kích được ưu tiên tuyệt đối cho Căn Cứ có cự ly gần Mục tiêu nhất.
_Avoid_: Gần nhất đánh trước, tranh mục tiêu

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
File dữ liệu JSON duy nhất lưu trữ toàn bộ trạng thái thiết lập và quy hoạch tự động hóa của tất cả các phân hệ (Xây Dựng, Nghiên Cứu, Thảo Phạt, Bình Man, Gọi Man, Hậu Cần).
_Avoid_: Config lẻ, file lưu cấu hình riêng, profile_settings

**Luyện Sĩ Khí**:
Hành động tăng điểm sĩ khí cho tướng tại Điểm Tướng Đài (`OPT.ashx?id=47`), mỗi lần tăng tối đa 10 điểm và có thời gian đếm ngược hoàn tất.
_Avoid_: Nâng sĩ khí, tăng morale, buff sĩ khí

**Luyện Sĩ Khí Đa Thành**:
Tính năng điều phối luyện sĩ khí đồng loạt cho tất cả tướng có quân đội đồn trú tại các Thành và Doanh trại khác nhau theo cơ chế vòng lặp chu kỳ (Tick Scheduler), tự động kích hoạt song song và lặp các nhịp 10 điểm cho đến khi chạm Sĩ Khí Mục Tiêu mà không bị giới hạn số luồng worker.
_Avoid_: Buff morale hàng loạt, train sĩ khí đa thành, nâng sĩ khí hàng loạt

**Đếm Ngược Luyện Sĩ Khí**:
Khoảng thời gian (tính bằng giây) một Võ tướng đang trong tiến trình nâng sĩ khí máy chủ (`upgrading_time > 0`); trong thời gian này cấm gửi thêm lệnh nâng để tránh phát sinh mã lỗi 40 hoặc bị hệ thống máy chủ nhận diện tự động hóa.
_Avoid_: Timer sĩ khí, thời gian nâng dở

**Giãn Cách Vi Mô**:
Khoảng trễ ngẫu nhiên (100ms - 250ms) chèn giữa các lệnh `OPT.ashx?id=47` gửi lên máy chủ trong cùng một nhịp kích hoạt đồng loạt nhằm phân tán gói tin và bảo vệ tài khoản khỏi cơ chế phát hiện bot theo tần suất.
_Avoid_: Sleep cứng, spam request

**Xuất Quân Sớm Theo Sĩ Khí**:
Cơ chế trong Thảo Phạt cho phép đạo quân xuất kích ngay khi lượt nâng sĩ khí cuối cùng đảm bảo đạt ngưỡng tối thiểu và thời gian đếm ngược còn lại nhỏ hơn hoặc bằng thời gian hành quân ($up\_t \le travel\_time$).
_Avoid_: Đi sớm, bỏ qua sĩ khí

**Định Mức Biên Chế**:
Quân số mục tiêu theo từng binh chủng (Bộ binh, Kỵ binh, Cung thủ) áp dụng chung cho các Võ tướng xuất kích của từng phân hệ; hệ thống chỉ bù phần quân số thiếu hụt và giữ nguyên nếu tướng đang mang nhiều quân hơn định mức.
_Avoid_: Mức lính mục tiêu, target army, biên chế cố định

**Biên Chế Quân Tự Động**:
Quy trình chuẩn bị quân lực trước khi xuất kích (Thảo Phạt, Bình Man, Gọi Man): trị thương Võ tướng, chiêu mộ tân binh tại Thành hoặc lấy từ quân đồn trú sẵn có tại Doanh trại để bù theo Định Mức Biên Chế, sau đó Luyện Sĩ Khí đạt ngưỡng tối thiểu.
_Avoid_: Bổ sung lính, refill lính, auto recruit

**Quy Hoạch Đa Căn Cứ**:
Thiết lập hàng đợi công trình độc lập cho từng Thành và Doanh trại, cho phép bot giám sát và tự động nâng cấp đồng thời nhiều căn cứ cùng lúc.
_Avoid_: Xây đa thành, multi-city queue

**Căn Cứ Thi Công**:
Thành hoặc Doanh trại được người chơi tích chọn tham gia tiến trình tự động nâng cấp công trình.
_Avoid_: Thành được chọn, active base

**Bình Man Đa Căn Cứ**:
Cơ chế tự động điều phối tiến trình Bình Man qua danh sách các Căn Cứ (Thành hoặc Doanh trại) được người chơi bật chạy, luân phiên kiểm tra trạng thái võ tướng, dời trại áp sát hoặc xuất kích theo hồ sơ cấu hình độc lập của từng căn cứ.
_Avoid_: Bình Man đa thành, multi-city binh man

**Căn Cứ Bình Man**:
Thành hoặc Doanh trại được người chơi tích chọn tham gia chiến dịch Bình Man tự động (`enabled = True`).
_Avoid_: Thành bình man, active binh man base

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
Cơ chế trên giao diện đăng nhập và thanh điều hướng cho phép lưu trữ và chuyển đổi nhanh giữa danh sách các tài khoản Linh Vương (kèm Server ID và Proxy riêng biệt tương ứng) mà không cần nhập lại thông tin thủ công.
_Avoid_: Account switcher, đổi acc, quản lý tài khoản

**Thanh Điều Hướng Tài Khoản**:
Khu vực menu dạng cột bên trái cửa sổ ứng dụng hiển thị danh sách các tài khoản đã lưu, kèm thẻ trạng thái hoạt động độc lập và nút ủng hộ tác giả.
_Avoid_: Account sidebar, menu trái, danh sách acc

**Ủng Hộ Tác Giả** (Buy Me A Coffee):
Nút bấm và cửa sổ tương tác (Modal Dialog) trên Thanh Điều Hướng Tài Khoản hiển thị mã QR thanh toán/ủng hộ (qrcode.webp) kèm thông điệp tri ân người dùng đã tin tưởng và đồng hành cùng dự án Auto Linh Vương.
_Avoid_: Nút donate, quét mã ủng hộ, donate button

**Không Gian Đa Tài Khoản**:
Cửa sổ ứng dụng hợp nhất vận hành song song nhiều phiên làm việc của các tài khoản Linh Vương khác nhau trên cùng một tiến trình duy nhất.
_Avoid_: Multi-account window, trình chạy đa acc, gộp cửa sổ

**Thẻ Tài Khoản**:
Thành phần giao diện trên Thanh Điều Hướng đại diện cho một tài khoản, hiển thị tên nhân vật, máy chủ, huy hiệu kết nối và trạng thái tác vụ tóm tắt.
_Avoid_: Account card, mục tài khoản, item acc

**Giao Diện Đăng Nhập Cục Bộ**:
Khung biểu mẫu nhập mật khẩu và cấu hình kết nối hiển thị trực tiếp trong Khung Làm Việc đối với tài khoản chưa kết nối phiên.
_Avoid_: In-workspace login, form đăng nhập con, login frame

**Đồng Bộ Dữ Liệu Thực Tế**:
Tiến trình tự động cập nhật cấp độ và trạng thái kiến trúc, kỹ thuật từ phản hồi của máy chủ về bộ nhớ và giao diện bot sau mỗi chu kỳ thi công mà không phát sinh thêm lệnh truy vấn dư thừa.
_Avoid_: Refresh dữ liệu, reload thực tế, fetch lặp

**Bảo Toàn Thứ Tự Ưu Tiên**:
Nguyên tắc bất biến duy trì chính xác vị trí sắp xếp của các đối tượng trong Hàng Đợi Xây Dựng và Hàng Đợi Nghiên Cứu qua các lần nạp dữ liệu thực tế, chuyển đổi căn cứ hoặc nạp hồ sơ cấu hình.
_Avoid_: Reset thứ tự, xếp lại theo server, auto-sort mặc định

**Nhật Ký Tác Vụ**:
Bản ghi tuần tự các sự kiện, hành động và kết quả thực thi của các phân hệ tự động hóa (Thảo Phạt, Bình Man, Gọi Dân, Xây Dựng, Nghiên Cứu, Hậu Cần) theo mốc thời gian thực.
_Avoid_: File log thô, console output

**Cắt Tỉa Nhật Ký**:
Cơ chế tự động giải phóng bộ nhớ bằng cách xóa một khối dòng nhật ký cũ nhất (batch pruning) trên giao diện khi đạt ngưỡng tối đa, và xoay vòng hoặc thanh lý các tệp log đã cũ trên ổ đĩa nhằm chống tràn RAM và làm chậm ứng dụng khi chạy dài hạn.
_Avoid_: Xóa log thủ công, purge log, trim log lẻ tẻ

**Quân Giới**:
Hệ thống trang thiết bị và khí giới quân sự gồm Binh khí (Đao, Thương, Cung, Kiếm, Kích), Khôi giáp (Giáp da, Giáp sắt, Chiến giáp), Chiến mã (Tuấn mã, Thiết kỵ) và Xe ném đá phục vụ việc chiêu mộ binh sĩ và gia tăng sức mạnh tác chiến của quân đội.
_Avoid_: Đồ lính, vũ khí thô, trang bị lính

**Chế Tạo Quân Giới**:
Tiến trình tự động điều phối lệnh sản xuất trang thiết bị quân sự định kỳ tại các công xưởng chuyên trách trong thành trì (Xưởng Binh Khí, Xưởng Khôi Giáp, Xưởng Ngựa) theo chỉ định về chủng loại, số lượng mẻ và chu kỳ lặp lại.
_Avoid_: Rèn vũ khí, đúc kiếm, mua đồ quân sự

**Ngưỡng Nhật Ký**:
Giới hạn số dòng tối đa trên khung hiển thị giao diện (mặc định 500 dòng cho tác vụ thường, 300 dòng cho chiến trường) hoặc dung lượng tệp log trên ổ đĩa (mặc định 2MB/tệp, giữ 3 bản sao và lưu giữ tối đa 7 ngày) trước khi kích hoạt Cắt Tỉa Nhật Ký.
_Avoid_: Max lines, log limit, dung lượng tối đa

**Vết Lỗi Thực Thi**:
Thông tin ngữ cảnh chi tiết (mã phản hồi máy chủ, tham số lệnh, vết ngăn xếp ngoại lệ) được ghi nhận khi phát sinh sự cố trong tiến trình tự động hóa nhằm phục vụ việc khoanh vùng nguyên nhân khi chạy dài hạn.
_Avoid_: Crash dump, log lỗi

**Quy Hoạch Theo Loại Công Trình**:
Cơ chế gom nhóm và điều phối thứ tự ưu tiên thi công theo từng chủng loại kiến trúc, cho phép thiết lập cấp mục tiêu chung và tự động nâng đồng đều các ô đất cùng loại.
_Avoid_: Gom nhóm nhà, group building, cây công trình

**Tự Động Kế Thừa Quy Hoạch Nhóm**:
Cơ chế tự động kết nạp các ô đất mới xây vào nhóm loại công trình tương ứng, tự động bật thi công và kế thừa cấp mục tiêu chung khi nhóm đó đang ở trạng thái chọn tất cả.
_Avoid_: Kế thừa cấp, auto inherit plot, tự add nhà

**Thành Nghiên Cứu**:
Thành trì được người chơi chỉ định (đánh dấu `NC` trên danh sách thành) làm trung tâm tiến hành nâng cấp 29 Kỹ Thuật Đại Học tại Đại Học Điện hoặc Thái Học Điện.
_Avoid_: Research city, thành học viện

**Ngưỡng Tài Nguyên**:
Mức Vàng tối thiểu và tỷ lệ phần trăm khoáng sản (Gỗ, Sắt, Đá, Thực) cài đặt làm mốc để bot tự động kiểm tra định kỳ và cắn mở rương tài nguyên khi số dư thực tế tụt xuống dưới ngưỡng.
_Avoid_: Resource threshold, mức khoáng sản

**Cấp Hiện Tại** (Cấp HT):
Cấp độ thực tế của công trình kiến trúc hoặc công nghệ kỹ thuật Viện Đại Học đang hiện hữu trên máy chủ game tại căn cứ được chọn. Đối với nhóm công trình đa ô đất khi thu gọn, Cấp HT thể hiện dải cấp độ từ ô thấp nhất đến ô cao nhất (`min - max`).
_Avoid_: Cấp thực tế, level hiện tại, current level

**Cấp Mục Tiêu** (Cấp MT):
Cấp độ mong muốn do người chơi thiết lập trong hàng đợi quy hoạch để bot tự động điều phối tiến trình nâng cấp (hoặc hạ cấp/dỡ bỏ) đạt tới.
_Avoid_: Cấp đích, target level, max level

**Trạng Thái Thi Công Mặc Định**:
Quy ước khi nạp công trình hoặc kỹ thuật mới (dữ liệu mặc định hoặc lấy từ server lần đầu), cột checkbox `Chạy` sẽ ở trạng thái chưa chọn (`☐` / uncheck / `enabled=False`) để người chơi chủ động lựa chọn công trình cần xây/nghiên cứu thay vì tự động bật tất cả.
_Avoid_: Check all mặc định, auto run all, bật sẵn

**Mở Rương Khi Toàn Bộ Thiếu Tài Nguyên**:
Chiến lược điều phối tài nguyên thông minh trong Hàng Đợi Xây Dựng: Khi một công trình báo thiếu tài nguyên (mã 32 hoặc 37), bot không mở rương ngay mà tạm thời chuyển sang công trình kế tiếp. Chỉ khi toàn bộ công trình hợp lệ trong lượt đều báo thiếu tài nguyên, bot mới mở đúng 1 rương tài nguyên và quay trở lại duyệt từ đầu hàng đợi theo đúng thứ tự ưu tiên.
_Avoid_: Mở rương tức thì, cắn rương liên tục, greedy box opening

**Động Cơ Tác Chiến**:
Bộ máy điều khiển và giám sát diễn biến chiến trường tập trung, hỗ trợ mọi hình thức giao tranh (Thảo Phạt, Bình Man, Gọi Man, hoặc giám sát độc lập qua `battle_id`), thay vì logic đơn lẻ phân tán theo từng nhiệm vụ.
_Avoid_: Battle controller riêng lẻ, script đánh trận

**Phương Thức Tấn Công Chi Tiết**:
Hành động chiến thuật được gửi qua `OPT.ashx?id=54` áp dụng cho từng đạo quân trong hiệp đấu, bao gồm: Phổ thông (1), Đơn chiến (2), Phòng ngự (3), Rút lui (4), Đột kích (10 - Kỵ binh), Mãnh công (11 - Bộ binh), Thủy công (12), Hỏa tiễn (13 - Cung thủ), Phản kích (14).
_Avoid_: Lệnh đánh, skill đánh thường

**Mưu Kế Chiến Trường**:
Các mưu lược đặc biệt được thi triển trong chiến trường thông qua `OPT.ashx?id=70`, gồm: Kim thiền thoát xác (92), Phản khách vi chủ (93), Quan môn tróc tặc (94), Cầm tặc cầm vương (95), Hủy bỏ trạng thái (96).
_Avoid_: Bùa chiến đấu, phép chiến trường

**Cửa Sổ Đổi Trận Cuối Hiệp**:
Quy tắc chỉ thực hiện đổi trận hình (`OPT.ashx?id=57`) ở 10~15 giây cuối của hiệp đấu (`bout_left <= 15s`), nhằm triệt tiêu khả năng đối phương quan sát và đổi trận ngược lại để phản khắc quân ta.
_Avoid_: Đổi trận đầu hiệp, đổi trận tức thì

**Tự Động Hủy Bỏ Trạng Thái**:
Cơ chế phản xạ tự động của bot: khi phát hiện đạo quân phe ta rơi vào trạng thái Hỗn loạn (`TrangThaiQuanDoi == 1`), bot lập tức kích hoạt mưu kế 96 ("Hủy bỏ trạng thái") để giải phóng hiệu ứng bất lợi và phục hồi năng lực chiến đấu bình thường.
_Avoid_: Tự cắn giải, auto cleanse

**Thích Ứng Binh Chủng**:
Cơ chế tự động phân tích và gán Phương Thức Tấn Công tối ưu tương ứng theo loại quân chiếm đa số của từng đạo quân (Cung thủ → Hỏa tiễn 13, Kỵ binh → Đột kích 10, Bộ binh/Xe → Mãnh công 11).
_Avoid_: Auto skill, ép chiêu chung

**Cô Lập BOSS**:
Chiến thuật tác chiến khi bật chế độ bắt sống danh tướng (`leave_boss_last`): Bot tập trung tiêu diệt toàn bộ các đạo lính bảo vệ phụ cận, và ngay khi chỉ còn lại duy nhất BOSS trên chiến trường, bot tự động chuyển toàn bộ quân ta sang thế Phòng ngự (3) và dừng tấn công để người chơi vào chiêu hàng.
_Avoid_: Giữ boss thụ động, không đánh boss từ đầu

**Rút Lui Khẩn Cấp**:
Quy tắc tự động kích hoạt mưu kế Kim thiền thoát xác (`OPT.ashx?id=70`, `lPlusFunc=92`) khi quân số hoặc thể lực của tướng rơi xuống dưới Ngưỡng An Toàn, nhằm rút lui bảo toàn 100% sĩ khí và quân lực còn lại mà không chịu phạt bại trận.
_Avoid_: Emergency retreat, chạy trốn

**Kho Lưu Trữ Hồ Sơ** (`ProfileStore`):
Module miền độc lập chịu trách nhiệm nạp, ghi nguyên tử (`atomic write-and-replace`), kiểm định lược đồ và chuyển đổi trạng thái của Hồ Sơ Cấu Hình tổng hợp (`auto_profile_{username}_{server_id}.json`) mà không phụ thuộc vào giao diện Tkinter, phục vụ dùng chung cho cả UI, CLI và bộ kiểm thử tự động.
_Avoid_: Config parser, profile manager, json helper

**Động Cơ Điều Phối Tác Vụ** (`AutomationEngine`):
Module điều hành vòng đời thực thi nền tập trung cho tất cả các phân hệ tự động hóa (Thảo Phạt, Xây Dựng, Nghiên Cứu, Bình Man, Gọi Man), quản lý luồng chạy ngầm, áp dụng Độ Trễ Ngẫu Nhiên, phát hiện và tạm dừng khi gặp Captcha qua một giao diện thống nhất duy nhất (`start`, `stop`, `status`, `resume`).
_Avoid_: ThreadManager, RunnerPool, task daemon

**Tác Vụ Tự Động Hóa** (`ExecutableTask`):
Seam chuẩn hóa cho mọi nhiệm vụ có thể thực thi tuần tự trong bot, cung cấp phương thức `run_step() -> str` và `reset()` để Động Cơ Điều Phối Tác Vụ có thể vận hành đa hình mà không cần biết chi tiết logic nội tại của từng nghiệp vụ.
_Avoid_: Runnable, TaskWrapper, WorkerJob

**Bể Proxy** (`ProxyPool`):
Module tập trung quản lý danh sách các Điểm Cầu Proxy được nạp từ URL hoặc tệp cấu hình, duy trì trạng thái hoạt động (Sống/Chết), độ trễ phản hồi và điều phối cấp phát proxy an toàn luồng cho toàn bộ phiên làm việc.
_Avoid_: ProxyList, ProxyArray, danh sách IP

**Điểm Cầu Proxy** (`ProxyEndpoint`):
Thực thể biểu diễn một địa chỉ proxy cụ thể gồm máy chủ (`host`), cổng (`port`), giao thức mạng (`http`/`socks5h`) và chứng thực truy cập (`username`, `password`), gắn liền với trạng thái kiểm định và độ trễ đo được.
_Avoid_: ProxyItem, ProxyAddress, chuỗi proxy

**Kiểm Tra Trạng Thái Proxy** (`ProxyHealthCheck`):
Tiến trình kiểm tra kết nối đồng thời đa luồng qua Điểm Cầu Proxy tới trực tiếp cổng xác thực của máy chủ game (`http://pass.dipan.com/`) với ngưỡng timeout chặt chẽ (3-5 giây) để loại trừ các proxy chết hoặc bị tường lửa game chặn.
_Avoid_: Ping proxy, test ip, proxy check

**Hoán Đổi Proxy Tự Động** (`ProxyFailover`):
Cơ chế tự động phát hiện lỗi gián đoạn kết nối proxy (`ProxyError`, `ConnectTimeout`) trong lúc bot đang vận hành, tức thì đánh dấu proxy hỏng, kích hoạt Điểm Cầu Proxy sống kế tiếp vào phiên kết nối và tự động thử lại yêu cầu dở dang.
_Avoid_: Chuyển proxy thủ công, restart session, switch proxy




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


## Danh Mục Man Tộc (Cấp Độ & Tên Tương Ứng)

Phân loại cấp độ Man và cứ điểm dã ngoại chuẩn hóa theo game Linh Vương và ZMan:

| Cấp Độ (`man_type`) | Tên Man Tộc Chuẩn | Đặc Điểm / Binh Chủng |
|:---:|:---|:---|
| 1 | `Uy Quốc` | Man cấp 1, binh lực cơ bản |
| 2 | `Tiên Ti` | Man cấp 2, kỵ xạ phương Bắc |
| 3 | `Ô Hoàn` | Man cấp 3, kỵ binh du mục |
| 4 | `Sơn Việt` | Man cấp 4, bộ binh sơn địa |
| 5 | `Khương Để` | Man cấp 5, quân Tây Lương thiện chiến |
| 6 | `Mạnh Hoạch` | Man cấp 6, bộ binh & tượng binh Nam Man |
| 7 | `Hung Nô` | Man cấp 7, thiết kỵ thảo nguyên |
| 8 | `Đột Quyết` | Man cấp 8, kỵ binh tinh nhuệ |
| 9 | `Long Phi` | Man cấp 9, tinh anh dã ngoại |
| 10 | `Hổ Báo Kỵ` | Man cấp 10, kỵ binh tối thượng |
| 301 | `Vong Linh` | Mục tiêu triệu hồi đặc biệt bằng Bùa Vong Linh (ID 268) |

