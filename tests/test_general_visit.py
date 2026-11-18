"""Kiểm thử chức năng kiểm tra và thông báo Danh Tướng / Danh Sỹ Viếng Thăm (S58)."""

from pathlib import Path
import threading
import time
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from linhvuong.dashboard.internal_aux import InternalAuxMixin
from linhvuong.gateway import GatewayClient
from linhvuong.tasks.base import CaptchaRequired, RET_CAPTCHA_REQUIRED, RET_OK
import linhvuong.notifications as notif_mod
from linhvuong.notifications import (
    NotificationConfig,
    clear_general_visit_alerts,
    sync_general_visit_alerts,
)
from linhvuong.profile import LogisticsProfile, NotificationProfile, Profile
from linhvuong.roster import City, Roster
import linhvuong.runtime as runtime_mod
from linhvuong.runtime import WorkspaceManager
from linhvuong.tasks.building import (
    GeneralVisit,
    check_general_visits,
    select_general_visit_city,
)


def _city(cid: int, name: str, ctype: str = "Thành") -> City:
    return City(id=cid, name=name, type=ctype, pos_x=10, pos_y=20)


def test_select_general_visit_city_prefers_visit_building_and_skips_camps():
    camp = _city(-100, "Trại 1", "Doanh trại")
    city_plain = _city(10128, "Phân Thành", "Thành")
    city_tavern = _city(10129, "Chính Thành", "Thành")

    class _FakeGw:
        def __init__(self):
            self.list_calls = []

        def building_list(self, cid):
            self.list_calls.append(cid)
            if cid == 10128:
                return {"items": [{"gid": 1, "pid": 1}]}
            if cid == 10129:
                return {"items": [{"gid": 8, "pid": 5}]}
            return {"items": []}

    gw = _FakeGw()
    chosen = select_general_visit_city(gw, [camp, city_plain, city_tavern])
    assert chosen is not None and chosen.id == 10129
    assert gw.list_calls == [10128, 10129]

    # Khi đã cache preferred_city_id thì không cần gọi lại building_list
    gw.list_calls.clear()
    cached = select_general_visit_city(gw, [camp, city_plain, city_tavern], preferred_city_id=10129)
    assert cached is not None and cached.id == 10129
    assert gw.list_calls == []

    # Nếu không thành nào có Tửu Quán / Quán Trọ thì fallback về Thành đầu tiên (vẫn bỏ Doanh trại)
    gw_empty = _FakeGw()
    gw_empty.building_list = lambda _cid: {"items": [{"gid": 1}]}
    fallback = select_general_visit_city(gw_empty, [camp, city_plain, city_tavern])
    assert fallback is not None and fallback.id == 10128
    assert select_general_visit_city(gw_empty, [camp]) is None


def test_check_general_visits_queries_both_gid8_and_gid7_independently():
    calls: list[tuple[str, int, dict]] = []

    class _FakeGw:
        def __init__(self):
            self._city_lock = threading.RLock()

        def call(self, endpoint, cmd_id, payload=None, **_kwargs):
            calls.append((endpoint, cmd_id, dict(payload or {})))
            if endpoint == "Build.ashx" and cmd_id == 2:
                gid = str((payload or {}).get("gid", ""))
                if gid == "8":
                    return {"ret": RET_OK, "look_for": [], "rumor": [265, 228, 83, "张嶷"], "list": []}
                if gid == "7":
                    return {"ret": RET_OK, "look_for": [], "rumor": [101, 12, 50, "Quách Gia"], "list": []}
            return {"ret": RET_OK}

    gw = _FakeGw()
    with patch("linhvuong.tasks.building.switch_city_verified", return_value=(True, RET_OK, {})) as sw_mock:
        visits = check_general_visits(gw, 10129, "Chính Thành")

    sw_mock.assert_called_once_with(gw, 10129)
    assert [(v.gid, v.building_name, v.general_name, v.city_id) for v in visits] == [
        (8, "Tửu Quán", "张嶷", 10129),
        (7, "Quán Trọ", "Quách Gia", 10129),
    ]
    assert [c[2]["gid"] for c in calls if c[0] == "Build.ashx"] == ["8", "7"]


def test_check_general_visits_raises_captcha():
    class _CaptchaGw:
        def __init__(self):
            self._city_lock = threading.RLock()

        def call(self, endpoint, cmd_id, payload=None, **_kwargs):
            return {"ret": RET_CAPTCHA_REQUIRED}

    gw = _CaptchaGw()
    with patch("linhvuong.tasks.building.switch_city_verified", return_value=(True, RET_OK, {})):
        with pytest.raises(CaptchaRequired):
            check_general_visits(gw, 10129, "Chính Thành")


def test_sync_general_visit_alerts_dedup_reset_and_telegram_toggle(monkeypatch):
    acc = "quilia @ S58"
    clear_general_visit_alerts(acc)

    logs: list[str] = []
    web_events: list[dict] = []
    sent_telegram: list[str] = []

    class _ImmediateThread:
        def __init__(self, target, daemon=True, name=None):
            self._target = target

        def start(self):
            self._target()

    monkeypatch.setattr(notif_mod.threading, "Thread", _ImmediateThread)
    monkeypatch.setattr(notif_mod, "send_desktop_toast", lambda *a, **kw: None)
    monkeypatch.setattr(notif_mod, "play_alert_sound", lambda: None)
    monkeypatch.setattr(
        notif_mod,
        "send_telegram_message",
        lambda bot_token, chat_id, message: (sent_telegram.append(message) or True, "ok"),
    )

    cfg = NotificationConfig(
        desktop_enabled=True,
        web_enabled=True,
        sound_enabled=False,
        telegram_enabled=True,
        telegram_alert_general_visit=True,
        telegram_bot_token="bot-tok",
        telegram_chat_id="chat-1",
    )
    visit = GeneralVisit(
        city_id=10129,
        city_name="Thành chính",
        gid=8,
        building_name="Tửu Quán",
        role_label="danh tướng",
        general_name="张嶷",
    )

    # Lần đầu xuất hiện -> phát thông báo
    arrived1 = sync_general_visit_alerts(
        acc, [visit], config=cfg, on_log=logs.append, on_web_event=web_events.append
    )
    assert len(arrived1) == 1
    assert len(web_events) == 1
    assert web_events[0]["kind"] == "general_visit"
    assert "张嶷" in web_events[0]["title"]
    assert len(sent_telegram) == 1
    assert "Tửu Quán (Thành chính)" in sent_telegram[0]

    # Vẫn vị tướng cũ ở lại ở lần poll tiếp theo -> chống lặp
    arrived2 = sync_general_visit_alerts(
        acc, [visit], config=cfg, on_log=logs.append, on_web_event=web_events.append
    )
    assert arrived2 == []
    assert len(web_events) == 1
    assert len(sent_telegram) == 1

    # Tắt báo Telegram riêng cho viếng thăm & tướng rời đi rồi quay lại -> Web vẫn báo, Telegram không gửi
    sync_general_visit_alerts(acc, [], config=cfg, on_log=logs.append, on_web_event=web_events.append)
    cfg_no_tg = NotificationConfig(
        desktop_enabled=False,
        web_enabled=True,
        telegram_enabled=True,
        telegram_alert_general_visit=False,
        telegram_bot_token="bot-tok",
        telegram_chat_id="chat-1",
    )
    arrived3 = sync_general_visit_alerts(
        acc, [visit], config=cfg_no_tg, on_log=logs.append, on_web_event=web_events.append
    )
    assert len(arrived3) == 1
    assert len(web_events) == 2
    assert len(sent_telegram) == 1
    clear_general_visit_alerts(acc)


def test_profile_general_visit_flags_roundtrip():
    prof = Profile.from_dict({})
    assert prof.logistics.notify_general_visit is True
    assert prof.notifications.telegram_alert_general_visit is True

    d = prof.to_dict()
    d["logistics"]["notify_general_visit"] = False
    d["notifications"]["telegram_alert_general_visit"] = False
    prof2 = Profile.from_dict(d)
    assert prof2.logistics.notify_general_visit is False
    assert prof2.notifications.telegram_alert_general_visit is False


def test_account_session_general_visit_integration_and_throttle(tmp_path, monkeypatch):
    roster = Roster()
    roster.cities = [_city(10129, "Chính Thành", "Thành")]
    roster.camps = [_city(-200, "Trại 1", "Doanh trại")]

    monkeypatch.setattr(runtime_mod, "login", lambda *a, **kw: None)
    monkeypatch.setattr(runtime_mod, "fetch_roster", lambda _gw: roster)
    monkeypatch.setattr(runtime_mod.AccountSession, "start_aux_loop", lambda self: None)

    wm = WorkspaceManager(data_dir=tmp_path, acquire_lock=True)
    sess = wm.login_account(server_id=58, username="quilia", password="pw")

    visit = GeneralVisit(
        city_id=10129,
        city_name="Chính Thành",
        gid=8,
        building_name="Tửu Quán",
        role_label="danh tướng",
        general_name="张嶷",
    )
    check_calls = 0

    def _fake_check(_gw, cid, cname=""):
        nonlocal check_calls
        check_calls += 1
        return [visit]

    monkeypatch.setattr(runtime_mod, "select_general_visit_city", lambda gw, cities, preferred_city_id=None: roster.cities[0])
    monkeypatch.setattr(runtime_mod, "check_general_visits", _fake_check)
    monkeypatch.setattr(notif_mod, "send_desktop_toast", lambda *a, **kw: None)
    monkeypatch.setattr(notif_mod, "play_alert_sound", lambda: None)

    sess._check_general_visit_once()
    assert check_calls == 1
    assert sess.get_aux_status()["general_visits"] == [visit.to_dict()]

    # Gọi lại ngay sau đó phải bị throttle (55s)
    sess._check_general_visit_once()
    assert check_calls == 1

    # Tắt checkbox -> reset trạng thái ngay
    sess.update_profile({"logistics": {"notify_general_visit": False}})
    assert sess.get_aux_status()["general_visits"] == []
    sess.destroy()


def test_desktop_internal_aux_general_visit_collect_apply_and_check(monkeypatch):
    class _FakeVar:
        def __init__(self, value):
            self._v = value

        def get(self):
            return self._v

        def set(self, value):
            self._v = value

    class _FakeLabel:
        def __init__(self):
            self.text = ""
            self.fg = ""

        def winfo_exists(self):
            return True

        def config(self, **kw):
            if "text" in kw:
                self.text = kw["text"]
            if "fg" in kw:
                self.fg = kw["fg"]

    class _DummyAux(InternalAuxMixin):
        def __init__(self):
            self.username = "quilia"
            self.gateway = SimpleNamespace(server_id=58, _city_lock=threading.RLock())
            self.roster = SimpleNamespace(cities=[_city(10129, "Chính Thành", "Thành")], server_id=58)
            self.aux_general_visit_var = _FakeVar(True)
            self.aux_visit_lbl = _FakeLabel()
            self.notification_config = NotificationConfig(desktop_enabled=False, telegram_enabled=False)
            self._general_visit_city_id = None
            self.bld_logs = []

        def _update_explore_turns_visibility(self):
            pass

        def _append_bld_log(self, msg):
            self.bld_logs.append(msg)

    app = _DummyAux()
    assert app._collect_logistics_profile_dict()["notify_general_visit"] is True
    app._apply_logistics_profile_dict({"notify_general_visit": False})
    assert app.aux_general_visit_var.get() is False
    app._check_and_notify_general_visit(async_check=False)
    assert app.aux_visit_lbl.text == "(Đang tắt)"

    app._apply_logistics_profile_dict({"notify_general_visit": True})
    monkeypatch.setattr("linhvuong.dashboard.internal_aux.select_general_visit_city", lambda gw, cities, preferred_city_id=None: cities[0])
    monkeypatch.setattr(
        "linhvuong.dashboard.internal_aux.check_general_visits",
        lambda gw, cid, cname="": [
            GeneralVisit(
                city_id=cid,
                city_name=cname,
                gid=8,
                building_name="Tửu Quán",
                role_label="danh tướng",
                general_name="张嶷",
            )
        ],
    )
    app._check_and_notify_general_visit(async_check=False)
    assert "Tửu Quán: 张嶷" in app.aux_visit_lbl.text
    assert any("张嶷" in m for m in app.bld_logs)
    clear_general_visit_alerts(app._general_visit_account_key())


def test_web_app_js_contains_general_visit_ui():
    js_path = Path("linhvuong/web/static/app.js")
    text = js_path.read_text(encoding="utf-8")
    for needle in (
        "aux-general-visit",
        "aux-visit-lbl",
        "notify_general_visit",
        "nf-visit",
        "telegram_alert_general_visit",
        "formatGeneralVisitText",
    ):
        assert needle in text
