# Server 58+ API Reference & Captured Samples

Tài liệu kỹ thuật tham chiếu cho kiến trúc **Linh Vương Server 58+** (`http://sg58.dipan.com/`), được kiểm chứng trực tiếp bằng tài khoản test (`quilia`, `uid=95`, `cid=10129`, thành `"inca"` tại `(202, 94)`, `mid=738765`) và đối chiếu với `adapter.js` / `Optimization.js` / `Map.js` của máy chủ.

---

## 1. Kiến trúc & Quy tắc chung

1. **Tách đôi tầng API**:
   - **REST `/api/*`**: Các API đọc danh sách thành, công trình, tài nguyên, bản đồ, hàng đợi, võ tướng, quân giới, thông báo lịch sử và 2 API ghi chính (`POST /api/city/current`, `POST /api/building/update`, `POST /api/oasis/exploit`). Phần lớn phản hồi thành công gói dữ liệu trong `{"ret": 0, "data": { ... }}`.
   - **Optimization `/GateWay/Optimization.ashx?action=*`**: Phân trang trang bị (`equipment`), phân trang hàng đợi sản xuất (`production`), năng lực mở rộng (`capabilities`), và mở rương theo lô bất đồng bộ (`bulk-start`, `bulk-status`).
   - **Legacy-compatible `/GateWay/*.ashx?id=*`**: Một số nghiệp vụ chiến đấu, an dân, luyện sĩ khí, nghiên cứu, chế tạo, chiêu mộ, Niên Thú, thám bảo và mở rương đơn vẫn gọi trực tiếp qua `/GateWay/*.ashx` (`POST application/x-www-form-urlencoded`).
2. **Định danh tài khoản (`userId`) và Thành trì (`cityTentId` / `cityId`)**:
   - Sau khi đăng nhập qua `/login` (chuyển hướng về `/city.html`), server cấp cookie `uid` (ví dụ `uid=95`).
   - Hầu hết `/api/*` yêu cầu truyền query/body `userId=<uid>` và `cityTentId=<cid>` (hoặc `cityId=<cid>`).
3. **HTTP 400 kèm JSON nghiệp vụ**:
   - Server 58 có thể trả **HTTP `400`** cùng body JSON có cấu trúc thay vì HTTP `200`, ví dụ `{"ret": 8105, "errMsg": "..."}` hoặc `{"ret": 8599, "errMsg": "..."}`. Client phải parse JSON cả ở status `400`.
4. **Kênh Thế Giới cũ đã gỡ bỏ**:
   - `SGWebIM.swf` / XMLSocket (`scs:scp`) không còn tồn tại (`ChatEnabled=false`). Thông báo hệ thống đọc qua `GET /api/notify/history`.

---

## 2. Bảng ánh xạ Endpoint (S1–S57 cũ vs Server 58+)

| Chức năng | Legacy S1–S57 (đã hỏng `ret=1` trên S58) | Server 58+ Endpoint | Method |
| :--- | :--- | :--- | :--- |
| Danh sách Thành & Trại | `Common.ashx?id=29` / `City.ashx?id=7` | `/api/city/list?userId=<uid>` | `GET` |
| Chuyển thành hiện tại | `City.ashx?id=50` | `/api/city/current` (`cityTentId`) | `POST` |
| Thông tin Thành (sĩ khí, vàng) | `City.ashx?id=6` *(còn chạy nhưng ở root)* | `/api/city/info?userId=<uid>&cityId=<cid>` | `GET` |
| Tài nguyên khoáng sản & kho | `City.ashx?id=20` *(mất `money`, trả list)* | `/api/resource/info?userId=<uid>&cityTentId=<cid>` | `GET` |
| Danh sách công trình | `City.ashx?id=5` | `/api/building/list?userId=<uid>&cityTentId=<cid>` | `GET` |
| Nâng / Hạ cấp công trình | `OPT.ashx?id=65` | `/api/building/update` (`userId, cityTentId, posId, gid, type`) | `POST` |
| Hàng đợi xây dựng & DS kiến trúc | `Common.ashx?id=77` | `/api/city/pagebuilding?userId=<uid>&cityTentId=<cid>` | `GET` |
| Danh sách Văn quan / Võ tướng | `Common.ashx?id=32` | `/api/city/pageofficial?userId=<uid>&heroType=<1\|2>` | `GET` |
| Quân số & Sĩ khí tướng trong thành | `Common.ashx?id=76` | `/api/city/pagemytroopslist?userId=<uid>&cityTentId=<cid>` | `GET` |
| Tân binh & Kho quân giới | `Common.ashx?id=27` | `/api/city/pagearmament?userId=<uid>` | `GET` |
| Quét bản đồ thế giới | `Map.ashx?id=6` | `/api/map/query?userId=<uid>&mid=<mid>` | `GET` |
| Danh sách trang bị (đủ >50 món) | `Common.ashx?id=24` *(bị cắt ở 50 món)* | `/GateWay/Optimization.ashx?action=equipment` | `POST` |
| Mở rương hàng loạt | Lặp `Common.ashx?id=48` | `/GateWay/Optimization.ashx?action=bulk-start` + `bulk-status` | `POST` |
| Thông báo hệ thống / Niên Thú | `SGWebIM.swf` XMLSocket | `/api/notify/history` | `GET` |

---

## 3. Sample Request & Response (Captured Live trên Server 58)

### 3.1. Tài khoản, Thành trì & Công trình

#### `GET /api/user/info`
```json
{
  "ret": 0,
  "data": {
    "m_lhead_img": 1,
    "m_llevel": 1,
    "m_lcredit": 97,
    "m_lally_id": 0,
    "m_lbullion": 5999,
    "m_lticket": 7724,
    "m_lbattle_exp_infantry": 0,
    "m_lbattle_exp_cavalry": 0,
    "m_lbattle_exp_bowman": 0,
    "m_lfamous": 0,
    "m_lvip_level": 0,
    "m_lpeace_status": 0,
    "m_lbullion_bonus": 6100,
    "m_lrecommend_ticket": 0,
    "m_lCurrentUserTitle": 0,
    "m_szname": "inti",
    "m_szally_name": "",
    "m_szFlag": ""
  }
}
```

#### `GET /api/city/list?userId=95`
```json
{
  "ret": 0,
  "data": {
    "items": [
      {
        "m_ltype": 1,
        "m_lid": 10129,
        "m_lmap_id": 738765,
        "m_lx_pos": 202,
        "m_ly_pos": 94,
        "m_lowner_cityid": 0,
        "m_llevel": 1,
        "m_szname": "inca"
      }
    ]
  }
}
```
> Lưu ý: Nếu gọi trực tiếp `City.ashx?id=7`, server trả list theo thứ tự `[cid, type, name, mid, x, y, owner, level]` (`[[10129, 1, "inca", 738765, 202, 94, 0, 1]]`), bị đảo `[0]` và `[1]` so với code cũ; luôn ưu tiên `/api/city/list`.

#### `POST /api/city/current`
- Request form: `cityTentId=10129`
```json
{
  "ret": 0,
  "data": {
    "head": {
      "m_dwTcpFlag": 3435973633,
      "m_dwLen": 20,
      "m_dwMsgID": 18890,
      "m_dwMsgType": 192,
      "m_lRet": 0
    },
    "bodyLen": 0
  }
}
```

#### `GET /api/building/list?userId=95&cityTentId=10129`
```json
{
  "ret": 0,
  "data": {
    "m_lsize": 1,
    "m_lbg": 0,
    "m_larch_type": 0,
    "items": [
      {"m_lpos": 0, "m_lgid": 2, "m_llevel": 1, "m_lstatus": 0, "m_tleft": 0, "m_szname": "城墙"},
      {"m_lpos": 1, "m_lgid": 4, "m_llevel": 2, "m_lstatus": 0, "m_tleft": 0, "m_szname": "仓库"},
      {"m_lpos": 5, "m_lgid": 6, "m_llevel": 1, "m_lstatus": 0, "m_tleft": 0, "m_szname": "大学殿"},
      {"m_lpos": 8, "m_lgid": 1, "m_llevel": 4, "m_lstatus": 0, "m_tleft": 0, "m_szname": "官府"}
    ]
  }
}
```

#### `POST /api/building/update`
- Request form: `userId=95&cityTentId=10129&posId=9&gid=3&type=1` (`type=1` nâng cấp, `type=2` hạ cấp)
```json
{"ret": 0, "data": {"m_tduration": 12}}
```

#### `GET /api/city/pagebuilding?userId=95&cityTentId=10129`
- Đang thi công:
```json
{
  "ret": 0,
  "data": {
    "ret": 0,
    "plus_finish": 3019848,
    "list": [[10129, "inca", 738765, 2792887, [[9, 3, 1, 1, 11]], []]]
  }
}
```
> **Cảnh báo schema**: `list[i][2]` (`738765`) là **`map_id`**, không phải thời gian speedup! Chỉ đọc `data.plus_finish` ở root (`3019848` giây sau khi kích hoạt DS kiến trúc: `3624615`).

---

### 3.2. Thành nội, Tài nguyên & Hành chính

#### `GET /api/city/info` & `City.ashx?id=6`
- Trường chuẩn trên `/api/city/info` (`adapter.js` case 6): `m_lmorale_current`, `m_lmorale_complaint`, `m_lmoney_balance`, `m_lsize`, `m_szname`.
- `POST /GateWay/City.ashx?id=6` (`tid=10129`) trả ở root (không có `data`):
```json
{
  "ret": 0,
  "name": "inca",
  "size": 1,
  "morale": [90, 0, 0],
  "tax": 10,
  "money": [3456186, 315, 300, 0, 0, 0],
  "population": [120, 264, 0, 0, 120, 0, 1, 0, 120, 100, 100, 0, 0]
}
```

#### `GET /api/resource/info` & `City.ashx?id=20`
- `/api/resource/info` (`adapter.js` case 20): `m_lfood_balance`, `m_lwood_balance`, `m_lstone_balance`, `m_liron_balance`, `m_lmax_storage`.
- `POST /GateWay/City.ashx?id=20` (`tid=10129`) trả ở root và không có `money`:
```json
{
  "ret": 0,
  "food": [4150, 10, 30],
  "wood": [2452, 40],
  "stone": [3353, 40],
  "iron": [4259, 40],
  "max_storage": 19400
}
```

#### `GET /api/city/pagefinance?userId=95&cityId=10129`
```json
{"ret": 0, "data": {"ret": 0, "city": [[10129, "inca", 3455055, 176, 10, 50, 0, 125, 0, 5, 0]]}}
```

#### `GET /api/city/manager?userId=95&cityId=10129`
```json
{
  "ret": 0,
  "data": {
    "ret": 0,
    "city": ["inca", 10129, 202, 94, 1],
    "morale": [90, 0, 0, 10],
    "manager": [0, "", 0, 0, 0],
    "military": [0, "", 0, 0, 0],
    "others": [0, 1],
    "resource_plus": [[0, 0, 0, 0], [0, 0, 0, 0]],
    "population": [120, 270, 0, 0, 50, 70, 0, 1],
    "market": [[120, 120], [480, 480], [480, 480], [480, 480]],
    "supply_line": [[24998, 0, 0], [25304, 0, 0], [25343, 0, 0], [25347, 0, 0]]
  }
}
```

---

### 3.3. Võ tướng, Quân đội & Trang bị

#### `GET /api/city/pageofficial?userId=95&heroType=2`
- `heroType=1` (Văn quan), `heroType=2` (Võ tướng):
```json
{
  "ret": 0,
  "data": {
    "ret": 0,
    "list": [[10129, "inca", 202, 94, [[4880, "吴沛祖", "", 2, 0, 0, 1, 80, 110, 110, 11, 11, 13, 10, 0]]]]
  }
}
```
> Lưu ý khi chiêu mộ từ Tửu quán (`OPT.ashx?id=33`, `lGeneralID=21639`): ID trong tửu quán (`21639`) khác ID chính thức sau khi chiêu mộ (`4880`).

#### `GET /api/city/pagemytroopslist?userId=95&cityTentId=10129`
```json
{"ret": 0, "data": {"ret": 0, "list": [[10129, "inca", []]]}}
```

#### `GET /api/troops/info?userId=95&cityTentId=10129`
```json
{
  "ret": 0,
  "data": {
    "items": [
      {
        "m_lgeneral_id": 4880,
        "m_linfantry": 0,
        "m_lcavalry": 0,
        "m_lbowman": 0,
        "m_lmangonel": 0,
        "m_szgeneral_name": "吴沛祖"
      }
    ]
  }
}
```

#### `GET /api/city/pagearmament?userId=95`
```json
{
  "ret": 0,
  "data": {
    "ret": 0,
    "list": [
      [
        10129,
        "inca",
        50,
        [[519180, "破风弓"], [521659, "百胜长刀"]],
        [[447380, "雷霆战甲"], [14294, "龙飞战甲"]],
        []
      ]
    ]
  }
}
```

#### `POST /GateWay/Optimization.ashx?action=equipment`
- Request form (**`page` đánh số từ `0`**): `kind=1&type=<lType>&target=0&page=0&pageSize=50&revision1=0&revision2=0`
- Response (`type=0` tổng hợp hoặc `type=1..4` theo slot):
```json
{
  "ret": 0,
  "list": [[14645, 1, 1132, 100, 18, 5, 16, 0, 0, ""]],
  "page": 0,
  "pageSize": 50,
  "total": 25,
  "revision": [3539695417, 2935716831],
  "totalItems": 36,
  "p": [0, 0]
}
```
- Khi gọi `page=1` vượt quá số trang: `"list": []`. Khi không có trang bị ở `kind=2`: `{"ret": 21, "errMsg": "装备ID不存在"}`. Khi revision thay đổi giữa chừng: `ret=8102` (reset về `page=0, revision1=0, revision2=0`).

---

### 3.4. Bản đồ thế giới (`GET /api/map/query`)

- Request: `GET /api/map/query?userId=95&mid=738765`
- Response trích xuất từ Server 58:
```json
{
  "citys": [
    [10129, "inca", 1, 95, 0, 0, 1, ""],
    [10158, "6", 1, 32, 0, 0, 0, ""]
  ],
  "infos": [
    [738765, 71, 0, 111, 738765, 10129]
  ],
  "npc": [
    [382, "濮阳", 3, 0, "", 0]
  ],
  "npc_tent": [
    [1326, 1, 755817, 51]
  ]
}
```
> **Thay đổi quan trọng cho `scan.py`**:
> - `citys[i]` = `[city_id, name, size, user_id, face, style, flag, banner]`: chỉ số `[3]` là **`user_id`** (`95`), không phải `cmid`.
> - `size` (`citys[i][2]`): `1` (1×1), `2` (2×2), `3` (3×3), **`4` (4×4 Thiên Thành)**.
> - `cmid` nằm ở `infos[n][4]` (với `infos[n][1]` trong khoảng `71..74` và `infos[n][5] == city_id`).

---

### 3.5. Rương & Optimization Bulk Open

#### `POST /GateWay/Optimization.ashx?action=capabilities`
```json
{
  "ret": 0,
  "version": 1,
  "capabilities": 15,
  "queueLimit": 50,
  "equipmentPageSize": 50,
  "equipmentPageMax": 100,
  "queuePageSize": 50,
  "queuePageMax": 100,
  "bulkEnabled": true,
  "bulkDefault": 10,
  "bulkMax": 99,
  "bulkChunk": 10,
  "policyVersion": 31,
  "storageMode": "merged",
  "bulkAllowed": [1,2,3,4,5,6,7,8,10,11,12,13,15,16,17,21,23,24,25,26,28,35,36,37,44,72,73,75,76]
}
```

#### `POST /GateWay/Optimization.ashx?action=bulk-start` & `bulk-status`
- Request form `bulk-start`: `requestId=<UUID4-with-dashes>&boxId=<id>&limit=<1..99>&cityId=<cid>`
- Nếu UUID không hợp lệ hoặc thiếu tham số (HTTP 400):
```json
{"ret": 8105, "errMsg": "请求参数不一致或无效，请查询原任务。"}
```
- Nếu hết rương hoặc thiếu chìa khóa:
```json
{"ret": 8108, "errMsg": "没有可用宝箱或配套钥匙。"}
```
- Trạng thái bất đồng bộ (`bulk-status`, gửi `requestId=<UUID4>`):
  - `state == 0`: Đang chạy (poll lại sau `250ms..1500ms`).
  - `state == 1`: Hoàn thành đủ `completed == planned`.
  - `state == 2`: Đã dừng sớm, phần dư hoàn trả.
  - Ngoại lệ không thuộc `bulkAllowed`: Box `53` dùng `Common.ashx?id=48`, các lễ bao đặc biệt dùng `OPT.ashx?id=69` (`type=33`, nếu hết trả `{"ret": 90, "errMsg": "道具已经用完"}`).

#### `POST /GateWay/Common.ashx?id=48` (`lBoxID=53`)
```json
{"ret": 0, "bonus_type": 128, "bonus": [0, 0, 0, 0, 0, 0, "", 0, 0, "", 0, "", 0, "", 0, 0, 0, 209, 5, 0]}
```

---

### 3.6. Thông báo hệ thống & Sự kiện

#### `GET /api/notify/history`
```json
{
  "ret": 0,
  "items": [
    {
      "kind": "notice",
      "text": "恭喜玩家 张志文 通过游历探索获得：名将【陈泰】",
      "color": "",
      "size": 18,
      "link": null,
      "sourceId": 1776,
      "createdAt": 1794805570913,
      "id": "notice-1776",
      "cursor": 1776
    }
  ]
}
```

#### `GET /api/user/notify` & `GET /api/active/list`
```json
{"ret": 0, "data": {"m_tsystem_time": 1794805855, "m_lnewreport": 1, "m_lnewmsg": 0, "m_lwar": 0, "m_lchatid": 0, "m_lcitylist": 0}}
```
```json
{
  "ret": 0,
  "data": {
    "m_lunion_arena": 0,
    "m_lnpc2_step1_open": 1,
    "m_lnpc2_step2_open": 1,
    "m_lnpc2_step3_open": 0,
    "m_dwCount": 4,
    "items": [
      {"m_ltype": 1, "m_tstart": 45000, "m_tend": 50400},
      {"m_ltype": 2, "m_tstart": 43200, "m_tend": 54000}
    ]
  }
}
```

---

### 3.7. Các `/GateWay/*.ashx` còn hoạt động trực tiếp (đã test live trên S58)

| Endpoint | Tham số test | Sample Response |
| :--- | :--- | :--- |
| `Build.ashx?id=2` (Tửu quán) | `pid=28, gid=8, tab=1, ttid=10129, optQueues=0` | `{"ret":0,"list":[[21639,"吴沛祖",1,110,11,11,13,10,100], ...]}` |
| `Build.ashx?id=2` (Đại Học Điện) | `pid=5, gid=6, tab=1, ttid=10129, optQueues=0` | `{"ret":0,"current":[0,"",0,0,0],"list":[[1,"种植技巧",0,6,...]]}` |
| `Build.ashx?id=2` (Binh Khí Phủ) | `pid=10, gid=13, tab=1, ttid=10129, optQueues=0` | `{"ret":0,"current":[],"list":[[101,"透甲枪",0,15,...]]}` |
| `Build.ashx?id=2` (Điểm Tướng Đài) | `pid=18, gid=10, tab=1, ttid=10129, optQueues=0` | `{"ret":0,"incity":[[4880,"吴沛祖","",0,0,1,100,...]],"healing":[],"tents":[]}` |
| `City.ashx?id=37` (Nghiên cứu) | `tid=10129` | `{"ret":0,"list":[[10129,"inca",738765,2792887,[],[],[],-1]],"tech":[0,0,0],"task":[0,"",0,0],"soul":[0,"","",0]}` |
| `Common.ashx?id=3` | `tid=10129` | `{"ret":0,"status":0,"current":[0,0,[]],"task":[[0,"踏征程",0,0,300,3]]}` |
| `Common.ashx?id=12` | `lGeneralID=4880, lCityID=10129` | `{"ret":0,"infantry_equip":[0,301,"鱼鳞甲",101,"透甲枪",...],"battle_array":1,...}` |
| `Common.ashx?id=13` | `lGeneralID=4880, lCityID=10129` | `{"ret":0,"type":2,"city_tent_id":10129,"hp_max":110,"equip_helm":[14645,"1132",1132,100,18,5,16,0],...}` |
| `Common.ashx?id=14` | `lGeneralID=4880, lCityID=10129` | `{"ret":0,"head_img":4006,"type":2,"job":0,"status":0,"level":1,"loyalty":80,...}` |
| `Common.ashx?id=15` | `lType=2, tid=10129` | `{"ret":0,"generals":[[4880,"吴沛祖","",0,2,0,1,80,110,110,11,11,13,0,4006]]}` |
| `Common.ashx?id=16` | `tid=10129` | `{"ret":0,"list":[[308,"雷霆战甲",4,447380],[208,"破风弓",2,519180],[108,"百胜长刀",1,521659],[351,"龙飞战甲",4,14294]]}` |
| `Common.ashx?id=40` | `tid=10129` | `{"ret":0,"come":[],"goto":[],"battle":[]}` |
| `Common.ashx?id=126` | `lStatID=1` | `{"ret":0,"list":[[2949,357,0,"宋宪"]]}` |
| `Common.ashx?id=140` | `lAction=0/1/2, lParam=0/2` | `action=1`: `{"ret":0,"left":86400,"bonus":"遇名士司马徽...</br>获得：破匣剪×1"}` / `action=2`: `{"ret":0,"left":0,"bonus":""}` |
| `Common.ashx?id=142` | `{}` | `{"ret":0,"curr":[0,0,0,0],"list":[]}` |
| `OPT.ashx?id=4` | `lType=1, tid=10129` | `{"ret":0}` |
| `OPT.ashx?id=6` | `lGeneralID=4880, lSoldierType=1, lAmount=10, tid=10129` | `{"ret":42}` *(thiếu trang bị mặc định của tướng)* |
| `OPT.ashx?id=33` | `lGeneralID=21639, tid=10129` | `{"ret":0}` *(cấp ID mới `4880`)* |
| `OPT.ashx?id=38` / `89` | `pos=10, gid=101, count=1, tid=10129` | `{"ret":0}` |
| `OPT.ashx?id=41` | `lAmount=50, tid=10129` | `{"ret":0}` |
| `OPT.ashx?id=43` (Đổi tên tướng) | `lCityID=10129, lGeneralID=4880, szNewName=DT_01` | `{"ret":0}`; mã `15` nếu tên rỗng hoặc vượt giới hạn (`< 18`, ký tự không phải ASCII tính 2) |
| `OPT.ashx?id=44` / `12` / `180` | `techid=1, tid=10129` | `{"ret":0}` |
| `OPT.ashx?id=46` / `47` / `58` | `lGeneralID=4880, ...` | `{"ret":0}` |
| `OPT.ashx?id=56` (Lưu quân giới tướng) | `lGeneralID, lInfantryEID1..3, lCavalryEID1..3, lBowmanEID1..3, lMangonelEID` (cần đủ 10 ô; id `46` thực chất là Ban thưởng `lCityID, lGeneralID, lMoney`) | `{"ret":0}`; `42` thiếu quân giới khi tướng đã có lính, `71` thiếu quân giới chính ô 1 khi đã có lính, `20` sai căn cứ, `40` tướng bận. Ô 1: Bộ=Giáp(4), Kỵ=Ngựa(8), Cung=Cung(2); ô 2–3 nhận mọi loại trừ Xe(16). Chỉ ô 1 cần > 0 khi ô 2/3 > 0. |
| `OPT.ashx?id=57` (Trận hình & tỷ lệ) | `lGeneralID, lRatioAttack, lRatioPK, lRatioStra (tổng 100), lBattleArray, lWithdrawLoss, lWithdrawMorale` | `{"ret":0}` |
| `OPT.ashx?id=55` | `tid=10129` | `{"ret":0}` |
| `OPT.ashx?id=63` | `{}` | `{"ret":86}` *(đã nhận chuyên cần trong ngày)* |
| `OPT.ashx?id=67` (Cộng điểm tướng) | `lCityID=10129, lGeneralID=25702, lAttribType=1\|2\|3, lAdd=1` | `{"ret":0}` (cộng được cả khi tướng đang bận `status!=0`); `ret=1` tham số sai (`lAdd<=0` hoặc `lAttribType` ngoài `1..3`), `ret=20` sai căn cứ/ID, `ret=38` (`没有可分配技能点`) hết điểm hoặc `lAdd > skill_point`, `ret=77` (`人物属性点分配过于悬殊`) vượt tổng 2 thuộc tính gốc còn lại |
| `OPT.ashx?id=69` (`type=1,2,3,33`) | `type=1`/`2`/`3` (`param1=slot, param2=city_id, paytype=1\|2`) | `type=1`: giảm 50% thời gian xây dựng (`10` Coin/Ngân Bảo); `type=2`: giảm 1 giờ (`10` Coin/Ngân Bảo); `{"ret":0,"errMsg":"成功"}`; Quan Phủ/Thành Tường (`gid=1,2,54,55`) hoặc công trình NPC (`22..53`) trả `{"ret":1,"errMsg":"操作失败，请稍后再试"}`; `type=33` khi hết: `{"ret":90,"errMsg":"道具已经用完"}` |

---

## 4. Bảng mã lỗi đặc trưng Server 58+

| Mã `ret` | `errMsg` / Ý nghĩa | Bối cảnh |
| :--- | :--- | :--- |
| `0` | Thành công | Chung |
| `1` | Tham số sai hoặc endpoint cũ đã bị vô hiệu hóa | Các `/GateWay/*` bị chuyển sang `/api/*` |
| `20` | Võ tướng không tồn tại / sai ID | `Common.ashx?id=12,13,14`, `OPT.ashx?id=67` |
| `21` | `"装备ID不存在"` | `Optimization.ashx?action=equipment` (`kind=2`) |
| `38` | `"没有可分配技能点"` (Không đủ Điểm Tiềm Năng) | `OPT.ashx?id=67` |
| `42` | Tướng chưa đủ vũ khí/điều kiện biên chế hoặc cooldown | `OPT.ashx?id=6`, `Common.ashx?id=55` |
| `77` | `"人物属性点分配过于悬殊"` (Thuộc tính gốc vượt tổng 2 thuộc tính gốc còn lại) | `OPT.ashx?id=67` |
| `86` | Đã nhận thưởng chuyên cần hôm nay | `OPT.ashx?id=63` |
| `90` | `"道具已经用完"` (Hết đạo cụ) | `OPT.ashx?id=69` (`type=33`) |
| `301` | `"该装备仅限女性名(蛮)将使用"` (Trang bị chỉ dành cho nữ danh tướng hoặc tướng Man) | `OPT.ashx?id=58` (mặc trang bị) |
| `8102` | Revision phân trang thay đổi, cần tải lại từ `page=0` | `Optimization.ashx?action=equipment` / `production` |
| `8104` / `8105` / `8107` | Trạng thái tiếp nhận bulk open chưa chắc chắn / sai tham số | `Optimization.ashx?action=bulk-start` |
| `8108` | `"没有可用宝箱或配套钥匙。"` (Hết rương hoặc thiếu chìa) | `Optimization.ashx?action=bulk-start` |
| `8109` | Job `requestId` chưa tồn tại trong hàng đợi | `Optimization.ashx?action=bulk-status` |
| `8599` | `"请求处理失败，请稍后重试"` (HTTP 400 JSON) | `Common.ashx?id=45`, hệ thống bận |
| `8601` | `"操作结果尚未确认..."` | `Build.ashx?id=1` trực tiếp |
| `198599` | Hết hạn phiên đăng nhập | Cần relogin |
