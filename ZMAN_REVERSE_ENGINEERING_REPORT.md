# Reverse-Engineering Technical Report: ZMan.exe

## Executive Summary
This document provides a comprehensive technical analysis of [`ZMan.exe`](file:///d:/Tools/rea/ZMan.exe), reverse-engineered using REA (Reverse Engineer Anything) static diagnostic workflows and Python runtime analysis.

`ZMan.exe` is an automation bot, management dashboard, and macro suite developed by **Zee** for the Vietnamese web strategy game **Linh Vương** (Linh Vương Truyền Kỳ / Linh Vương Private Servers hosted on `dipan.com`).

---

## 1. Binary Identification & Packaging Architecture

| Property | Value |
| :--- | :--- |
| **File Path** | [`d:\Tools\rea\ZMan.exe`](file:///d:/Tools/rea/ZMan.exe) |
| **File Size** | 14,759,975 bytes (~14.08 MiB) |
| **SHA-256 Digest** | `9216c781b4ff06644d9793b8f81b8416a23930d61d98b814c89310f032e592bc` |
| **PE Subsystem** | Windows GUI (PE32+, 64-bit AMD64) |
| **Linker** | MSVC 14.44 (Visual Studio 2022) |
| **Packager** | **PyInstaller 6.x** CArchive bundle targeting **Python 3.13 (64-bit)** |
| **Magic Cookie** | `MEI\x0c\x0b\x0a\x0b\x0e` located at offset `14,759,887` |
| **PE Overlay** | Offset `0x55400` (349,184 bytes), length `14,410,791` bytes |
| **Main Python Script** | `ZMan.py` (entrypoint `ZMan`), uncompressed size `1,163,601` bytes (>27,180 lines of code) |
| **Primary Class** | `LinhVuongApp` (contains 387 methods implementing the complete application logic) |
| **Bundled Libraries** | `python313.dll`, `_tkinter.pyd`, `tcl86t.dll`, `tk86t.dll`, `_wmi.pyd`, `requests`, `urllib3`, `certifi`, `idna`, `charset_normalizer`, `pysocks` |

---

## 2. REA Inspection Evidence

* **PE Resource Inventory** (`inspect_pe_resources`):
  * `RT_ICON` / `RT_GROUP_ICON`: Embedded icon `sword.ico` (128x128 32-bit RGBA).
  * `RT_MANIFEST`: Standard Windows manifest specifying `asInvoker`, DPI awareness (`longPathAware`), and `Microsoft.Windows.Common-Controls` 6.0.0.0.
* **Format Discrimination**:
  * `inspect_managed_artifact`: Confirmed not a .NET CLR binary (`cli-directory-absent`).
  * `inspect_go_binary`: No Go build metadata.
  * `inspect_rust_binary`: No `.dep-v0` section.

```mermaid
graph TD
    A["ZMan.exe (PE32+ x64)"] --> B["PyInstaller Bootloader (349 KB)"]
    A --> C["CArchive Overlay (14.4 MB)"]
    C --> D["python313.dll & Tkinter Runtimes"]
    C --> E["PYZ.pyz (Python Standard & Third-Party Libs)"]
    C --> F["ZMan (Compiled Code Object: ZMan.py)"]
    F --> G["LinhVuongApp Controller (387 methods)"]
```

---

## 3. Remote Licensing & Security Architecture

### 3.1 Supabase Licensing Backend
The application validates user access and expiration dates via a Supabase PostgreSQL backend using a remote procedure call (RPC):
* **Endpoint**: `https://nurwoidqiueiieyirpbg.supabase.co/rest/v1/rpc/check_user_access`
* **Hardcoded JWT / Anon Key**:
  ```jwt
  eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im51cndvaWRxaXVlaWlleWlycGJnIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzE0MjU5NzcsImV4cCI6MjA4NzAwMTk3N30.uNyaTo92K6d8SgMkhrICpkHWf_BGjkKWcUF4FVsMWaA
  ```
* **Payload Structure**:
  ```json
  {
    "p_username": "<username>",
    "p_server": "<server_id>"
  }
  ```
* **Response Handling**:
  * Returns JSON containing `{ "status": true, "exp": "<date_or_3000-12-31>" }`.
  * If `exp == "3000-12-31"`, it displays `Vĩnh viễn` (Permanent).
  * If unauthorized, displays:
    > *"Tài khoản này chưa được cấp phép sử dụng! Vui lòng liên hệ Zee để được cấp quyền."*

### 3.2 Continuous License Monitoring
* **Methods**: `start_license_monitor`, `license_monitor_worker`, `_check_license_silent`, `_force_logout`.
* **Behavior**:
  * Spawns a daemon thread executing `_check_license_silent()` at fixed intervals.
  * If validation fails consecutively beyond `license_max_fail`, `_force_logout()` is triggered:
    1. Stops license monitor and worker threads.
    2. Cancels and clears running tasks from the UI Treeview.
    3. Destroys the current HTTP session.
    4. Resets the UI back to `show_login()`.

### 3.3 Network Probing & Proxy Support
* **External IP Resolution**: Queries `https://api.ipify.org` for external IP detection.
* **Proxy Configuration**: Supports HTTP/SOCKS proxies (`apply_proxy_to_session`, `get_proxy_dict_for_requests`) for game requests and license validation.

---

## 4. Game Integration & Gateway Protocol

The bot interfaces with Linh Vương game servers hosted under `http://sg<server_id>.dipan.com/GateWay/`:

### 4.1 Authentication Gateway
* **Login URL**: `http://pass.dipan.com/aspx/LoginAPI.aspx`
* **Parameters**: `LoginType1=0`, `UserName1=<user>`, `Password1=<pass>`, `callback=http://sg<sv>.dipan.com`
* **Handshake**: Verifies `登录成功` (Login Successful), follows redirect to `http://sg<sv>.dipan.com/login`, and extracts session cookies (`uid`, `uname`).
* **Sub-Account Management** (`_login_sub_account`, `test_sub_account_login`): Supports secondary accounts for resource pushing, camp feeding, or co-op farming.

### 4.2 Gateway API Mapping

| API Endpoint | Category | Functionality |
| :--- | :--- | :--- |
| `Common.ashx?id=2` | Warehouse | Fetches stored items and gems (`nid`, `gem_id`). |
| `Common.ashx?id=24` | Equipment | Reads general equipment profiles and attributes. |
| `Common.ashx?id=27` | Military | Checks available recruits and resources (horse, armor, bow). |
| `Common.ashx?id=29` | Profile | Retrieves user ID, username, and level. |
| `Common.ashx?id=32` | Generals | Lists civilian (`type=1`) and martial (`type=2`) generals. |
| `Common.ashx?id=40` | Movements | Tracks troop dispatches (`come`, `goto`, `battle`). |
| `Common.ashx?id=48` | Chests | Opens daily gold reward chests. |
| `Common.ashx?id=49` | Navigation | Computes troop march / travel duration to coordinates. |
| `Common.ashx?id=55` / `id=80` | Encampment | Relocates mobile camps (`Trại`) step-by-step. |
| `Common.ashx?id=73` | Anti-Bot | Retrieves 4 image options for in-game captcha challenges. |
| `Common.ashx?id=76` | Overview | Master state: city status, general morale, and stamina. |
| `City.ashx?id=5` | Buildings | Lists city buildings with slot `pid` and type `gid`. |
| `City.ashx?id=6` | Morale | Reads city morale percentage. |
| `City.ashx?id=20` | Resources | Reads city resource counts (Wood, Stone, Iron, Food). |
| `City.ashx?id=37` | Research | Checks current technology research status. |
| `City.ashx?id=50` | Rebel Spawn | Calls "Gọi Dân / Gọi Vong Linh" to summon targets. |
| `Map.ashx?id=6` | Map Scan | Scans coordinate grid tiles within search radius. |
| `OPT.ashx?id=4` | Comfort | Comforts population (An dân) to restore morale. |
| `OPT.ashx?id=5` | Advisor | Attaches advisor general (Mưu sĩ) to martial general. |
| `OPT.ashx?id=6` | Recruits | Assigns troop counts to general formations. |
| `OPT.ashx?id=24` | Battle | Polls battle status; `ret=13` indicates battle ended. |
| `OPT.ashx?id=31` | Treatment | Heals wounded generals after combat. |
| `OPT.ashx?id=39` | Balance | Equalizes troop counts across camp generals. |
| `OPT.ashx?id=41` | Purchase | Auto-purchases recruits when city barracks are low. |
| `OPT.ashx?id=44` | Technology | Initiates tech upgrade for any of the 29 technologies. |
| `OPT.ashx?id=50` | Dispatch | Transits generals between city and forward encampments. |
| `OPT.ashx?id=53` | Attack | Dispatches army against barbarians, rebels, or camps. |
| `OPT.ashx?id=54` | Tactical | In-battle tactical command (moves units, focuses boss index 19). |
| `OPT.ashx?id=57` | Formation | Switches combat formations. |
| `OPT.ashx?id=58` | Equipment | Equips weapons/armor on designated general. |
| `OPT.ashx?id=62` | Campaign | Initiates "Thảo Phạt" missions. |
| `OPT.ashx?id=63` | Daily | Collects daily attendance rewards. |
| `OPT.ashx?id=65` | Construction | Executes building upgrade tasks. |
| `OPT.ashx?id=100` | Treasure | Automates treasure exploration ("Tầm bảo"). |
| `OPT.ashx?id=101` | Retreat | Withdraws general from battlefield (`BattleID`, `Act=2`). |
| `OPT.ashx?id=102` | Captcha | Submits chosen captcha answer (`num=...`). |
| `OPT.ashx?id=178` | Training | Dispatches generals to "Tu luyện" for XP gain. |

---

## 5. Automation Subsystems

1. **Bình Man & Trại Di Chuyển**:
   * Scans barbarian camps around city or forward encampments (`Trại`).
   * When using mobile encampments, moves the camp step-by-step toward target coordinates until distance $\le 2$ tiles, then launches attack.
   * Enforces return thresholds (`return_threshold`): retreats to city, heals wounded generals, refills soldiers, and redeploys.
2. **Combat Management & Thảo Phạt**:
   * Real-time battle automation via `OPT.ashx?id=54`.
   * Targets boss units identified at army slot index 19.
   * Auto-retreats generals via `OPT.ashx?id=101` if health or stamina falls below safe thresholds.
3. **General Training & Advisor Rotation**:
   * Continuous training cycling for civil and martial heroes (`OPT.ashx?id=178`).
   * Implements automated advisor rotation (`build_advisor_rotation_map`, `get_next_advisor_from_rotation`): swaps out tired advisors for rested ones to maintain 24/7 training.
4. **29-Technology Research & Building Queue**:
   * Manages queues for all 29 game technologies (Làm thực, Rèn sắt, Đào đá, Chặt gỗ, Mưu lược, Trận pháp, Bạt doanh, Thuần hóa ngựa, v.v.).
   * Supports speedup items (*Binh Pháp / Art of War*) and preserves prioritized custom build orders.
5. **Captcha Handling**:
   * Solves in-game 4-choice image captchas using a randomized selector (`random.randint(0, 3)`) through `_solve_captcha_random` and `_submit_captcha_random`.
6. **Data & Configuration Formats**:
   * Full profile settings exported/imported as JSON files with `.zman` extension.
   * Target coordinates and IDs stored in CSV format in `man.txt`.
   * Official guides referenced in the code:
     * Game Guide: `https://linhvuong.notion.site/`
     * Auto Guide: `https://linhvuong.notion.site/hdsd`
