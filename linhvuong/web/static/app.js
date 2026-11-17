/* Linh Vương Web Dashboard SPA (No-build ES6, ADR-0038 & ADR-0039) */
(() => {
  const state = {
    auth: { auth_enabled: false, authenticated: false, username: "admin", vault_unlocked: false },
    meta: null,
    accounts: [],
    currentKey: null,
    snapshot: null,
    activeTab: "internal",
    soundEnabled: true,
    ws: null,
    selectedBldCityId: null,
    selectedBldPid: null,
    expandedBldGroups: new Set(),
    selectedOverviewCityId: null,
    selectedOverviewGenId: null,
    selectedMoraleGens: new Set(),
    moraleInitAccount: null,
    selectedCraftCityId: null,
    selectedBmBaseId: null,
    selectedResTechId: null,
    battleIdInput: "0",
    saveTimer: null,
    auxSyncedAt: 0,
    auxTimer: null,
  };

  const $ = (id) => document.getElementById(id);
  const esc = (s) =>
    String(s ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");

  async function api(url, opts = {}) {
    const init = {
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", ...(opts.headers || {}) },
      ...opts,
    };
    if (init.body && typeof init.body !== "string") {
      init.body = JSON.stringify(init.body);
    }
    const resp = await fetch(url, init);
    if (resp.status === 401) {
      state.auth.authenticated = false;
      renderAuthGate();
      throw new Error("Phiên quản trị đã hết hạn.");
    }
    const text = await resp.text();
    let data = {};
    try { data = text ? JSON.parse(text) : {}; } catch { data = { detail: text }; }
    if (!resp.ok) throw new Error(data.detail || `HTTP ${resp.status}`);
    return data;
  }

  function playAlertBeep() {
    if (!state.soundEnabled) return;
    try {
      const Ctx = window.AudioContext || window.webkitAudioContext;
      if (!Ctx) return;
      const ctx = new Ctx();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "triangle";
      osc.frequency.setValueAtTime(880, ctx.currentTime);
      gain.gain.setValueAtTime(0.12, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.35);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + 0.36);
    } catch {}
  }

  function showToast(title, body = "", kind = "info") {
    const stack = $("toast-stack");
    const el = document.createElement("div");
    el.className = `toast ${kind}`;
    el.innerHTML = `<strong>${esc(title)}</strong>${body ? `<div style="margin-top:4px;color:var(--muted);white-space:pre-line;">${esc(body)}</div>` : ""}`;
    stack.appendChild(el);
    setTimeout(() => el.remove(), 6500);
  }

  function triggerWebNotification(ev) {
    showToast(ev.title || "Thông báo", ev.body || "", ev.kind === "captcha" ? "warn" : "info");
    if (ev.sound !== false) playAlertBeep();
    if ("Notification" in window && Notification.permission === "granted") {
      try { new Notification(ev.title || "Linh Vương", { body: ev.body || "" }); } catch {}
    }
  }

  // ---------------------------------------------------------------------------
  // AUTH & INITIALIZATION
  // ---------------------------------------------------------------------------
  async function init() {
    bindStaticEvents();
    if (!state.auxTimer) {
      state.auxTimer = setInterval(renderAuxCountdownsOnly, 1000);
    }
    const auth = await api("/api/auth/status");
    state.auth = auth;
    renderAuthGate();
    if (!auth.auth_enabled || auth.authenticated) {
      await bootstrapWorkspace();
    }
  }

  function renderAuthGate() {
    const needLogin = state.auth.auth_enabled && !state.auth.authenticated;
    $("admin-login-view").classList.toggle("hidden", !needLogin);
    $("app-shell").classList.toggle("hidden", needLogin);
    $("btn-admin-logout").classList.toggle("hidden", !state.auth.auth_enabled);
  }

  async function bootstrapWorkspace() {
    state.meta = await api("/api/meta");
    const res = await api("/api/accounts");
    state.accounts = res.accounts || [];
    state.auth.vault_unlocked = !!res.vault_unlocked;
    renderSidebar();
    if (state.accounts.length > 0) {
      const target = state.currentKey && state.accounts.some((a) => a.account_key === state.currentKey)
        ? state.currentKey
        : state.accounts[0].account_key;
      await selectAccount(target);
    } else {
      showAddAccountForm();
    }
    connectWebSocket();
  }

  function connectWebSocket() {
    if (state.ws) {
      try { state.ws.close(); } catch {}
    }
    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    const ws = new WebSocket(`${proto}//${location.host}/ws`);
    state.ws = ws;
    ws.onopen = () => {
      $("ws-realtime-pill").textContent = "WS: Realtime";
      $("ws-realtime-pill").className = "pill ok";
    };
    ws.onclose = () => {
      $("ws-realtime-pill").textContent = "WS: Mất kết nối";
      $("ws-realtime-pill").className = "pill warn";
      setTimeout(() => {
        if (!state.auth.auth_enabled || state.auth.authenticated) connectWebSocket();
      }, 3000);
    };
    ws.onmessage = (msg) => {
      let data;
      try { data = JSON.parse(msg.data); } catch { return; }
      handleWsEvent(data);
    };
  }

  function handleWsEvent(msg) {
    const { account_key, event, payload } = msg;
    if (event === "connected" && msg.accounts) {
      state.accounts = msg.accounts;
      renderSidebar();
      return;
    }
    if (event === "accounts_changed" && payload?.accounts) {
      state.accounts = payload.accounts;
      renderSidebar();
      if (state.snapshot) renderHeaderProfileBar();
      if (state.currentKey && !state.accounts.some((a) => a.account_key === state.currentKey)) {
        state.currentKey = state.accounts[0]?.account_key || null;
        state.snapshot = null;
        if (state.currentKey) selectAccount(state.currentKey);
        else showAddAccountForm();
      }
      return;
    }
    if (event === "notification" && payload) {
      triggerWebNotification(payload);
      return;
    }
    if (event === "captcha_alert" && payload) {
      triggerWebNotification({
        kind: "captcha",
        title: `⚠️ Cần giải Captcha: ${account_key}`,
        body: payload.reason || "Tác vụ đã tạm dừng chờ xác nhận.",
        sound: true,
      });
    }
    if (account_key) {
      const idx = state.accounts.findIndex((a) => a.account_key === account_key);
      if (idx >= 0 && event === "status_changed") {
        state.accounts[idx] = { ...state.accounts[idx], ...payload };
        renderSidebar();
      }
    }
    if (account_key !== state.currentKey || !state.snapshot) return;

    if (event === "log" && payload) {
      const ch = payload.channel || "global";
      state.snapshot.logs[ch] = state.snapshot.logs[ch] || [];
      state.snapshot.logs[ch].push(payload.line);
      if (state.snapshot.logs[ch].length > 500) state.snapshot.logs[ch].shift();
      if (ch !== "global") {
        state.snapshot.logs.global.push(`[${ch}] ${payload.line}`);
        if (state.snapshot.logs.global.length > 500) state.snapshot.logs.global.shift();
      }
      appendLogToDom(ch, payload.line);
    } else if (event === "logs_cleared" && payload) {
      state.snapshot.logs[payload.channel] = [];
      renderActiveTab();
    } else if (event === "status_changed") {
      state.snapshot.summary = payload;
      renderTopbar();
      updateRunningButtonsOnly();
    } else if (event === "profile_updated") {
      state.snapshot.profile = payload;
      renderHeaderProfileBar();
      renderActiveTab();
    } else if (event === "roster_updated") {
      state.snapshot.roster = payload;
      renderActiveTab();
    } else if (event === "techs_updated") {
      state.snapshot.tech_levels = payload.levels || {};
      state.snapshot.tech_current = payload.current || null;
      renderActiveTab();
    } else if (event === "aux_updated") {
      state.snapshot.aux = payload;
      state.auxSyncedAt = Date.now();
      renderAuxDomOnly();
    } else if (event === "battle_updated") {
      state.snapshot.aux.battle_id = payload.battle_id;
      state.snapshot.aux.battle_state = payload.state;
      if (state.activeTab === "battle") renderActiveTab();
    } else if (event === "proxy_updated") {
      state.snapshot.summary.proxy = payload;
      renderTopbar();
    }
  }

  // ---------------------------------------------------------------------------
  // SIDEBAR & ACCOUNT SELECTION
  // ---------------------------------------------------------------------------
  function renderSidebar() {
    const list = $("account-list");
    list.innerHTML = state.accounts
      .map((a) => {
        const icon = a.status === "connected" ? "🟢" : a.status === "captcha" ? "⚠️" : a.status === "error" ? "🔴" : "⚪";
        const active = a.account_key === state.currentKey ? "active" : "";
        const vaultBadge = a.has_vault_password ? "🔐" : "";
        return `
          <div class="account-card ${active}" data-key="${esc(a.account_key)}">
            <div class="account-card-top">
              <span>${esc(a.account_key)}</span>
              <span>${vaultBadge}</span>
            </div>
            <div class="account-card-badge">${icon} ${esc(a.status_text || "Chưa đăng nhập")}</div>
            <div class="account-card-tasks">${esc(a.tasks_summary || "Nghỉ")}</div>
          </div>`;
      })
      .join("");
    list.querySelectorAll(".account-card").forEach((el) => {
      el.addEventListener("click", () => {
        $("sidebar").classList.remove("open");
        selectAccount(el.dataset.key);
      });
    });
  }

  async function selectAccount(key) {
    state.currentKey = key;
    state.snapshot = null;
    state.selectedBldCityId = null;
    state.selectedOverviewCityId = null;
    state.selectedOverviewGenId = null;
    state.selectedBmBaseId = null;
    state.selectedCraftCityId = null;
    renderSidebar();

    const acc = state.accounts.find((a) => a.account_key === key);
    if (!acc || acc.status === "disconnected") {
      showGameLoginView(acc);
      return;
    }
    try {
      const snap = await api(`/api/accounts/${encodeURIComponent(key)}/snapshot`);
      state.snapshot = snap;
      state.auxSyncedAt = Date.now();
      showDashboardView();
    } catch {
      showGameLoginView(acc);
    }
  }

  function showAddAccountForm() {
    state.currentKey = null;
    state.snapshot = null;
    renderSidebar();
    showGameLoginView(null);
  }

  const DEFAULT_AUTOSTART_OPTIONS = [
    { id: "building", label: "🏛️ Xây dựng" },
    { id: "research", label: "🔬 Nghiên cứu" },
    { id: "resource_monitor", label: "🌾 An dân / Tài nguyên" },
    { id: "thaophat", label: "⚔️ Thảo phạt" },
    { id: "binhman", label: "🏕️ Bình man" },
    { id: "goidan", label: "🧛 Gọi man" },
    { id: "nienthu", label: "🧧 Niên thú" },
    { id: "crafting", label: "🛡️ Chế tạo quân giới" },
  ];

  function getAutoStartOptions() {
    return state.meta?.auto_start_task_options?.length ? state.meta.auto_start_task_options : DEFAULT_AUTOSTART_OPTIONS;
  }

  function renderAutoStartCheckboxes(containerId, selectedIds, clsName) {
    const el = $(containerId);
    if (!el) return;
    const selected = new Set(selectedIds || []);
    el.innerHTML = getAutoStartOptions()
      .map((t) => `<label><input type="checkbox" class="${clsName}" value="${esc(t.id)}" ${selected.has(t.id) ? "checked" : ""}/> ${esc(t.label)}</label>`)
      .join("");
  }

  function getCurrentAccountMeta() {
    return state.accounts.find((a) => a.account_key === state.currentKey) || null;
  }

  function applyUpdatedAccountMeta(acc) {
    if (!acc?.account_key) return;
    const idx = state.accounts.findIndex((a) => a.account_key === acc.account_key);
    if (idx >= 0) state.accounts[idx] = acc;
    else state.accounts.push(acc);
    renderSidebar();
    renderHeaderProfileBar();
  }

  function showGameLoginView(acc) {
    $("game-login-view").classList.remove("hidden");
    $("dashboard-view").classList.add("hidden");
    $("profile-header-bar").classList.add("hidden");
    $("captcha-banner").classList.add("hidden");
    $("btn-reload-roster").classList.add("hidden");
    $("btn-rotate-proxy").classList.add("hidden");
    $("btn-notify-settings").classList.add("hidden");
    $("btn-account-logout").classList.add("hidden");

    const cfg = acc?.config || {};
    $("ws-title").textContent = acc ? acc.account_key : "Thêm tài khoản mới";
    $("ws-status-pill").textContent = "⚪ Chưa đăng nhập";
    $("ws-status-pill").className = "pill";
    $("ws-proxy-pill").classList.add("hidden");

    $("gl-server").value = cfg.server || "";
    $("gl-user").value = cfg.username || "";
    $("gl-pass").value = "";
    $("gl-proxy-url").value = cfg.proxy_url || "";
    $("gl-proxy").value = cfg.proxy || "";
    $("gl-proxy-user").value = cfg.proxy_user || "";
    $("gl-proxy-pass").value = cfg.proxy_pass || "";
    $("gl-auto-resume").checked = cfg.auto_resume !== false;
    $("gl-save-vault").checked = acc ? !!acc.has_vault_password : true;
    $("gl-vault-hint").textContent = acc?.has_vault_password ? "(đã lưu trong Két — có thể để trống)" : "";
    $("gl-vault-box").classList.toggle("hidden", !state.auth.vault_unlocked);
    renderAutoStartCheckboxes("gl-autostart-tasks", cfg.auto_start_tasks || [], "gl-as-chk");
    $("btn-delete-acc").classList.toggle("hidden", !acc);
    $("gl-status").textContent = "";
  }

  function renderHeaderProfileBar() {
    const snap = state.snapshot;
    if (!snap || !state.currentKey) return;
    const acc = getCurrentAccountMeta();
    const cfg = acc?.config || {};
    const asTasks = cfg.auto_start_tasks || [];
    $("hdr-profile-name").textContent = snap.profile_filename || "-";
    $("hdr-profile-export").href = `/api/accounts/${encodeURIComponent(state.currentKey)}/profile/export`;
    $("hdr-save-vault").checked = !!acc?.has_vault_password;
    $("hdr-save-vault").disabled = !state.auth.vault_unlocked;
    $("hdr-auto-resume").checked = cfg.auto_resume !== false;
    $("hdr-autostart-count").textContent = String(asTasks.length);
  }

  function showDashboardView() {
    $("game-login-view").classList.add("hidden");
    $("dashboard-view").classList.remove("hidden");
    $("profile-header-bar").classList.remove("hidden");
    $("btn-reload-roster").classList.remove("hidden");
    $("btn-notify-settings").classList.remove("hidden");
    $("btn-account-logout").classList.remove("hidden");
    renderTopbar();
    renderHeaderProfileBar();
    renderActiveTab();
  }

  function renderTopbar() {
    const s = state.snapshot?.summary;
    if (!s) return;
    $("ws-title").textContent = `[S${s.server_id}] ${s.username}`;
    const pill = $("ws-status-pill");
    if (s.captcha_required) {
      pill.textContent = "⚠️ Cần giải Captcha";
      pill.className = "pill warn";
    } else if (s.status === "error") {
      pill.textContent = `🔴 ${s.status_text}`;
      pill.className = "pill err";
    } else {
      pill.textContent = `🟢 ${s.status_text}`;
      pill.className = "pill ok";
    }
    $("captcha-banner").classList.toggle("hidden", !s.captcha_required);
    $("captcha-reason-text").textContent = s.captcha_reason || "Tác vụ đang tạm dừng.";

    const pPill = $("ws-proxy-pill");
    if (s.proxy?.active) {
      pPill.classList.remove("hidden");
      pPill.textContent = s.proxy.mode === "pool"
        ? `🌐 ${s.proxy.active} (${s.proxy.alive}/${s.proxy.total})`
        : `🌐 ${s.proxy.active}`;
    } else {
      pPill.classList.add("hidden");
    }
    $("btn-rotate-proxy").classList.toggle("hidden", s.proxy?.mode !== "pool");
  }

  // ---------------------------------------------------------------------------
  // PROFILE SYNC HELPERS
  // ---------------------------------------------------------------------------
  function scheduleProfileSave(patch) {
    if (!state.currentKey || !state.snapshot) return;
    // Merge optimistically into local snapshot
    const prof = state.snapshot.profile;
    for (const [k, v] of Object.entries(patch)) {
      if (prof[k] && typeof prof[k] === "object" && !Array.isArray(prof[k]) && typeof v === "object") {
        prof[k] = { ...prof[k], ...v };
      } else {
        prof[k] = v;
      }
    }
    clearTimeout(state.saveTimer);
    state.saveTimer = setTimeout(async () => {
      try {
        await api(`/api/accounts/${encodeURIComponent(state.currentKey)}/profile`, {
          method: "PUT",
          body: patch,
        });
      } catch (e) {
        showToast("Lỗi lưu cấu hình", e.message, "error");
      }
    }, 300);
  }

  async function saveProfileImmediate(patch) {
    clearTimeout(state.saveTimer);
    const prof = state.snapshot.profile;
    for (const [k, v] of Object.entries(patch)) {
      if (prof[k] && typeof prof[k] === "object" && !Array.isArray(prof[k]) && typeof v === "object") {
        prof[k] = { ...prof[k], ...v };
      } else {
        prof[k] = v;
      }
    }
    await api(`/api/accounts/${encodeURIComponent(state.currentKey)}/profile`, {
      method: "PUT",
      body: patch,
    });
  }

  async function toggleTask(taskName) {
    const running = !!state.snapshot?.summary?.tasks?.[taskName]?.running;
    const action = running ? "stop" : "start";
    try {
      await saveProfileImmediate(state.snapshot.profile);
      const res = await api(`/api/accounts/${encodeURIComponent(state.currentKey)}/tasks/${taskName}/${action}`, {
        method: "POST",
      });
      if (res.summary) {
        state.snapshot.summary = res.summary;
        renderTopbar();
        renderActiveTab();
      }
    } catch (e) {
      showToast("Không thể thực hiện", e.message, "error");
    }
  }

  function appendLogToDom(channel, line) {
    const map = {
      building: "log-internal",
      logistics: "log-internal",
      thaophat: "log-thaophat",
      binhman: "log-binhman",
      goidan: "log-goidan",
      battle: "log-battle",
      nienthu: "log-nienthu",
    };
    const box = $(map[channel]);
    if (box) {
      box.textContent += (box.textContent ? "\n" : "") + line;
      box.scrollTop = box.scrollHeight;
    }
  }

  function getLiveAuxSeconds(field) {
    const aux = state.snapshot?.aux;
    if (!aux) return 0;
    const base = Math.max(0, Number(aux[field] || 0));
    if (base <= 0) return 0;
    const elapsed = state.auxSyncedAt ? Math.max(0, Math.floor((Date.now() - state.auxSyncedAt) / 1000)) : 0;
    return Math.max(0, base - elapsed);
  }

  function renderAuxCountdownsOnly() {
    const aux = state.snapshot?.aux;
    if (!aux) return;
    const boostLeft = getLiveAuxSeconds("boost_left_seconds");
    const exploreLeft = getLiveAuxSeconds("explore_left_seconds");
    const boostEl = $("aux-boost-lbl");
    if (boostEl) {
      boostEl.textContent = boostLeft > 0 ? `(Còn ${fmtSec(boostLeft)})` : "(Hết hạn)";
      boostEl.style.color = boostLeft > 0 ? "#4ade80" : "#f87171";
    }
    const expEl = $("aux-explore-lbl");
    if (expEl) {
      expEl.textContent = exploreLeft > 0 ? `(Còn ${fmtSec(exploreLeft)})` : "(Sẵn sàng)";
      expEl.style.color = exploreLeft > 0 ? "#4ade80" : "#fbbf24";
    }
  }

  function renderAuxDomOnly() {
    const aux = state.snapshot?.aux;
    if (!aux) return;
    renderAuxCountdownsOnly();
    const dtEl = $("dt-status-lbl");
    if (dtEl) dtEl.textContent = aux.ditrai_status || "Sẵn sàng";
    const chestFill = $("chest-progress-fill");
    const chestLbl = $("chest-progress-lbl");
    if (chestFill && aux.chest_progress) chestFill.style.width = `${aux.chest_progress.pct || 0}%`;
    if (chestLbl && aux.chest_progress) chestLbl.textContent = `${aux.chest_progress.status || ""} (${aux.chest_progress.done || 0}/${aux.chest_progress.total || 0})`;
    const moLbl = $("morale-status-lbl");
    if (moLbl) moLbl.textContent = aux.morale_status || "";
    const crLbl = $("craft-status-lbl");
    if (crLbl) crLbl.textContent = Object.values(aux.craft_statuses || {}).slice(-1)[0] || "";
    const ntAnn = $("nt-ann-lbl");
    if (ntAnn && aux.nien_thu_announcement) {
      const a = aux.nien_thu_announcement;
      ntAnn.textContent = `Kênh thế giới: ${a.vi_name} (${a.state_name}) - ${a.server_time || "?"}`;
    }
  }

  function updateRunningButtonsOnly() {
    const t = state.snapshot?.summary?.tasks || {};
    const bindBtn = (id, running, onTxt, offTxt) => {
      const el = $(id);
      if (!el) return;
      el.textContent = running ? onTxt : offTxt;
      el.className = running ? "btn-danger btn-sm" : "btn-success btn-sm";
    };
    bindBtn("btn-tgl-bld", t.building?.running, "⏹️ Dừng Xây", "▶️ Xây");
    bindBtn("btn-tgl-res", t.research?.running, "⏹️ Dừng NC", "▶️ Nghiên Cứu");
    bindBtn("btn-tgl-resmon", t.resource_monitor?.running, "⏹️ Dừng mở rương TN/Vàng", "▶️ Tự mở rương TN/Vàng");
    bindBtn("btn-tgl-tp", t.thaophat?.running, "⏹️ Dừng Thảo Phạt", "▶️ Bắt đầu Thảo Phạt");
    bindBtn("btn-tgl-bm", t.binhman?.running, "⏹️ Dừng Bình Man", "▶️ Bắt đầu Bình Man");
    bindBtn("btn-tgl-gd", t.goidan?.running, "⏹️ Dừng Gọi Man", "▶️ Bắt đầu Gọi Man");
    bindBtn("btn-tgl-nt", t.nienthu?.running, "⏹️ Dừng Niên Thú", "▶️ Bắt đầu Niên Thú");
    bindBtn("btn-tgl-craft", t.crafting?.running, "⏹️ Dừng Chế Tạo", "▶️ Chạy Chế Tạo");
  }

  function fmtSec(s) {
    s = Math.max(0, Number(s) || 0);
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    const sec = s % 60;
    return `${h}:${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
  }

  // ---------------------------------------------------------------------------
  // RENDER 7 TABS
  // ---------------------------------------------------------------------------
  function renderActiveTab() {
    if (!state.snapshot) return;
    document.querySelectorAll(".tab-btn").forEach((b) => b.classList.toggle("active", b.dataset.tab === state.activeTab));
    const root = $("tab-content");
    const renderers = {
      internal: renderInternalTab,
      thaophat: renderThaoPhatTab,
      binhman: renderBinhManTab,
      goidan: renderGoiDanTab,
      overview: renderOverviewTab,
      battle: renderBattleTab,
      nienthu: renderNienThuTab,
    };
    renderers[state.activeTab](root);
    updateRunningButtonsOnly();
    renderAuxDomOnly();
  }

  // TAB 1: NỘI CHÍNH & NGHIÊN CỨU
  function renderInternalTab(root) {
    const snap = state.snapshot;
    const prof = snap.profile;
    const bld = prof.building;
    const res = prof.research;
    const rsrc = prof.resource;
    const logi = prof.logistics;
    const dt = prof.ditrai;
    const bases = snap.roster.bases || [];
    const cities = snap.roster.cities || [];
    const camps = snap.roster.camps?.length ? snap.roster.camps : bases;

    if (!state.selectedBldCityId && bases.length) state.selectedBldCityId = bases[0].id;
    const curBldCid = state.selectedBldCityId;
    const curCityCfg = bld.cities[String(curBldCid)] || { enabled: false, resource: false, plans: [] };
    const plans = curCityCfg.plans || [];

    const boxNames = [
      "1: Dân Sinh Bảo Nang",
      "6: Dân Sinh Bảo Phiên",
      "11: Dân Sinh Chi Hạp",
      "16: Dân Sinh Chi Độc",
      "24: Dân Sinh Bảo Đỉnh",
      "35: Bạch Kim Tài Nguyên Lễ Hộp",
    ];
    const chestOpts = (state.meta?.chests || []).map((c) => `<option value="${esc(c.name)}">${esc(c.name)}</option>`).join("");
    const baseOpts = bases.map((b) => `<option value="${b.id}">${esc(b.display_name)}</option>`).join("");
    const cityOpts = cities.map((c) => `<option value="${c.id}">${esc(c.display_name)}</option>`).join("");
    const campOpts = camps.map((c) => `<option value="${c.id}">${esc(c.display_name)}</option>`).join("");

    // Group building plans by gid preserving order (ADR-0016)
    const groupedOrder = [];
    const groupedMap = {};
    for (const p of plans) {
      const gid = Number(p.gid || 1);
      if (!groupedMap[gid]) { groupedMap[gid] = []; groupedOrder.push(gid); }
      groupedMap[gid].push(p);
    }

    let bldRowsHtml = "";
    for (const gid of groupedOrder) {
      const plots = groupedMap[gid];
      if (plots.length === 1) {
        const p = plots[0];
        const done = Number(p.cur_lvl || 0) >= Number(p.target_level || 20);
        bldRowsHtml += `<tr class="${done ? "row-done" : ""} ${state.selectedBldPid === p.pid ? "selected" : ""}" data-pid="${p.pid}" data-gid="${gid}">
          <td><input type="checkbox" class="bld-chk" data-pid="${p.pid}" ${p.enabled ? "checked" : ""}/></td>
          <td>${esc(p.name)}</td>
          <td>${p.pid}</td>
          <td>${p.cur_lvl ?? 0}</td>
          <td><input type="number" class="bld-tgt" data-pid="${p.pid}" value="${p.target_level ?? 20}" min="0" max="35" style="width:58px;"/></td>
        </tr>`;
      } else {
        const allEn = plots.every((x) => x.enabled);
        const lvls = plots.map((x) => Number(x.cur_lvl || 0));
        const maxTgt = Math.max(...plots.map((x) => Number(x.target_level || 20)));
        const isOpen = state.expandedBldGroups.has(gid);
        bldRowsHtml += `<tr style="background:#1c2136;" data-group="${gid}">
          <td><input type="checkbox" class="bld-grp-chk" data-gid="${gid}" ${allEn ? "checked" : ""}/></td>
          <td><button class="btn-sm bld-grp-exp" data-gid="${gid}">${isOpen ? "▾" : "▸"}</button> <strong>${esc(plots[0].name)} (${plots.length} ô)</strong></td>
          <td>Nhóm</td>
          <td>${Math.min(...lvls)}-${Math.max(...lvls)}</td>
          <td><input type="number" class="bld-grp-tgt" data-gid="${gid}" value="${maxTgt}" min="0" max="35" style="width:58px;"/></td>
        </tr>`;
        if (isOpen) {
          for (const p of plots) {
            const done = Number(p.cur_lvl || 0) >= Number(p.target_level || 20);
            bldRowsHtml += `<tr class="${done ? "row-done" : ""}" data-pid="${p.pid}">
              <td><input type="checkbox" class="bld-chk" data-pid="${p.pid}" ${p.enabled ? "checked" : ""}/></td>
              <td style="padding-left:26px;">↳ Ô ${p.pid}</td>
              <td>${p.pid}</td>
              <td>${p.cur_lvl ?? 0}</td>
              <td><input type="number" class="bld-tgt" data-pid="${p.pid}" value="${p.target_level ?? 20}" min="0" max="35" style="width:58px;"/></td>
            </tr>`;
          }
        }
      }
    }

    const techs = res.techs?.length
      ? res.techs
      : (state.meta?.tech_names || []).map((t) => ({ id: t.id, name: t.name, enabled: false, target_level: 20, current_level: snap.tech_levels[t.id] ?? "-" }));

    const mergedLogs = [...(snap.logs.building || []), ...(snap.logs.logistics || [])].slice(-250);

    root.innerHTML = `
      <div class="grid-internal">
        <!-- CỘT 1 -->
        <div>
          <div class="card">
            <div class="card-title">⚙️ Điều khiển Nội Chính</div>
            <div class="form-row">
              <button id="btn-tgl-bld" class="btn-success btn-sm">▶️ Xây</button>
              <button id="btn-tgl-res" class="btn-success btn-sm">▶️ Nghiên Cứu</button>
              <button id="btn-tgl-resmon" class="btn-success btn-sm">▶️ Tự mở rương TN/Vàng</button>
            </div>
            <div class="form-row" style="margin-bottom:0;">
              <button id="btn-bld-all-on" class="btn-sm">☑ Chọn hết thành</button>
              <button id="btn-bld-all-off" class="btn-sm">☐ Bỏ hết</button>
            </div>
          </div>

          <div class="card">
            <div class="card-title">🏰 Danh sách Thành / Trại</div>
            <div class="table-wrap" style="max-height:260px;">
              <table>
                <thead><tr><th>Thành</th><th>Xây</th><th>TN</th><th>NC</th></tr></thead>
                <tbody>
                  ${bases.map((b) => {
                    const c = bld.cities[String(b.id)] || {};
                    const isNc = res.city_id === b.id;
                    return `<tr class="bld-base-row ${b.id === curBldCid ? "selected" : ""}" data-bid="${b.id}">
                      <td>${esc(b.name)}</td>
                      <td><input type="checkbox" class="base-bld-chk" data-bid="${b.id}" ${c.enabled ? "checked" : ""}/></td>
                      <td><input type="checkbox" class="base-res-chk" data-bid="${b.id}" ${c.resource || rsrc.resource_cities.includes(b.id) ? "checked" : ""}/></td>
                      <td><input type="radio" name="nc-city" class="base-nc-rad" data-bid="${b.id}" ${isNc ? "checked" : ""}/></td>
                    </tr>`;
                  }).join("")}
                </tbody>
              </table>
            </div>
          </div>

          <div class="card">
            <div class="card-title">🏕️ Di Trại Độc Lập</div>
            <div class="field"><label>Doanh trại</label><select id="dt-camp">${campOpts}</select></div>
            <div class="form-row">
              <label>Đích X <input id="dt-x" type="number" value="${esc(dt.dest_x)}" style="width:70px;"/></label>
              <label>Y <input id="dt-y" type="number" value="${esc(dt.dest_y)}" style="width:70px;"/></label>
            </div>
            <div class="form-row">
              <button id="btn-dt-start" class="btn-success btn-sm">▶ Dịch Trại</button>
              <button id="btn-dt-stop" class="btn-danger btn-sm">⏹ Dừng</button>
            </div>
            <div id="dt-status-lbl" style="font-size:12px;color:var(--info);">Sẵn sàng</div>
          </div>
        </div>

        <!-- CỘT 2 -->
        <div>
          <div class="card">
            <div class="card-title">
              <span>🏗️ Xây Dựng (${esc(bases.find((b) => b.id === curBldCid)?.name || curBldCid || "")})</span>
              <button id="btn-bld-fetch" class="btn-primary btn-sm">🔄 Tải công trình</button>
            </div>
            <div class="form-row">
              <label>Slots <select id="bld-slots">${[1, 2, 3].map((n) => `<option ${Number(bld.slots) === n ? "selected" : ""}>${n}</option>`).join("")}</select></label>
              <label><input id="bld-speedup" type="checkbox" ${bld.auto_speedup ? "checked" : ""}/> Tăng tốc</label>
              <select id="bld-spd-item">${["Ngân Bảo", "Coin", "Lệnh Bài"].map((x) => `<option ${bld.speedup_item === x ? "selected" : ""}>${x}</option>`).join("")}</select>
              <label>≤ <input id="bld-spd-hrs" type="text" value="${esc(bld.speedup_hours)}" style="width:48px;"/>h</label>
              <label>Chu kỳ <input id="bld-interval" type="number" value="${esc(bld.interval)}" style="width:55px;"/>s</label>
              <label><input id="bld-even" type="checkbox" ${bld.even_upgrade ? "checked" : ""}/> Nâng đồng đều</label>
            </div>
            <div class="form-row">
              <button id="btn-bld-all-chk" class="btn-sm">☑ Chọn tất cả</button>
              <button id="btn-bld-none-chk" class="btn-sm">☐ Bỏ chọn</button>
              <input id="bld-batch-lvl" type="number" value="20" min="0" max="35" style="width:60px;"/>
              <button id="btn-bld-set-all" class="btn-sm">🌟 Đặt cấp tất cả</button>
              <button id="btn-bld-demolish" class="btn-warning btn-sm">🔨 Đặt cấp 0 (Dỡ ô chọn)</button>
            </div>
            <div class="table-wrap" style="max-height:280px;">
              <table>
                <thead><tr><th>Chạy</th><th>Công trình</th><th>Ô (PID)</th><th>HT</th><th>Cấp MT</th></tr></thead>
                <tbody>${bldRowsHtml || '<tr><td colspan="5" style="color:var(--muted);">Bấm "Tải công trình" để nạp dữ liệu từ server.</td></tr>'}</tbody>
              </table>
            </div>
          </div>

          <div class="card">
            <div class="card-title">
              <span>🔬 Kỹ Thuật Đại Học (29 Kỹ Thuật)</span>
              <button id="btn-res-fetch" class="btn-primary btn-sm">🔄 Tải kỹ thuật</button>
            </div>
            <div class="form-row">
              <label><input id="res-art" type="checkbox" ${res.art_speedup ? "checked" : ""}/> 📜 Binh Pháp</label>
              <label><input id="res-even" type="checkbox" ${res.even_research ? "checked" : ""}/> ⚖️ Đồng đều</label>
              <label>Chu kỳ <input id="res-interval" type="number" value="${esc(res.interval)}" style="width:55px;"/>s</label>
              <button id="btn-res-all" class="btn-sm">☑ Tất cả</button>
              <button id="btn-res-none" class="btn-sm">☐ Bỏ</button>
              <input id="res-batch-lvl" type="number" value="20" min="1" max="30" style="width:55px;"/>
              <button id="btn-res-set-all" class="btn-sm">🌟 Đặt tất cả</button>
            </div>
            <div class="table-wrap" style="max-height:240px;">
              <table>
                <thead><tr><th>Chạy</th><th>Kỹ thuật</th><th>HT</th><th>Cấp MT</th><th>Ưu tiên</th></tr></thead>
                <tbody>
                  ${techs.map((t, idx) => {
                    const cur = snap.tech_levels[t.id] ?? t.current_level ?? "-";
                    const done = Number(cur) >= Number(t.target_level || 20);
                    return `<tr class="${done ? "row-done" : ""}">
                      <td><input type="checkbox" class="res-chk" data-idx="${idx}" ${t.enabled ? "checked" : ""}/></td>
                      <td>${esc(t.name)}</td>
                      <td>${cur}</td>
                      <td><input type="number" class="res-tgt" data-idx="${idx}" value="${t.target_level ?? 20}" min="1" max="30" style="width:55px;"/></td>
                      <td>
                        <button class="btn-sm res-up" data-idx="${idx}">⬆️</button>
                        <button class="btn-sm res-down" data-idx="${idx}">⬇️</button>
                      </td>
                    </tr>`;
                  }).join("")}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <!-- CỘT 3 -->
        <div>
          <div class="card">
            <div class="card-title">📦 Ngưỡng Tài Nguyên & Rương</div>
            <div class="form-row"><label><input id="rsrc-open-bld" type="checkbox" ${bld.auto_open_box ? "checked" : ""}/> Mở khi thiếu lúc xây dựng</label></div>
            <div class="form-grid" style="margin-bottom:8px;">
              <label>Vàng tối thiểu</label><input id="rsrc-gold" type="text" value="${esc(rsrc.gold_threshold)}"/>
              <label>Gỗ / Sắt / Đá / Thực (%)</label>
              <div class="form-row" style="margin:0;">
                <input id="rsrc-wood" type="number" value="${esc(rsrc.wood_pct)}" style="width:54px;"/>
                <input id="rsrc-iron" type="number" value="${esc(rsrc.iron_pct)}" style="width:54px;"/>
                <input id="rsrc-stone" type="number" value="${esc(rsrc.stone_pct)}" style="width:54px;"/>
                <input id="rsrc-food" type="number" value="${esc(rsrc.food_pct)}" style="width:54px;"/>
              </div>
              <label>Rương Vàng</label><select id="rsrc-gbox">${boxNames.map((n, i) => `<option value="${i}" ${Number(rsrc.gold_box_idx) === i ? "selected" : ""}>${esc(n)}</option>`).join("")}</select>
              <label>Rương TN</label><select id="rsrc-tnbox">${boxNames.map((n, i) => `<option value="${i}" ${Number(rsrc.tn_box_idx) === i ? "selected" : ""}>${esc(n)}</option>`).join("")}</select>
            </div>
            <div class="form-row">
              <label><input id="aux-daily" type="checkbox" ${logi.auto_daily_reward ? "checked" : ""}/> Thưởng ngày</label>
              <label><input id="aux-comfort" type="checkbox" ${bld.auto_comfort ? "checked" : ""}/> Tự an ủi</label>
              <label><input id="aux-boost" type="checkbox" ${bld.auto_boost ? "checked" : ""}/> DS kiến trúc <span id="aux-boost-lbl" style="color:#4ade80;"></span></label>
            </div>
            <div class="form-row">
              <label><input id="aux-explore" type="checkbox" ${logi.auto_explore ? "checked" : ""}/> Thám bảo <span id="aux-explore-lbl" style="color:#4ade80;"></span></label>
              <label><input id="aux-whip" type="checkbox" ${logi.explore_use_whip ? "checked" : ""}/> Roi</label>
              <label><input id="aux-coin" type="checkbox" ${logi.explore_use_coin ? "checked" : ""}/> Coin</label>
              <input id="aux-turns" type="number" value="${esc(logi.explore_turns)}" style="width:52px;" title="Số lượt"/>
              <button id="btn-run-explore" class="btn-sm">🧭 Thám bảo</button>
            </div>
          </div>

          <div class="card">
            <div class="card-title">🎁 Mở Rương Hàng Loạt & Hậu Cần</div>
            <div class="form-row">
              <select id="chest-type" style="flex:1;">${chestOpts}</select>
              <select id="chest-city">${cityOpts}</select>
            </div>
            <div class="form-row">
              <label>Số lượt <input id="chest-times" type="number" value="10" min="1" style="width:70px;"/></label>
              <button id="btn-chest-start" class="btn-success btn-sm">▶️ Mở</button>
              <button id="btn-chest-stop" class="btn-danger btn-sm">⏹️ Dừng</button>
            </div>
            <div class="progress-track"><div id="chest-progress-fill" class="progress-fill"></div></div>
            <div id="chest-progress-lbl" style="font-size:12px;color:var(--muted);margin:4px 0 8px;">Sẵn sàng</div>

            <div class="form-row">
              <select id="logi-from">${baseOpts}</select> ➔ <select id="logi-to">${baseOpts}</select>
              <select id="logi-type"><option value="1">1: Bộ binh</option><option value="2">2: Kỵ binh</option><option value="3">3: Cung binh</option></select>
              <input id="logi-amt" type="number" value="${esc(logi.amount)}" style="width:75px;"/>
              <button id="btn-logi-xfer" class="btn-sm">🚚 Chuyển quân</button>
              <button id="btn-logi-comfort" class="btn-sm">🕊️ An dân</button>
              <button id="btn-logi-daily" class="btn-sm">🎁 Điểm danh</button>
            </div>
          </div>

          <div class="card">
            <div class="card-title">
              <span>📜 Nhật ký Nội Chính & Hậu Cần</span>
              <button id="btn-clr-int-log" class="btn-sm">🗑️ Xóa</button>
            </div>
            <div id="log-internal" class="log-box">${esc(mergedLogs.join("\n"))}</div>
          </div>
        </div>
      </div>`;

    // Bind Internal tab events
    $("btn-tgl-bld").onclick = () => toggleTask("building");
    $("btn-tgl-res").onclick = () => toggleTask("research");
    $("btn-tgl-resmon").onclick = () => toggleTask("resource_monitor");
    $("btn-bld-fetch").onclick = async () => {
      try {
        await api(`/api/accounts/${encodeURIComponent(state.currentKey)}/buildings/fetch`, { method: "POST", body: { city_id: curBldCid } });
      } catch (e) { showToast("Lỗi tải công trình", e.message, "error"); }
    };
    $("btn-res-fetch").onclick = async () => {
      try {
        await api(`/api/accounts/${encodeURIComponent(state.currentKey)}/techs/fetch`, { method: "POST", body: { city_id: res.city_id || curBldCid } });
      } catch (e) { showToast("Lỗi tải kỹ thuật", e.message, "error"); }
    };
    $("btn-bld-all-on").onclick = () => {
      bases.forEach((b) => { bld.cities[String(b.id)] = { ...(bld.cities[String(b.id)] || {}), name: b.name, enabled: true }; });
      scheduleProfileSave({ building: { cities: bld.cities } });
      renderActiveTab();
    };
    $("btn-bld-all-off").onclick = () => {
      bases.forEach((b) => { bld.cities[String(b.id)] = { ...(bld.cities[String(b.id)] || {}), name: b.name, enabled: false }; });
      scheduleProfileSave({ building: { cities: bld.cities } });
      renderActiveTab();
    };

    root.querySelectorAll(".bld-base-row").forEach((tr) => {
      tr.addEventListener("click", (e) => {
        if (e.target.tagName === "INPUT") return;
        state.selectedBldCityId = Number(tr.dataset.bid);
        renderActiveTab();
      });
    });
    root.querySelectorAll(".base-bld-chk").forEach((chk) => {
      chk.onchange = () => {
        const bid = chk.dataset.bid;
        bld.cities[bid] = { ...(bld.cities[bid] || {}), enabled: chk.checked };
        scheduleProfileSave({ building: { cities: bld.cities } });
      };
    });
    root.querySelectorAll(".base-res-chk").forEach((chk) => {
      chk.onchange = () => {
        const bid = Number(chk.dataset.bid);
        bld.cities[String(bid)] = { ...(bld.cities[String(bid)] || {}), resource: chk.checked };
        const set = new Set(rsrc.resource_cities || []);
        if (chk.checked) set.add(bid); else set.delete(bid);
        rsrc.resource_cities = [...set];
        scheduleProfileSave({ building: { cities: bld.cities }, resource: { resource_cities: rsrc.resource_cities } });
      };
    });
    root.querySelectorAll(".base-nc-rad").forEach((rad) => {
      rad.onchange = () => {
        res.city_id = Number(rad.dataset.bid);
        scheduleProfileSave({ research: { city_id: res.city_id } });
      };
    });

    const saveBldMeta = () => scheduleProfileSave({
      building: {
        slots: Number($("bld-slots").value),
        auto_speedup: $("bld-speedup").checked,
        speedup_item: $("bld-spd-item").value,
        speedup_hours: $("bld-spd-hrs").value,
        interval: $("bld-interval").value,
        even_upgrade: $("bld-even").checked,
        auto_comfort: $("aux-comfort").checked,
        auto_boost: $("aux-boost").checked,
        auto_open_box: $("rsrc-open-bld").checked,
      },
    });
    ["bld-slots", "bld-speedup", "bld-spd-item", "bld-spd-hrs", "bld-interval", "bld-even", "aux-comfort", "aux-boost", "rsrc-open-bld"].forEach((id) => {
      $(id).onchange = saveBldMeta;
    });

    root.querySelectorAll(".bld-grp-exp").forEach((btn) => {
      btn.onclick = (e) => {
        e.stopPropagation();
        const gid = Number(btn.dataset.gid);
        if (state.expandedBldGroups.has(gid)) state.expandedBldGroups.delete(gid); else state.expandedBldGroups.add(gid);
        renderActiveTab();
      };
    });
    root.querySelectorAll(".bld-chk").forEach((chk) => {
      chk.onchange = () => {
        const pid = Number(chk.dataset.pid);
        const p = plans.find((x) => Number(x.pid) === pid);
        if (p) p.enabled = chk.checked;
        scheduleProfileSave({ building: { cities: bld.cities } });
      };
    });
    root.querySelectorAll(".bld-tgt").forEach((inp) => {
      inp.onchange = () => {
        const pid = Number(inp.dataset.pid);
        const p = plans.find((x) => Number(x.pid) === pid);
        if (p) { p.target_level = Number(inp.value); p.enabled = true; }
        scheduleProfileSave({ building: { cities: bld.cities } });
      };
    });
    root.querySelectorAll(".bld-grp-chk").forEach((chk) => {
      chk.onchange = () => {
        const gid = Number(chk.dataset.gid);
        plans.forEach((p) => { if (Number(p.gid) === gid) p.enabled = chk.checked; });
        scheduleProfileSave({ building: { cities: bld.cities } });
        renderActiveTab();
      };
    });
    root.querySelectorAll(".bld-grp-tgt").forEach((inp) => {
      inp.onchange = () => {
        const gid = Number(inp.dataset.gid);
        const v = Number(inp.value);
        plans.forEach((p) => { if (Number(p.gid) === gid) { p.target_level = v; p.enabled = true; } });
        scheduleProfileSave({ building: { cities: bld.cities } });
        renderActiveTab();
      };
    });
    root.querySelectorAll("tr[data-pid]").forEach((tr) => {
      tr.onclick = (e) => {
        if (e.target.tagName === "INPUT") return;
        state.selectedBldPid = Number(tr.dataset.pid);
        renderActiveTab();
      };
    });
    $("btn-bld-all-chk").onclick = () => { plans.forEach((p) => (p.enabled = true)); scheduleProfileSave({ building: { cities: bld.cities } }); renderActiveTab(); };
    $("btn-bld-none-chk").onclick = () => { plans.forEach((p) => (p.enabled = false)); scheduleProfileSave({ building: { cities: bld.cities } }); renderActiveTab(); };
    $("btn-bld-set-all").onclick = () => {
      const v = Number($("bld-batch-lvl").value || 20);
      plans.forEach((p) => { p.target_level = v; p.enabled = true; });
      scheduleProfileSave({ building: { cities: bld.cities } });
      renderActiveTab();
    };
    $("btn-bld-demolish").onclick = () => {
      if (!state.selectedBldPid) return showToast("Chọn công trình", "Nhấp vào 1 ô công trình trước khi đặt cấp 0.", "warn");
      const p = plans.find((x) => Number(x.pid) === state.selectedBldPid);
      if (p) { p.target_level = 0; p.enabled = true; }
      scheduleProfileSave({ building: { cities: bld.cities } });
      renderActiveTab();
    };

    // Research bindings
    res.techs = techs;
    const saveResMeta = () => scheduleProfileSave({
      research: {
        art_speedup: $("res-art").checked,
        even_research: $("res-even").checked,
        interval: $("res-interval").value,
        techs: res.techs,
      },
    });
    ["res-art", "res-even", "res-interval"].forEach((id) => ($(id).onchange = saveResMeta));
    $("btn-res-all").onclick = () => { res.techs.forEach((t) => (t.enabled = true)); saveResMeta(); renderActiveTab(); };
    $("btn-res-none").onclick = () => { res.techs.forEach((t) => (t.enabled = false)); saveResMeta(); renderActiveTab(); };
    $("btn-res-set-all").onclick = () => {
      const v = Number($("res-batch-lvl").value || 20);
      res.techs.forEach((t) => (t.target_level = v));
      saveResMeta();
      renderActiveTab();
    };
    root.querySelectorAll(".res-chk").forEach((c) => (c.onchange = () => { res.techs[Number(c.dataset.idx)].enabled = c.checked; saveResMeta(); }));
    root.querySelectorAll(".res-tgt").forEach((i) => (i.onchange = () => { res.techs[Number(i.dataset.idx)].target_level = Number(i.value); saveResMeta(); }));
    root.querySelectorAll(".res-up").forEach((b) => (b.onclick = () => {
      const idx = Number(b.dataset.idx);
      if (idx > 0) { [res.techs[idx - 1], res.techs[idx]] = [res.techs[idx], res.techs[idx - 1]]; saveResMeta(); renderActiveTab(); }
    }));
    root.querySelectorAll(".res-down").forEach((b) => (b.onclick = () => {
      const idx = Number(b.dataset.idx);
      if (idx < res.techs.length - 1) { [res.techs[idx + 1], res.techs[idx]] = [res.techs[idx], res.techs[idx + 1]]; saveResMeta(); renderActiveTab(); }
    }));

    // Resource & Aux bindings
    const saveResCfg = () => scheduleProfileSave({
      resource: {
        gold_threshold: $("rsrc-gold").value,
        wood_pct: $("rsrc-wood").value,
        iron_pct: $("rsrc-iron").value,
        stone_pct: $("rsrc-stone").value,
        food_pct: $("rsrc-food").value,
        gold_box_idx: Number($("rsrc-gbox").value),
        tn_box_idx: Number($("rsrc-tnbox").value),
        auto_open_box: $("rsrc-open-bld").checked,
      },
      logistics: {
        auto_daily_reward: $("aux-daily").checked,
        auto_explore: $("aux-explore").checked,
        explore_use_whip: $("aux-whip").checked,
        explore_use_coin: $("aux-coin").checked,
        explore_turns: $("aux-turns").value,
        amount: $("logi-amt").value,
      },
      ditrai: { dest_x: $("dt-x").value, dest_y: $("dt-y").value },
    });
    ["rsrc-gold", "rsrc-wood", "rsrc-iron", "rsrc-stone", "rsrc-food", "rsrc-gbox", "rsrc-tnbox",
      "aux-daily", "aux-explore", "aux-whip", "aux-coin", "aux-turns", "logi-amt", "dt-x", "dt-y"].forEach((id) => {
      $(id).onchange = () => {
        if (id === "aux-whip" && $("aux-whip").checked) $("aux-coin").checked = false;
        if (id === "aux-coin" && $("aux-coin").checked) $("aux-whip").checked = false;
        saveResCfg();
      };
    });

    $("btn-run-explore").onclick = () => api(`/api/accounts/${encodeURIComponent(state.currentKey)}/aux/explore`, {
      method: "POST",
      body: { use_whip: $("aux-whip").checked, use_coin: $("aux-coin").checked, turns: Number($("aux-turns").value || 1) },
    });
    $("btn-chest-start").onclick = async () => {
      try {
        await api(`/api/accounts/${encodeURIComponent(state.currentKey)}/chests/start`, {
          method: "POST",
          body: { chest_name: $("chest-type").value, times: Number($("chest-times").value || 1), city_id: Number($("chest-city").value || 0) },
        });
      } catch (e) { showToast("Lỗi mở rương", e.message, "error"); }
    };
    $("btn-chest-stop").onclick = () => api(`/api/accounts/${encodeURIComponent(state.currentKey)}/chests/stop`, { method: "POST" });
    $("btn-logi-xfer").onclick = () => api(`/api/accounts/${encodeURIComponent(state.currentKey)}/aux/transfer`, {
      method: "POST",
      body: {
        from_city_id: Number($("logi-from").value),
        to_city_id: Number($("logi-to").value),
        army_id: Number($("logi-type").value),
        amount: Number($("logi-amt").value || 1000),
      },
    });
    $("btn-logi-comfort").onclick = () => api(`/api/accounts/${encodeURIComponent(state.currentKey)}/aux/comfort`, {
      method: "POST", body: { city_id: Number($("logi-from").value) },
    });
    $("btn-logi-daily").onclick = () => api(`/api/accounts/${encodeURIComponent(state.currentKey)}/aux/daily-reward`, { method: "POST" });
    $("btn-dt-start").onclick = async () => {
      try {
        await api(`/api/accounts/${encodeURIComponent(state.currentKey)}/ditrai/start`, {
          method: "POST", body: { camp_id: Number($("dt-camp").value), dest_x: Number($("dt-x").value), dest_y: Number($("dt-y").value) },
        });
      } catch (e) { showToast("Lỗi Di Trại", e.message, "error"); }
    };
    $("btn-dt-stop").onclick = () => api(`/api/accounts/${encodeURIComponent(state.currentKey)}/ditrai/stop`, { method: "POST" });
    $("btn-clr-int-log").onclick = () => api(`/api/accounts/${encodeURIComponent(state.currentKey)}/logs/clear`, { method: "POST", body: { channel: "building" } });
  }

  // TAB 2: THẢO PHẠT
  function renderThaoPhatTab(root) {
    const snap = state.snapshot;
    const tp = snap.profile.thao_phat;
    const bases = snap.roster.bases || [];
    const cid = tp.city_id || bases[0]?.id || 0;
    const gens = (snap.roster.generals || []).filter((g) => g.city_id === cid && g.role === "vo");
    const missions = state.meta?.missions || [];

    root.innerHTML = `
      <div class="card">
        <div class="form-row">
          <label>Thành trì <select id="tp-city">${bases.map((b) => `<option value="${b.id}" ${b.id === cid ? "selected" : ""}>${esc(b.display_name)}</option>`).join("")}</select></label>
          <label>Chiến dịch <select id="tp-mission">${missions.map((m) => `<option value="${m.idx}" ${Number(tp.mission_idx) === m.idx ? "selected" : ""}>${esc(m.name)} (ID: ${m.id})</option>`).join("")}</select></label>
          <label>Bộ <input id="tp-inf" type="number" value="${esc(tp.target_infantry)}" style="width:70px;"/></label>
          <label>Kỵ <input id="tp-cav" type="number" value="${esc(tp.target_cavalry)}" style="width:70px;"/></label>
          <label>Cung <input id="tp-arc" type="number" value="${esc(tp.target_archers)}" style="width:70px;"/></label>
          <button id="btn-tp-prov" class="btn-sm">⚔️ Biên chế ngay</button>
          <button id="btn-tgl-tp" class="btn-success btn-sm">▶️ Bắt đầu Thảo Phạt</button>
        </div>
        <div class="form-row" style="margin-bottom:0;">
          <label><input id="tp-rec" type="checkbox" ${tp.auto_recruit ? "checked" : ""}/> Tự bổ sung lính</label>
          <label><input id="tp-mor" type="checkbox" ${tp.auto_morale ? "checked" : ""}/> Tự nâng sĩ khí</label>
          <label>Sĩ khí ≥ <input id="tp-minm" type="number" value="${esc(tp.min_morale)}" style="width:58px;"/></label>
          <label>Chu kỳ <input id="tp-int" type="number" value="${esc(tp.interval)}" style="width:58px;"/>s</label>
        </div>
      </div>
      <div class="card">
        <div class="card-title">Võ tướng xuất kích (Chọn tối đa 5)</div>
        <div class="table-wrap">${renderGeneralSelectTable(gens, tp.generals, "tp-gen")}</div>
      </div>
      <div class="card">
        <div class="card-title"><span>Nhật ký Thảo Phạt</span><button id="btn-clr-tp" class="btn-sm">🗑️ Xóa</button></div>
        <div id="log-thaophat" class="log-box">${esc((snap.logs.thaophat || []).join("\n"))}</div>
      </div>`;

    const syncTp = () => scheduleProfileSave({
      thao_phat: {
        city_id: Number($("tp-city").value),
        mission_idx: Number($("tp-mission").value),
        target_infantry: $("tp-inf").value,
        target_cavalry: $("tp-cav").value,
        target_archers: $("tp-arc").value,
        auto_recruit: $("tp-rec").checked,
        auto_morale: $("tp-mor").checked,
        min_morale: $("tp-minm").value,
        interval: $("tp-int").value,
        generals: [...root.querySelectorAll(".tp-gen-chk:checked")].map((x) => Number(x.dataset.gid)),
      },
    });
    $("tp-city").onchange = () => { syncTp(); renderActiveTab(); };
    ["tp-mission", "tp-inf", "tp-cav", "tp-arc", "tp-rec", "tp-mor", "tp-minm", "tp-int"].forEach((id) => ($(id).onchange = syncTp));
    root.querySelectorAll(".tp-gen-chk").forEach((c) => (c.onchange = syncTp));
    $("btn-tgl-tp").onclick = () => toggleTask("thaophat");
    $("btn-tp-prov").onclick = async () => {
      await saveProfileImmediate(state.snapshot.profile);
      api(`/api/accounts/${encodeURIComponent(state.currentKey)}/tasks/thaophat/provision`, { method: "POST" })
        .catch((e) => showToast("Lỗi", e.message, "error"));
    };
    $("btn-clr-tp").onclick = () => api(`/api/accounts/${encodeURIComponent(state.currentKey)}/logs/clear`, { method: "POST", body: { channel: "thaophat" } });
  }

  // TAB 3: BÌNH MAN ĐA CĂN CỨ
  function renderBinhManTab(root) {
    const snap = state.snapshot;
    const bm = snap.profile.binh_man;
    const bases = snap.roster.bases || [];
    const cities = snap.roster.cities || [];
    if (!state.selectedBmBaseId && bases.length) state.selectedBmBaseId = bm.current_base_id || bases[0].id;
    const bid = state.selectedBmBaseId;
    const bcfg = bm.bases[String(bid)] || {
      name: bases.find((b) => b.id === bid)?.name || "",
      enabled: false, mode: 1, radius: "5", threshold: "30", camp_id: String(bid), parent_city_id: String(cities[0]?.id || ""),
      target_types: [7, 8, 9, 10], generals: [], target_infantry: "0", target_cavalry: "0", target_archers: "0",
      auto_recruit: true, auto_morale: true, min_morale: "95", action_combo_idx: 0,
    };
    bm.bases[String(bid)] = bcfg;
    const gens = (snap.roster.generals || []).filter((g) => g.city_id === bid && g.role === "vo");
    const manOpts = state.meta?.man_targets || [];
    const actOpts = state.meta?.attack_action_options || [];

    root.innerHTML = `
      <div class="grid-2" style="grid-template-columns: 320px 1fr;">
        <div>
          <div class="card">
            <div class="card-title">🏰 Căn Cứ Bình Man</div>
            <div class="form-row">
              <button id="btn-bm-all" class="btn-sm">✅ Chọn tất cả</button>
              <button id="btn-bm-none" class="btn-sm">❌ Bỏ tất cả</button>
              <button id="btn-bm-prov-all" class="btn-sm">⚔️ Biên chế tất cả</button>
            </div>
            <div class="table-wrap" style="max-height:280px;">
              <table>
                <thead><tr><th>Chạy</th><th>Căn cứ</th><th>Tọa độ</th><th>Tướng</th></tr></thead>
                <tbody>
                  ${bases.map((b) => {
                    const c = bm.bases[String(b.id)] || {};
                    return `<tr class="bm-base-row ${b.id === bid ? "selected" : ""}" data-bid="${b.id}">
                      <td><input type="checkbox" class="bm-base-chk" data-bid="${b.id}" ${c.enabled ? "checked" : ""}/></td>
                      <td>${esc(b.name)}</td>
                      <td>${b.pos_x},${b.pos_y}</td>
                      <td>${(c.generals || []).length}</td>
                    </tr>`;
                  }).join("")}
                </tbody>
              </table>
            </div>
            <div class="form-row" style="margin-top:10px;margin-bottom:0;">
              <label>Chu kỳ <input id="bm-int" type="number" value="${esc(bm.interval)}" style="width:55px;"/>s</label>
              <button id="btn-tgl-bm" class="btn-success btn-sm">▶️ Bắt đầu Bình Man</button>
              <button id="btn-bm-once" class="btn-sm">⚡ 1 Lượt</button>
            </div>
          </div>
        </div>
        <div>
          <div class="card">
            <div class="card-title">
              <span>⚙️ Cấu hình: ${esc(bases.find((b) => b.id === bid)?.name || bid)}</span>
              <button id="btn-bm-prov-one" class="btn-sm">⚔️ Biên chế căn cứ này</button>
            </div>
            <div class="form-row">
              <label><input type="radio" name="bm-mode" value="1" ${Number(bcfg.mode) === 1 ? "checked" : ""}/> 1: Di Doanh trại</label>
              <label><input type="radio" name="bm-mode" value="2" ${Number(bcfg.mode) === 2 ? "checked" : ""}/> 2: Từ Thành</label>
              <label>Thành mẹ <select id="bm-parent">${cities.map((c) => `<option value="${c.id}" ${String(bcfg.parent_city_id) === String(c.id) ? "selected" : ""}>${esc(c.display_name)}</option>`).join("")}</select></label>
            </div>
            <div class="form-row">
              <label>Bán kính <input id="bm-rad" type="number" value="${esc(bcfg.radius)}" style="width:55px;"/></label>
              <label>Ngưỡng TL/Quân <input id="bm-thresh" type="number" value="${esc(bcfg.threshold)}" style="width:58px;"/></label>
              <label>Chiêu đánh <select id="bm-act">${actOpts.map((o, i) => `<option value="${i}" ${Number(bcfg.action_combo_idx) === i ? "selected" : ""}>${esc(o)}</option>`).join("")}</select></label>
            </div>
            <div class="form-row">
              <label>Bộ <input id="bm-inf" type="number" value="${esc(bcfg.target_infantry)}" style="width:65px;"/></label>
              <label>Kỵ <input id="bm-cav" type="number" value="${esc(bcfg.target_cavalry)}" style="width:65px;"/></label>
              <label>Cung <input id="bm-arc" type="number" value="${esc(bcfg.target_archers)}" style="width:65px;"/></label>
              <label><input id="bm-rec" type="checkbox" ${bcfg.auto_recruit ? "checked" : ""}/> Bù lính</label>
              <label><input id="bm-mor" type="checkbox" ${bcfg.auto_morale ? "checked" : ""}/> Sĩ khí ≥</label>
              <input id="bm-minm" type="number" value="${esc(bcfg.min_morale)}" style="width:55px;"/>
            </div>
            <div class="form-row" style="margin-bottom:0;">
              <span style="color:var(--muted);">Loại Man:</span>
              ${manOpts.map((m) => `<label style="font-size:12px;"><input type="checkbox" class="bm-mtype" value="${m.id}" ${(bcfg.target_types || []).includes(m.id) ? "checked" : ""}/> ${esc(m.label)}</label>`).join("")}
            </div>
          </div>
          <div class="card">
            <div class="card-title">Võ tướng căn cứ này</div>
            <div class="table-wrap" style="max-height:200px;">${renderGeneralSelectTable(gens, bcfg.generals, "bm-gen")}</div>
          </div>
          <div class="card">
            <div class="card-title"><span>Nhật ký Bình Man</span><button id="btn-clr-bm" class="btn-sm">🗑️ Xóa</button></div>
            <div id="log-binhman" class="log-box">${esc((snap.logs.binhman || []).join("\n"))}</div>
          </div>
        </div>
      </div>`;

    const syncBm = () => {
      bcfg.mode = Number(root.querySelector('input[name="bm-mode"]:checked')?.value || 1);
      bcfg.parent_city_id = $("bm-parent").value;
      bcfg.radius = $("bm-rad").value;
      bcfg.threshold = $("bm-thresh").value;
      bcfg.action_combo_idx = Number($("bm-act").value);
      bcfg.target_infantry = $("bm-inf").value;
      bcfg.target_cavalry = $("bm-cav").value;
      bcfg.target_archers = $("bm-arc").value;
      bcfg.auto_recruit = $("bm-rec").checked;
      bcfg.auto_morale = $("bm-mor").checked;
      bcfg.min_morale = $("bm-minm").value;
      bcfg.target_types = [...root.querySelectorAll(".bm-mtype:checked")].map((x) => Number(x.value));
      bcfg.mantypes = bcfg.target_types.join(",");
      bcfg.generals = [...root.querySelectorAll(".bm-gen-chk:checked")].map((x) => Number(x.dataset.gid));
      bm.current_base_id = bid;
      bm.interval = $("bm-int").value;
      scheduleProfileSave({ binh_man: { interval: bm.interval, current_base_id: bid, bases: bm.bases } });
    };

    root.querySelectorAll(".bm-base-row").forEach((tr) => (tr.onclick = (e) => {
      if (e.target.tagName === "INPUT") return;
      state.selectedBmBaseId = Number(tr.dataset.bid);
      renderActiveTab();
    }));
    root.querySelectorAll(".bm-base-chk").forEach((c) => (c.onchange = () => {
      const k = c.dataset.bid;
      bm.bases[k] = { ...(bm.bases[k] || bcfg), enabled: c.checked };
      scheduleProfileSave({ binh_man: { bases: bm.bases } });
    }));
    $("btn-bm-all").onclick = () => { bases.forEach((b) => { bm.bases[String(b.id)] = { ...(bm.bases[String(b.id)] || {}), enabled: true }; }); scheduleProfileSave({ binh_man: { bases: bm.bases } }); renderActiveTab(); };
    $("btn-bm-none").onclick = () => { bases.forEach((b) => { bm.bases[String(b.id)] = { ...(bm.bases[String(b.id)] || {}), enabled: false }; }); scheduleProfileSave({ binh_man: { bases: bm.bases } }); renderActiveTab(); };
    root.querySelectorAll('input[name="bm-mode"], .bm-mtype, .bm-gen-chk').forEach((el) => (el.onchange = syncBm));
    ["bm-int", "bm-parent", "bm-rad", "bm-thresh", "bm-act", "bm-inf", "bm-cav", "bm-arc", "bm-rec", "bm-mor", "bm-minm"].forEach((id) => ($(id).onchange = syncBm));
    $("btn-tgl-bm").onclick = () => toggleTask("binhman");
    $("btn-bm-once").onclick = async () => {
      await saveProfileImmediate(state.snapshot.profile);
      api(`/api/accounts/${encodeURIComponent(state.currentKey)}/tasks/binhman/once`, { method: "POST" }).catch((e) => showToast("Lỗi", e.message, "error"));
    };
    $("btn-bm-prov-one").onclick = async () => {
      await saveProfileImmediate(state.snapshot.profile);
      api(`/api/accounts/${encodeURIComponent(state.currentKey)}/tasks/binhman/provision`, { method: "POST", body: { base_id: bid } }).catch((e) => showToast("Lỗi", e.message, "error"));
    };
    $("btn-bm-prov-all").onclick = async () => {
      await saveProfileImmediate(state.snapshot.profile);
      api(`/api/accounts/${encodeURIComponent(state.currentKey)}/tasks/binhman/provision`, { method: "POST", body: {} }).catch((e) => showToast("Lỗi", e.message, "error"));
    };
    $("btn-clr-bm").onclick = () => api(`/api/accounts/${encodeURIComponent(state.currentKey)}/logs/clear`, { method: "POST", body: { channel: "binhman" } });
  }

  // TAB 4: GỌI MAN & VONG LINH
  function renderGoiDanTab(root) {
    const snap = state.snapshot;
    const gd = snap.profile.goi_dan;
    const cities = snap.roster.cities?.length ? snap.roster.cities : (snap.roster.bases || []);
    const cid = gd.city_id || cities[0]?.id || 0;
    const gens = (snap.roster.generals || []).filter((g) => g.city_id === cid && g.role === "vo");
    const manOpts = [{ id: 301, label: "301: Vong Linh (Bùa 268)" }, ...(state.meta?.man_targets || [])];
    const actOpts = state.meta?.attack_action_options || [];

    root.innerHTML = `
      <div class="card">
        <div class="form-row">
          <label>Thành trì <select id="gd-city">${cities.map((c) => `<option value="${c.id}" ${c.id === cid ? "selected" : ""}>${esc(c.display_name)}</option>`).join("")}</select></label>
          <label>Bán kính <input id="gd-rad" type="number" value="${esc(gd.radius)}" style="width:58px;"/></label>
          <label>Chu kỳ <input id="gd-int" type="number" value="${esc(gd.interval)}" style="width:58px;"/>s</label>
          <label>Chiêu <select id="gd-act">${actOpts.map((o, i) => `<option value="${i}" ${Number(gd.action_combo_idx) === i ? "selected" : ""}>${esc(o)}</option>`).join("")}</select></label>
          <button id="btn-tgl-gd" class="btn-success btn-sm">▶️ Bắt đầu Gọi Man</button>
          <button id="btn-gd-once" class="btn-sm">⚡ Chạy 1 Lượt</button>
        </div>
        <div class="form-row">
          <label>Bộ <input id="gd-inf" type="number" value="${esc(gd.target_infantry)}" style="width:68px;"/></label>
          <label>Kỵ <input id="gd-cav" type="number" value="${esc(gd.target_cavalry)}" style="width:68px;"/></label>
          <label>Cung <input id="gd-arc" type="number" value="${esc(gd.target_archers)}" style="width:68px;"/></label>
          <button id="btn-gd-prov" class="btn-sm">⚔️ Biên chế ngay</button>
          <label><input id="gd-rec" type="checkbox" ${gd.auto_recruit ? "checked" : ""}/> Bù lính</label>
          <label><input id="gd-mor" type="checkbox" ${gd.auto_morale ? "checked" : ""}/> Sĩ khí ≥</label>
          <input id="gd-minm" type="number" value="${esc(gd.min_morale)}" style="width:55px;"/>
        </div>
        <div class="form-row" style="margin-bottom:0;">
          <span style="color:var(--muted);">Mục tiêu:</span>
          ${manOpts.map((m) => `<label style="font-size:12px;"><input type="checkbox" class="gd-mtype" value="${m.id}" ${(gd.target_types || [301]).includes(m.id) ? "checked" : ""}/> ${esc(m.label)}</label>`).join("")}
        </div>
      </div>
      <div class="card">
        <div class="card-title">Võ tướng xuất kích</div>
        <div class="table-wrap">${renderGeneralSelectTable(gens, gd.generals, "gd-gen")}</div>
      </div>
      <div class="card">
        <div class="card-title"><span>Nhật ký Gọi Man</span><button id="btn-clr-gd" class="btn-sm">🗑️ Xóa</button></div>
        <div id="log-goidan" class="log-box">${esc((snap.logs.goidan || []).join("\n"))}</div>
      </div>`;

    const syncGd = () => {
      const types = [...root.querySelectorAll(".gd-mtype:checked")].map((x) => Number(x.value));
      scheduleProfileSave({
        goi_dan: {
          city_id: Number($("gd-city").value),
          radius: $("gd-rad").value,
          interval: $("gd-int").value,
          action_combo_idx: Number($("gd-act").value),
          target_infantry: $("gd-inf").value,
          target_cavalry: $("gd-cav").value,
          target_archers: $("gd-arc").value,
          auto_recruit: $("gd-rec").checked,
          auto_recover: $("gd-rec").checked,
          auto_morale: $("gd-mor").checked,
          min_morale: $("gd-minm").value,
          target_types: types.length ? types : [301],
          target_type: types[0] || 301,
          generals: [...root.querySelectorAll(".gd-gen-chk:checked")].map((x) => Number(x.dataset.gid)),
        },
      });
    };
    $("gd-city").onchange = () => { syncGd(); renderActiveTab(); };
    ["gd-rad", "gd-int", "gd-act", "gd-inf", "gd-cav", "gd-arc", "gd-rec", "gd-mor", "gd-minm"].forEach((id) => ($(id).onchange = syncGd));
    root.querySelectorAll(".gd-mtype, .gd-gen-chk").forEach((c) => (c.onchange = syncGd));
    $("btn-tgl-gd").onclick = () => toggleTask("goidan");
    $("btn-gd-once").onclick = async () => {
      await saveProfileImmediate(state.snapshot.profile);
      api(`/api/accounts/${encodeURIComponent(state.currentKey)}/tasks/goidan/once`, { method: "POST" }).catch((e) => showToast("Lỗi", e.message, "error"));
    };
    $("btn-gd-prov").onclick = async () => {
      await saveProfileImmediate(state.snapshot.profile);
      api(`/api/accounts/${encodeURIComponent(state.currentKey)}/tasks/goidan/provision`, { method: "POST" }).catch((e) => showToast("Lỗi", e.message, "error"));
    };
    $("btn-clr-gd").onclick = () => api(`/api/accounts/${encodeURIComponent(state.currentKey)}/logs/clear`, { method: "POST", body: { channel: "goidan" } });
  }

  // TAB 5: TỔNG QUAN & QUÂN ĐỘI
  function renderOverviewTab(root) {
    const snap = state.snapshot;
    const bases = snap.roster.bases || [];
    const cities = snap.roster.cities?.length ? snap.roster.cities : bases;
    if (!state.selectedOverviewCityId && bases.length) state.selectedOverviewCityId = bases[0].id;
    const gens = (snap.roster.generals || []).filter((g) => g.city_id === state.selectedOverviewCityId);
    const selGen = gens.find((g) => g.id === state.selectedOverviewGenId) || gens[0] || null;
    if (selGen) state.selectedOverviewGenId = selGen.id;

    const armyGens = (snap.roster.generals || []).filter((g) => (g.army?.total || 0) > 0);
    if (state.moraleInitAccount !== state.currentKey) {
      state.selectedMoraleGens = new Set(armyGens.map((g) => g.id));
      state.moraleInitAccount = state.currentKey;
    }

    if (!state.selectedCraftCityId && cities.length) state.selectedCraftCityId = cities[0].id;
    const craftCities = snap.profile.crafting.cities || {};
    const curCraft = craftCities[String(state.selectedCraftCityId)] || { city_id: state.selectedCraftCityId, weapon_ids: [101], amount: "1000", interval: "5", enabled: false };
    const weapons = state.meta?.weapons || [];

    root.innerHTML = `
      <div class="card">
        <div class="form-row" style="margin-bottom:0;">
          <button id="btn-reward-all" class="btn-success btn-sm">🎁 Ban Thưởng Toàn Bộ</button>
          <button id="btn-open-tactician" class="btn-sm">🧠 Thiết Lập Mưu Sĩ</button>
          <button id="btn-open-equip" class="btn-sm">🛡️ Trang Bị Tướng</button>
        </div>
      </div>

      <div class="grid-3">
        <div class="card">
          <div class="card-title">Thành & Doanh trại</div>
          <div class="table-wrap" style="max-height:220px;">
            <table><thead><tr><th>Tên</th><th>Loại</th><th>Tọa độ</th></tr></thead>
            <tbody>${bases.map((b) => `<tr class="ov-base ${b.id === state.selectedOverviewCityId ? "selected" : ""}" data-bid="${b.id}"><td>${esc(b.name)}</td><td>${esc(b.type)}</td><td>${b.pos_x},${b.pos_y}</td></tr>`).join("")}</tbody></table>
          </div>
        </div>
        <div class="card">
          <div class="card-title">Tướng đồn trú</div>
          <div class="table-wrap" style="max-height:220px;">
            <table><thead><tr><th>Tên</th><th>Hệ</th><th>Cấp</th><th>TL</th><th>TT</th><th>Mưu sĩ</th><th>Trạng thái</th></tr></thead>
            <tbody>${gens.map((g) => `<tr class="ov-gen ${selGen && g.id === selGen.id ? "selected" : ""}" data-gid="${g.id}"><td>${esc(g.name)}</td><td>${g.role === "van" ? "Văn" : "Võ"}</td><td>${g.level}</td><td>${g.stamina}/${g.stamina_max}</td><td>${g.loyalty}</td><td>${esc(g.tactician_name || "-")}</td><td>${esc(g.status_text)}</td></tr>`).join("")}</tbody></table>
          </div>
        </div>
        <div class="card">
          <div class="card-title">Chi tiết biên chế</div>
          ${selGen ? `
            <div style="font-size:16px;font-weight:700;color:var(--accent);">${esc(selGen.name)} (Lv.${selGen.level})</div>
            <div style="color:var(--muted);font-size:12px;margin:4px 0 10px;">Sĩ khí: ${selGen.morale}/100 | Thể lực: ${selGen.stamina}/${selGen.stamina_max} | Trung thành: ${selGen.loyalty}</div>
            <div>Bộ binh: <strong>${(selGen.army?.infantry || 0).toLocaleString()}</strong></div>
            <div>Kỵ binh: <strong>${(selGen.army?.cavalry || 0).toLocaleString()}</strong></div>
            <div>Cung binh: <strong>${(selGen.army?.archers || 0).toLocaleString()}</strong></div>
            <div style="margin-top:8px;color:var(--accent);font-weight:700;">Tổng quân: ${(selGen.army?.total || 0).toLocaleString()}</div>
          ` : '<div style="color:var(--muted);">Chọn một tướng để xem.</div>'}
        </div>
      </div>

      <div class="grid-2">
        <div class="card">
          <div class="card-title">⚔️ Luyện Sĩ Khí Quân Đội (Đa Thành)</div>
          <div class="form-row">
            <label>Đích <select id="mo-target">${[100, 95, 90, 85].map((x) => `<option value="${x}">${x}</option>`).join("")}</select></label>
            <button id="btn-mo-all" class="btn-sm">☑ Tất cả</button>
            <button id="btn-mo-none" class="btn-sm">☐ Bỏ</button>
            <button id="btn-mo-start" class="btn-primary btn-sm">⚔️ Luyện Sĩ Khí</button>
            <button id="btn-mo-stop" class="btn-danger btn-sm">⏹️ Dừng</button>
          </div>
          <div id="morale-status-lbl" style="font-size:12px;color:var(--muted);margin-bottom:6px;"></div>
          <div class="table-wrap" style="max-height:220px;">
            <table><thead><tr><th>Chọn</th><th>Tướng</th><th>Thành</th><th>SK</th><th>Quân</th><th>Trạng thái</th></tr></thead>
            <tbody>${armyGens.map((g) => {
              const bname = bases.find((b) => b.id === g.city_id)?.name || g.city_id;
              return `<tr><td><input type="checkbox" class="mo-chk" data-gid="${g.id}" ${state.selectedMoraleGens.has(g.id) ? "checked" : ""}/></td><td>${esc(g.name)}</td><td>${esc(bname)}</td><td>${g.morale}/100</td><td>${(g.army?.total || 0).toLocaleString()}</td><td>${esc(snap.aux?.morale_gen_status?.[g.id] || "Chờ")}</td></tr>`;
            }).join("")}</tbody></table>
          </div>
        </div>

        <div class="card">
          <div class="card-title">🛠️ Chế Tạo Quân Giới (Đa Thành)</div>
          <div class="form-row">
            <label>Thành <select id="cr-city">${cities.map((c) => `<option value="${c.id}" ${c.id === state.selectedCraftCityId ? "selected" : ""}>${esc(c.display_name)}</option>`).join("")}</select></label>
            <label>SL/mẻ <input id="cr-amt" type="number" value="${esc(curCraft.amount)}" style="width:70px;"/></label>
            <label>Chu kỳ (phút) <input id="cr-int" type="number" value="${esc(curCraft.interval)}" style="width:55px;"/></label>
            <label><input id="cr-en" type="checkbox" ${curCraft.enabled ? "checked" : ""}/> Bật thành</label>
          </div>
          <div class="form-row">
            <label style="flex:1;">Quân giới (giữ Ctrl để chọn nhiều)
              <select id="cr-weapons" multiple size="3" style="width:100%;">
                ${weapons.map((w) => `<option value="${w.id}" ${(curCraft.weapon_ids || []).includes(w.id) ? "selected" : ""}>${w.id}. ${esc(w.name)} (${esc(w.category)})</option>`).join("")}
              </select>
            </label>
          </div>
          <div class="form-row">
            <button id="btn-cr-now" class="btn-sm">⚡ Chế tạo ngay</button>
            <button id="btn-tgl-craft" class="btn-success btn-sm">▶️ Chạy Chế Tạo</button>
            <span id="craft-status-lbl" style="font-size:12px;color:var(--muted);"></span>
          </div>
          <div class="table-wrap" style="max-height:150px;">
            <table><thead><tr><th>Bật</th><th>Thành</th><th>SL</th><th>Phút</th><th>Trạng thái</th></tr></thead>
            <tbody>${cities.map((c) => {
              const cfg = craftCities[String(c.id)] || {};
              return `<tr><td>${cfg.enabled ? "☑" : "☐"}</td><td>${esc(c.name)}</td><td>${esc(cfg.amount || 1000)}</td><td>${esc(cfg.interval || 5)}</td><td>${esc(snap.aux?.craft_statuses?.[c.id] || (cfg.enabled ? "Sẵn sàng" : "Tắt"))}</td></tr>`;
            }).join("")}</tbody></table>
          </div>
        </div>
      </div>`;

    root.querySelectorAll(".ov-base").forEach((tr) => (tr.onclick = () => { state.selectedOverviewCityId = Number(tr.dataset.bid); renderActiveTab(); }));
    root.querySelectorAll(".ov-gen").forEach((tr) => (tr.onclick = () => { state.selectedOverviewGenId = Number(tr.dataset.gid); renderActiveTab(); }));
    $("btn-reward-all").onclick = async () => {
      try {
        const pre = await api(`/api/accounts/${encodeURIComponent(state.currentKey)}/reward/preview`, { method: "POST" });
        if (pre.count === 0) return showToast("Ban thưởng", "Tất cả tướng đều đã đạt 100 Lòng trung thành.");
        if (!confirm(`Tìm thấy ${pre.count} tướng cần thưởng (~${pre.total_gold.toLocaleString()} Vàng). Tiến hành ngay?`)) return;
        const res = await api(`/api/accounts/${encodeURIComponent(state.currentKey)}/reward/run`, { method: "POST" });
        showToast("Ban thưởng hoàn tất", `Thành công ${res.success}/${res.total} tướng`);
      } catch (e) { showToast("Lỗi", e.message, "error"); }
    };
    $("btn-open-tactician").onclick = openTacticianModal;
    $("btn-open-equip").onclick = openEquipModal;

    root.querySelectorAll(".mo-chk").forEach((c) => (c.onchange = () => {
      const gid = Number(c.dataset.gid);
      if (c.checked) state.selectedMoraleGens.add(gid); else state.selectedMoraleGens.delete(gid);
    }));
    $("btn-mo-all").onclick = () => { armyGens.forEach((g) => state.selectedMoraleGens.add(g.id)); renderActiveTab(); };
    $("btn-mo-none").onclick = () => { state.selectedMoraleGens.clear(); renderActiveTab(); };
    $("btn-mo-start").onclick = () => api(`/api/accounts/${encodeURIComponent(state.currentKey)}/morale/start`, {
      method: "POST", body: { general_ids: [...state.selectedMoraleGens], target_morale: Number($("mo-target").value) },
    }).catch((e) => showToast("Lỗi", e.message, "error"));
    $("btn-mo-stop").onclick = () => api(`/api/accounts/${encodeURIComponent(state.currentKey)}/morale/stop`, { method: "POST" });

    const syncCraft = () => {
      const wids = [...$("cr-weapons").selectedOptions].map((o) => Number(o.value));
      craftCities[String(state.selectedCraftCityId)] = {
        city_id: state.selectedCraftCityId,
        weapon_id: wids[0] || 101,
        weapon_ids: wids.length ? wids : [101],
        amount: $("cr-amt").value,
        interval: $("cr-int").value,
        enabled: $("cr-en").checked,
      };
      scheduleProfileSave({ crafting: { cities: craftCities } });
    };
    $("cr-city").onchange = () => { state.selectedCraftCityId = Number($("cr-city").value); renderActiveTab(); };
    ["cr-amt", "cr-int", "cr-en", "cr-weapons"].forEach((id) => ($(id).onchange = syncCraft));
    $("btn-cr-now").onclick = async () => {
      await saveProfileImmediate(state.snapshot.profile);
      api(`/api/accounts/${encodeURIComponent(state.currentKey)}/tasks/crafting/now`, { method: "POST", body: { city_id: state.selectedCraftCityId } });
    };
    $("btn-tgl-craft").onclick = () => toggleTask("crafting");
  }

  // TAB 6: CHIẾN TRƯỜNG
  function renderBattleTab(root) {
    const snap = state.snapshot;
    const cb = snap.profile.combat;
    const bs = snap.aux?.battle_state;
    const bid = snap.aux?.battle_id || state.battleIdInput || "0";
    const actOpts = state.meta?.attack_action_options || [];
    const stratOpts = ["0: Tự động", "92: Kim thiền thoát xác", "93: Phản khách vi chủ", "94: Quan môn tróc tặc", "95: Cầm tặc cầm vương"];
    const formOpts = state.meta?.formations || [];
    const manualStratOpts = state.meta?.stratagems || [];

    root.innerHTML = `
      <div class="card">
        <div class="form-row">
          <label>Mã Chiến Trường <input id="bt-id" type="number" value="${esc(bid)}" style="width:100px;"/></label>
          <button id="btn-bt-load" class="btn-sm">🔍 Nạp</button>
          <button id="btn-bt-toggle" class="${snap.aux?.battle_running ? "btn-danger" : "btn-success"} btn-sm">${snap.aux?.battle_running ? "⏹️ Dừng Theo Dõi" : "▶️ Theo Dõi & Tác Chiến"}</button>
          <span class="pill">Hiệp: ${bs?.bout ?? "-"}</span>
          <span class="pill warn">Đếm ngược: ${bs?.bout_left ?? "-"}s</span>
        </div>
        <div class="form-row">
          <label><input id="cb-counter" type="checkbox" ${cb.auto_counter_formation ? "checked" : ""}/> Tự đổi trận cuối hiệp (≤</label>
          <input id="cb-win" type="number" value="${esc(cb.formation_window_seconds)}" style="width:52px;"/>s)
          <label>Chiêu <select id="cb-act">${actOpts.map((o, i) => `<option value="${i}" ${Number(cb.action_combo_idx) === i ? "selected" : ""}>${esc(o)}</option>`).join("")}</select></label>
          <label>Mưu kế <select id="cb-strat">${stratOpts.map((o, i) => `<option value="${i}" ${Number(cb.stratagem_combo_idx) === i ? "selected" : ""}>${esc(o)}</option>`).join("")}</select></label>
        </div>
        <div class="form-row" style="margin-bottom:0;">
          <label><input id="cb-skip" type="checkbox" ${cb.skip_confused_enemy ? "checked" : ""}/> Tránh đánh địch Hỗn loạn</label>
          <label><input id="cb-boss" type="checkbox" ${cb.leave_boss_last ? "checked" : ""}/> Giữ BOSS sống (Cô lập)</label>
          <label><input id="cb-cleanse" type="checkbox" ${cb.auto_cleanse_confusion ? "checked" : ""}/> Tự giải Hỗn loạn (96)</label>
          <label>Rút khẩn cấp khi quân < <input id="cb-retreat" type="number" value="${esc(cb.emergency_retreat_threshold)}" style="width:65px;"/></label>
        </div>
      </div>

      <div class="grid-2">
        <div class="card">
          <div class="card-title">🛡️ Quân Ta</div>
          <div class="table-wrap">${renderBattleTroopsTable(bs?.our_troops || [], false)}</div>
        </div>
        <div class="card">
          <div class="card-title">🎯 Phe Địch</div>
          <div class="table-wrap">${renderBattleTroopsTable(bs?.enemy_troops || [], true)}</div>
        </div>
      </div>

      <div class="card">
        <div class="form-row">
          <label>Vị trí ta <input id="bt-pos" type="number" value="${bs?.our_troops?.[0]?.position ?? 1}" style="width:60px;"/></label>
          <select id="bt-mform">${formOpts.map((f) => `<option value="${f.id}">${f.id}. ${esc(f.name)}</option>`).join("")}</select>
          <button id="btn-bt-form" class="btn-sm">🔄 Đổi trận</button>
          <select id="bt-mstrat">${manualStratOpts.map((s) => `<option value="${s.id}">${s.id}. ${esc(s.name)}</option>`).join("")}</select>
          <button id="btn-bt-strat" class="btn-sm">✨ Mưu kế</button>
          <button id="btn-bt-defend" class="btn-warning btn-sm">🛡️ Phòng ngự toàn quân</button>
          <button id="btn-clr-bt" class="btn-sm" style="margin-left:auto;">🗑️ Xóa</button>
        </div>
        <div id="log-battle" class="log-box">${esc((snap.logs.battle || []).join("\n"))}</div>
      </div>`;

    const syncCb = () => scheduleProfileSave({
      combat: {
        auto_counter_formation: $("cb-counter").checked,
        formation_window_seconds: $("cb-win").value,
        action_combo_idx: Number($("cb-act").value),
        stratagem_combo_idx: Number($("cb-strat").value),
        skip_confused_enemy: $("cb-skip").checked,
        leave_boss_last: $("cb-boss").checked,
        auto_cleanse_confusion: $("cb-cleanse").checked,
        emergency_retreat_threshold: $("cb-retreat").value,
      },
    });
    ["cb-counter", "cb-win", "cb-act", "cb-strat", "cb-skip", "cb-boss", "cb-cleanse", "cb-retreat"].forEach((id) => ($(id).onchange = syncCb));
    $("bt-id").onchange = () => { state.battleIdInput = $("bt-id").value; };
    $("btn-bt-load").onclick = () => api(`/api/accounts/${encodeURIComponent(state.currentKey)}/battle/load`, {
      method: "POST", body: { battle_id: Number($("bt-id").value || 0) },
    }).catch((e) => showToast("Lỗi", e.message, "error"));
    $("btn-bt-toggle").onclick = async () => {
      const running = !!state.snapshot?.aux?.battle_running;
      await saveProfileImmediate(state.snapshot.profile);
      await api(`/api/accounts/${encodeURIComponent(state.currentKey)}/battle/${running ? "stop" : "start"}`, {
        method: "POST", body: { battle_id: Number($("bt-id").value || 0) },
      });
    };
    $("btn-bt-form").onclick = () => api(`/api/accounts/${encodeURIComponent(state.currentKey)}/battle/formation`, {
      method: "POST", body: { battle_id: Number($("bt-id").value || 0), position: Number($("bt-pos").value), formation_id: Number($("bt-mform").value) },
    });
    $("btn-bt-strat").onclick = () => api(`/api/accounts/${encodeURIComponent(state.currentKey)}/battle/stratagem`, {
      method: "POST", body: { battle_id: Number($("bt-id").value || 0), position: Number($("bt-pos").value), stratagem_id: Number($("bt-mstrat").value) },
    });
    $("btn-bt-defend").onclick = () => api(`/api/accounts/${encodeURIComponent(state.currentKey)}/battle/defend-all`, {
      method: "POST", body: { battle_id: Number($("bt-id").value || 0) },
    });
    $("btn-clr-bt").onclick = () => api(`/api/accounts/${encodeURIComponent(state.currentKey)}/logs/clear`, { method: "POST", body: { channel: "battle" } });
  }

  // TAB 7: NIÊN THÚ
  function renderNienThuTab(root) {
    const snap = state.snapshot;
    const nt = snap.profile.nien_thu;
    const bases = snap.roster.bases || [];
    const cid = nt.city_id || bases[0]?.id || 0;
    const gens = (snap.roster.generals || []).filter((g) => g.city_id === cid && g.role === "vo");

    root.innerHTML = `
      <div class="card">
        <div class="form-row">
          <label>Thành/Trại <select id="nt-city">${bases.map((b) => `<option value="${b.id}" ${b.id === cid ? "selected" : ""}>${esc(b.display_name)}</option>`).join("")}</select></label>
          <label>Bộ <input id="nt-inf" type="number" value="${esc(nt.target_infantry)}" style="width:68px;"/></label>
          <label>Kỵ <input id="nt-cav" type="number" value="${esc(nt.target_cavalry)}" style="width:68px;"/></label>
          <label>Cung <input id="nt-arc" type="number" value="${esc(nt.target_archers)}" style="width:68px;"/></label>
          <button id="btn-tgl-nt" class="btn-success btn-sm">▶️ Bắt đầu Niên Thú</button>
        </div>
        <div class="form-row">
          <label><input id="nt-rec" type="checkbox" ${nt.auto_recruit ? "checked" : ""}/> Tự chiêu mộ & biên chế</label>
          <label><input id="nt-mor" type="checkbox" ${nt.auto_morale ? "checked" : ""}/> Tự nâng sĩ khí ≥</label>
          <input id="nt-minm" type="number" value="${esc(nt.min_morale)}" style="width:55px;"/>
          <label><input id="nt-march" type="checkbox" ${nt.speed_up_march ? "checked" : ""}/> Tốc hành quân đi</label>
          <label><input id="nt-ret" type="checkbox" ${nt.speed_up_return ? "checked" : ""}/> Tốc hành quân về</label>
        </div>
        <div class="form-row" style="margin-bottom:0;">
          <label><input id="nt-jade" type="checkbox" ${nt.stop_on_jade ? "checked" : ""}/> Dừng khi có 玉兔呈祥</label>
          <label><input id="nt-chat" type="checkbox" ${nt.use_world_chat ? "checked" : ""}/> Theo dõi kênh Thế Giới</label>
          <label><input id="nt-now" type="checkbox" ${nt.run_immediately ? "checked" : ""}/> Chạy ngay giờ hiện tại</label>
          <span id="nt-ann-lbl" style="color:var(--info);font-size:12px;">Kênh thế giới: Chưa có thông báo</span>
        </div>
      </div>
      <div class="card">
        <div class="card-title">Võ tướng luân phiên đánh Niên Thú</div>
        <div class="table-wrap">${renderGeneralSelectTable(gens, nt.generals, "nt-gen")}</div>
      </div>
      <div class="card">
        <div class="card-title"><span>Nhật ký Niên Thú</span><button id="btn-clr-nt" class="btn-sm">🗑️ Xóa</button></div>
        <div id="log-nienthu" class="log-box">${esc((snap.logs.nienthu || []).join("\n"))}</div>
      </div>`;

    const syncNt = () => scheduleProfileSave({
      nien_thu: {
        city_id: Number($("nt-city").value),
        target_infantry: $("nt-inf").value,
        target_cavalry: $("nt-cav").value,
        target_archers: $("nt-arc").value,
        auto_recruit: $("nt-rec").checked,
        auto_morale: $("nt-mor").checked,
        min_morale: $("nt-minm").value,
        speed_up_march: $("nt-march").checked,
        speed_up_return: $("nt-ret").checked,
        stop_on_jade: $("nt-jade").checked,
        use_world_chat: $("nt-chat").checked,
        run_immediately: $("nt-now").checked,
        generals: [...root.querySelectorAll(".nt-gen-chk:checked")].map((x) => Number(x.dataset.gid)),
      },
    });
    $("nt-city").onchange = () => { syncNt(); renderActiveTab(); };
    ["nt-inf", "nt-cav", "nt-arc", "nt-rec", "nt-mor", "nt-minm", "nt-march", "nt-ret", "nt-jade", "nt-chat", "nt-now"].forEach((id) => ($(id).onchange = syncNt));
    root.querySelectorAll(".nt-gen-chk").forEach((c) => (c.onchange = syncNt));
    $("btn-tgl-nt").onclick = () => toggleTask("nienthu");
    $("btn-clr-nt").onclick = () => api(`/api/accounts/${encodeURIComponent(state.currentKey)}/logs/clear`, { method: "POST", body: { channel: "nienthu" } });
  }

  function renderGeneralSelectTable(gens, selectedIds, clsPrefix) {
    const sel = new Set((selectedIds || []).map(Number));
    return `<table><thead><tr><th>Chọn</th><th>Võ tướng</th><th>Cấp</th><th>Thể lực</th><th>Sĩ khí</th><th>Bộ</th><th>Kỵ</th><th>Cung</th><th>Tổng</th></tr></thead>
      <tbody>${gens.map((g) => `<tr>
        <td><input type="checkbox" class="${clsPrefix}-chk" data-gid="${g.id}" ${sel.has(g.id) ? "checked" : ""}/></td>
        <td>${esc(g.name)}</td><td>${g.level}</td><td>${g.stamina}/${g.stamina_max}</td><td>${g.morale}</td>
        <td>${g.army?.infantry ?? 0}</td><td>${g.army?.cavalry ?? 0}</td><td>${g.army?.archers ?? 0}</td><td>${g.army?.total ?? 0}</td>
      </tr>`).join("")}</tbody></table>`;
  }

  function renderBattleTroopsTable(troops, isEnemy) {
    return `<table><thead><tr><th>Ô</th><th>Tướng</th><th>Quân</th><th>SK</th><th>Trận hình</th><th>Trạng thái</th><th>Mục tiêu</th></tr></thead>
      <tbody>${troops.map((t) => `<tr class="${isEnemy && t.is_boss ? "row-boss" : ""}">
        <td>${t.position}</td><td>${esc(t.general_name)} ${t.is_boss ? "👑" : ""}</td><td>${t.soldiers}/${t.initial_soldiers}</td>
        <td>${t.morale}</td><td>${esc(t.formation_name)}</td><td>${esc(t.status_text)}</td><td>${t.target_id || "Tùy chọn"}</td>
      </tr>`).join("")}</tbody></table>`;
  }

  // ---------------------------------------------------------------------------
  // MODALS (Notifications, Tactician, Equip, Logs Viewer, Admin Password, Coffee)
  // ---------------------------------------------------------------------------
  function openModal(title, bodyHtml, footerHtml = "") {
    $("modal-title").textContent = title;
    $("modal-body").innerHTML = bodyHtml;
    $("modal-footer").innerHTML = footerHtml;
    $("modal-backdrop").classList.remove("hidden");
  }
  function closeModal() { $("modal-backdrop").classList.add("hidden"); }

  function openNotificationModal() {
    const np = state.snapshot.profile.notifications;
    const cb = state.snapshot.profile.combat;
    openModal(
      "🔔 Cài Đặt Thông Báo & Bắt Sống BOSS",
      `<div class="form-row"><label><input id="nf-web" type="checkbox" ${np.web_enabled !== false ? "checked" : ""}/> 🌐 Web Toast & Browser Notification</label></div>
       <div class="form-row"><label><input id="nf-sound" type="checkbox" ${np.sound_enabled ? "checked" : ""}/> 🔊 Âm thanh cảnh báo</label></div>
       <div class="form-row"><label><input id="nf-tele" type="checkbox" ${np.telegram_enabled ? "checked" : ""}/> ✈️ Telegram Bot</label></div>
       <div class="form-row" style="padding-left:20px;">
         <label><input id="nf-cap" type="checkbox" ${np.telegram_alert_captcha !== false ? "checked" : ""}/> Báo Captcha qua Telegram</label>
         <label><input id="nf-disc" type="checkbox" ${np.telegram_alert_disconnect !== false ? "checked" : ""}/> Báo mất kết nối qua Telegram</label>
       </div>
       <div class="field"><label>Telegram Bot Token</label><input id="nf-tok" type="password" value="${esc(np.telegram_bot_token)}"/></div>
       <div class="field"><label>Telegram Chat ID</label><input id="nf-cid" type="text" value="${esc(np.telegram_chat_id)}"/></div>
       <hr style="border-color:var(--border);margin:12px 0;"/>
       <div class="form-row"><label><input id="nf-autocap" type="checkbox" ${cb.auto_capture_boss ? "checked" : ""}/> 👑 Tự động bắt sống BOSS bằng Coin khi sĩ khí &lt; </label><input id="nf-mor" type="number" value="${esc(cb.capture_boss_max_morale)}" style="width:65px;"/></div>`,
      `<button id="btn-nf-test" class="btn-sm">🧪 Thử nghiệm</button>
       <button id="btn-nf-save" class="btn-primary btn-sm">💾 Lưu cấu hình</button>`
    );
    $("btn-nf-save").onclick = async () => {
      await saveProfileImmediate({
        notifications: {
          web_enabled: $("nf-web").checked,
          sound_enabled: $("nf-sound").checked,
          telegram_enabled: $("nf-tele").checked,
          telegram_alert_captcha: $("nf-cap").checked,
          telegram_alert_disconnect: $("nf-disc").checked,
          telegram_bot_token: $("nf-tok").value.trim(),
          telegram_chat_id: $("nf-cid").value.trim(),
        },
        combat: {
          auto_capture_boss: $("nf-autocap").checked,
          capture_boss_max_morale: $("nf-mor").value,
        },
      });
      closeModal();
      showToast("Đã lưu", "Cài đặt thông báo & BOSS đã được cập nhật.");
    };
    $("btn-nf-test").onclick = async () => {
      await $("btn-nf-save").click();
      await api(`/api/accounts/${encodeURIComponent(state.currentKey)}/notifications/test`, { method: "POST" });
    };
  }

  function openTacticianModal() {
    const vos = (state.snapshot.roster.generals || []).filter((g) => g.role === "vo");
    const bases = state.snapshot.roster.bases || [];
    openModal(
      "🧠 Thiết Lập Mưu Sĩ Cho Võ Tướng",
      `<div class="form-row"><label><input id="tac-reassign" type="checkbox"/> Đổi mưu sĩ (tháo Mưu sĩ hiện tại để chia lại)</label></div>
       <div class="table-wrap" style="max-height:280px;">
         <table><thead><tr><th><input id="tac-all" type="checkbox" checked/></th><th>Võ tướng</th><th>Thành</th><th>Cấp</th><th>Mưu sĩ hiện tại</th></tr></thead>
         <tbody>${vos.map((g) => `<tr><td><input type="checkbox" class="tac-chk" data-gid="${g.id}" checked/></td><td>${esc(g.name)}</td><td>${esc(bases.find((b) => b.id === g.city_id)?.name || g.city_id)}</td><td>${g.level}</td><td>${esc(g.tactician_name || "-")}</td></tr>`).join("")}</tbody></table>
       </div>
       <div class="log-box" style="height:120px;margin-top:10px;">${esc((state.snapshot.logs.tactician || []).join("\n"))}</div>`,
      `<button class="btn-success btn-sm tac-run" data-mode="by_level">📈 Theo cấp</button>
       <button class="btn-sm tac-run" data-mode="by_name">🏷️ Theo tên</button>
       <button class="btn-sm tac-run" data-mode="sequential">🔢 Tuần tự</button>
       <button class="btn-warning btn-sm tac-run" data-mode="remove">🔓 Tháo MS</button>
       <button id="btn-tac-stop" class="btn-danger btn-sm">⏹ Dừng</button>`
    );
    $("tac-all").onchange = () => document.querySelectorAll(".tac-chk").forEach((c) => (c.checked = $("tac-all").checked));
    document.querySelectorAll(".tac-run").forEach((b) => (b.onclick = () => {
      const ids = [...document.querySelectorAll(".tac-chk:checked")].map((c) => Number(c.dataset.gid));
      api(`/api/accounts/${encodeURIComponent(state.currentKey)}/tactician/run`, {
        method: "POST", body: { mode: b.dataset.mode, general_ids: ids, reassign: $("tac-reassign").checked },
      }).then(() => showToast("Mưu sĩ", "Đang xử lý trong nền...")).catch((e) => showToast("Lỗi", e.message, "error"));
    }));
    $("btn-tac-stop").onclick = () => api(`/api/accounts/${encodeURIComponent(state.currentKey)}/tactician/stop`, { method: "POST" });
  }

  async function openEquipModal() {
    const gens = state.snapshot.roster.generals || [];
    const bases = state.snapshot.roster.bases || [];
    let inv = null;
    try {
      const res = await api(`/api/accounts/${encodeURIComponent(state.currentKey)}/equip/inventory`);
      inv = res.inventory;
    } catch {}
    openModal(
      "🛡️ Tự Động Trang Bị Quan Văn & Võ Tướng",
      `<div class="form-row">
         <label><input id="eq-reassign" type="checkbox"/> Đổi trang bị (tháo chia lại từ đầu Cao → Thấp)</label>
         <span class="pill">Kho đồ: ${inv?.total_items ?? "?"} món</span>
       </div>
       <div class="table-wrap" style="max-height:280px;">
         <table><thead><tr><th><input id="eq-all" type="checkbox" checked/></th><th>Tướng</th><th>Hệ</th><th>Cấp</th><th>Mũ</th><th>Vũ khí</th><th>Giáp</th><th>Thú cưỡi</th></tr></thead>
         <tbody>${gens.map((g) => {
           const eq = inv?.equipped_by_general?.[String(g.id)] || {};
           return `<tr><td><input type="checkbox" class="eq-chk" data-gid="${g.id}" checked/></td><td>${esc(g.name)}</td><td>${g.role === "van" ? "Văn" : "Võ"}</td><td>${g.level}</td><td>${esc(eq["1"] || "-")}</td><td>${esc(eq["2"] || "-")}</td><td>${esc(eq["3"] || "-")}</td><td>${esc(eq["4"] || "-")}</td></tr>`;
         }).join("")}</tbody></table>
       </div>
       <div class="log-box" style="height:120px;margin-top:10px;">${esc((state.snapshot.logs.equip || []).join("\n"))}</div>`,
      `<button id="btn-eq-assign" class="btn-success btn-sm">🛡️ Tự Động Trang Bị</button>
       <button id="btn-eq-remove" class="btn-warning btn-sm">🔓 Tháo Trang Bị</button>
       <button id="btn-eq-stop" class="btn-danger btn-sm">⏹ Dừng</button>`
    );
    $("eq-all").onchange = () => document.querySelectorAll(".eq-chk").forEach((c) => (c.checked = $("eq-all").checked));
    $("btn-eq-assign").onclick = () => {
      const ids = [...document.querySelectorAll(".eq-chk:checked")].map((c) => Number(c.dataset.gid));
      api(`/api/accounts/${encodeURIComponent(state.currentKey)}/equip/run`, { method: "POST", body: { mode: "assign", general_ids: ids, reassign: $("eq-reassign").checked } })
        .then(() => showToast("Trang bị", "Đang xử lý trong nền...")).catch((e) => showToast("Lỗi", e.message, "error"));
    };
    $("btn-eq-remove").onclick = () => {
      const ids = [...document.querySelectorAll(".eq-chk:checked")].map((c) => Number(c.dataset.gid));
      api(`/api/accounts/${encodeURIComponent(state.currentKey)}/equip/run`, { method: "POST", body: { mode: "unequip", general_ids: ids, reassign: false } })
        .then(() => showToast("Trang bị", "Đang tháo trang bị...")).catch((e) => showToast("Lỗi", e.message, "error"));
    };
    $("btn-eq-stop").onclick = () => api(`/api/accounts/${encodeURIComponent(state.currentKey)}/equip/stop`, { method: "POST" });
  }

  async function openSysLogsModal() {
    const res = await api("/api/logs/files");
    const files = res.files || [];
    openModal(
      "📄 Nhật Ký Hệ Thống (Ubuntu Server Logs)",
      `<div class="form-row">
         <select id="syslog-sel" style="flex:1;">${files.map((f) => `<option value="${esc(f.name)}">${esc(f.name)} (${Math.round(f.size / 1024)} KB)</option>`).join("")}</select>
         <button id="btn-syslog-load" class="btn-sm">🔄 Đọc 500 dòng cuối</button>
         <a id="btn-syslog-dl" class="btn btn-sm" href="#" target="_blank">⬇️ Tải về</a>
       </div>
       <div id="syslog-content" class="log-box" style="height:360px;">${files.length ? "Chọn tệp và bấm Đọc..." : "Chưa có tệp nhật ký nào."}</div>`,
      `<button class="btn-sm" onclick="document.getElementById('modal-backdrop').classList.add('hidden')">Đóng</button>`
    );
    const loadFile = async () => {
      const name = $("syslog-sel")?.value;
      if (!name) return;
      $("btn-syslog-dl").href = `/api/logs/files/${encodeURIComponent(name)}?download=true`;
      const resp = await fetch(`/api/logs/files/${encodeURIComponent(name)}?lines=500`, { credentials: "same-origin" });
      $("syslog-content").textContent = await resp.text();
    };
    if ($("btn-syslog-load")) $("btn-syslog-load").onclick = loadFile;
    if (files.length) loadFile();
  }

  function openAdminPasswordModal() {
    openModal(
      "🔐 Đổi Mật Khẩu Phiên Quản Trị Web",
      `<div class="field"><label>Tên đăng nhập</label><input id="adm-new-user" type="text" value="${esc(state.auth.username)}"/></div>
       <div class="field"><label>Mật khẩu hiện tại</label><input id="adm-cur-pwd" type="password"/></div>
       <div class="field"><label>Mật khẩu mới (≥ 6 ký tự)</label><input id="adm-new-pwd" type="password"/></div>`,
      `<button id="btn-adm-save" class="btn-primary btn-sm">💾 Cập nhật</button>`
    );
    $("btn-adm-save").onclick = async () => {
      try {
        await api("/api/auth/password", {
          method: "POST",
          body: { current_password: $("adm-cur-pwd").value, new_password: $("adm-new-pwd").value, new_username: $("adm-new-user").value },
        });
        closeModal();
        showToast("Thành công", "Đã cập nhật thông tin Phiên Quản Trị Web.");
      } catch (e) { showToast("Lỗi", e.message, "error"); }
    };
  }

  function openAutoStartModal() {
    const acc = getCurrentAccountMeta();
    const cfg = acc?.config || {};
    const hasVault = !!acc?.has_vault_password;
    openModal(
      `🚀 Cấu Hình Tự Động Khởi Chạy (${esc(state.currentKey)})`,
      `<div class="form-row">
         <label><input id="as-save-vault" type="checkbox" ${hasVault ? "checked" : ""}/> 🔐 Lưu mật khẩu mã hóa vào Két (bắt buộc để tự đăng nhập lại khi server khởi động)</label>
       </div>
       <div class="form-row">
         <label><input id="as-auto-resume" type="checkbox" ${cfg.auto_resume !== false ? "checked" : ""}/> 🔄 Tự động chạy lại các tác vụ đang chạy trước khi tắt/restart</label>
       </div>
       <div class="field" style="margin-top:8px;">
         <label>📌 Các tác vụ luôn tự động khởi chạy khi server khởi động & đăng nhập lại:</label>
         <div id="modal-autostart-tasks" class="autostart-grid"></div>
       </div>
       <div style="font-size:12px;color:var(--muted);margin-top:6px;">
         Lưu ý: Các tác vụ được tích chọn sẽ tự động chạy ngay sau khi server khởi động lại (kể cả trước đó đã tắt tay).
       </div>`,
      `<button class="btn-sm" onclick="document.getElementById('modal-backdrop').classList.add('hidden')">Hủy</button>
       <button id="btn-as-save" class="btn-primary btn-sm">💾 Lưu cấu hình</button>`
    );
    renderAutoStartCheckboxes("modal-autostart-tasks", cfg.auto_start_tasks || [], "modal-as-chk");
    $("btn-as-save").onclick = async () => {
      try {
        const tasks = [...document.querySelectorAll(".modal-as-chk:checked")].map((c) => c.value);
        const res = await api(`/api/accounts/${encodeURIComponent(state.currentKey)}/autostart`, {
          method: "PUT",
          body: {
            auto_resume: $("as-auto-resume").checked,
            auto_start_tasks: tasks,
            save_to_vault: $("as-save-vault").checked,
          },
        });
        applyUpdatedAccountMeta(res.account);
        closeModal();
        showToast("Đã lưu", "Cấu hình lưu mật khẩu & tự động khởi chạy đã được cập nhật.");
      } catch (e) { showToast("Lỗi", e.message, "error"); }
    };
  }

  function openCoffeeModal() {
    openModal(
      "☕ Buy Me A Coffee — Ủng Hộ Tác Giả",
      `<div style="text-align:center;">
         <p style="color:var(--muted);">Cảm ơn bạn đã tin tưởng và đồng hành cùng Auto Linh Vương!</p>
         <img src="/assets/qrcode.png" alt="QR" style="max-width:280px;border-radius:10px;border:1px solid var(--border);"/>
       </div>`,
      `<button class="btn-sm" onclick="document.getElementById('modal-backdrop').classList.add('hidden')">Đóng</button>`
    );
  }

  // ---------------------------------------------------------------------------
  // STATIC EVENT BINDINGS
  // ---------------------------------------------------------------------------
  function bindStaticEvents() {
    $("admin-login-form").onsubmit = async (e) => {
      e.preventDefault();
      $("admin-login-error").textContent = "";
      try {
        await api("/api/auth/login", { method: "POST", body: { username: $("admin-user").value, password: $("admin-pass").value } });
        state.auth.authenticated = true;
        renderAuthGate();
        await bootstrapWorkspace();
      } catch (err) { $("admin-login-error").textContent = err.message; }
    };
    $("btn-admin-logout").onclick = async () => {
      await api("/api/auth/logout", { method: "POST" });
      state.auth.authenticated = false;
      renderAuthGate();
    };
    $("btn-mobile-menu").onclick = () => $("sidebar").classList.toggle("open");
    $("btn-add-account").onclick = () => { $("sidebar").classList.remove("open"); showAddAccountForm(); };
    $("btn-start-all").onclick = () => api("/api/workspace/start-all", { method: "POST" }).then((r) => showToast("Chạy tất cả", `Đã khởi động ${r.started_accounts} tài khoản.`));
    $("btn-stop-all").onclick = () => api("/api/workspace/stop-all", { method: "POST" }).then((r) => showToast("Dừng tất cả", `Đã dừng ${r.stopped_accounts} tài khoản.`));
    $("btn-open-syslogs").onclick = openSysLogsModal;
    $("btn-admin-settings").onclick = openAdminPasswordModal;
    $("btn-coffee").onclick = openCoffeeModal;
    $("modal-close").onclick = closeModal;

    $("btn-sound-toggle").onclick = () => {
      state.soundEnabled = !state.soundEnabled;
      $("btn-sound-toggle").textContent = state.soundEnabled ? "🔊 Âm thanh: Bật" : "🔇 Âm thanh: Tắt";
      if ("Notification" in window && Notification.permission === "default") Notification.requestPermission();
    };
    $("btn-reload-roster").onclick = () => api(`/api/accounts/${encodeURIComponent(state.currentKey)}/roster/reload`, { method: "POST" }).catch((e) => showToast("Lỗi", e.message, "error"));
    $("btn-rotate-proxy").onclick = () => api(`/api/accounts/${encodeURIComponent(state.currentKey)}/proxy/rotate`, { method: "POST" }).catch((e) => showToast("Lỗi", e.message, "error"));
    $("btn-notify-settings").onclick = openNotificationModal;
    $("btn-account-logout").onclick = () => api(`/api/accounts/${encodeURIComponent(state.currentKey)}/logout`, { method: "POST" });
    $("btn-resume-captcha").onclick = () => api(`/api/accounts/${encodeURIComponent(state.currentKey)}/captcha/resume`, { method: "POST" });

    $("hdr-profile-import").onchange = async (e) => {
      const f = e.target.files?.[0];
      if (!f || !state.currentKey) return;
      try {
        const json = JSON.parse(await f.text());
        await api(`/api/accounts/${encodeURIComponent(state.currentKey)}/profile/import`, { method: "POST", body: json });
        showToast("Đã nạp hồ sơ", f.name);
      } catch (err) { showToast("Lỗi nạp JSON", err.message, "error"); }
      e.target.value = "";
    };
    $("hdr-save-vault").onchange = async () => {
      if (!state.currentKey) return;
      const save = $("hdr-save-vault").checked;
      try {
        const res = await api(`/api/accounts/${encodeURIComponent(state.currentKey)}/vault`, {
          method: "POST",
          body: { save },
        });
        applyUpdatedAccountMeta(res.account);
        showToast("Két Mật Khẩu", save ? "Đã lưu mật khẩu mã hóa vào Két." : "Đã xóa mật khẩu khỏi Két.");
      } catch (err) {
        $("hdr-save-vault").checked = !save;
        showToast("Lỗi Lưu Mật Khẩu", err.message, "error");
      }
    };
    $("hdr-auto-resume").onchange = async () => {
      if (!state.currentKey) return;
      const checked = $("hdr-auto-resume").checked;
      const curTasks = getCurrentAccountMeta()?.config?.auto_start_tasks || [];
      try {
        const res = await api(`/api/accounts/${encodeURIComponent(state.currentKey)}/autostart`, {
          method: "PUT",
          body: { auto_resume: checked, auto_start_tasks: curTasks },
        });
        applyUpdatedAccountMeta(res.account);
        showToast("Tự động khởi chạy", checked ? "Đã bật tự chạy lại tác vụ khi restart." : "Đã tắt tự chạy lại tác vụ khi restart.");
      } catch (err) {
        $("hdr-auto-resume").checked = !checked;
        showToast("Lỗi", err.message, "error");
      }
    };
    $("btn-autostart-cfg").onclick = () => {
      if (state.currentKey) openAutoStartModal();
    };

    $("btn-free-proxy").onclick = () => { $("gl-proxy-url").value = state.meta?.default_free_proxy_url || ""; $("gl-status").textContent = "Đã điền ProxyScrape SOCKS5 Free."; };
    $("btn-test-proxy").onclick = async () => {
      $("gl-status").textContent = "🔄 Đang kiểm tra proxy...";
      try {
        const res = await api("/api/accounts/proxy-test", { method: "POST", body: { proxy_url: $("gl-proxy-url").value } });
        $("gl-status").textContent = res.message;
      } catch (e) { $("gl-status").textContent = `❌ ${e.message}`; }
    };
    $("game-login-form").onsubmit = async (e) => {
      e.preventDefault();
      $("gl-status").textContent = "🔑 Đang kết nối...";
      $("btn-game-login").disabled = true;
      try {
        const autoStartTasks = [...document.querySelectorAll(".gl-as-chk:checked")].map((c) => c.value);
        const res = await api("/api/accounts/login", {
          method: "POST",
          body: {
            server_id: Number($("gl-server").value),
            username: $("gl-user").value.trim(),
            password: $("gl-pass").value,
            proxy_url: $("gl-proxy-url").value.trim(),
            proxy: $("gl-proxy").value.trim(),
            proxy_user: $("gl-proxy-user").value.trim(),
            proxy_pass: $("gl-proxy-pass").value,
            save_to_vault: $("gl-save-vault").checked,
            auto_resume: $("gl-auto-resume").checked,
            auto_start_tasks: autoStartTasks,
            old_key: state.currentKey,
          },
        });
        state.snapshot = res.snapshot;
        state.auxSyncedAt = Date.now();
        state.currentKey = res.snapshot.summary.account_key;
        const accRes = await api("/api/accounts");
        state.accounts = accRes.accounts || [];
        renderSidebar();
        showDashboardView();
      } catch (err) {
        $("gl-status").textContent = `❌ ${err.message}`;
      } finally {
        $("btn-game-login").disabled = false;
      }
    };
    $("btn-save-acc-only").onclick = async () => {
      try {
        const acc = getCurrentAccountMeta();
        const pwd = $("gl-pass").value;
        const saveChk = $("gl-save-vault").checked;
        const saveVault = !saveChk ? false : (pwd || acc?.has_vault_password ? true : null);
        const autoStartTasks = [...document.querySelectorAll(".gl-as-chk:checked")].map((c) => c.value);
        const res = await api("/api/accounts", {
          method: "POST",
          body: {
            server_id: Number($("gl-server").value),
            username: $("gl-user").value.trim(),
            password: pwd,
            proxy_url: $("gl-proxy-url").value.trim(),
            proxy: $("gl-proxy").value.trim(),
            proxy_user: $("gl-proxy-user").value.trim(),
            proxy_pass: $("gl-proxy-pass").value,
            save_to_vault: saveVault,
            auto_resume: $("gl-auto-resume").checked,
            auto_start_tasks: autoStartTasks,
            old_key: state.currentKey,
          },
        });
        state.currentKey = res.account.account_key;
        applyUpdatedAccountMeta(res.account);
        $("gl-status").textContent = "✅ Đã lưu cấu hình tài khoản.";
      } catch (e) { $("gl-status").textContent = `❌ ${e.message}`; }
    };
    $("btn-delete-acc").onclick = async () => {
      if (!state.currentKey || !confirm(`Xóa tài khoản '${state.currentKey}'?`)) return;
      await api(`/api/accounts/${encodeURIComponent(state.currentKey)}`, { method: "DELETE" });
    };

    document.querySelectorAll(".tab-btn").forEach((btn) => {
      btn.onclick = () => {
        state.activeTab = btn.dataset.tab;
        renderActiveTab();
      };
    });
  }

  window.addEventListener("DOMContentLoaded", init);
})();
