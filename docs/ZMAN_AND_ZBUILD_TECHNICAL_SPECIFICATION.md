# Báo Cáo Kỹ Thuật Đảo Ngược Toàn Diện: ZMan.exe & ZBuild.exe
**Hệ thống phân tích tự động hóa Game Web Linh Vương (Linh Vương Truyền Kỳ - Dipan.com)**

---

## 1. Tổng Quan Kiến Trúc & Nhận Diện Nhị Phân (Binary Architecture)

Cả hai phần mềm [`ZMan.exe`](file:///d:/Tools/AutoFixLic/ZMan.exe) và [`ZBuild.exe`](file:///d:/Tools/AutoFixLic/ZBuild.exe) đều được xây dựng bởi tác giả **Zee** nhằm tự động hóa các hoạt động vi mô và vĩ mô trong game Linh Vương.

### 1.1 Bảng So Sánh Thông Số Nhị Phân (Binary Profiling)

| Đặc tính kỹ thuật | `ZMan.exe` (Automation & Combat) | `ZBuild.exe` (City & Infrastructure) |
| :--- | :--- | :--- |
| **Kích thước file** | 14,759,975 bytes (~14.08 MB) | 14,609,356 bytes (~13.93 MB) |
| **Định dạng nhị phân** | PE32+ (x86-64 GUI Executable) | PE32+ (x86-64 GUI Executable) |
| **Compiler / Toolchain** | MSVC 14.44 (Visual Studio 2022) | MSVC 14.44 (Visual Studio 2022) |
| **Trình đóng gói** | PyInstaller 6.x CArchive | PyInstaller 6.x CArchive |
| **Python Runtime** | CPython 3.13.9 (64-bit) | CPython 3.13.9 (64-bit) |
| **Magic Cookie** | `MEI\x0c\x0b\x0a\x0b\x0e` | `MEI\x0c\x0b\x0a\x0b\x0e` |
| **File Entrypoint** | `ZMan.pyc` (Uncompressed: 1,163,617 bytes) | `ZBuild-nocaptcha.pyc` (Uncompressed: 379,314 bytes) |
| **Class điều khiển chính** | `LinhVuongApp` (422 methods) | `LinhVuongApp` (176 methods) |
| **GUI Framework** | Tkinter / Tcl/Tk 8.6 | Tkinter / Tcl/Tk 8.6 |
| **Cơ chế Licensing** | **Supabase RPC Gate** (`check_user_access`) | **Không có (Unprotected / Direct Login)** |
| **Phạm vi nghiệp vụ** | Chiến đấu, Thảo Phạt, Bình Man, Di Trại, Gọi Dân/Vong Linh, Tầm Bảo, Tu Luyện, Xếp trận, Vi điều khiển trận đánh (Tactical Boss Focus). | Nâng cấp công trình, Nghiên cứu Đại Học (29 Techs), Điều quân liên thành, An Dân, Tăng tốc (Binh Pháp/Boost), Di chuyển trại. |

```mermaid
graph TD
    subgraph "ZMan.exe Architecture"
        ZM_EXE["ZMan.exe"] --> ZM_BOOT["PyInstaller Bootloader (349 KB)"]
        ZM_EXE --> ZM_ARC["CArchive Overlay (14.4 MB)"]
        ZM_ARC --> ZM_PY["ZMan.pyc (1.16 MB)"]
        ZM_PY --> ZM_APP["LinhVuongApp Controller\n(422 Methods)"]
        ZM_APP --> ZM_LIC["Supabase License Gate\n(check_user_access)"]
        ZM_APP --> ZM_COMBAT["Combat Engine & Tactical Solver\n(Boss Index 19 Focus)"]
        ZM_APP --> ZM_SCAN["Map Scanning Engine\n(10 Parallel Workers)"]
    end

    subgraph "ZBuild.exe Architecture"
        ZB_EXE["ZBuild.exe"] --> ZB_BOOT["PyInstaller Bootloader (349 KB)"]
        ZB_EXE --> ZB_ARC["CArchive Overlay (13.9 MB)"]
        ZB_ARC --> ZB_PY["ZBuild-nocaptcha.pyc (379 KB)"]
        ZB_PY --> ZB_APP["LinhVuongApp Controller\n(176 Methods)"]
        ZB_APP --> ZB_DIRECT["Direct Login Flow\n(No Remote Gate)"]
        ZB_APP --> ZB_QUEUE["Construction & Upgrade Queue"]
        ZB_APP --> ZB_TECH["University Research Manager (29 Techs)"]
    end
```

---

## 2. Hệ Thống Xác Thực & Quản Lý Bản Quyền (Authentication & Licensing)

### 2.1 Cổng Xác Thực Game (Game Authentication Gateway)
Cả hai ứng dụng đều sử dụng chung giao thức HTTP Form POST tới máy chủ xác thực trung tâm của Dipan:
* **URL**: `http://pass.dipan.com/aspx/LoginAPI.aspx`
* **HTTP Method**: `POST`
* **Content-Type**: `application/x-www-form-urlencoded`
* **Request Body**:
  ```http
  LoginType1=0&UserName1={username}&Password1={password}&callback=http://sg{server_id}.dipan.com
  ```
* **Phản hồi & Xử lý (Response Handling)**:
  * Kiểm tra chuỗi unicode `登录成功` (Đăng nhập thành công) trong phản hồi.
  * Trích xuất Session Cookies: `uid` (User ID), `uname` (Tên tài khoản mã hóa), và thiết lập phiên làm việc `requests.Session()`.
  * Sau đó gửi GET tới `http://sg{server_id}.dipan.com/login` để kích hoạt session game.

### 2.2 Cổng Kiểm Soát Bản Quyền Từ Xa (Chỉ Có Trong `ZMan.exe`)
`ZMan.exe` tích hợp hệ thống kiểm tra bản quyền đám mây qua **Supabase PostgreSQL RPC**:
* **Endpoint**: `https://nurwoidqiueiieyirpbg.supabase.co/rest/v1/rpc/check_user_access`
* **HTTP Method**: `POST`
* **Headers**:
  ```http
  apikey: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im51cndvaWRxaXVlaWlleWlycGJnIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzE0MjU5NzcsImV4cCI6MjA4NzAwMTk3N30.uNyaTo92K6d8SgMkhrICpkHWf_BGjkKWcUF4FVsMWaA
  Authorization: Bearer <cùng chuỗi JWT trên>
  Content-Type: application/json
  ```
* **Request Body**:
  ```json
  {
    "p_username": "tên_đăng_nhập",
    "p_server": "id_server"
  }
  ```
* **Phản hồi**:
  ```json
  {
    "status": true,
    "exp": "2026-12-31" // hoặc "3000-12-31" biểu thị Vĩnh Viễn
  }
  ```
* **Cơ chế giám sát nền (`start_license_monitor`)**:
  * Chạy daemon thread gọi `_check_license_silent()` định kỳ.
  * Nếu số lần thất bại vượt quá `license_max_fail`, hàm `_force_logout()` được kích hoạt: dừng toàn bộ luồng worker, hủy danh sách tác vụ đang chạy, hủy HTTP Session và đưa giao diện về màn hình đăng nhập.

> **Đặc biệt lưu ý**: Trong `ZBuild.exe` (entrypoint `ZBuild-nocaptcha.pyc`), toàn bộ mã nguồn gọi Supabase đã được lược bỏ hoàn toàn, cho phép người chơi đăng nhập trực tiếp không qua kiểm tra bản quyền.

---

## 3. Danh Mục Chi Tiết API Gateway (Complete API Specification)

Tất cả các lệnh điều khiển game được gửi tới cổng `http://sg{server_id}.dipan.com/GateWay/{Handler}.ashx?id={ID}`.

### 3.1 Nhóm API Thông Tin Chung (`Common.ashx`)

| API & ID | Method | Phương Thức Gọi | Request Body / Query Params | Cấu Trúc Response | Ứng Dụng |
| :--- | :---: | :--- | :--- | :--- | :---: |
| **`Common.ashx?id=2`** | `POST` | `get_item_count_from_warehouse` | `nid={item_nid}&_=` | `{"ret": 0, "list": [{"id": ..., "count": ...}]}` | `ZMan` |
| **`Common.ashx?id=16`** | `POST` | `fetch_army_data` | `tid={city_id}&_=` | `{"ret": 0, "list": [{"gid": <army_id>, "count": <num>}]}` | `ZBuild` |
| **`Common.ashx?id=24`** | `POST` | `save_equipment_data`, `check_and_reequip` | `lType={type}&_=` | `{"ret": 0, "list": [{"id": ..., "name": ..., "attrs": ...}]}` | `ZMan` |
| **`Common.ashx?id=27`** | `POST` | `get_resource_info_from_api27`, `_call_api_check_recruits` | `tid={city_id}&_=` | `{"ret": 0, "list": [{"type": "ngua/giap/cung", "count": ...}]}` | `ZMan` |
| **`Common.ashx?id=29`** | `POST` | `_get_gold_info` | `_=` | `{"ret": 0, "data": {"gold": <so_vang>, "uid": ..., "level": ...}}` | Cả hai |
| **`Common.ashx?id=32`** | `POST` | `get_all_generals_info`, `fetch_all_generals_for_training`, `get_wounded_generals` | `_=` | `{"ret": 0, "list": [{"id": ..., "name": ..., "type": 1|2, "stamina": ..., "morale": ..., "city_id": ...}]}` | `ZMan` |
| **`Common.ashx?id=40`** | `POST` | `get_movement_info`, `get_goto_duration`, `wait_for_generals_to_arrive` | `tid={city_id}&_=` | `{"ret": 0, "list": [{"goto": [{"duration": ..., "generals": [...]}], "come": [...], "battle": [...]}]}` | `ZMan` |
| **`Common.ashx?id=48`** | `POST` | `_open_box` | `lBoxID={box_id}&_=` | `{"ret": 0, "msg": "..."}` | Cả hai |
| **`Common.ashx?id=49`** | `GET` | `get_attack_duration` | `strDestName={name}&lDestX={x}&lDestY={y}&lType=1&lGeneralID1={g1}&lGeneralID2={g2}&lGeneralID3={g3}&lBout=-1` | `{"ret": 0, "data": {"duration": <so_giay>}}` | `ZMan` |
| **`Common.ashx?id=55`** | `POST` | `_perform_relocate`, `move_camp_to_position` | `lDestX={x}&lDestY={y}&lTentID={tent_id}&_=` | `{"ret": 0, "frozen": <thoi_gian_dong_bang>}` (ret=39: vướng ô, 40: thiếu tài nguyên, 41: quá xa, 42: đóng băng) | Cả hai |
| **`Common.ashx?id=73`** | `POST` | `_solve_captcha_random` | `_=` | `{"ret": 0, "data": {"images": [id1, id2, id3, id4]}}` | Cả hai |
| **`Common.ashx?id=76`** | `POST` | `get_api76_data`, `final_check_comprehensive` | `_=` | `{"ret": 0, "list": [{"city_id": ..., "morale": ..., "generals": [...]}]}` | `ZMan` |
| **`Common.ashx?id=77`** | `POST` | `_get_all_cities_upgrade_status`, `_check_building_boost_time` | `cid={city_id_hoac_0}&_=` | `{"ret": 0, "list": [{"slot": ..., "bid": ..., "time_left": ..., "plus_finish": ...}]}` | Cả hai |
| **`Common.ashx?id=80`** | `POST` | `move_camp_towards_target` | `tid={camp_id}&_=` | `{"ret": 0, "path": [...]}` | `ZMan` |
| **`Common.ashx?id=147`** | `POST` | `_check_tribute_status` | `_=` | `{"ret": 0, "status": 0|1}` | Cả hai |

---

### 3.2 Nhóm API Thành Trì & Bản Đồ (`City.ashx`, `Map.ashx`, `Build.ashx`)

| API & ID | Method | Phương Thức Gọi | Request Body / Query Params | Cấu Trúc Response | Ứng Dụng |
| :--- | :---: | :--- | :--- | :--- | :---: |
| **`City.ashx?id=5`** | `POST` | `fetch_buildings`, `_get_real_buildings_for_city` | `tid={city_id}&_=` | `{"ret": 0, "buildings": [{"pid": <slot>, "gid": <loai_nha>, "level": <cap>}]}` | Cả hai |
| **`City.ashx?id=6`** | `POST` | `_get_current_gold`, `_check_city_morale` | `tid={city_id}&_=` | `{"ret": 0, "data": {"morale": 100, "anger": 0, "gold": ...}}` | Cả hai |
| **`City.ashx?id=7`** | `POST` | `fetch_cities`, `_fetch_tent_position` | `_=` | `{"ret": 0, "citys": [{"id": ..., "name": ..., "x": ..., "y": ...}], "tents": [...]}` | Cả hai |
| **`City.ashx?id=20`** | `POST` | `_check_city_resources` | `tid={city_id}&_=` | `{"ret": 0, "data": {"wood": ..., "stone": ..., "iron": ..., "food": ...}}` | Cả hai |
| **`City.ashx?id=37`** | `POST` | `_check_tech_status` | `ttid=0&_=` | `{"ret": 0, "tech": {"techid": ..., "time_left": ...}}` | Cả hai |
| **`City.ashx?id=50`** | `POST` | `_switch_to_city` | `tid={city_id}&_=` | `{"ret": 0}` | Cả hai |
| **`Map.ashx?id=6`** | `POST` | `scan_map_logic`, `_scan_map_with_retry` | `mid={mapid}&_=` | `{"ret": 0, "npc_tent": [...], "citys": [...], "tents": [...], "users": [...], "infos": [...]}` | `ZMan` |
| **`Build.ashx?id=2`** | `POST` | `_get_tech_list_and_levels` | `pid=8&gid=1&tab=2&tid={city_id}&_=` | `{"ret": 0, "list": [{"id": <tech_id>, "name": ..., "level": <cur_level>, "max_level": ...}]}` | Cả hai |

---

### 3.3 Nhóm API Điều Hành Tác Chiến & Quân Sự (`OPT.ashx`)

| API & ID | Method | Phương Thức Gọi | Request Body (Form / JSON Key-Map) | Cấu Trúc Response | Ứng Dụng |
| :--- | :---: | :--- | :--- | :--- | :---: |
| **`OPT.ashx?id=4`** | `POST` | `_comfort_city` | `lType={1:TếTrời, 2:PhátLương}&tid={city_id}&_=` | `{"ret": 0}` | Cả hai |
| **`OPT.ashx?id=5`** | `POST` | `assign_advisor_to_general` | `lGeneralID={advisor_id}&lType=3&lFollowGeneralID={general_id}&lCityID={city_id}&_=` | `{"ret": 0}` | `ZMan` |
| **`OPT.ashx?id=6`** | `POST` | `_call_api_recruit_soldiers` | `lGeneralID={general_id}&lSoldierType={type}&lAmount={count}&tid={city_id}&_=` | `{"ret": 0}` | `ZMan` |
| **`OPT.ashx?id=24`** | `POST` | `get_battle_info` | `battleid={battle_id}&_=` | `{"ret": 0|13, "data": {"bout": ..., "our_troops": [...], "enemy_troops": [...]}}` (ret=13: trận đánh kết thúc) | `ZMan` |
| **`OPT.ashx?id=31`** | `POST` | `heal_single_general` | `lCityTentID={city_id}&lGeneralID={general_id}&_=` | `{"ret": 0}` | `ZMan` |
| **`OPT.ashx?id=39`** | `POST` | `balance_troops_in_camp_with_campid` | `campid={camp_id}&_=` | `{"ret": 0}` | `ZMan` |
| **`OPT.ashx?id=41`** | `POST` | `_call_api_buy_recruits` | `lAmount={count}&tid={city_id}&_=` | `{"ret": 0}` | `ZMan` |
| **`OPT.ashx?id=44`** | `POST` | `_research_technology` | `techid={tech_id}&tid={city_id}&_=` | `{"ret": 0}` | Cả hai |
| **`OPT.ashx?id=48`** | `POST` | `_sell_equipment` | `type={equip_id}&count={count}&price={price}&tid={city_id}&_=` | `{"ret": 0}` | Cả hai |
| **`OPT.ashx?id=50`** | `POST` | `dispatch_generals_with_retry` | `lCityID={from_city}&lGeneralID={general_id}&lDestID={to_tent_id}&_=` | `{"ret": 0}` | `ZMan` |
| **`OPT.ashx?id=52`** | `POST` | `_perform_transfer_army` | `dest={to_city}&tid={from_city}&gid={army_id}&gamount={amount}&times=1&Food=0&Wood=0&Stone=0&Iron=0&Money=0&_=` | `{"ret": 0}` | `ZBuild` |
| **`OPT.ashx?id=53`** | `POST` | `attack_logic` | `lDestID={target_id}&lType={type}&lGeneralID1={g1}&lGeneralID2={g2}&lGeneralID3={g3}&lBout=-1&lTarget1GID=0&lTarget2GID=0&lTarget3GID=0&lPlusFuncID=0&lPlusDestID=0&tid={city_id}&_=` | `{"ret": 0}` | `ZMan` |
| **`OPT.ashx?id=54`** | `POST` | `control_battle_units` | `battleid={battle_id}&posid={our_pos}&action=1&destposid={target_pos}&_=` | `{"ret": 0}` | `ZMan` |
| **`OPT.ashx?id=57`** | `POST` | `change_formation` | `lGeneralID={g_id}&lRatioAttack=0&lRatioPK=0&lRatioStra=100&lBattleArray={formation_id}&lWithdrawLoss=0&lWithdrawMorale=0&_=` | `{"ret": 0}` | `ZMan` |
| **`OPT.ashx?id=58`** | `POST` | `_equip_item` | `lCityTentID={city_id}&lGeneralID={general_id}&lEquipType={type}&lEquipID={id}&_=` | `{"ret": 0}` | `ZMan` |
| **`OPT.ashx?id=62`** | `POST` | `send_thaophat_request` | `taskid={task_id}&counts={count}&general1={g1}&general2={g2}&general3={g3}&general4={g4}&general5={g5}&tid={city_id}&_=` | `{"ret": 0}` | `ZMan` |
| **`OPT.ashx?id=63`** | `POST` | `_daily_reward_worker` | `_=` | `{"ret": 0}` | Cả hai |
| **`OPT.ashx?id=65`** | `POST` | `_upgrade_building_for_city_new` | `pid={slot_pid}&gid={building_gid}&type={1:Nâng, 2:Hạ}&tid={city_id}&_=` | `{"ret": 0}` | Cả hai |
| **`OPT.ashx?id=69`** | `POST` | `_perform_speedup` | `type=1&param1={city_id}&param2={slot}&paytype={paytype}&_=` | `{"ret": 0}` | Cả hai |
| **`OPT.ashx?id=69`** | `POST` | `_activate_building_boost` | `type=3&param1=0&param2=0&paytype=2` | `{"ret": 0}` | Cả hai |
| **`OPT.ashx?id=69`** | `POST` | `call_man_with_item_goidan` | `{"type": 63, "param1": target_id, "param2": mid, "paytype": 1, "_": ""}` | `{"ret": 0}` | `ZMan` |
| **`OPT.ashx?id=69`** | `POST` | `task_worker_goidan_vonglinh` | `{"type": 33, "param1": 268, "param2": 0, "paytype": 1, "_": ""}` | `{"ret": 0}` (ret=209: bận, 0: thành công) | `ZMan` |
| **`OPT.ashx?id=69`** | `POST` | `_call_mienchien_api` | `type=26&param1=0&param2={duration}&paytype=1&_=` | `{"ret": 0}` | `ZMan` |
| **`OPT.ashx?id=100`** | `POST` | `call_tambao_api` | `DestMapID={mid}&HeroID={hero_id}&tid={city_id}&_=` | `{"ret": 0}` | `ZMan` |
| **`OPT.ashx?id=101`** | `POST` | `withdraw_general` | `BattleID={battle_id}&General={general_id}&Act=2&_=` | `{"ret": 0}` | `ZMan` |
| **`OPT.ashx?id=102`** | `POST` | `_submit_captcha_random` | `num={image_id}&_=` | `{"ret": 0}` | Cả hai |
| **`OPT.ashx?id=178`** | `POST` | `_call_training_api` | `{"lType": <type>, "lPos": <pos>, "lHeroID": <id>, "_": ""}` | `{"ret": 0}` | `ZMan` |
| **`OPT.ashx?id=180`** | `POST` | `_use_art_of_war` | `_=` | `{"ret": 0}` | `ZBuild` |

---

## 4. Lưu Đồ Luồng Xử Lý Chức Năng (Detailed Function Flows)

### 4.1 Luồng Khởi Tạo & Đăng Nhập Hệ Thống (Login Flow)

```mermaid
sequenceDiagram
    autonumber
    actor User as Người dùng
    participant App as LinhVuongApp
    participant Gate as pass.dipan.com (LoginAPI)
    participant Game as sg{sv}.dipan.com (Gateway)
    participant Supa as Supabase RPC (ZMan only)

    User->>App: Nhập Server, Username, Password
    App->>Gate: POST /aspx/LoginAPI.aspx (UserName1, Password1, callback)
    Gate-->>App: Trả về Set-Cookie (uid, uname) + Redirect
    App->>Game: GET /login (Handshake & Activate Session)
    
    alt Đối với ZMan.exe
        App->>Supa: POST /rpc/check_user_access (p_username, p_server)
        alt Không hợp lệ / Hết hạn
            Supa-->>App: {"status": false}
            App-->>User: "Tài khoản chưa được cấp phép sử dụng!" -> Logout
        else Hợp lệ
            Supa-->>App: {"status": true, "exp": "3000-12-31"}
            App->>App: Khởi động start_license_monitor daemon thread
            App->>Game: Fetch Thành Trì, Tướng, Khoáng sản
        end
    else Đối với ZBuild.exe
        Note over App: Bỏ qua kiểm tra bản quyền (No-Captcha / Direct)
        App->>Game: Fetch Thành Trì, Công Trình, Hàng đợi xây dựng
    end
```

---

### 4.2 Luồng Xây Dựng & Nâng Cấp Công Trình (`ZBuild.exe`)

```mermaid
graph TD
    A["Bắt đầu vòng lặp xây dựng (_building_worker_new)"] --> B["Lấy danh sách thành được chọn (sync_selected_cities)"]
    B --> C["Kiểm tra hàng đợi nâng cấp hiện tại (Common.ashx?id=77)"]
    C --> D{"Số lượng slot nâng cấp còn trống?"}
    D -- "Đầy slot (Busy)" --> E["Chờ 10 - 30 giây"] --> C
    D -- "Còn slot trống" --> F["Lấy danh sách công trình thực tế (City.ashx?id=5)"]
    F --> G["Khớp nối với danh sách cấu hình người dùng (GID plans)"]
    G --> H["Sắp xếp độ ưu tiên công trình (_prioritize_building_tasks)"]
    H --> I["Kiểm tra tài nguyên Thành: Gỗ, Đá, Sắt, Lúa (City.ashx?id=20)"]
    I --> J{"Đủ tài nguyên?"}
    J -- "Thiếu tài nguyên" --> K["Tự động An Dân (OPT.ashx?id=4) hoặc bỏ qua"]
    J -- "Đủ tài nguyên" --> L["Gửi lệnh nâng cấp (OPT.ashx?id=65, pid, gid, type=1)"]
    L --> M{"Cấu hình tự động tăng tốc?"}
    M -- "Bật Speedup" --> N["Gọi OPT.ashx?id=69 (type=1, slot, paytype)"]
    M -- "Không bật" --> O["Cập nhật Treeview giao diện"]
    N --> O
    O --> E
```

---

### 4.3 Luồng Nghiên Cứu Kỹ Thuật Đại Học (29 Technologies - `ZBuild.exe`)

```mermaid
graph TD
    A["Khởi động luồng nghiên cứu (_check_tech_status)"] --> B["Gửi City.ashx?id=37 (ttid=0)"]
    B --> C{"Có kỹ thuật đang nghiên cứu?"}
    C -- "Đang nghiên cứu" --> D{"Cấu hình dùng Binh Pháp?"}
    D -- "Có" --> E["Gửi OPT.ashx?id=180 (Sử dụng Binh Pháp tăng tốc)"] --> F["Chờ thời gian hoàn tất"]
    D -- "Không" --> F
    C -- "Đang rảnh" --> G["Gọi Build.ashx?id=2 lấy cấp độ 29 công nghệ"]
    G --> H["So khớp với cây kỹ thuật mục tiêu (Tech Target Levels)"]
    H --> I["Chọn kỹ thuật có mức ưu tiên cao nhất chưa đạt cấp đích"]
    I --> J["Chuyển focus về Thành Nghiên Cứu (City.ashx?id=50)"]
    J --> K["Gửi lệnh nghiên cứu OPT.ashx?id=44 (techid, tid)"]
    K --> L["Cập nhật trạng thái hiển thị giao diện UI"]
```

---

### 4.4 Luồng Quét Bản Đồ & Định Tọa Độ 2D Geometry (`ZMan.exe`)

Hệ thống lưới tọa độ game Linh Vương được ánh xạ phẳng với tâm $(0, 0)$ ứng với Map ID $\text{mid} = 861.985$:
$$\text{mid} = y \times 1.313 + x + 861.985$$
$$x = ((\text{mid} - 1) \pmod{1313}) - 656, \quad y = \lfloor(\text{mid} - 1) / 1313\rfloor - 656$$

```mermaid
graph TD
    A["Yêu cầu quét: Tâm (x, y) & Bán kính R"] --> B["Tính danh sách MID các vòng tròn đồng tâm (find_target_circles)"]
    B --> C["Chia tải cho 10 Parallel Worker Threads"]
    C --> D["Gửi Map.ashx?id=6 (mid, _)"]
    D --> E{"HTTP Status?"}
    E -- "503 Server Busy" --> F["Exponential Backoff Retry (1s, 2s, 4s)"] --> D
    E -- "200 OK" --> G["Parser JSON: npc_tent, citys, tents, users, infos"]
    G --> H["Lọc mục tiêu theo loại (Man, Vong Linh, Tướng cướp)"]
    H --> I["Kiểm tra vùng cấm (Thiên Thành cấp 5, 6)"]
    I --> J["Cơ chế khóa mục tiêu cục bộ (try_lock_target_id)"]
    J --> K["Lưu kết quả ra bộ nhớ và file man.txt"]
```

---

### 4.5 Luồng Chiến Đấu Tự Động & Thảo Phạt (`ZMan.exe`)

```mermaid
graph TD
    A["Bắt đầu Thảo Phạt (send_thaophat_request)"] --> B["Kiểm tra quân lương, thể lực, quân số tướng (Common.ashx?id=76)"]
    B --> C["Gửi lệnh xuất kích (OPT.ashx?id=62: taskid, g1..g5)"]
    C --> D["Truy vấn thời gian hành quân (Common.ashx?id=40)"]
    D --> E["Chờ đạo quân tiếp cận chiến trường"]
    E --> F["Vòng lặp kiểm tra trạng thái chiến trận (OPT.ashx?id=24)"]
    F --> G{"Phản hồi API id=24?"}
    G -- "ret == 13" --> H["Chiến trường kết thúc (Thắng / Bại)"]
    G -- "ret == 0 (Đang đánh)" --> I["Thuật toán điều khiển chiến thuật (control_battle_units)"]
    
    subgraph "Vi Điều Khiển Chiến Trường (Tactical Solver)"
        I --> J["Định vị Boss quân địch tại Slot Index 19"]
        J --> K{"Có quân ta trong tầm đánh Boss?"}
        K -- "Có" --> L["Gửi OPT.ashx?id=54 (destposid=19: Tập trung diệt Boss)"]
        K -- "Không" --> M["Gửi OPT.ashx?id=54 (Tiêu diệt lính bảo vệ phụ cận)"]
        L --> N{"Thể lực / Quân số tướng chạm ngưỡng rút lui?"}
        M --> N
        N -- "Chạm ngưỡng nguy hiểm" --> O["Gửi OPT.ashx?id=101 (Rút lui khẩn cấp: Act=2)"]
        N -- "An toàn" --> P["Đổi trận hình tương khắc (OPT.ashx?id=57)"]
    end
    
    P --> F
    H --> Q["Tự động trị thương danh tướng (OPT.ashx?id=31)"]
    Q --> R["Bổ sung tân binh vào đội hình (OPT.ashx?id=6)"]
    R --> S["Xoay tua Mưu Sĩ hồi thể lực (OPT.ashx?id=5)"]
```

---

### 4.6 Luồng Bình Man & Doanh Trại Lưu Động (Trại Di Chuyển)

```mermaid
graph TD
    A["Khởi động Bình Man quanh Trại"] --> B["Quét tìm Man hợp lệ quanh Trại (Bán kính R)"]
    B --> C{"Tìm thấy mục tiêu trong tầm đánh (Khoảng cách <= 2 ô)?"}
    C -- "Đã trong tầm" --> D["Khóa mục tiêu (try_lock_target_id)"]
    D --> E["Tấn công Man trực diện (OPT.ashx?id=53: lDestID, g1..g3)"]
    E --> F["Theo dõi trận đánh qua API id=24 đến khi kết thúc"]
    
    C -- "Mục tiêu ở xa (> 2 ô)" --> G["Tính toán vector di chuyển từng bước tới tọa độ mục tiêu"]
    G --> H["Gửi lệnh dời Trại (Common.ashx?id=55: lDestX, lDestY, lTentID)"]
    H --> I{"Kết quả dời trại?"}
    I -- "ret == 0" --> J["Chờ hết thời gian đóng băng (frozen_time)"] --> C
    I -- "ret == 39 (Vướng chướng ngại)" --> K["Dò bước phụ / Giảm bước nhảy"] --> H
    I -- "ret == 42 (Đang đóng băng)" --> L["Chờ đóng băng kết thúc"] --> H
```

---

### 4.7 Luồng Triệu Hồi: Gọi Dân & Gọi Vong Linh (`ZMan.exe`)

```mermaid
graph TD
    A["Khởi động Task Gọi Dân / Gọi Vong Linh"] --> B{"Loại Task?"}
    
    B -- "Gọi Dân Thường" --> C["Chọn vị trí (x, y) trống gần thành"]
    C --> D["Tính Map ID: mid = get_mid_from_coords(x, y)"]
    D --> E["Tạo payload: type=63, param1=target_id, param2=mid, paytype=1"]
    E --> F["Gửi OPT.ashx?id=69 kích hoạt gọi quái"]
    
    B -- "Gọi Vong Linh (ID=301)" --> G["Chuyển focus về Thành chính (City.ashx?id=50)"]
    G --> H["Kiểm tra đạo cụ gọi Vong Linh (ID=268) trong kho"]
    H --> I["Gửi OPT.ashx?id=69: type=33, param1=268, param2=0, paytype=1"]
    I --> J{"Kết quả phản hồi?"}
    J -- "ret == 209 (Vong Linh đang bận)" --> K["Chờ 30s thử lại"] --> I
    J -- "ret == 0 (Thành công)" --> L["Quét map tìm vị trí Vong Linh vừa xuất hiện"]
    
    F --> M["Quét bản đồ phát hiện quái vừa xuất hiện"]
    L --> M
    M --> N["Khóa mục tiêu và xuất quân tiêu diệt (OPT.ashx?id=53)"]
```

---

## 5. Kết Luận & So Sánh Nghiệp Vụ

1. **`ZBuild.exe`**: Được thiết kế chuyên biệt cho việc **phát triển cơ sở hạ tầng (Macro & City Management)**:
   * Giữ thành trì luôn đầy tài nguyên và không bị bạo loạn (tự động an dân).
   * Tối ưu hóa chuỗi nâng cấp nhà và nghiên cứu 29 kỹ thuật liên tục 24/7.
   * Bản dựng này **không bị ràng buộc bởi hệ thống bản quyền Supabase**, hoàn toàn độc lập và nhẹ tải.

2. **`ZMan.exe`**: Là công cụ **tác chiến và cày cuốc vi mô chuyên sâu (Micro Combat & Campaign Bot)**:
   * Khả năng quét map song song cực mạnh với 10 threads.
   * Tự động điều khiển chiến trường thời gian thực, có thuật toán tập trung hỏa lực bắt sống hoặc tiêu diệt Boss (slot 19).
   * Đầy đủ hệ thống logistics quân sự: dời trại lưu động, trị thương, chia đều quân, mua lính, xoay tua mưu sĩ giữ thể lực tối đa.
   * Được bảo vệ bởi cổng kiểm soát bản quyền Supabase RPC liên tục.
