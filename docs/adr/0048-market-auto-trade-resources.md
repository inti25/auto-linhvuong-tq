# Tự Động Mua & Bán Tài Nguyên Qua Chợ Trong Giám Sát Tài Nguyên (Server 58+)

Status: accepted

## Bối cảnh

Trước đây, tác vụ định kỳ **Tài Nguyên** (`resource_monitor`) chỉ kiểm tra **Ngưỡng Tài Nguyên** (`gold_threshold` và `wood_pct`/`iron_pct`/`stone_pct`/`food_pct`) rồi mở rương Vàng / rương Tài Nguyên khi số dư tụt dưới ngưỡng. Trên **Server 58+** (`sg58.dipan.com`), theo kiến trúc REST + passthrough (ADR-0038):
- Đọc công trình thành qua `GET /api/building/list` (`m_lgid in {11 (Chợ), 64 (Tập Thị)}`, `m_llevel > 0`), thay cho `City.ashx?id=5` đã lỗi thời trên S58.
- Đọc sản lượng/kho/vàng qua `/api/resource/info` và `/api/city/info`, và chuyển thành trước khi mở rương qua `switch_city_verified` trong `gateway_city_context`.
- Các thao tác sàn Chợ đi qua `_p_marketPassthrough` tới `/GateWay/*.ashx`:
  - `Common.ashx?id=38` (`stab=1|2`, `type=1..4`, `tid`): top 10 đơn rao bán rẻ nhất (hoặc đơn của bản thân khi `stab=2`); trả về `false` nếu sàn trống.
  - `OPT.ashx?id=29` (`type=1..4`): giá trung bình hôm qua (trả số nguyên thô, vd `480` hoặc `-1` nếu chưa có lịch sử).
  - `OPT.ashx?id=9`: mua theo đơn (`tid`, `buyinprice`, `count`, `buyincount`, `seqno`, `seller`, `countprice`, `type3`). Lưu ý: trên endpoint này `ret=73` nghĩa là đơn hàng đang bận (`RET_ORDER_BUSY`), **không phải** Captcha.
  - `OPT.ashx?id=49`: treo đơn bán (`tid`, `type1`, `sellcount1`, `sellprice1`, `countprice1 = sellcount1 * sellprice1`).

## Quyết định

1. **Module miền dùng chung (`linhvuong/market.py`)**:
   - Đóng gói `CityMarketCache` (nhận diện `gid in {11, 64}` qua `gateway.building_list` có fallback `City.ashx?id=5`), đọc trạng thái kho/vàng S58, truy vấn sàn Chợ, mua (`buy_resource_from_market`), bán (`sell_resource_on_market`), và điều phối `process_city_resource_cycle`.
   - Các endpoint Chợ chỉ coi `ret == 110` là `CaptchaRequired`, giữ nguyên `ret == 73` là `RET_ORDER_BUSY` để bỏ qua đơn bận khi mua. Việc mở rương (`Common.ashx?id=48`) và `switch_city_verified` vẫn kiểm tra `(110, 73)` như các tác vụ khác.
2. **Thứ tự chu kỳ cho mỗi Thành**:
   - **Bước 1 — Bán tài nguyên dư** (khi bật `auto_sell_resource` và Thành có Chợ): áp dụng cho cả Gỗ, Sắt, Đá, Thực; kích hoạt khi `tồn kho > max_storage * S%` (hoặc `>= max_storage` khi `S == 100`), gom 1 đơn bán xuống mức `max(S - 10%, buy_pct, 0%)`. Nếu `buy_pct >= S%`, bỏ qua bán loại đó và cảnh báo 1 lần theo `(city_id, res_key)`. Giá treo khớp giá rẻ nhất trên sàn (fallback giá TB hôm qua `OPT.ashx?id=29`), kẹp trong biên động theo giờ CST/UTC+8 (`±10%` 08:00–24:00, `±5%` 00:00–08:00) giao với `[base//2, base*2]`, thử lại 1 lần ở giá TB hôm qua nếu `ret=74`.
   - **Bước 2 — Mở rương Vàng** nếu `money < gold_threshold` (trong `gateway_city_context` + `switch_city_verified`), và làm mới số vàng nếu sắp mua Chợ.
   - **Bước 3 — Mua bù thiếu qua Chợ** (khi bật `prefer_market_buy`, Thành có Chợ và thiếu `>= 1 đản = 1.000`): mua tối đa tới ngưỡng `buy_pct` trong phạm vi vàng hiện có & sức chứa kho còn lại; thành không có Chợ và Doanh Trại (`id <= 0`) bỏ qua mua Chợ.
   - **Bước 4 — Fallback mở 1 rương TN** nếu còn thiếu khoáng sản sau mua Chợ hoặc thành không dùng mua Chợ.
3. **Đồng bộ cấu hình & giao diện Desktop/Web**:
   - Mở rộng `ResourceProfile` (`prefer_market_buy`, `auto_sell_resource`, `sell_threshold_pct="90"`) tương thích ngược với profile cũ.
   - Tích hợp vào cả Desktop (`linhvuong/dashboard/`), Web Dashboard (`linhvuong/web/static/app.js`), và `linhvuong/runtime.py`, đổi nhãn nút/tự khởi động thành **`Tài Nguyên`**.

## Hệ quả

- Thành có Chợ hoặc Tập Thị tự cân đối mua/bán tài nguyên theo giá thị trường trước khi tiêu rương, hạn chế tràn kho và tận dụng vàng nhàn rỗi.
- Thành không có Chợ và Doanh Trại vẫn giữ hành vi mở rương mặc định không gián đoạn.
- Chuẩn hóa xử lý `ret=73` riêng cho sàn Chợ trên Server 58+ giúp tránh dừng oan tác vụ khi gặp đơn đang giao dịch (`正在交易`).
