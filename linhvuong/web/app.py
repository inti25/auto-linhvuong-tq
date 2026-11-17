"""Ứng dụng FastAPI + WebSocket cho Bảng Điều Khiển Web Linh Vương (ADR-0038 & ADR-0039)."""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
import sys
from typing import Any, Optional
import urllib.parse

from fastapi import Body, Depends, FastAPI, HTTPException, Request, Response, WebSocket, WebSocketDisconnect, status
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ..auth import LoginError
from ..battle import ATTACK_ACTION_COMBO_OPTIONS, FORMATION_NAMES, STRATAGEMS
from ..logger import list_log_files, read_log_tail
from ..paths import logs_dir
from ..proxy import DEFAULT_FREE_PROXY_URL
from ..runtime import AUTO_START_TASK_LABELS, LOG_CHANNELS, AccountSession, WorkspaceManager
from ..security import SESSION_COOKIE_NAME, VaultError, WebAdminAuth
from ..tasks.binh_man import MAN_TARGET_OPTIONS
from ..tasks.building import BUILDING_NAMES, CHEST_MAPPING, chest_needs_city_switch
from ..tasks.crafting import WEAPONS_DATA
from ..tasks.research import TECH_NAMES
from ..tasks.thao_phat import THAOPHAT_MISSIONS

def _resolve_static_dir() -> Path:
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        cand = Path(meipass) / "linhvuong" / "web" / "static"
        if cand.is_dir():
            return cand
    return Path(__file__).resolve().parent / "static"


STATIC_DIR = _resolve_static_dir()
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class AdminLoginRequest(BaseModel):
    username: str = "admin"
    password: str = ""


class AdminPasswordChangeRequest(BaseModel):
    current_password: str = ""
    new_password: str
    new_username: Optional[str] = None


class AccountConfigRequest(BaseModel):
    server_id: int
    username: str
    password: str = ""
    proxy_url: str = ""
    proxy: str = ""
    proxy_user: str = ""
    proxy_pass: str = ""
    save_to_vault: Optional[bool] = None
    auto_resume: bool = True
    auto_start_tasks: Optional[list[str]] = None
    old_key: Optional[str] = None


class GameLoginRequest(BaseModel):
    server_id: int
    username: str
    password: str = ""
    proxy_url: str = ""
    proxy: str = ""
    proxy_user: str = ""
    proxy_pass: str = ""
    save_to_vault: bool = False
    auto_resume: bool = True
    auto_start_tasks: Optional[list[str]] = None
    old_key: Optional[str] = None


class VaultUpdateRequest(BaseModel):
    save: bool = True
    password: str = ""


class AutoStartUpdateRequest(BaseModel):
    auto_resume: bool = True
    auto_start_tasks: list[str] = []
    save_to_vault: Optional[bool] = None
    password: str = ""


class ProxyTestRequest(BaseModel):
    proxy_url: str


class WebSocketHub:
    """Điều phối phát sự kiện thời gian thực từ luồng nền sang các WebSocket client."""

    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._clients.add(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self._clients.discard(ws)

    def publish_from_thread(self, account_key: str, event_type: str, payload: dict) -> None:
        loop = self._loop
        if not loop or loop.is_closed() or not self._clients:
            return
        message = {"account_key": account_key, "event": event_type, "payload": payload}
        try:
            loop.call_soon_threadsafe(lambda: asyncio.create_task(self._broadcast(message)))
        except RuntimeError:
            pass

    async def _broadcast(self, message: dict) -> None:
        dead = []
        for ws in list(self._clients):
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._clients.discard(ws)


def create_app(
    *,
    workspace: Optional[WorkspaceManager] = None,
    auth: Optional[WebAdminAuth] = None,
    data_dir: Optional[str | Path] = None,
    host: str = "127.0.0.1",
    allow_no_auth: bool = False,
    auto_restore: bool = True,
) -> FastAPI:
    """Khởi tạo FastAPI app gắn WorkspaceManager và WebAdminAuth."""
    hub = WebSocketHub()
    owned_workspace = workspace is None
    ws_manager = workspace or WorkspaceManager(data_dir=data_dir, acquire_lock=True)
    admin_auth = auth or WebAdminAuth(data_dir=ws_manager.data_dir, host=host, allow_no_auth=allow_no_auth)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        hub.bind_loop(asyncio.get_running_loop())
        ws_manager.subscribe(hub.publish_from_thread)
        if auto_restore:
            try:
                ws_manager.auto_restore_on_startup()
            except Exception:
                pass
        try:
            yield
        finally:
            ws_manager.unsubscribe(hub.publish_from_thread)
            if owned_workspace:
                ws_manager.graceful_shutdown()

    app = FastAPI(title="Linh Vương Auto Web Dashboard", version="1.0.4", lifespan=lifespan)
    app.state.workspace = ws_manager
    app.state.auth = admin_auth
    app.state.hub = hub

    if STATIC_DIR.is_dir():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    def require_admin(request: Request) -> None:
        if not admin_auth.auth_enabled:
            return
        token = request.cookies.get(SESSION_COOKIE_NAME)
        if not admin_auth.verify_session_token(token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Phiên quản trị chưa đăng nhập hoặc đã hết hạn.",
            )

    def _get_session(account_key: str) -> AccountSession:
        decoded_key = urllib.parse.unquote(account_key)
        try:
            return ws_manager.get_session(decoded_key)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    # -------------------------------------------------------------------------
    # HEALTH & STATIC ROOT
    # -------------------------------------------------------------------------
    @app.get("/api/health")
    def health() -> dict:
        return {"ok": True, "auth_enabled": admin_auth.auth_enabled}

    @app.get("/", response_class=HTMLResponse)
    def index():
        index_file = STATIC_DIR / "index.html"
        if not index_file.is_file():
            return HTMLResponse("<h1>Linh Vương Web Dashboard</h1><p>Thiếu tệp giao diện tĩnh.</p>")
        return FileResponse(index_file)

    @app.get("/assets/{asset_name}")
    def get_root_asset(asset_name: str):
        allowed = {"qrcode.png", "linhvuong.png", "linhvuong_menu.png"}
        if asset_name not in allowed:
            raise HTTPException(status_code=404, detail="Không tìm thấy tài nguyên.")
        meipass = getattr(sys, "_MEIPASS", None)
        candidates = [PROJECT_ROOT / asset_name, Path(asset_name)]
        if meipass:
            candidates.insert(0, Path(meipass) / asset_name)
        for candidate in candidates:
            if candidate.is_file():
                return FileResponse(candidate)
        raise HTTPException(status_code=404, detail="Không tìm thấy tệp tài nguyên.")

    # -------------------------------------------------------------------------
    # PHIÊN QUẢN TRỊ WEB (WEB ADMIN AUTH)
    # -------------------------------------------------------------------------
    @app.get("/api/auth/status")
    def auth_status(request: Request) -> dict:
        token = request.cookies.get(SESSION_COOKIE_NAME)
        return {
            "auth_enabled": admin_auth.auth_enabled,
            "authenticated": admin_auth.verify_session_token(token),
            "username": admin_auth.username,
            "vault_unlocked": ws_manager.vault.is_unlocked(),
        }

    @app.post("/api/auth/login")
    def auth_login(payload: AdminLoginRequest, response: Response) -> dict:
        if not admin_auth.verify_credentials(payload.username, payload.password):
            raise HTTPException(status_code=401, detail="Sai tên đăng nhập hoặc mật khẩu quản trị.")
        token = admin_auth.create_session_token()
        response.set_cookie(
            key=SESSION_COOKIE_NAME,
            value=token,
            httponly=True,
            samesite="lax",
            max_age=7 * 24 * 3600,
        )
        return {"ok": True, "username": admin_auth.username}

    @app.post("/api/auth/logout")
    def auth_logout(response: Response) -> dict:
        response.delete_cookie(SESSION_COOKIE_NAME)
        return {"ok": True}

    @app.post("/api/auth/password", dependencies=[Depends(require_admin)])
    def auth_change_password(payload: AdminPasswordChangeRequest) -> dict:
        if admin_auth.auth_enabled and not admin_auth.verify_credentials(admin_auth.username, payload.current_password):
            raise HTTPException(status_code=400, detail="Mật khẩu hiện tại không đúng.")
        try:
            admin_auth.change_password(payload.new_password, payload.new_username)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True, "username": admin_auth.username}

    # -------------------------------------------------------------------------
    # METADATA DANH MỤC GAME
    # -------------------------------------------------------------------------
    @app.get("/api/meta", dependencies=[Depends(require_admin)])
    def get_metadata() -> dict:
        chests = [
            {"name": name, "needs_city": chest_needs_city_switch(name)}
            for name in CHEST_MAPPING.keys()
        ]
        weapons = [
            {"id": wid, "name": wname, "category": wcat}
            for wid, (wname, wcat) in sorted(WEAPONS_DATA.items())
        ]
        missions = [
            {"idx": idx, "id": mid, "name": m["name"], "travel_time": m.get("travel_time", 300)}
            for idx, (mid, m) in enumerate(THAOPHAT_MISSIONS.items())
        ]
        return {
            "building_names": {str(k): v for k, v in BUILDING_NAMES.items()},
            "tech_names": [{"id": tid, "name": tname} for tid, tname in sorted(TECH_NAMES.items())],
            "missions": missions,
            "man_targets": [{"id": mid, "label": lbl} for mid, lbl in MAN_TARGET_OPTIONS],
            "chests": chests,
            "weapons": weapons,
            "attack_action_options": list(ATTACK_ACTION_COMBO_OPTIONS),
            "formations": [{"id": k, "name": v} for k, v in sorted(FORMATION_NAMES.items())],
            "stratagems": [{"id": k, "name": v} for k, v in sorted(STRATAGEMS.items())],
            "default_free_proxy_url": DEFAULT_FREE_PROXY_URL,
            "log_channels": list(LOG_CHANNELS),
            "auto_start_task_options": [{"id": tid, "label": lbl} for tid, lbl in AUTO_START_TASK_LABELS],
            "vault_unlocked": ws_manager.vault.is_unlocked(),
        }

    # -------------------------------------------------------------------------
    # QUẢN LÝ ĐA TÀI KHOẢN & KHÔNG GIAN LÀM VIỆC
    # -------------------------------------------------------------------------
    @app.get("/api/accounts", dependencies=[Depends(require_admin)])
    def list_accounts() -> dict:
        return {"accounts": ws_manager.list_accounts(), "vault_unlocked": ws_manager.vault.is_unlocked()}

    @app.post("/api/accounts", dependencies=[Depends(require_admin)])
    def save_account_config(payload: AccountConfigRequest) -> dict:
        try:
            data = payload.model_dump()
            pwd = data.pop("password", "")
            save_vault = data.pop("save_to_vault", None)
            acc = ws_manager.add_or_update_account(**data)
            if save_vault is not None:
                acc = ws_manager.set_account_vault_password(
                    acc["account_key"],
                    save=bool(save_vault),
                    password=pwd,
                    auto_resume=payload.auto_resume,
                )
            return {"ok": True, "account": acc}
        except (ValueError, VaultError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/accounts/{account_key}/vault", dependencies=[Depends(require_admin)])
    def update_account_vault(account_key: str, payload: VaultUpdateRequest) -> dict:
        key = urllib.parse.unquote(account_key)
        try:
            acc = ws_manager.set_account_vault_password(
                key,
                save=payload.save,
                password=payload.password,
            )
            return {"ok": True, "account": acc}
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (ValueError, VaultError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.put("/api/accounts/{account_key}/autostart", dependencies=[Depends(require_admin)])
    def update_account_autostart(account_key: str, payload: AutoStartUpdateRequest) -> dict:
        key = urllib.parse.unquote(account_key)
        try:
            acc = ws_manager.update_account_autostart(
                key,
                auto_resume=payload.auto_resume,
                auto_start_tasks=payload.auto_start_tasks,
            )
            if payload.save_to_vault is not None:
                acc = ws_manager.set_account_vault_password(
                    key,
                    save=bool(payload.save_to_vault),
                    password=payload.password,
                    auto_resume=payload.auto_resume,
                )
            return {"ok": True, "account": acc}
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (ValueError, VaultError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/accounts/proxy-test", dependencies=[Depends(require_admin)])
    def test_proxy(payload: ProxyTestRequest) -> dict:
        try:
            return ws_manager.test_proxy_list(payload.proxy_url)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/accounts/login", dependencies=[Depends(require_admin)])
    def login_game_account(payload: GameLoginRequest) -> dict:
        try:
            sess = ws_manager.login_account(**payload.model_dump())
            return {"ok": True, "snapshot": sess.get_full_snapshot()}
        except (LoginError, ValueError, VaultError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/accounts/{account_key}/logout", dependencies=[Depends(require_admin)])
    def logout_game_account(account_key: str) -> dict:
        ws_manager.logout_account(urllib.parse.unquote(account_key))
        return {"ok": True}

    @app.delete("/api/accounts/{account_key}", dependencies=[Depends(require_admin)])
    def delete_game_account(account_key: str) -> dict:
        ws_manager.delete_account(urllib.parse.unquote(account_key))
        return {"ok": True}

    @app.post("/api/workspace/start-all", dependencies=[Depends(require_admin)])
    def start_all_accounts() -> dict:
        return {"ok": True, "started_accounts": ws_manager.start_all_accounts()}

    @app.post("/api/workspace/stop-all", dependencies=[Depends(require_admin)])
    def stop_all_accounts() -> dict:
        return {"ok": True, "stopped_accounts": ws_manager.stop_all_accounts()}

    # -------------------------------------------------------------------------
    # THAO TÁC TRONG TỪNG PHIÊN TÀI KHOẢN
    # -------------------------------------------------------------------------
    @app.get("/api/accounts/{account_key}/snapshot", dependencies=[Depends(require_admin)])
    def get_account_snapshot(account_key: str) -> dict:
        return _get_session(account_key).get_full_snapshot()

    @app.put("/api/accounts/{account_key}/profile", dependencies=[Depends(require_admin)])
    def update_account_profile(account_key: str, patch: dict = Body(...)) -> dict:
        sess = _get_session(account_key)
        return {"ok": True, "profile": sess.update_profile(patch)}

    @app.post("/api/accounts/{account_key}/profile/import", dependencies=[Depends(require_admin)])
    def import_account_profile(account_key: str, data: dict = Body(...)) -> dict:
        sess = _get_session(account_key)
        return {"ok": True, "profile": sess.import_profile(data)}

    @app.get("/api/accounts/{account_key}/profile/export", dependencies=[Depends(require_admin)])
    def export_account_profile(account_key: str):
        sess = _get_session(account_key)
        sess.save_profile()
        return FileResponse(
            sess.profile_path,
            filename=sess.profile_path.name,
            media_type="application/json",
        )

    @app.post("/api/accounts/{account_key}/roster/reload", dependencies=[Depends(require_admin)])
    def reload_account_roster(account_key: str) -> dict:
        sess = _get_session(account_key)
        try:
            return {"ok": True, "roster": sess.reload_roster()}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/accounts/{account_key}/buildings/fetch", dependencies=[Depends(require_admin)])
    def fetch_buildings(account_key: str, body: dict = Body(...)) -> dict:
        sess = _get_session(account_key)
        cid = int(body.get("city_id", 0))
        try:
            plans = sess.fetch_city_buildings(cid)
            return {"ok": True, "city_id": cid, "plans": plans, "profile": sess.profile.to_dict()}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/accounts/{account_key}/techs/fetch", dependencies=[Depends(require_admin)])
    def fetch_techs(account_key: str, body: dict = Body(default={})) -> dict:
        sess = _get_session(account_key)
        cid = body.get("city_id")
        try:
            res = sess.fetch_city_techs(int(cid) if cid else None)
            return {"ok": True, **res, "profile": sess.profile.to_dict()}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/accounts/{account_key}/tasks/{task_name}/start", dependencies=[Depends(require_admin)])
    def start_task(account_key: str, task_name: str) -> dict:
        sess = _get_session(account_key)
        dispatch = {
            "building": sess.start_building,
            "research": sess.start_research,
            "thaophat": sess.start_thaophat,
            "binhman": sess.start_binhman,
            "goidan": sess.start_goidan,
            "nienthu": sess.start_nienthu,
            "resource_monitor": sess.start_resource_monitor,
            "crafting": sess.start_crafting,
        }
        fn = dispatch.get(task_name)
        if not fn:
            raise HTTPException(status_code=404, detail=f"Tác vụ '{task_name}' không tồn tại.")
        try:
            fn()
            return {"ok": True, "summary": sess.get_status_snapshot()}
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/accounts/{account_key}/tasks/{task_name}/stop", dependencies=[Depends(require_admin)])
    def stop_task(account_key: str, task_name: str) -> dict:
        sess = _get_session(account_key)
        dispatch = {
            "building": sess.stop_building,
            "research": sess.stop_research,
            "thaophat": sess.stop_thaophat,
            "binhman": sess.stop_binhman,
            "goidan": sess.stop_goidan,
            "nienthu": sess.stop_nienthu,
            "resource_monitor": sess.stop_resource_monitor,
            "crafting": sess.stop_crafting,
        }
        fn = dispatch.get(task_name)
        if not fn:
            raise HTTPException(status_code=404, detail=f"Tác vụ '{task_name}' không tồn tại.")
        fn()
        return {"ok": True, "summary": sess.get_status_snapshot()}

    @app.post("/api/accounts/{account_key}/tasks/binhman/once", dependencies=[Depends(require_admin)])
    def binhman_once(account_key: str) -> dict:
        sess = _get_session(account_key)
        try:
            sess.run_binhman_once()
            return {"ok": True}
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/accounts/{account_key}/tasks/binhman/provision", dependencies=[Depends(require_admin)])
    def binhman_provision(account_key: str, body: dict = Body(default={})) -> dict:
        sess = _get_session(account_key)
        bid = body.get("base_id")
        try:
            sess.adjust_binhman_troops(int(bid) if bid is not None else None)
            return {"ok": True}
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/accounts/{account_key}/tasks/thaophat/provision", dependencies=[Depends(require_admin)])
    def thaophat_provision(account_key: str) -> dict:
        sess = _get_session(account_key)
        try:
            sess.adjust_thaophat_troops()
            return {"ok": True}
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/accounts/{account_key}/tasks/goidan/once", dependencies=[Depends(require_admin)])
    def goidan_once(account_key: str) -> dict:
        sess = _get_session(account_key)
        try:
            sess.run_goidan_once()
            return {"ok": True}
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/accounts/{account_key}/tasks/goidan/provision", dependencies=[Depends(require_admin)])
    def goidan_provision(account_key: str) -> dict:
        sess = _get_session(account_key)
        try:
            sess.adjust_goidan_troops()
            return {"ok": True}
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/accounts/{account_key}/tasks/crafting/now", dependencies=[Depends(require_admin)])
    def craft_now(account_key: str, body: dict = Body(...)) -> dict:
        sess = _get_session(account_key)
        try:
            sess.craft_now(int(body["city_id"]))
            return {"ok": True}
        except (KeyError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/accounts/{account_key}/aux/explore", dependencies=[Depends(require_admin)])
    def run_explore(account_key: str, body: dict = Body(default={})) -> dict:
        sess = _get_session(account_key)
        sess.run_explore(
            use_whip=bool(body.get("use_whip", False)),
            use_coin=bool(body.get("use_coin", False)),
            turns=int(body.get("turns", 1)),
        )
        return {"ok": True}

    @app.post("/api/accounts/{account_key}/aux/daily-reward", dependencies=[Depends(require_admin)])
    def claim_daily(account_key: str) -> dict:
        _get_session(account_key).claim_daily_reward()
        return {"ok": True}

    @app.post("/api/accounts/{account_key}/aux/comfort", dependencies=[Depends(require_admin)])
    def comfort_city(account_key: str, body: dict = Body(...)) -> dict:
        _get_session(account_key).comfort_city(int(body["city_id"]))
        return {"ok": True}

    @app.post("/api/accounts/{account_key}/aux/tribute", dependencies=[Depends(require_admin)])
    def tribute_city(account_key: str, body: dict = Body(...)) -> dict:
        _get_session(account_key).tribute_city(int(body["city_id"]), int(body.get("building_gid", 1)))
        return {"ok": True}

    @app.post("/api/accounts/{account_key}/aux/transfer", dependencies=[Depends(require_admin)])
    def transfer_army(account_key: str, body: dict = Body(...)) -> dict:
        _get_session(account_key).transfer_army(
            int(body["from_city_id"]),
            int(body["to_city_id"]),
            int(body["army_id"]),
            int(body["amount"]),
        )
        return {"ok": True}

    @app.post("/api/accounts/{account_key}/chests/start", dependencies=[Depends(require_admin)])
    def chests_start(account_key: str, body: dict = Body(...)) -> dict:
        sess = _get_session(account_key)
        try:
            sess.start_batch_open_chest(
                str(body["chest_name"]),
                int(body["times"]),
                int(body["city_id"]) if body.get("city_id") else None,
            )
            return {"ok": True}
        except (ValueError, RuntimeError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/accounts/{account_key}/chests/stop", dependencies=[Depends(require_admin)])
    def chests_stop(account_key: str) -> dict:
        _get_session(account_key).stop_batch_open_chest()
        return {"ok": True}

    @app.post("/api/accounts/{account_key}/ditrai/start", dependencies=[Depends(require_admin)])
    def ditrai_start(account_key: str, body: dict = Body(...)) -> dict:
        sess = _get_session(account_key)
        try:
            sess.start_ditrai(int(body["camp_id"]), int(body["dest_x"]), int(body["dest_y"]))
            return {"ok": True}
        except (ValueError, RuntimeError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/accounts/{account_key}/ditrai/stop", dependencies=[Depends(require_admin)])
    def ditrai_stop(account_key: str) -> dict:
        _get_session(account_key).stop_ditrai()
        return {"ok": True}

    @app.post("/api/accounts/{account_key}/morale/start", dependencies=[Depends(require_admin)])
    def morale_start(account_key: str, body: dict = Body(...)) -> dict:
        sess = _get_session(account_key)
        try:
            sess.start_morale_training(
                [int(x) for x in body.get("general_ids", [])],
                int(body.get("target_morale", 100)),
            )
            return {"ok": True}
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/accounts/{account_key}/morale/stop", dependencies=[Depends(require_admin)])
    def morale_stop(account_key: str) -> dict:
        _get_session(account_key).stop_morale_training()
        return {"ok": True}

    @app.post("/api/accounts/{account_key}/reward/preview", dependencies=[Depends(require_admin)])
    def reward_preview(account_key: str) -> dict:
        try:
            return {"ok": True, **_get_session(account_key).preview_reward_all()}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/accounts/{account_key}/reward/run", dependencies=[Depends(require_admin)])
    def reward_run(account_key: str) -> dict:
        try:
            return {"ok": True, **_get_session(account_key).run_reward_all()}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/accounts/{account_key}/tactician/run", dependencies=[Depends(require_admin)])
    def tactician_run(account_key: str, body: dict = Body(...)) -> dict:
        sess = _get_session(account_key)
        try:
            sess.run_tactician_action(
                str(body["mode"]),
                [int(x) for x in body.get("general_ids", [])],
                bool(body.get("reassign", False)),
            )
            return {"ok": True}
        except (ValueError, RuntimeError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/accounts/{account_key}/tactician/stop", dependencies=[Depends(require_admin)])
    def tactician_stop(account_key: str) -> dict:
        _get_session(account_key).stop_tactician_action()
        return {"ok": True}

    @app.get("/api/accounts/{account_key}/equip/inventory", dependencies=[Depends(require_admin)])
    def equip_inventory(account_key: str) -> dict:
        try:
            return {"ok": True, "inventory": _get_session(account_key).fetch_equip_inventory()}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/accounts/{account_key}/equip/run", dependencies=[Depends(require_admin)])
    def equip_run(account_key: str, body: dict = Body(...)) -> dict:
        sess = _get_session(account_key)
        try:
            sess.run_equip_action(
                str(body["mode"]),
                [int(x) for x in body.get("general_ids", [])],
                bool(body.get("reassign", False)),
            )
            return {"ok": True}
        except (ValueError, RuntimeError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/accounts/{account_key}/equip/stop", dependencies=[Depends(require_admin)])
    def equip_stop(account_key: str) -> dict:
        _get_session(account_key).stop_equip_action()
        return {"ok": True}

    @app.post("/api/accounts/{account_key}/battle/load", dependencies=[Depends(require_admin)])
    def battle_load(account_key: str, body: dict = Body(...)) -> dict:
        try:
            st = _get_session(account_key).load_battle(int(body["battle_id"]))
            return {"ok": True, "state": st}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/accounts/{account_key}/battle/start", dependencies=[Depends(require_admin)])
    def battle_start(account_key: str, body: dict = Body(...)) -> dict:
        _get_session(account_key).start_battle_tracker(int(body["battle_id"]))
        return {"ok": True}

    @app.post("/api/accounts/{account_key}/battle/stop", dependencies=[Depends(require_admin)])
    def battle_stop(account_key: str) -> dict:
        _get_session(account_key).stop_battle_tracker()
        return {"ok": True}

    @app.post("/api/accounts/{account_key}/battle/formation", dependencies=[Depends(require_admin)])
    def battle_formation(account_key: str, body: dict = Body(...)) -> dict:
        ok = _get_session(account_key).battle_change_formation(
            int(body["battle_id"]), int(body["position"]), int(body["formation_id"])
        )
        return {"ok": ok}

    @app.post("/api/accounts/{account_key}/battle/stratagem", dependencies=[Depends(require_admin)])
    def battle_stratagem(account_key: str, body: dict = Body(...)) -> dict:
        ok = _get_session(account_key).battle_cast_stratagem(
            int(body["battle_id"]), int(body["position"]), int(body["stratagem_id"])
        )
        return {"ok": ok}

    @app.post("/api/accounts/{account_key}/battle/defend-all", dependencies=[Depends(require_admin)])
    def battle_defend(account_key: str, body: dict = Body(...)) -> dict:
        _get_session(account_key).battle_defend_all(int(body["battle_id"]))
        return {"ok": True}

    @app.post("/api/accounts/{account_key}/captcha/resume", dependencies=[Depends(require_admin)])
    def captcha_resume(account_key: str) -> dict:
        sess = _get_session(account_key)
        sess.resume_after_captcha()
        return {"ok": True, "summary": sess.get_status_snapshot()}

    @app.post("/api/accounts/{account_key}/proxy/rotate", dependencies=[Depends(require_admin)])
    def proxy_rotate(account_key: str) -> dict:
        try:
            return {"ok": True, "proxy": _get_session(account_key).rotate_proxy()}
        except RuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/accounts/{account_key}/relogin", dependencies=[Depends(require_admin)])
    def account_relogin(account_key: str) -> dict:
        try:
            ok = _get_session(account_key).relogin()
            return {"ok": ok}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/accounts/{account_key}/notifications/test", dependencies=[Depends(require_admin)])
    def notifications_test(account_key: str) -> dict:
        _get_session(account_key).test_notification()
        return {"ok": True}

    @app.post("/api/accounts/{account_key}/logs/clear", dependencies=[Depends(require_admin)])
    def logs_clear(account_key: str, body: dict = Body(default={})) -> dict:
        _get_session(account_key).clear_logs(str(body.get("channel", "global")))
        return {"ok": True}

    # -------------------------------------------------------------------------
    # XEM & TẢI TỆP NHẬT KÝ HỆ THỐNG TRÊN UBUNTU SERVER
    # -------------------------------------------------------------------------
    @app.get("/api/logs/files", dependencies=[Depends(require_admin)])
    def logs_files() -> dict:
        return {"files": list_log_files(logs_dir(ws_manager.data_dir))}

    @app.get("/api/logs/files/{filename}", dependencies=[Depends(require_admin)])
    def logs_file_content(filename: str, lines: int = 500, download: bool = False):
        ldir = logs_dir(ws_manager.data_dir)
        try:
            if download:
                safe = Path(filename).name
                target = (ldir / safe).resolve()
                if safe != filename or target.parent != ldir.resolve() or not target.is_file():
                    raise FileNotFoundError()
                return FileResponse(target, filename=safe, media_type="text/plain; charset=utf-8")
            text = read_log_tail(filename, lines=lines, log_dir=ldir)
            return PlainTextResponse(text)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Không tìm thấy tệp log.") from exc

    # -------------------------------------------------------------------------
    # WEBSOCKET REALTIME STREAM
    # -------------------------------------------------------------------------
    @app.websocket("/ws")
    async def websocket_endpoint(ws: WebSocket):
        if admin_auth.auth_enabled:
            token = ws.cookies.get(SESSION_COOKIE_NAME)
            if not admin_auth.verify_session_token(token):
                await ws.close(code=4401)
                return
        await hub.connect(ws)
        try:
            await ws.send_json({"event": "connected", "accounts": ws_manager.list_accounts()})
            while True:
                msg = await ws.receive_text()
                if msg == "ping":
                    await ws.send_text("pong")
        except WebSocketDisconnect:
            pass
        finally:
            hub.disconnect(ws)

    return app
