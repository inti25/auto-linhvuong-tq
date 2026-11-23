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
    selectedBldGid: null,
    selectedXferIdx: -1,
    expandedBldGroups: new Set(),
    selectedOverviewCityId: null,
    selectedOverviewGenId: null,
    selectedMoraleGens: new Set(),
    moraleInitAccount: null,
    selectedCraftCityId: null,
    selectedBmBaseId: null,
    selectedResTechId: null,
    moraleCityFilter: "all",
    selectedDtCampId: null,
    logiFromId: null,
    logiToId: null,
    logiType: "108",
    cityWeaponsCache: {},
    chestType: null,
    chestCityId: null,
    battleIdInput: "0",
    selectedBattleOurPos: null,
    btManualForm: null,
    btManualStrat: null,
    saveTimer: null,
    pendingProfilePatch: null,
    pendingSelfProfileUpdates: 0,
    pendingSelfProfileExpiresAt: 0,
    auxSyncedAt: 0,
    auxTimer: null,
    enhanceUi: {},
    gdCallerPassByKey: {},
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
    } catch { }
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
      try { new Notification(ev.title || "Linh Vương", { body: ev.body || "" }); } catch { }
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
      try { state.ws.close(); } catch { }
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
      if (state.pendingSelfProfileUpdates > 0 && Date.now() < state.pendingSelfProfileExpiresAt) {
        state.pendingSelfProfileUpdates -= 1;
      } else {
        state.pendingSelfProfileUpdates = 0;
        renderActiveTab();
      }
      if (typeof renderTrainingModalBody === "function" && $("trn-tbody")) renderTrainingModalBody();
    } else if (event === "roster_updated") {
      state.snapshot.roster = payload;
      renderActiveTab();
      if (typeof renderTacticianModalBody === "function" && $("tac-tbody")) renderTacticianModalBody();
      if (typeof renderEquipModalBody === "function" && $("eq-tbody")) renderEquipModalBody();
      if (typeof renderArmamentModalBody === "function" && $("arm-tbody")) renderArmamentModalBody();
      if (typeof renderRenameModalBody === "function" && $("ren-tbody")) renderRenameModalBody();
      if (typeof renderAddPointsModalBody === "function" && $("ap-tbody")) renderAddPointsModalBody();
      if (typeof renderTrainingModalBody === "function" && $("trn-tbody")) renderTrainingModalBody();
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
    const prevScrollTop = list.scrollTop;
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
      el.addEventListener("contextmenu", (e) => {
        e.preventDefault();
        showAccountContextMenu(e.clientX, e.clientY, el.dataset.key);
      });
    });
    list.scrollTop = prevScrollTop;
  }

  function hideAccountContextMenu() {
    const old = document.getElementById("acc-ctx-menu");
    if (old) old.remove();
  }

  function showAccountContextMenu(x, y, key) {
    hideAccountContextMenu();
    const menu = document.createElement("div");
    menu.id = "acc-ctx-menu";
    menu.className = "ctx-menu";
    menu.style.left = `${Math.min(x, window.innerWidth - 190)}px`;
    menu.style.top = `${Math.min(y, window.innerHeight - 90)}px`;
    menu.innerHTML = `<button data-act="logout">🚪 Đăng xuất</button><button data-act="delete" class="danger">🗑️ Xóa tài khoản</button>`;
    document.body.appendChild(menu);
    menu.querySelector('[data-act="logout"]').onclick = async () => {
      hideAccountContextMenu();
      try {
        await api(`/api/accounts/${encodeURIComponent(key)}/logout`, { method: "POST" });
        showToast("Đăng xuất", `Đã đăng xuất ${key}`);
      } catch (err) { showToast("Lỗi", err.message, "error"); }
    };
    menu.querySelector('[data-act="delete"]').onclick = async () => {
      hideAccountContextMenu();
      if (!confirm(`Xóa tài khoản '${key}'?`)) return;
      try {
        await api(`/api/accounts/${encodeURIComponent(key)}`, { method: "DELETE" });
      } catch (err) { showToast("Lỗi", err.message, "error"); }
    };
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
    { id: "resource_monitor", label: "📦 Tài Nguyên" },
    { id: "thaophat", label: "⚔️ Thảo phạt" },
    { id: "binhman", label: "🏕️ Bình man" },
    { id: "goidan", label: "🧛 Gọi man" },
    { id: "nienthu", label: "🧧 Niên thú" },
    { id: "crafting", label: "🛡️ Chế tạo quân giới" },
    { id: "transfer_loop", label: "🚚 Chuyển quân giới lặp" },
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
    $("btn-relogin").classList.add("hidden");

    const cfg = acc?.config || {};
    $("ws-title").textContent = acc ? acc.account_key : "Thêm tài khoản mới";
    $("ws-status-pill").textContent = "⚪ Chưa đăng nhập";
    $("ws-status-pill").className = "pill";
    $("ws-proxy-pill").classList.add("hidden");

    $("gl-server").value = cfg.server || "";
    updateServerHint();
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

  function updateServerHint() {
    const el = $("gl-server-hint");
    if (!el) return;
    const sid = Number($("gl-server").value);
    el.textContent = sid > 0 ? `Cổng game: http://sg${sid}.dipan.com/` : "";
  }

  // Tự tách chuỗi proxy ip:port:user:pass (giống Desktop _on_proxy_change)
  function autoSplitProxyInput() {
    const raw = $("gl-proxy").value.trim();
    if (!raw || raw.includes("://") || raw.includes("@")) return;
    const parts = raw.split(":");
    if (parts.length === 4 && /^\d+$/.test(parts[1])) {
      $("gl-proxy").value = `${parts[0]}:${parts[1]}`;
      $("gl-proxy-user").value = parts[2];
      $("gl-proxy-pass").value = parts[3];
      $("gl-status").textContent = "Đã tự tách host:port / user / pass từ chuỗi proxy.";
    }
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
    $("btn-relogin").classList.remove("hidden");
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
  function mergePatchInto(target, patch) {
    for (const [k, v] of Object.entries(patch || {})) {
      if (target[k] && typeof target[k] === "object" && !Array.isArray(target[k]) && typeof v === "object" && !Array.isArray(v)) {
        target[k] = { ...target[k], ...v };
      } else {
        target[k] = v;
      }
    }
  }

  async function putProfilePatch(patch) {
    state.pendingSelfProfileUpdates += 1;
    state.pendingSelfProfileExpiresAt = Date.now() + 5000;
    try {
      await api(`/api/accounts/${encodeURIComponent(state.currentKey)}/profile`, {
        method: "PUT",
        body: patch,
      });
    } catch (e) {
      state.pendingSelfProfileUpdates = Math.max(0, state.pendingSelfProfileUpdates - 1);
      throw e;
    }
  }

  function scheduleProfileSave(patch) {
    if (!state.currentKey || !state.snapshot) return;
    // Merge optimistically into local snapshot and coalesce pending patches
    mergePatchInto(state.snapshot.profile, patch);
    state.pendingProfilePatch = state.pendingProfilePatch || {};
    mergePatchInto(state.pendingProfilePatch, patch);
    clearTimeout(state.saveTimer);
    state.saveTimer = setTimeout(async () => {
      const toSend = state.pendingProfilePatch;
      state.pendingProfilePatch = null;
      if (!toSend || !state.currentKey) return;
      try {
        await putProfilePatch(toSend);
      } catch (e) {
        showToast("Lỗi lưu cấu hình", e.message, "error");
      }
    }, 300);
  }

  async function saveProfileImmediate(patch) {
    clearTimeout(state.saveTimer);
    const queued = state.pendingProfilePatch || {};
    state.pendingProfilePatch = null;
    mergePatchInto(queued, patch);
    mergePatchInto(state.snapshot.profile, patch);
    await putProfilePatch(queued);
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

  function isNearBottom(el, threshold = 24) {
    return (el.scrollHeight - el.scrollTop - el.clientHeight) <= threshold;
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
      tactician: "log-tactician",
      equip: "log-equip",
      armament: "log-armament",
      rename: "log-rename",
      add_points: "log-add-points",
      enhance: "log-enhance",
      training: "log-training",
    };
    if (channel === "building" || channel === "logistics") {
      const mb = $("log-modal-box");
      if (mb) {
        mb.textContent += (mb.textContent ? "\n" : "") + line;
        mb.scrollTop = mb.scrollHeight;
      }
    }
    const box = $(map[channel]);
    if (box) {
      const stickBottom = isNearBottom(box);
      box.textContent += (box.textContent ? "\n" : "") + line;
      if (stickBottom) box.scrollTop = box.scrollHeight;
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

  function getLiveTrainHallSummary(hallKey) {
    const hall = state.snapshot?.aux?.training?.[hallKey];
    if (!hall) return null;
    const elapsed = state.auxSyncedAt ? Math.max(0, Math.floor((Date.now() - state.auxSyncedAt) / 1000)) : 0;
    const unlockedSlots = Number(hall.unlocked_slots || 0);
    if (unlockedSlots <= 0) return { text: "Chưa mở", ready: false };
    const slots = (hall.slots || []).filter((s) => s.unlocked);
    const rems = slots.map((s) => Math.max(0, Number(s.remaining_seconds || 0) - elapsed));
    const freeCount = rems.filter((r) => r <= 0).length;
    if (freeCount > 0) return { text: "Sẵn sàng", ready: true };
    const activeRems = rems.filter((r) => r > 0);
    if (activeRems.length > 0) return { text: fmtSec(Math.min(...activeRems)), ready: false };
    return { text: "--", ready: false };
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
    const trnEl = $("aux-training-lbl");
    if (trnEl) {
      const voSum = getLiveTrainHallSummary("vo");
      const vanSum = getLiveTrainHallSummary("van");
      if (voSum || vanSum) {
        trnEl.textContent = `(Võ: ${voSum ? voSum.text : "--"} | Văn: ${vanSum ? vanSum.text : "--"})`;
        trnEl.style.color = (voSum?.ready || vanSum?.ready) ? "#fbbf24" : "#4ade80";
      } else {
        trnEl.textContent = state.snapshot?.profile?.training?.enabled ? "(Chờ kiểm tra)" : "";
        trnEl.style.color = "#8a90b0";
      }
    }
    const elapsed = state.auxSyncedAt ? Math.max(0, Math.floor((Date.now() - state.auxSyncedAt) / 1000)) : 0;
    document.querySelectorAll(".train-slot-cd[data-slot-rem]").forEach((el) => {
      const rem = Math.max(0, Number(el.dataset.slotRem || 0) - elapsed);
      el.textContent = rem > 0 ? `Còn ${fmtSec(rem)}` : "✅ Sẵn sàng";
    });
  }

  function formatGeneralVisitText(aux, enabled) {
    if (enabled === false) return "Đang tắt";
    const visits = Array.isArray(aux?.general_visits) ? aux.general_visits : [];
    if (!visits.length) return "Không có khách viếng thăm";
    return visits
      .map((v) => `${v.building_name || (Number(v.gid) === 8 ? "Tửu Quán" : "Quán Trọ")}: ${v.general_name}`)
      .join(" | ");
  }

  function renderAuxDomOnly() {
    const aux = state.snapshot?.aux;
    if (!aux) return;
    renderAuxCountdownsOnly();
    const visitLbl = $("aux-visit-lbl");
    if (visitLbl) {
      const enabled = state.snapshot?.profile?.logistics?.notify_general_visit !== false;
      const visits = Array.isArray(aux.general_visits) ? aux.general_visits : [];
      visitLbl.textContent = formatGeneralVisitText(aux, enabled);
      visitLbl.style.color = enabled && visits.length ? "var(--warn)" : "var(--muted)";
    }
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
    const tacLbl = $("tac-status-lbl");
    if (tacLbl) tacLbl.textContent = aux.tactician_status || "Sẵn sàng";
    const xferLbl = $("xfer-status-lbl");
    if (xferLbl) xferLbl.textContent = aux.transfer_status || "Sẵn sàng";
    const armyXferLbl = $("army-xfer-status-lbl");
    if (armyXferLbl) armyXferLbl.textContent = aux.army_transfer_status || "Sẵn sàng";
    const armLbl = $("arm-status-lbl");
    if (armLbl) armLbl.textContent = aux.armament_status || "Sẵn sàng";
    const renLbl = $("ren-status-lbl");
    if (renLbl) renLbl.textContent = `${aux.rename_status || "Sẵn sàng"}${aux.rename_progress?.total ? ` (${aux.rename_progress.done}/${aux.rename_progress.total})` : ""}`;
    const apLbl = $("ap-status-lbl");
    if (apLbl) apLbl.textContent = `${aux.add_points_status || "Sẵn sàng"}${aux.add_points_progress?.total ? ` (${aux.add_points_progress.done}/${aux.add_points_progress.total})` : ""}`;
    const eqLbl = $("eq-status-lbl");
    if (eqLbl) eqLbl.textContent = aux.equip_status || "Sẵn sàng";
    const trnLbl = $("train-status-lbl");
    if (trnLbl) trnLbl.textContent = aux.training_status || "Sẵn sàng";
    if (typeof renderTrainingModalSlots === "function" && $("trn-slots-grid")) renderTrainingModalSlots();
    const ntSt = $("nt-status-lbl");
    if (ntSt) ntSt.textContent = ntStatusText();
    const gdCallerSt = $("gd-caller-status");
    if (gdCallerSt) {
      const callerAux = aux.goidan_caller || {};
      const callerUsr = $("gd-caller-user")?.value ?? state.snapshot?.profile?.goi_dan?.caller_username ?? "";
      gdCallerSt.textContent = formatGdCallerStatusText(callerAux, callerUsr);
      gdCallerSt.style.color = callerAux.ready ? "#4ade80" : "var(--muted)";
    }
    if (typeof updateEnhanceAuxDom === "function") updateEnhanceAuxDom(aux);
  }

  function formatGdCallerStatusText(callerAux, username) {
    const usr = String(callerAux?.username || username || "").trim();
    if (!usr) return "Chưa nhập tài khoản";
    if (callerAux?.reused_session) return "🔗 Đang dùng phiên sẵn có";
    if (callerAux?.has_vault_password && callerAux?.has_ram_password) return "🔐 Đã lưu RAM & Két";
    if (callerAux?.has_vault_password) return "🔐 Đã lưu trong Két";
    if (callerAux?.has_ram_password) return "✅ Đã nhập trong phiên";
    return "Chưa có mật khẩu";
  }

  function ntStatusText() {
    const t = state.snapshot?.summary?.tasks?.nienthu;
    if (!t) return "Chưa chạy";
    if (t.running) return "Đang chạy";
    const st = String(t.status || "");
    if (st.includes("Captcha")) return "Tạm dừng (Captcha)";
    if (st.includes("玉兔") || st.toLowerCase().includes("hoàn")) return "Đã hoàn tất (玉兔呈祥)";
    return st && st !== "idle" ? st : "Đã dừng";
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
    bindBtn("btn-tgl-resmon", t.resource_monitor?.running, "⏹️ Dừng Tài Nguyên", "▶️ Tài Nguyên");
    bindBtn("btn-tgl-tp", t.thaophat?.running, "⏹️ Dừng Thảo Phạt", "▶️ Bắt đầu Thảo Phạt");
    bindBtn("btn-tgl-bm", t.binhman?.running, "⏹️ Dừng Bình Man", "▶️ Bắt đầu Bình Man");
    bindBtn("btn-tgl-gd", t.goidan?.running, "⏹️ Dừng Gọi Man", "▶️ Bắt đầu Gọi Man");
    bindBtn("btn-tgl-nt", t.nienthu?.running, "⏹️ Dừng Niên Thú", "▶️ Bắt đầu Niên Thú");
    bindBtn("btn-tgl-craft", t.crafting?.running, "⏹️ Dừng Chế Tạo", "▶️ Chạy Chế Tạo");
    bindBtn("btn-tgl-xfer", t.transfer_loop?.running, "⏹️ Dừng lặp", "▶️ Chạy lặp");
    bindBtn("btn-tgl-army-xfer", t.army_transfer?.running, "⏹️ Dừng chuyển", "▶️ Chạy lặp");
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
  function captureTabUiState(root) {
    const curKey = state.currentKey || "";
    if (root.dataset.renderedKey !== curKey || root.dataset.renderedTab !== state.activeTab) {
      return null;
    }
    const tableScrolls = [...root.querySelectorAll(".table-wrap")].map((el) => ({
      top: el.scrollTop,
      left: el.scrollLeft,
    }));
    const logScrolls = {};
    root.querySelectorAll(".log-box").forEach((el) => {
      if (!el.id) return;
      logScrolls[el.id] = { top: el.scrollTop, atBottom: isNearBottom(el) };
    });
    let focus = null;
    const active = document.activeElement;
    if (active && root.contains(active)) {
      focus = {
        id: active.id || "",
        tag: active.tagName,
        cls: active.className || "",
        pid: active.dataset?.pid,
        gid: active.dataset?.gid,
        idx: active.dataset?.idx,
        bid: active.dataset?.bid,
        selStart: typeof active.selectionStart === "number" ? active.selectionStart : null,
        selEnd: typeof active.selectionEnd === "number" ? active.selectionEnd : null,
      };
    }
    return {
      rootTop: root.scrollTop,
      rootLeft: root.scrollLeft,
      tableScrolls,
      logScrolls,
      focus,
    };
  }

  function restoreTabUiState(root, saved) {
    root.querySelectorAll(".log-box").forEach((el) => {
      const prev = saved && el.id ? saved.logScrolls[el.id] : null;
      if (prev) {
        el.scrollTop = prev.atBottom ? el.scrollHeight : prev.top;
      } else {
        el.scrollTop = el.scrollHeight;
      }
    });
    if (!saved) return;
    root.querySelectorAll(".table-wrap").forEach((el, idx) => {
      const s = saved.tableScrolls[idx];
      if (s) {
        el.scrollTop = s.top;
        el.scrollLeft = s.left;
      }
    });
    root.scrollTop = saved.rootTop;
    root.scrollLeft = saved.rootLeft;

    if (saved.focus) {
      const f = saved.focus;
      let target = f.id ? $(f.id) : null;
      if (target && !root.contains(target)) target = null;
      if (!target) {
        target = [...root.querySelectorAll("input, select, textarea, button")].find(
          (el) =>
            el.tagName === f.tag &&
            (el.className || "") === f.cls &&
            el.dataset?.pid === f.pid &&
            el.dataset?.gid === f.gid &&
            el.dataset?.idx === f.idx &&
            el.dataset?.bid === f.bid
        ) || null;
      }
      if (target && typeof target.focus === "function") {
        try { target.focus({ preventScroll: true }); } catch { }
        if (f.selStart !== null && typeof target.setSelectionRange === "function") {
          try { target.setSelectionRange(f.selStart, f.selEnd); } catch { }
        }
      }
    }
  }

  function renderActiveTab() {
    if (!state.snapshot) return;
    document.querySelectorAll(".tab-btn").forEach((b) => b.classList.toggle("active", b.dataset.tab === state.activeTab));
    const root = $("tab-content");
    const savedUi = captureTabUiState(root);
    const renderers = {
      internal: renderInternalTab,
      thaophat: renderThaoPhatTab,
      binhman: renderBinhManTab,
      goidan: renderGoiDanTab,
      overview: renderOverviewTab,
      battle: renderBattleTab,
      nienthu: renderNienThuTab,
      enhance: renderEnhanceTab,
    };
    renderers[state.activeTab](root);
    root.dataset.renderedKey = state.currentKey || "";
    root.dataset.renderedTab = state.activeTab;
    updateRunningButtonsOnly();
    renderAuxDomOnly();
    restoreTabUiState(root, savedUi);
  }

  // TAB 1: NỘI CHÍNH & NGHIÊN CỨU
  function renderInternalTab(root) {
    const snap = state.snapshot;
    const prof = snap.profile;
    const bld = prof.building;
    const res = prof.research;
    const rsrc = prof.resource;
    const logi = prof.logistics;
    const trn = prof.training || { enabled: false, vo_general_ids: [], van_general_ids: [] };
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
    const mkOpts = (list, selId, lbl = "display_name") => list.map((x) => `<option value="${x.id}" ${String(x.id) === String(selId) ? "selected" : ""}>${esc(x[lbl])}</option>`).join("");
    const chestSel = state.chestType || state.meta?.chests?.[0]?.name || "";
    const chestOpts = (state.meta?.chests || []).map((c) => `<option value="${esc(c.name)}" ${c.name === chestSel ? "selected" : ""}>${esc(c.name)}</option>`).join("");
    const cityListOnly = cities.length ? cities : bases.filter((b) => Number(b.id) > 0);
    const baseOptsFrom = mkOpts(cityListOnly, state.logiFromId ?? cityListOnly[0]?.id);
    const baseOptsTo = mkOpts(cityListOnly, state.logiToId ?? cityListOnly[1]?.id ?? cityListOnly[0]?.id);
    const armyFromCid = Number(logi.army_transfer_from_city_id || cityListOnly[0]?.id || 0);
    const armyToCid = Number(logi.army_transfer_to_city_id || cityListOnly[1]?.id || cityListOnly[0]?.id || 0);
    const armyOptsFrom = mkOpts(cityListOnly, armyFromCid);
    const armyOptsTo = mkOpts(cityListOnly, armyToCid);
    const cityOpts = mkOpts(cities, state.chestCityId ?? cities[0]?.id);
    const campOpts = mkOpts(camps, state.selectedDtCampId ?? camps[0]?.id);

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
        bldRowsHtml += `<tr class="row-clickable" style="background:${state.selectedBldGid === gid ? "rgba(108,123,255,.28)" : "#1c2136"};" data-group="${gid}">
          <td><input type="checkbox" class="bld-grp-chk" data-gid="${gid}" ${allEn ? "checked" : ""}/></td>
          <td><button class="btn-sm bld-grp-exp" data-gid="${gid}">${isOpen ? "▾" : "▸"}</button> <strong>${esc(plots[0].name)} (${plots.length} ô)</strong></td>
          <td>Nhóm</td>
          <td>${Math.min(...lvls)}-${Math.max(...lvls)}</td>
          <td><input type="number" class="bld-grp-tgt" data-gid="${gid}" value="${maxTgt}" min="0" max="35" style="width:58px;"/></td>
        </tr>`;
        if (isOpen) {
          for (const p of plots) {
            const done = Number(p.cur_lvl || 0) >= Number(p.target_level || 20);
            bldRowsHtml += `<tr class="${done ? "row-done" : ""} ${state.selectedBldPid === p.pid ? "selected" : ""}" data-pid="${p.pid}">
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
    const transferWeapons = state.meta?.transfer_weapons || state.meta?.weapons || [];
    const weaponNameMap = Object.fromEntries(transferWeapons.map((w) => [Number(w.id), w.name]));
    const buildWeaponOpts = (cid, selectedId, { excludeSiege = false } = {}) => {
      const stocks = state.cityWeaponsCache[String(cid)] || [];
      const stockMap = Object.fromEntries(stocks.map((s) => [Number(s.id), s]));
      const seen = new Set();
      const opts = [];
      for (const s of stocks) {
        const wid = Number(s.id);
        if (excludeSiege && wid >= 500) continue;
        seen.add(wid);
        const label = `${wid}. ${s.name} [Kho: ${Number(s.count || 0).toLocaleString()}]`;
        opts.push(`<option value="${wid}" ${wid === Number(selectedId) ? "selected" : ""}>${esc(label)}</option>`);
      }
      for (const w of transferWeapons) {
        const wid = Number(w.id);
        if (seen.has(wid)) continue;
        if (excludeSiege && wid >= 500) continue;
        const label = `${wid}. ${w.name} (${w.category})`;
        opts.push(`<option value="${wid}" ${wid === Number(selectedId) ? "selected" : ""}>${esc(label)}</option>`);
      }
      if (selectedId && !seen.has(Number(selectedId)) && !transferWeapons.some((w) => Number(w.id) === Number(selectedId))) {
        opts.unshift(`<option value="${selectedId}" selected>${selectedId}. Quân giới #${selectedId}</option>`);
      }
      return opts.join("");
    };
    const curMarketFromCid = Number(state.logiFromId ?? cityListOnly[0]?.id ?? 0);
    const marketWeaponOpts = buildWeaponOpts(curMarketFromCid, state.logiType);
    const armyWeaponId = Number(logi.army_transfer_weapon_id || 406);
    const armyWeaponOpts = buildWeaponOpts(armyFromCid, armyWeaponId, { excludeSiege: true });
    const xferMode = logi.transfer_mode === "army" ? "army" : "market";
    const baseNameOf = (id) => bases.find((b) => b.id === Number(id))?.name || id;
    const xferOrders = logi.transfer_orders || [];
    const xferRows = xferOrders.length
      ? xferOrders.map((o, i) => `<tr class="xfer-row row-clickable ${i === state.selectedXferIdx ? "selected" : ""}" data-idx="${i}"><td>${esc(baseNameOf(o.from_city_id))} ➔ ${esc(baseNameOf(o.to_city_id))}</td><td>${Number(o.amount).toLocaleString()}</td><td>${esc(weaponNameMap[Number(o.army_id)] ? `${o.army_id}. ${weaponNameMap[Number(o.army_id)]}` : `QG #${o.army_id}`)}</td></tr>`).join("")
      : '<tr><td colspan="3" style="color:var(--muted);">Chưa có lệnh. Chọn Từ ➔ Đến, quân giới, SL rồi bấm Add.</td></tr>';
    const voGenerals = (snap.roster.generals || []).filter((g) => g.role === "vo");
    const selectedArmyGids = new Set((logi.army_transfer_general_ids || []).map((x) => Number(x)));
    const armyGenRows = voGenerals.length
      ? voGenerals.map((g) => {
          const checked = selectedArmyGids.has(Number(g.id)) ? "checked" : "";
          const troops = Number(g.infantry || 0) + Number(g.cavalry || 0) + Number(g.bowman || 0);
          return `<tr>
            <td><input type="checkbox" class="army-xfer-gen-chk" value="${g.id}" ${checked}/></td>
            <td>${esc(g.name)}</td>
            <td>${esc(baseNameOf(g.city_id))}</td>
            <td>${troops.toLocaleString()}</td>
            <td>${esc(g.status_text || (g.status === 0 ? "Rảnh" : "Bận"))}</td>
          </tr>`;
        }).join("")
      : '<tr><td colspan="5" style="color:var(--muted);">Chưa có Võ tướng.</td></tr>';
    const tc = snap.tech_current;
    const techCurHtml = tc ? ` <small style="color:var(--info);font-weight:400;">• Đang NC: ${esc(tc.name)} (${esc(tc.cur)} ➔ ${esc(tc.next)}, còn ${esc(tc.left)})</small>` : "";

    root.innerHTML = `
      <div class="grid-internal">
        <!-- CỘT 1 -->
        <div>
          <div class="card">
            <div class="card-title">⚙️ Điều khiển Nội Chính</div>
            <div class="form-row">
              <button id="btn-tgl-bld" class="btn-success btn-sm">▶️ Xây</button>
              <button id="btn-tgl-res" class="btn-success btn-sm">▶️ Nghiên Cứu</button>
              <button id="btn-tgl-resmon" class="btn-success btn-sm">▶️ Tài Nguyên</button>
            </div>
            <div class="form-row" style="margin-bottom:0;">
              <button id="btn-bld-all-on" class="btn-sm">☑ Chọn hết thành</button>
              <button id="btn-bld-all-off" class="btn-sm">☐ Bỏ hết</button>
            </div>
            <div class="form-row" style="margin:8px 0 0;">
              <button id="btn-nc-clear" class="btn-sm">✖ Bỏ NC</button>
              <button class="btn-sm btn-view-log">🔍 Xem Log</button>
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
            <div id="dt-origin-lbl" style="font-size:12px;font-weight:700;color:var(--accent);margin-bottom:6px;">Vị trí: (---, ---)</div>
            <div class="form-row">
              <label>Đích X <input id="dt-x" type="number" value="${esc(dt.dest_x)}" style="width:70px;"/></label>
              <label>Y <input id="dt-y" type="number" value="${esc(dt.dest_y)}" style="width:70px;"/></label>
            </div>
            <div class="form-row">
              <button id="btn-dt-start" class="btn-success btn-sm">▶ Di Trại</button>
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
              <label>Cấp mục tiêu <input id="bld-tgt-lvl" type="number" value="20" min="0" max="40" style="width:58px;"/></label>
              <button id="btn-bld-up-lvl" class="btn-success btn-sm">Nâng</button>
              <button id="btn-bld-down-lvl" class="btn-danger btn-sm">Hạ</button>
              <button id="btn-bld-mv-up" class="btn-sm" title="Đưa lên ưu tiên cao hơn">↑</button>
              <button id="btn-bld-mv-down" class="btn-sm" title="Đưa xuống ưu tiên thấp hơn">↓</button>
              <span style="color:var(--muted);font-size:11px;">(bấm chọn dòng hoặc nhóm; 0 = dỡ bỏ)</span>
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
              <span>🔬 Kỹ Thuật Đại Học (29 Kỹ Thuật)${techCurHtml}</span>
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
              <label>Ưu tiên Chợ</label><label style="margin:0;"><input id="rsrc-prefer-market" type="checkbox" ${rsrc.prefer_market_buy ? "checked" : ""}/> Ưu tiên mua ở chợ (Thành có Chợ)</label>
              <label>Bán dư tài nguyên</label><div class="form-row" style="margin:0;"><label style="margin:0;"><input id="rsrc-auto-sell" type="checkbox" ${rsrc.auto_sell_resource ? "checked" : ""}/> Bán tài nguyên nếu quá</label><input id="rsrc-sell-pct" type="number" min="1" max="100" value="${esc(rsrc.sell_threshold_pct ?? "90")}" style="width:54px;"/><span>%</span></div>
            </div>
            <div class="form-row">
              <label><input id="aux-daily" type="checkbox" ${logi.auto_daily_reward ? "checked" : ""}/> Thưởng ngày</label>
              <label><input id="aux-comfort" type="checkbox" ${bld.auto_comfort ? "checked" : ""}/> Tự An Dân</label>
              <label><input id="aux-boost" type="checkbox" ${bld.auto_boost ? "checked" : ""}/> DS kiến trúc <span id="aux-boost-lbl" style="color:#4ade80;"></span></label>
            </div>
            <div class="form-row">
              <label><input id="aux-explore" type="checkbox" ${logi.auto_explore ? "checked" : ""}/> Thám bảo <span id="aux-explore-lbl" style="color:#4ade80;"></span></label>
              <label><input id="aux-whip" type="checkbox" ${logi.explore_use_whip ? "checked" : ""}/> Roi</label>
              <label><input id="aux-coin" type="checkbox" ${logi.explore_use_coin ? "checked" : ""}/> Coin</label>
              <input id="aux-turns" type="number" value="${esc(logi.explore_turns)}" style="width:52px;" title="Số lượt"/>
              <button id="btn-run-explore" class="btn-sm">🧭 Thám bảo</button>
            </div>
            <div class="form-row">
              <label><input id="aux-tribute" type="checkbox" ${logi.tribute_enabled ? "checked" : ""}/> Cống quận</label>
              <select id="aux-tribute-gid">
                <option value="1" ${Number(logi.tribute_building_gid) === 1 ? "selected" : ""}>官府 (Quan Phủ)</option>
                <option value="2" ${Number(logi.tribute_building_gid) === 2 ? "selected" : ""}>城墙 (Tường Thành)</option>
              </select>
              <button id="btn-tribute-now" class="btn-sm">🏛️ Cống quận ngay</button>
            </div>
            <div class="form-row">
              <label><input id="aux-general-visit" type="checkbox" ${logi.notify_general_visit !== false ? "checked" : ""}/> Báo danh tướng viếng thăm</label>
              <span id="aux-visit-lbl" style="font-size:12px;color:${logi.notify_general_visit !== false && (snap.aux?.general_visits || []).length ? "var(--warn)" : "var(--muted)"};">${esc(formatGeneralVisitText(snap.aux, logi.notify_general_visit !== false))}</span>
            </div>
            <div class="form-row">
              <label><input id="aux-training" type="checkbox" ${trn.enabled ? "checked" : ""}/> 🎓 Đào tạo tướng <span id="aux-training-lbl" style="color:#4ade80;"></span></label>
              <button id="btn-open-training-aux" class="btn-sm">⚙️ Chọn tướng</button>
            </div>
            <div class="form-row" style="margin-bottom:0;">
              <button id="btn-apply-rsrc" class="btn-primary btn-sm">✅ Áp Dụng Thiết Lập</button>
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

            <div class="card-title" style="margin-top:6px;">
              <span>🚚 Chuyển Quân Giới</span>
              <span style="font-size:12px;font-weight:400;display:inline-flex;gap:10px;">
                <label style="cursor:pointer;"><input type="radio" class="xfer-mode-rad" name="xfer-mode" value="market" ${xferMode === "market" ? "checked" : ""}/> 🏪 Bằng Chợ</label>
                <label style="cursor:pointer;"><input type="radio" class="xfer-mode-rad" name="xfer-mode" value="army" ${xferMode === "army" ? "checked" : ""}/> 🐎 Bằng Quân đội</label>
              </span>
            </div>

            <div id="xfer-panel-market" style="${xferMode === "market" ? "" : "display:none;"}">
              <div class="form-row">
                <select id="logi-from">${baseOptsFrom}</select> ➔ <select id="logi-to">${baseOptsTo}</select>
                <button id="btn-logi-load-stock" class="btn-sm" title="Tải kho Quân giới thực tế của Thành gửi">🔄 Tải kho</button>
              </div>
              <div class="form-row">
                <select id="logi-type" style="flex:1;min-width:140px;">${marketWeaponOpts}</select>
                <input id="logi-amt" type="number" min="1" value="${esc(logi.amount)}" style="width:75px;" title="SL"/>
                <button id="btn-xfer-add" class="btn-sm">➕ Add</button>
                <button id="btn-xfer-del" class="btn-sm">🗑️ Xóa</button>
              </div>
              <div class="table-wrap" style="max-height:120px;">
                <table><thead><tr><th>Từ – Đến</th><th>SL</th><th>Quân giới</th></tr></thead><tbody>${xferRows}</tbody></table>
              </div>
              <div class="form-row" style="margin-top:6px;">
                <label>Lặp lại (giây) <input id="xfer-int" type="number" min="3" value="${esc(logi.transfer_interval)}" style="width:62px;"/></label>
                <button id="btn-tgl-xfer" class="btn-success btn-sm">▶️ Chạy lặp</button>
                <button id="btn-logi-xfer" class="btn-sm" title="Chuyển ngay một lần theo lựa chọn đang nhập">🚚 Chuyển ngay</button>
              </div>
              <div id="xfer-status-lbl" style="font-size:12px;color:var(--info);margin-bottom:6px;">Sẵn sàng</div>
            </div>

            <div id="xfer-panel-army" style="${xferMode === "army" ? "" : "display:none;"}">
              <div class="form-row">
                <label>Thành chứa QG <select id="army-xfer-from">${armyOptsFrom}</select></label> ➔
                <label>Thành nhận <select id="army-xfer-to">${armyOptsTo}</select></label>
                <button id="btn-army-xfer-load-stock" class="btn-sm" title="Tải kho Quân giới thực tế của Thành chứa QG">🔄 Tải kho</button>
              </div>
              <div class="form-row">
                <select id="army-xfer-weapon" style="flex:1;min-width:160px;">${armyWeaponOpts}</select>
                <label><input id="army-xfer-loop" type="checkbox" ${logi.army_transfer_loop !== false ? "checked" : ""}/> Lặp vô tận</label>
              </div>
              <div class="table-wrap" style="max-height:130px;">
                <table>
                  <thead><tr><th></th><th>Võ tướng</th><th>Căn cứ</th><th>Quân số</th><th>Trạng thái</th></tr></thead>
                  <tbody>${armyGenRows}</tbody>
                </table>
              </div>
              <div class="form-row" style="margin-top:6px;">
                <button id="btn-tgl-army-xfer" class="btn-success btn-sm">▶️ Chạy lặp</button>
                <button id="btn-army-xfer-once" class="btn-sm" title="Chuyển 1 chuyến bằng các Võ tướng đã chọn">🐎 Chuyển 1 chuyến</button>
              </div>
              <div id="army-xfer-status-lbl" style="font-size:12px;color:var(--info);margin-bottom:6px;">Sẵn sàng</div>
            </div>

            <div class="form-row" style="margin-bottom:0;">
              <button id="btn-logi-comfort" class="btn-sm">🕊️ An Dân</button>
              <button id="btn-logi-daily" class="btn-sm">🎁 Điểm danh</button>
            </div>
          </div>

          <div class="card">
            <div class="card-title">
              <span>📜 Nhật ký Nội Chính & Hậu Cần</span>
              <span><button class="btn-sm btn-view-log">🔍 Xem Log</button> <button id="btn-clr-int-log" class="btn-sm">🗑️ Xóa</button></span>
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
        state.selectedBldGid = null;
        renderActiveTab();
      };
    });
    root.querySelectorAll("tr[data-group]").forEach((tr) => {
      tr.onclick = (e) => {
        if (e.target.tagName === "INPUT" || e.target.tagName === "BUTTON") return;
        state.selectedBldGid = Number(tr.dataset.group);
        state.selectedBldPid = null;
        renderActiveTab();
      };
    });

    // Thanh Cấp mục tiêu: Nâng / Hạ / ↑ / ↓ (chuẩn Desktop)
    const selectedBldPlans = () => {
      if (state.selectedBldGid != null) return plans.filter((p) => Number(p.gid) === state.selectedBldGid);
      if (state.selectedBldPid != null) return plans.filter((p) => Number(p.pid) === state.selectedBldPid);
      return [];
    };
    const applyBldTarget = (rawLvl) => {
      const lvl = Number(rawLvl);
      if (!Number.isInteger(lvl) || lvl < 0 || lvl > 45) return showToast("Lỗi", "Cấp mục tiêu phải là số nguyên từ 0 đến 45 (0: dỡ bỏ)!", "error");
      const sel = selectedBldPlans();
      if (!sel.length) return showToast("Cảnh báo", "Vui lòng chọn 1 công trình hoặc nhóm trong bảng!", "warn");
      sel.forEach((p) => { p.target_level = lvl; p.enabled = true; });
      scheduleProfileSave({ building: { cities: bld.cities } });
      renderActiveTab();
    };
    $("btn-bld-up-lvl").onclick = () => applyBldTarget($("bld-tgt-lvl").value);
    $("btn-bld-down-lvl").onclick = () => applyBldTarget($("bld-tgt-lvl").value);
    const moveBld = (dir) => {
      let gid = state.selectedBldGid;
      if (gid == null && state.selectedBldPid != null) gid = Number(plans.find((p) => Number(p.pid) === state.selectedBldPid)?.gid);
      if (gid == null || Number.isNaN(gid)) return;
      const order = [];
      const map = {};
      for (const p of plans) {
        const g = Number(p.gid || 1);
        if (!map[g]) { map[g] = []; order.push(g); }
        map[g].push(p);
      }
      const i = order.indexOf(gid);
      const j = i + dir;
      if (i < 0 || j < 0 || j >= order.length) return;
      [order[i], order[j]] = [order[j], order[i]];
      const flat = order.flatMap((g) => map[g]);
      plans.splice(0, plans.length, ...flat);
      scheduleProfileSave({ building: { cities: bld.cities } });
      renderActiveTab();
    };
    $("btn-bld-mv-up").onclick = () => moveBld(-1);
    $("btn-bld-mv-down").onclick = () => moveBld(1);
    $("btn-bld-all-chk").onclick = () => { plans.forEach((p) => (p.enabled = true)); scheduleProfileSave({ building: { cities: bld.cities } }); renderActiveTab(); };
    $("btn-bld-none-chk").onclick = () => { plans.forEach((p) => (p.enabled = false)); scheduleProfileSave({ building: { cities: bld.cities } }); renderActiveTab(); };
    $("btn-bld-set-all").onclick = () => {
      const v = Number($("bld-batch-lvl").value || 20);
      plans.forEach((p) => { p.target_level = v; p.enabled = true; });
      scheduleProfileSave({ building: { cities: bld.cities } });
      renderActiveTab();
    };
    $("btn-bld-demolish").onclick = () => {
      if (state.selectedBldPid == null && state.selectedBldGid == null) return showToast("Chọn công trình", "Nhấp vào 1 ô hoặc nhóm công trình trước khi đặt cấp 0.", "warn");
      const sel = state.selectedBldGid != null
        ? plans.filter((x) => Number(x.gid) === state.selectedBldGid)
        : plans.filter((x) => Number(x.pid) === state.selectedBldPid);
      sel.forEach((p) => { p.target_level = 0; p.enabled = true; });
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
        prefer_market_buy: Boolean($("rsrc-prefer-market")?.checked),
        auto_sell_resource: Boolean($("rsrc-auto-sell")?.checked),
        sell_threshold_pct: $("rsrc-sell-pct")?.value ?? "90",
      },
      logistics: {
        auto_daily_reward: $("aux-daily").checked,
        auto_explore: $("aux-explore").checked,
        explore_use_whip: $("aux-whip").checked,
        explore_use_coin: $("aux-coin").checked,
        explore_turns: $("aux-turns").value,
        amount: $("logi-amt").value,
        transfer_interval: $("xfer-int").value,
        tribute_enabled: $("aux-tribute").checked,
        tribute_building_gid: Number($("aux-tribute-gid").value),
        notify_general_visit: $("aux-general-visit").checked,
      },
      training: {
        enabled: $("aux-training").checked,
      },
      ditrai: { dest_x: $("dt-x").value, dest_y: $("dt-y").value },
    });
    ["rsrc-gold", "rsrc-wood", "rsrc-iron", "rsrc-stone", "rsrc-food", "rsrc-gbox", "rsrc-tnbox", "rsrc-prefer-market", "rsrc-auto-sell", "rsrc-sell-pct",
      "aux-daily", "aux-explore", "aux-whip", "aux-coin", "aux-turns", "logi-amt", "dt-x", "dt-y", "xfer-int", "aux-tribute", "aux-tribute-gid", "aux-general-visit", "aux-training"].forEach((id) => {
        const el = $(id);
        if (!el) return;
        el.onchange = () => {
          if (id === "aux-whip" && $("aux-whip").checked) $("aux-coin").checked = false;
          if (id === "aux-coin" && $("aux-coin").checked) $("aux-whip").checked = false;
          saveResCfg();
        };
      });
    $("btn-open-training-aux").onclick = openTrainingModal;

    $("btn-run-explore").onclick = () => api(`/api/accounts/${encodeURIComponent(state.currentKey)}/aux/explore`, {
      method: "POST",
      body: { use_whip: $("aux-whip").checked, use_coin: $("aux-coin").checked, turns: Number($("aux-turns").value || 1) },
    });
    $("btn-chest-start").onclick = async () => {
      try {
        await api(`/api/accounts/${encodeURIComponent(state.currentKey)}/chests/start`, {
          method: "POST",
          body: { chest_name: $("chest-type").value, times: Number($("chest-times").value || 1), city_id: $("chest-city").disabled ? 0 : Number($("chest-city").value || 0) },
        });
      } catch (e) { showToast("Lỗi mở rương", e.message, "error"); }
    };
    $("btn-chest-stop").onclick = () => api(`/api/accounts/${encodeURIComponent(state.currentKey)}/chests/stop`, { method: "POST" });
    $("btn-logi-xfer").onclick = async () => {
      const from = Number($("logi-from").value);
      const to = Number($("logi-to").value);
      const wid = Number($("logi-type").value);
      const amt = Number($("logi-amt").value || 0);
      if (!from || !to || from === to) return showToast("Cảnh báo", "Vui lòng chọn 2 Thành khác nhau!", "warn");
      if (wid <= 0 || amt <= 0) return showToast("Cảnh báo", "Vui lòng chọn Quân giới và số lượng > 0!", "warn");
      try {
        await api(`/api/accounts/${encodeURIComponent(state.currentKey)}/aux/transfer`, {
          method: "POST",
          body: { from_city_id: from, to_city_id: to, army_id: wid, amount: amt },
        });
        showToast("Chuyển quân giới", "Đã gửi lệnh chuyển qua Chợ.");
      } catch (e) { showToast("Lỗi Chuyển quân giới", e.message, "error"); }
    };
    $("btn-logi-comfort").onclick = () => {
      const mode = root.querySelector(".xfer-mode-rad:checked")?.value || (logi.transfer_mode === "army" ? "army" : "market");
      const cid = mode === "army" ? Number($("army-xfer-to").value) : Number($("logi-from").value);
      api(`/api/accounts/${encodeURIComponent(state.currentKey)}/aux/comfort`, {
        method: "POST", body: { city_id: cid },
      });
    };
    $("btn-logi-daily").onclick = () => api(`/api/accounts/${encodeURIComponent(state.currentKey)}/aux/daily-reward`, { method: "POST" });
    $("btn-dt-start").onclick = async () => {
      try {
        await api(`/api/accounts/${encodeURIComponent(state.currentKey)}/ditrai/start`, {
          method: "POST", body: { camp_id: Number($("dt-camp").value), dest_x: Number($("dt-x").value), dest_y: Number($("dt-y").value) },
        });
      } catch (e) { showToast("Lỗi Di Trại", e.message, "error"); }
    };
    $("btn-dt-stop").onclick = () => api(`/api/accounts/${encodeURIComponent(state.currentKey)}/ditrai/stop`, { method: "POST" });
    // Bỏ NC / Xem Log
    $("btn-nc-clear").onclick = () => {
      res.city_id = null;
      scheduleProfileSave({ research: { city_id: null } });
      renderActiveTab();
    };
    root.querySelectorAll(".btn-view-log").forEach((b) => (b.onclick = openInternalLogModal));

    // Di Trại: hiển thị vị trí hiện tại của Doanh trại
    const updateDtOrigin = () => {
      state.selectedDtCampId = $("dt-camp").value;
      const camp = camps.find((c) => String(c.id) === state.selectedDtCampId);
      $("dt-origin-lbl").textContent = camp ? `Vị trí: (${camp.pos_x}, ${camp.pos_y})` : "Vị trí: (---, ---)";
    };
    $("dt-camp").onchange = updateDtOrigin;
    updateDtOrigin();

    const loadCityWeaponStock = async (cid, selectId, excludeSiege = false) => {
      if (!cid || Number(cid) <= 0) return showToast("Cảnh báo", "Vui lòng chọn Thành hợp lệ!", "warn");
      try {
        const resStock = await api(`/api/accounts/${encodeURIComponent(state.currentKey)}/aux/city-weapons?city_id=${cid}`);
        state.cityWeaponsCache[String(cid)] = resStock.items || [];
        if (selectId === "logi-type" && resStock.items?.length) {
          if (!resStock.items.some((x) => Number(x.id) === Number(state.logiType))) {
            state.logiType = String(resStock.items[0].id);
          }
        }
        if (selectId === "army-xfer-weapon" && resStock.items?.length) {
          const firstNonSiege = resStock.items.find((x) => !excludeSiege || Number(x.id) < 500);
          if (firstNonSiege && !resStock.items.some((x) => Number(x.id) === Number(logi.army_transfer_weapon_id))) {
            logi.army_transfer_weapon_id = Number(firstNonSiege.id);
            scheduleProfileSave({ logistics: { army_transfer_weapon_id: logi.army_transfer_weapon_id } });
          }
        }
        renderActiveTab();
        showToast("Đã tải kho", `Tìm thấy ${(resStock.items || []).length} loại Quân giới tại Thành ${baseNameOf(cid)}.`);
      } catch (e) { showToast("Lỗi tải kho", e.message, "error"); }
    };

    root.querySelectorAll(".xfer-mode-rad").forEach((r) => {
      r.onchange = () => {
        if (!r.checked) return;
        logi.transfer_mode = r.value;
        scheduleProfileSave({ logistics: { transfer_mode: r.value } });
        $("xfer-panel-market").style.display = r.value === "market" ? "" : "none";
        $("xfer-panel-army").style.display = r.value === "army" ? "" : "none";
      };
    });

    $("logi-from").onchange = () => { state.logiFromId = $("logi-from").value; renderActiveTab(); };
    $("logi-to").onchange = () => { state.logiToId = $("logi-to").value; };
    $("logi-type").onchange = () => { state.logiType = $("logi-type").value; };
    $("btn-logi-load-stock").onclick = () => loadCityWeaponStock(Number($("logi-from").value), "logi-type", false);

    const saveArmyXferCfg = () => {
      const gids = [...root.querySelectorAll(".army-xfer-gen-chk:checked")].map((c) => Number(c.value)).filter((n) => n > 0);
      logi.army_transfer_from_city_id = Number($("army-xfer-from").value || 0);
      logi.army_transfer_to_city_id = Number($("army-xfer-to").value || 0);
      logi.army_transfer_weapon_id = Number($("army-xfer-weapon").value || 406);
      logi.army_transfer_general_ids = gids;
      logi.army_transfer_loop = $("army-xfer-loop").checked;
      scheduleProfileSave({
        logistics: {
          army_transfer_from_city_id: logi.army_transfer_from_city_id,
          army_transfer_to_city_id: logi.army_transfer_to_city_id,
          army_transfer_weapon_id: logi.army_transfer_weapon_id,
          army_transfer_general_ids: gids,
          army_transfer_loop: logi.army_transfer_loop,
        },
      });
    };
    $("army-xfer-from").onchange = () => { saveArmyXferCfg(); renderActiveTab(); };
    $("army-xfer-to").onchange = saveArmyXferCfg;
    $("army-xfer-weapon").onchange = saveArmyXferCfg;
    $("army-xfer-loop").onchange = saveArmyXferCfg;
    root.querySelectorAll(".army-xfer-gen-chk").forEach((chk) => (chk.onchange = saveArmyXferCfg));
    $("btn-army-xfer-load-stock").onclick = () => loadCityWeaponStock(Number($("army-xfer-from").value), "army-xfer-weapon", true);

    const startArmyXfer = async (loopMode) => {
      saveArmyXferCfg();
      const from = Number($("army-xfer-from").value);
      const to = Number($("army-xfer-to").value);
      const wid = Number($("army-xfer-weapon").value);
      const gids = [...root.querySelectorAll(".army-xfer-gen-chk:checked")].map((c) => Number(c.value)).filter((n) => n > 0);
      if (!from || !to || from === to) return showToast("Cảnh báo", "Vui lòng chọn 2 Thành khác nhau!", "warn");
      if (!gids.length) return showToast("Cảnh báo", "Vui lòng chọn ít nhất 1 Võ tướng!", "warn");
      try {
        await api(`/api/accounts/${encodeURIComponent(state.currentKey)}/aux/army-transfer/start`, {
          method: "POST",
          body: { from_city_id: from, to_city_id: to, weapon_id: wid, general_ids: gids, loop: loopMode },
        });
        await refreshSnapshot();
      } catch (e) { showToast("Lỗi Chuyển bằng Quân đội", e.message, "error"); }
    };
    $("btn-tgl-army-xfer").onclick = async () => {
      const running = state.snapshot?.summary?.tasks?.army_transfer?.running;
      if (running) {
        await api(`/api/accounts/${encodeURIComponent(state.currentKey)}/aux/army-transfer/stop`, { method: "POST" });
        await refreshSnapshot();
      } else {
        await startArmyXfer($("army-xfer-loop").checked);
      }
    };
    $("btn-army-xfer-once").onclick = () => startArmyXfer(false);
    $("chest-city").onchange = () => { state.chestCityId = $("chest-city").value; };

    // Rương cấp tài khoản không cần chọn Thành
    const syncChestCity = () => {
      state.chestType = $("chest-type").value;
      const meta = (state.meta?.chests || []).find((c) => c.name === state.chestType);
      $("chest-city").disabled = meta ? !meta.needs_city : false;
    };
    $("chest-type").onchange = syncChestCity;
    syncChestCity();

    // Áp Dụng Thiết Lập (lưu ngay ngưỡng tài nguyên & phụ trợ)
    $("btn-apply-rsrc").onclick = async () => {
      try {
        saveResCfg();
        saveBldMeta();
        await saveProfileImmediate({});
        showToast("Đã áp dụng", "Thiết lập ngưỡng tài nguyên & phụ trợ đã được lưu.");
      } catch (e) { showToast("Lỗi", e.message, "error"); }
    };

    // Cống quận ngay (chỉ Thành, bỏ qua Doanh trại)
    $("btn-tribute-now").onclick = async () => {
      const cid = Number(curBldCid);
      if (!cid || cid < 0) return showToast("Cống quận", "Vui lòng chọn một Thành (không phải Doanh trại) trong danh sách bên trái.", "warn");
      try {
        await api(`/api/accounts/${encodeURIComponent(state.currentKey)}/aux/tribute`, {
          method: "POST", body: { city_id: cid, building_gid: Number($("aux-tribute-gid").value) },
        });
        showToast("Cống quận", "Đã gửi lệnh Cống quận.");
      } catch (e) { showToast("Lỗi", e.message, "error"); }
    };

    // Bảng Chuyển quân giới (hàng đợi lặp)
    root.querySelectorAll(".xfer-row").forEach((tr) => (tr.onclick = () => { state.selectedXferIdx = Number(tr.dataset.idx); renderActiveTab(); }));
    $("btn-xfer-add").onclick = () => {
      const from = Number($("logi-from").value);
      const to = Number($("logi-to").value);
      if (!from || !to || from === to) return showToast("Cảnh báo", "Vui lòng chọn 2 Thành khác nhau!", "warn");
      const amt = Math.max(1, Number($("logi-amt").value || 1));
      logi.transfer_orders = [...(logi.transfer_orders || []), { from_city_id: from, to_city_id: to, army_id: Number($("logi-type").value), amount: amt }];
      scheduleProfileSave({ logistics: { transfer_orders: logi.transfer_orders } });
      renderActiveTab();
    };
    $("btn-xfer-del").onclick = () => {
      const i = state.selectedXferIdx;
      if (i < 0 || i >= (logi.transfer_orders || []).length) return showToast("Cảnh báo", "Vui lòng chọn 1 lệnh chuyển quân giới trong bảng để xóa!", "warn");
      logi.transfer_orders = logi.transfer_orders.filter((_, k) => k !== i);
      state.selectedXferIdx = -1;
      scheduleProfileSave({ logistics: { transfer_orders: logi.transfer_orders } });
      renderActiveTab();
    };
    $("btn-tgl-xfer").onclick = () => toggleTask("transfer_loop");
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
          <span style="color:var(--muted);font-style:italic;font-size:12px;">(Tự động tính toán thời gian hành quân để xuất quân tối ưu)</span>
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
    const curBase = bases.find((b) => b.id === bid) || null;
    const bcfg = bm.bases[String(bid)] || {
      name: curBase?.name || "",
      enabled: false, mode: curBase?.is_camp === false ? 2 : 1, radius: "5", threshold: "30",
      camp_id: String(bid || ""), parent_city_id: String(cities[0]?.id || ""),
      target_types: [7, 8, 9, 10], generals: [], target_infantry: "0", target_cavalry: "0", target_archers: "0",
      auto_recruit: true, auto_morale: true, min_morale: "95",
      auto_swap_tactician: false, min_tactician_stamina: "30", action_combo_idx: 0,
    };
    bm.bases[String(bid)] = bcfg;
    const allGens = snap.roster.generals || [];
    const gens = allGens.filter((g) => g.city_id === bid && g.role === "vo");
    const manOpts = state.meta?.man_targets || [];
    const actOpts = state.meta?.attack_action_options || [];
    const isMode2 = Number(bcfg.mode) === 2;
    const selGenIds = new Set((bcfg.generals || []).map(Number));
    const selCount = gens.filter((g) => selGenIds.has(g.id)).length;
    const waveCount = selCount > 0 ? Math.ceil(selCount / 3) : 0;

    root.innerHTML = `
      <div class="grid-2" style="grid-template-columns: 340px 1fr;">
        <div>
          <div class="card">
            <div class="card-title">🏰 Danh Sách Căn Cứ Bình Man</div>
            <div class="form-row">
              <button id="btn-bm-all" class="btn-sm">✅ Chọn tất cả</button>
              <button id="btn-bm-none" class="btn-sm">❌ Bỏ tất cả</button>
              <button id="btn-bm-prov-all" class="btn-sm">⚔️ Biên chế tất cả</button>
            </div>
            <div class="table-wrap" style="max-height:280px;">
              <table>
                <thead><tr><th>Chạy</th><th>Căn cứ</th><th>Loại</th><th>Tọa độ</th><th>Tướng</th></tr></thead>
                <tbody>
                  ${bases.map((b) => {
      const c = bm.bases[String(b.id)] || {};
      const totVo = allGens.filter((g) => g.city_id === b.id && g.role === "vo").length;
      const chosenVo = (c.generals || []).length;
      return `<tr class="bm-base-row row-clickable ${b.id === bid ? "selected" : ""}" data-bid="${b.id}">
                      <td><input type="checkbox" class="bm-base-chk" data-bid="${b.id}" ${c.enabled ? "checked" : ""}/></td>
                      <td>${esc(b.name)}</td>
                      <td>${esc(b.type || (b.is_camp ? "Doanh trại" : "Thành"))}</td>
                      <td>${b.pos_x},${b.pos_y}</td>
                      <td>${chosenVo}/${totVo}</td>
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
              <span>⚙️ Cấu hình: ${esc(curBase?.name || bid)}</span>
              <button id="btn-bm-prov-one" class="btn-sm">⚔️ Biên chế căn cứ này</button>
            </div>
            <div class="form-row">
              <label><input type="radio" name="bm-mode" value="1" ${!isMode2 ? "checked" : ""}/> 1: Di Doanh trại đến cạnh Man</label>
              <label><input type="radio" name="bm-mode" value="2" ${isMode2 ? "checked" : ""}/> 2: Xuất quân thẳng từ Thành</label>
            </div>
            <div class="form-row">
              <label>${isMode2 ? "Thành xuất phát" : "Doanh trại xuất phát"} <select id="bm-base-sel">${bases.map((b) => `<option value="${b.id}" ${b.id === bid ? "selected" : ""}>${esc(b.display_name)}</option>`).join("")}</select></label>
              <label>Thành mẹ (Hồi quân) <select id="bm-parent" ${isMode2 ? "disabled" : ""}>${cities.map((c) => `<option value="${c.id}" ${String(bcfg.parent_city_id) === String(c.id) ? "selected" : ""}>${esc(c.display_name)}</option>`).join("")}</select></label>
              <label>Doanh trại ID <input id="bm-camp-id" type="text" value="${esc(bcfg.camp_id || bid || "")}" style="width:90px;" ${isMode2 ? "disabled" : ""}/></label>
            </div>
            <div class="form-row">
              <label>Ngưỡng An Toàn (%) <input id="bm-thresh" type="number" value="${esc(bcfg.threshold)}" style="width:58px;"/></label>
              <label>Bán kính <input id="bm-rad" type="number" value="${esc(bcfg.radius)}" style="width:55px;"/></label>
              <label>Chiêu tấn công <select id="bm-act">${actOpts.map((o, i) => `<option value="${i}" ${Number(bcfg.action_combo_idx) === i ? "selected" : ""}>${esc(o)}</option>`).join("")}</select></label>
            </div>
            <div class="form-row">
              <label>Bộ <input id="bm-inf" type="number" value="${esc(bcfg.target_infantry)}" style="width:65px;"/></label>
              <label>Kỵ <input id="bm-cav" type="number" value="${esc(bcfg.target_cavalry)}" style="width:65px;"/></label>
              <label>Cung <input id="bm-arc" type="number" value="${esc(bcfg.target_archers)}" style="width:65px;"/></label>
              <label><input id="bm-rec" type="checkbox" ${bcfg.auto_recruit ? "checked" : ""}/> Tự động bổ sung lính</label>
              <label><input id="bm-mor" type="checkbox" ${bcfg.auto_morale ? "checked" : ""}/> Tự động nâng sĩ khí ≥</label>
              <input id="bm-minm" type="number" value="${esc(bcfg.min_morale)}" style="width:55px;"/>
            </div>
            <div class="form-row">
              <label><input id="bm-swap-tac" type="checkbox" ${bcfg.auto_swap_tactician ? "checked" : ""}/> Tự động đổi mưu sĩ (thể lực ≥</label>
              <input id="bm-min-tac-stam" type="number" min="0" max="100" value="${esc(bcfg.min_tactician_stamina ?? "30")}" style="width:55px;"/>%)
            </div>
            <div class="form-row" style="margin-bottom:0;">
              <span style="color:var(--muted);">Loại Man mục tiêu:</span>
              ${manOpts.map((m) => `<label style="font-size:12px;"><input type="checkbox" class="bm-mtype" value="${m.id}" ${(bcfg.target_types || []).includes(m.id) ? "checked" : ""}/> ${esc(m.label)}</label>`).join("")}
            </div>
          </div>
          <div class="card">
            <div class="card-title">
              <span>Võ tướng căn cứ này</span>
              <span style="display:flex;align-items:center;gap:6px;flex-wrap:wrap;">
                <button id="btn-bm-gen-all" class="btn-sm">✅ Chọn tất cả</button>
                <button id="btn-bm-gen-none" class="btn-sm">❌ Bỏ chọn tất cả</button>
                <span id="bm-gen-count-lbl" style="font-size:12px;color:var(--accent);">Đã chọn: ${selCount} tướng (${waveCount} đợt xuất kích)</span>
              </span>
            </div>
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
      bcfg.camp_id = $("bm-camp-id").value.trim();
      bcfg.radius = $("bm-rad").value;
      bcfg.threshold = $("bm-thresh").value;
      bcfg.action_combo_idx = Number($("bm-act").value);
      bcfg.target_infantry = $("bm-inf").value;
      bcfg.target_cavalry = $("bm-cav").value;
      bcfg.target_archers = $("bm-arc").value;
      bcfg.auto_recruit = $("bm-rec").checked;
      bcfg.auto_morale = $("bm-mor").checked;
      bcfg.min_morale = $("bm-minm").value;
      bcfg.auto_swap_tactician = $("bm-swap-tac").checked;
      bcfg.min_tactician_stamina = $("bm-min-tac-stam").value;
      bcfg.target_types = [...root.querySelectorAll(".bm-mtype:checked")].map((x) => Number(x.value));
      bcfg.mantypes = bcfg.target_types.join(",");
      bcfg.generals = [...root.querySelectorAll(".bm-gen-chk:checked")].map((x) => Number(x.dataset.gid));
      bm.current_base_id = bid;
      bm.interval = $("bm-int").value;
      const cnt = bcfg.generals.length;
      const lbl = $("bm-gen-count-lbl");
      if (lbl) lbl.textContent = `Đã chọn: ${cnt} tướng (${cnt > 0 ? Math.ceil(cnt / 3) : 0} đợt xuất kích)`;
      scheduleProfileSave({ binh_man: { interval: bm.interval, current_base_id: bid, bases: bm.bases } });
    };

    $("bm-base-sel").onchange = () => { state.selectedBmBaseId = Number($("bm-base-sel").value); renderActiveTab(); };
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
    $("btn-bm-gen-all").onclick = () => { root.querySelectorAll(".bm-gen-chk").forEach((c) => (c.checked = true)); syncBm(); renderActiveTab(); };
    $("btn-bm-gen-none").onclick = () => { root.querySelectorAll(".bm-gen-chk").forEach((c) => (c.checked = false)); syncBm(); renderActiveTab(); };
    root.querySelectorAll('input[name="bm-mode"]').forEach((el) => (el.onchange = () => { syncBm(); renderActiveTab(); }));
    root.querySelectorAll(".bm-mtype, .bm-gen-chk").forEach((el) => (el.onchange = syncBm));
    ["bm-int", "bm-parent", "bm-camp-id", "bm-rad", "bm-thresh", "bm-act", "bm-inf", "bm-cav", "bm-arc", "bm-rec", "bm-mor", "bm-minm", "bm-swap-tac", "bm-min-tac-stam"].forEach((id) => ($(id).onchange = syncBm));
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
    const callerAux = snap.aux?.goidan_caller || {};
    const draftPass = state.gdCallerPassByKey[state.currentKey] || "";
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
        <div class="form-row">
          <label><input id="gd-swap-tac" type="checkbox" ${gd.auto_swap_tactician ? "checked" : ""}/> Tự động đổi mưu sĩ (thể lực ≥</label>
          <input id="gd-min-tac-stam" type="number" min="0" max="100" value="${esc(gd.min_tactician_stamina ?? "30")}" style="width:55px;"/>%)
        </div>
        <div class="form-row">
          <label><input id="gd-caller-en" type="checkbox" ${gd.caller_enabled ? "checked" : ""}/> Tài khoản gọi hộ</label>
          <label>TK <input id="gd-caller-user" type="text" value="${esc(gd.caller_username || "")}" placeholder="Username cùng server" style="width:130px;"/></label>
          <label>MK <input id="gd-caller-pass" type="password" value="${esc(draftPass)}" placeholder="${callerAux.ready ? "(Đã lưu sẵn)" : "Mật khẩu acc phụ"}" style="width:125px;"/></label>
          <label><input id="gd-caller-vault" type="checkbox" ${callerAux.has_vault_password ? "checked" : ""}/> Lưu Két</label>
          <button id="btn-gd-caller-test" type="button" class="btn-sm">🔑 Kiểm tra</button>
          <span id="gd-caller-status" style="font-size:12px;color:${callerAux.ready ? "#4ade80" : "var(--muted)"};">${esc(formatGdCallerStatusText(callerAux, gd.caller_username))}</span>
        </div>
        <div class="form-row" style="margin-bottom:0;">
          <span style="color:var(--muted);">Mục tiêu:</span>
          ${manOpts.map((m) => `<label style="font-size:12px;"><input type="checkbox" class="gd-mtype" value="${m.id}" ${(gd.target_types || [301]).includes(m.id) ? "checked" : ""}/> ${esc(m.label)}</label>`).join("")}
        </div>
      </div>
      <div class="card">
        <div class="card-title">
          <span>Võ tướng xuất kích</span>
          <span style="display:flex;align-items:center;gap:6px;flex-wrap:wrap;">
            <button id="btn-gd-gen-all" class="btn-sm">✅ Chọn tất cả</button>
            <button id="btn-gd-gen-none" class="btn-sm">❌ Bỏ chọn tất cả</button>
            <span id="gd-gen-count-lbl" style="font-size:12px;color:var(--accent);">Đã chọn: ${(gd.generals || []).filter((id) => gens.some((g) => g.id === id)).length} tướng (${(() => { const n = (gd.generals || []).filter((id) => gens.some((g) => g.id === id)).length; return n > 0 ? Math.ceil(n / 3) : 0; })()} đợt xuất kích)</span>
          </span>
        </div>
        <div class="table-wrap">${renderGeneralSelectTable(gens, gd.generals, "gd-gen")}</div>
      </div>
      <div class="card">
        <div class="card-title"><span>Nhật ký Gọi Man</span><button id="btn-clr-gd" class="btn-sm">🗑️ Xóa</button></div>
        <div id="log-goidan" class="log-box">${esc((snap.logs.goidan || []).join("\n"))}</div>
      </div>`;

    const syncGd = () => {
      const types = [...root.querySelectorAll(".gd-mtype:checked")].map((x) => Number(x.value));
      const gids = [...root.querySelectorAll(".gd-gen-chk:checked")].map((x) => Number(x.dataset.gid));
      const lbl = $("gd-gen-count-lbl");
      if (lbl) lbl.textContent = `Đã chọn: ${gids.length} tướng (${gids.length > 0 ? Math.ceil(gids.length / 3) : 0} đợt xuất kích)`;
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
          auto_swap_tactician: $("gd-swap-tac").checked,
          min_tactician_stamina: $("gd-min-tac-stam").value,
          caller_enabled: $("gd-caller-en").checked,
          caller_username: ($("gd-caller-user").value || "").trim(),
          target_types: types.length ? types : [301],
          target_type: types[0] || 301,
          generals: [...root.querySelectorAll(".gd-gen-chk:checked")].map((x) => Number(x.dataset.gid)),
        },
      });
    };
    const syncGdCallerCredentials = async ({ sendVault = false } = {}) => {
      const usr = ($("gd-caller-user")?.value || "").trim();
      const pwd = $("gd-caller-pass")?.value || "";
      state.gdCallerPassByKey[state.currentKey] = pwd;
      const saveVault = !!$("gd-caller-vault")?.checked;
      if (!usr) return null;
      if (!pwd && !sendVault) return null;
      const res = await api(`/api/accounts/${encodeURIComponent(state.currentKey)}/tasks/goidan/caller/credentials`, {
        method: "POST",
        body: {
          username: usr,
          password: pwd,
          save_to_vault: sendVault || saveVault ? saveVault : null,
        },
      });
      if (res.caller && state.snapshot?.aux) {
        state.snapshot.aux.goidan_caller = res.caller;
        renderAuxDomOnly();
      }
      return res;
    };
    $("gd-city").onchange = () => { syncGd(); renderActiveTab(); };
    ["gd-rad", "gd-int", "gd-act", "gd-inf", "gd-cav", "gd-arc", "gd-rec", "gd-mor", "gd-minm", "gd-swap-tac", "gd-min-tac-stam", "gd-caller-en", "gd-caller-user"].forEach((id) => ($(id).onchange = syncGd));
    $("gd-caller-pass").oninput = () => { state.gdCallerPassByKey[state.currentKey] = $("gd-caller-pass").value || ""; };
    $("gd-caller-pass").onchange = () => {
      syncGdCallerCredentials({ sendVault: !!$("gd-caller-vault")?.checked }).catch((e) => showToast("Lỗi", e.message, "error"));
    };
    $("gd-caller-vault").onchange = () => {
      syncGdCallerCredentials({ sendVault: true }).catch((e) => showToast("Lỗi", e.message, "error"));
    };
    $("btn-gd-caller-test").onclick = async () => {
      const usr = ($("gd-caller-user").value || "").trim();
      const pwd = $("gd-caller-pass").value || "";
      const saveVault = !!$("gd-caller-vault").checked;
      try {
        await saveProfileImmediate(state.snapshot.profile);
        const res = await api(`/api/accounts/${encodeURIComponent(state.currentKey)}/tasks/goidan/caller/test`, {
          method: "POST",
          body: { username: usr, password: pwd, save_to_vault: saveVault ? true : null },
        });
        if (res.status && state.snapshot?.aux) {
          state.snapshot.aux.goidan_caller = res.status;
          renderAuxDomOnly();
        }
        showToast("Thành công", res.reused_session ? `Đang dùng lại phiên '${res.username}'.` : `Đăng nhập '${res.username}' thành công!`, "success");
      } catch (e) {
        showToast("Kiểm tra thất bại", e.message, "error");
      }
    };
    $("btn-gd-gen-all").onclick = () => { root.querySelectorAll(".gd-gen-chk").forEach((c) => (c.checked = true)); syncGd(); };
    $("btn-gd-gen-none").onclick = () => { root.querySelectorAll(".gd-gen-chk").forEach((c) => (c.checked = false)); syncGd(); };
    root.querySelectorAll(".gd-mtype, .gd-gen-chk").forEach((c) => (c.onchange = syncGd));
    $("btn-tgl-gd").onclick = async () => {
      if (!state.snapshot?.summary?.tasks?.goidan?.running && $("gd-caller-en")?.checked && ($("gd-caller-pass")?.value || $("gd-caller-vault")?.checked)) {
        try {
          await syncGdCallerCredentials({ sendVault: !!$("gd-caller-vault")?.checked });
        } catch (e) {
          showToast("Lỗi", e.message, "error");
          return;
        }
      }
      await toggleTask("goidan");
    };
    $("btn-gd-once").onclick = async () => {
      try {
        if ($("gd-caller-en")?.checked && ($("gd-caller-pass")?.value || $("gd-caller-vault")?.checked)) {
          await syncGdCallerCredentials({ sendVault: !!$("gd-caller-vault")?.checked });
        }
        await saveProfileImmediate(state.snapshot.profile);
        await api(`/api/accounts/${encodeURIComponent(state.currentKey)}/tasks/goidan/once`, { method: "POST" });
      } catch (e) {
        showToast("Lỗi", e.message, "error");
      }
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
    const moFilteredGens = state.moraleCityFilter === "all"
      ? armyGens
      : armyGens.filter((g) => String(g.city_id) === String(state.moraleCityFilter));
    const weaponCats = [
      ["🗡️ Binh khí", "Binh khí"],
      ["🏹 Cung nỗ", "Cung nỗ"],
      ["🛡️ Khôi giáp", "Khôi giáp"],
      ["🐎 Chiến mã", "Chiến mã"],
      ["🚜 Xe ném đá", "Xe ném đá"],
    ];
    const wNameById = Object.fromEntries(weapons.map((w) => [w.id, w.name]));
    const craftLabelOf = (wids) => (wids || [101]).map((id) => wNameById[id] || `#${id}`).join(", ");
    const roleLabel = (g) => (g.is_mayor ? "Thái thú" : (g.role === "van" ? "Văn quan" : "Võ tướng"));
    const maxArm = selGen ? Math.max(1, selGen.army?.infantry || 0, selGen.army?.cavalry || 0, selGen.army?.archers || 0) : 1;

    root.innerHTML = `
      <div class="card">
        <div class="form-row" style="margin-bottom:0;">
          <button id="btn-reward-all" class="btn-success btn-sm">🎁 Ban Thưởng Toàn Bộ</button>
          <button id="btn-open-tactician" class="btn-sm">🧠 Thiết Lập Mưu Sĩ</button>
          <button id="btn-open-equip" class="btn-sm">🛡️ Trang Bị Tướng</button>
          <button id="btn-open-armament" class="btn-sm">⚔️ Quân Giới Tướng</button>
          <button id="btn-open-rename" class="btn-sm">✏️ Đổi Tên Tướng</button>
          <button id="btn-open-add-points" class="btn-sm">✨ Cộng Điểm</button>
          <button id="btn-open-training" class="btn-sm">🎓 Đào Tạo Tướng</button>
        </div>
      </div>

      <div class="grid-3">
        <div class="card">
          <div class="card-title">Thành & Doanh trại</div>
          <div class="table-wrap" style="max-height:220px;">
            <table><thead><tr><th>Tên</th><th>Loại</th><th>ID</th><th>Tọa độ</th></tr></thead>
            <tbody>${bases.map((b) => `<tr class="ov-base row-clickable ${b.id === state.selectedOverviewCityId ? "selected" : ""}" data-bid="${b.id}"><td>${esc(b.name)}</td><td>${esc(b.type)}</td><td>${b.id}</td><td>${b.pos_x},${b.pos_y}</td></tr>`).join("")}</tbody></table>
          </div>
        </div>
        <div class="card">
          <div class="card-title">Tướng đồn trú</div>
          <div class="table-wrap" style="max-height:220px;">
            <table><thead><tr><th>Tên tướng</th><th>Chức vụ</th><th>Cấp</th><th>Thể lực</th><th>TT</th><th>Mưu sĩ</th><th>Trạng thái</th></tr></thead>
            <tbody>${gens.map((g) => `<tr class="ov-gen row-clickable ${selGen && g.id === selGen.id ? "selected" : ""}" data-gid="${g.id}"><td>${esc(g.name)}</td><td>${esc(roleLabel(g))}</td><td>${g.level}</td><td>${g.stamina}/${g.stamina_max}</td><td>${g.loyalty}</td><td>${esc(g.tactician_name || "-")}</td><td>${esc(g.status_text)}</td></tr>`).join("")}</tbody></table>
          </div>
        </div>
        <div class="card">
          <div class="card-title">Chi tiết biên chế</div>
          ${selGen ? `
            <div style="font-size:16px;font-weight:700;color:var(--accent);">${esc(selGen.name)} (${esc(roleLabel(selGen))} Lv.${selGen.level})</div>
            <div style="color:var(--muted);font-size:12px;margin:4px 0 12px;">Sĩ khí: ${selGen.morale}/100 | Thể lực: ${selGen.stamina}/${selGen.stamina_max} | Trung thành: ${selGen.loyalty} | Mưu sĩ: ${esc(selGen.tactician_name || "-")}</div>
            <div class="bar-row"><span>Bộ binh</span><div class="bar-track"><div class="bar-fill" style="width:${Math.round(((selGen.army?.infantry || 0) / maxArm) * 100)}%"></div></div><strong style="text-align:right;">${(selGen.army?.infantry || 0).toLocaleString()}</strong></div>
            <div class="bar-row"><span>Kỵ binh</span><div class="bar-track"><div class="bar-fill cav" style="width:${Math.round(((selGen.army?.cavalry || 0) / maxArm) * 100)}%"></div></div><strong style="text-align:right;">${(selGen.army?.cavalry || 0).toLocaleString()}</strong></div>
            <div class="bar-row"><span>Cung binh</span><div class="bar-track"><div class="bar-fill arc" style="width:${Math.round(((selGen.army?.archers || 0) / maxArm) * 100)}%"></div></div><strong style="text-align:right;">${(selGen.army?.archers || 0).toLocaleString()}</strong></div>
            <div style="margin-top:10px;color:var(--accent);font-weight:700;">Tổng quân: ${(selGen.army?.total || 0).toLocaleString()}</div>
          ` : '<div style="color:var(--muted);">Chọn một tướng để xem.</div>'}
        </div>
      </div>

      <div class="grid-2">
        <div class="card">
          <div class="card-title">⚔️ Luyện Sĩ Khí Quân Đội (Đa Thành)</div>
          <div class="form-row">
            <label>Thành <select id="mo-city">
              <option value="all" ${state.moraleCityFilter === "all" ? "selected" : ""}>🌟 Tất cả các thành</option>
              ${bases.map((b) => `<option value="${b.id}" ${String(state.moraleCityFilter) === String(b.id) ? "selected" : ""}>${esc(b.display_name)}</option>`).join("")}
            </select></label>
            <label>Đích <select id="mo-target">${[100, 95, 90, 85].map((x) => `<option value="${x}">${x}</option>`).join("")}</select></label>
            <button id="btn-mo-all" class="btn-sm">☑ Tất cả</button>
            <button id="btn-mo-none" class="btn-sm">☐ Bỏ chọn</button>
          </div>
          <div class="form-row">
            <button id="btn-mo-start" class="btn-primary btn-sm">⚔️ Luyện Sĩ Khí</button>
            <button id="btn-mo-stop" class="btn-danger btn-sm">⏹️ Dừng</button>
            <span id="morale-status-lbl" style="font-size:12px;color:var(--muted);"></span>
          </div>
          <div class="table-wrap" style="max-height:220px;">
            <table><thead><tr><th>Chọn</th><th>Tên tướng</th><th>Thành</th><th>Sĩ khí</th><th>Quân số</th><th>Chi tiết</th><th>Trạng thái</th></tr></thead>
            <tbody>${moFilteredGens.map((g) => {
      const bname = bases.find((b) => b.id === g.city_id)?.name || g.city_id;
      const a = g.army || {};
      return `<tr><td><input type="checkbox" class="mo-chk" data-gid="${g.id}" ${state.selectedMoraleGens.has(g.id) ? "checked" : ""}/></td><td>${esc(g.name)}</td><td>${esc(bname)}</td><td>${g.morale}/100</td><td>${(a.total || 0).toLocaleString()}</td><td>B:${a.infantry || 0} K:${a.cavalry || 0} C:${a.archers || 0}</td><td>${esc(snap.aux?.morale_gen_status?.[g.id] || "Chờ")}</td></tr>`;
    }).join("")}</tbody></table>
          </div>
        </div>

        <div class="card">
          <div class="card-title">🛠️ Chế Tạo Quân Giới (Đa Thành)</div>
          <div class="form-row">
            <label>Thành <select id="cr-city">${cities.map((c) => `<option value="${c.id}" ${c.id === state.selectedCraftCityId ? "selected" : ""}>${esc(c.display_name)}</option>`).join("")}</select></label>
            <label>SL/mẻ <input id="cr-amt" type="number" value="${esc(curCraft.amount)}" style="width:70px;"/></label>
            <label>Chu kỳ (phút) <input id="cr-int" type="number" value="${esc(curCraft.interval)}" style="width:55px;"/></label>
            <label><input id="cr-en" type="checkbox" ${curCraft.enabled ? "checked" : ""}/> Bật thành này</label>
          </div>
          <div class="field" style="margin-bottom:8px;">
            <label>Quân giới (<span id="cr-sel-summary">${esc(craftLabelOf(curCraft.weapon_ids))}</span>)</label>
            <div class="grp-menu" id="cr-weapons-menu">
              ${weaponCats.map(([title, cat]) => {
      const items = weapons.filter((w) => w.category === cat);
      return `<details><summary>${title} (${items.filter((w) => (curCraft.weapon_ids || []).includes(w.id)).length}/${items.length})</summary>
                  ${items.map((w) => `<label><input type="checkbox" class="cr-w-chk" value="${w.id}" ${(curCraft.weapon_ids || []).includes(w.id) ? "checked" : ""}/> ${w.id}. ${esc(w.name)}</label>`).join("")}
                </details>`;
    }).join("")}
            </div>
          </div>
          <div class="form-row">
            <button id="btn-cr-now" class="btn-sm">⚡ Chế tạo ngay</button>
            <button id="btn-tgl-craft" class="btn-success btn-sm">▶️ Chạy Chế Tạo</button>
            <span id="craft-status-lbl" style="font-size:12px;color:var(--muted);"></span>
          </div>
          <div class="table-wrap" style="max-height:150px;">
            <table><thead><tr><th>Bật</th><th>Thành trì</th><th>Quân Giới</th><th>Số lượng</th><th>Chu kỳ (phút)</th><th>Trạng thái</th></tr></thead>
            <tbody>${cities.map((c) => {
      const cfg = craftCities[String(c.id)] || {};
      const wids = cfg.weapon_ids?.length ? cfg.weapon_ids : [cfg.weapon_id || 101];
      return `<tr class="cr-row row-clickable ${c.id === state.selectedCraftCityId ? "selected" : ""}" data-cid="${c.id}">
                <td class="cr-tgl-cell" style="text-align:center;">${cfg.enabled ? "☑" : "☐"}</td>
                <td>${esc(c.name)}</td>
                <td>${esc(craftLabelOf(wids))}</td>
                <td>${esc(cfg.amount || 1000)}</td>
                <td>${esc(cfg.interval || 5)}</td>
                <td>${esc(snap.aux?.craft_statuses?.[c.id] || (cfg.enabled ? "Sẵn sàng" : "Tắt"))}</td>
              </tr>`;
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
    $("btn-open-armament").onclick = openArmamentModal;
    $("btn-open-rename").onclick = openRenameModal;
    $("btn-open-add-points").onclick = openAddPointsModal;
    $("btn-open-training").onclick = openTrainingModal;

    $("mo-city").onchange = () => { state.moraleCityFilter = $("mo-city").value; renderActiveTab(); };
    root.querySelectorAll(".mo-chk").forEach((c) => (c.onchange = () => {
      const gid = Number(c.dataset.gid);
      if (c.checked) state.selectedMoraleGens.add(gid); else state.selectedMoraleGens.delete(gid);
    }));
    $("btn-mo-all").onclick = () => { moFilteredGens.forEach((g) => state.selectedMoraleGens.add(g.id)); renderActiveTab(); };
    $("btn-mo-none").onclick = () => { moFilteredGens.forEach((g) => state.selectedMoraleGens.delete(g.id)); renderActiveTab(); };
    $("btn-mo-start").onclick = () => api(`/api/accounts/${encodeURIComponent(state.currentKey)}/morale/start`, {
      method: "POST", body: { general_ids: [...state.selectedMoraleGens], target_morale: Number($("mo-target").value) },
    }).catch((e) => showToast("Lỗi", e.message, "error"));
    $("btn-mo-stop").onclick = () => api(`/api/accounts/${encodeURIComponent(state.currentKey)}/morale/stop`, { method: "POST" });

    const syncCraft = () => {
      const wids = [...root.querySelectorAll(".cr-w-chk:checked")].map((x) => Number(x.value));
      const finalWids = wids.length ? wids : [101];
      craftCities[String(state.selectedCraftCityId)] = {
        city_id: state.selectedCraftCityId,
        weapon_id: finalWids[0],
        weapon_ids: finalWids,
        amount: $("cr-amt").value,
        interval: $("cr-int").value,
        enabled: $("cr-en").checked,
      };
      const sum = $("cr-sel-summary");
      if (sum) sum.textContent = craftLabelOf(finalWids);
      scheduleProfileSave({ crafting: { cities: craftCities } });
    };
    $("cr-city").onchange = () => { state.selectedCraftCityId = Number($("cr-city").value); renderActiveTab(); };
    ["cr-amt", "cr-int", "cr-en"].forEach((id) => ($(id).onchange = syncCraft));
    root.querySelectorAll(".cr-w-chk").forEach((c) => (c.onchange = syncCraft));
    root.querySelectorAll(".cr-row").forEach((tr) => {
      tr.onclick = (e) => {
        const cid = Number(tr.dataset.cid);
        if (e.target.classList.contains("cr-tgl-cell")) {
          const cur = craftCities[String(cid)] || { city_id: cid, weapon_id: 101, weapon_ids: [101], amount: "1000", interval: "5", enabled: false };
          cur.enabled = !cur.enabled;
          craftCities[String(cid)] = cur;
          scheduleProfileSave({ crafting: { cities: craftCities } });
          renderActiveTab();
          return;
        }
        state.selectedCraftCityId = cid;
        renderActiveTab();
      };
    });
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
    const stratOpts = ["0. Không dùng", "93. Phản khách vi chủ", "95. Cầm tặc cầm vương", "94. Quan môn tróc tặc"];
    const basicForms = (state.meta?.formations || []).filter((f) => f.id >= 1 && f.id <= 5);
    const formOpts = basicForms.length ? basicForms : (state.meta?.formations || []);
    const manualStratOpts = state.meta?.stratagems || [];
    const selPos = state.selectedBattleOurPos ?? (bs?.our_troops?.[0]?.position ?? 1);

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
          <label><input id="cb-counter" type="checkbox" ${cb.auto_counter_formation ? "checked" : ""}/> Tự đổi trận ngũ hành (Cửa sổ ≤</label>
          <input id="cb-win" type="number" value="${esc(cb.formation_window_seconds)}" style="width:52px;"/>s cuối hiệp)
          <label><input id="cb-boss" type="checkbox" ${cb.leave_boss_last ? "checked" : ""}/> Giữ BOSS bắt sống (Thủ khi chỉ còn BOSS)</label>
          <label><input id="cb-cleanse" type="checkbox" ${cb.auto_cleanse_confusion ? "checked" : ""}/> Tự giải Hỗn loạn (96)</label>
        </div>
        <div class="form-row">
          <label>Chiêu tấn công <select id="cb-act">${actOpts.map((o, i) => `<option value="${i}" ${Number(cb.action_combo_idx) === i ? "selected" : ""}>${esc(o)}</option>`).join("")}</select></label>
          <label><input id="cb-skip" type="checkbox" ${cb.skip_confused_enemy ? "checked" : ""}/> Bỏ qua địch hỗn loạn</label>
          <label>Mưu kế Hiệp 1 <select id="cb-strat">${stratOpts.map((o, i) => `<option value="${i}" ${Number(cb.stratagem_combo_idx) === i ? "selected" : ""}>${esc(o)}</option>`).join("")}</select></label>
          <label>Rút lui khẩn cấp (mưu 92 khi lính < %) <input id="cb-retreat" type="number" value="${esc(cb.emergency_retreat_threshold)}" style="width:65px;"/></label>
        </div>
        <div class="form-row" style="margin-bottom:0;">
          <label><input id="cb-autocap" type="checkbox" ${cb.auto_capture_boss ? "checked" : ""}/> Tự động bắt sống BOSS bằng Coin</label>
          <label>khi Sĩ khí &lt; <input id="cb-capmor" type="number" value="${esc(cb.capture_boss_max_morale)}" style="width:58px;"/> điểm</label>
          <button id="btn-bt-notify" class="btn-sm">🔔 Cài Đặt Thông Báo & Bắt Sống BOSS</button>
        </div>
      </div>

      <div class="grid-2">
        <div class="card">
          <div class="card-title">🛡️ Phe Ta (Quân đội & Tướng lĩnh)</div>
          <div class="table-wrap">${renderBattleTroopsTable(bs?.our_troops || [], false)}</div>
        </div>
        <div class="card">
          <div class="card-title">🎯 Phe Địch (Mục tiêu & BOSS)</div>
          <div class="table-wrap">${renderBattleTroopsTable(bs?.enemy_troops || [], true)}</div>
        </div>
      </div>

      <div class="card">
        <div class="form-row">
          <label>Vị trí ta <input id="bt-pos" type="number" value="${selPos}" style="width:60px;"/></label>
          <select id="bt-mform">${formOpts.map((f) => `<option value="${f.id}" ${String(state.btManualForm ?? formOpts[0]?.id) === String(f.id) ? "selected" : ""}>${f.id}. ${esc(f.name)}</option>`).join("")}</select>
          <button id="btn-bt-form" class="btn-sm">🔄 Đổi ngay</button>
          <select id="bt-mstrat">${manualStratOpts.map((s) => `<option value="${s.id}" ${String(state.btManualStrat ?? manualStratOpts[0]?.id) === String(s.id) ? "selected" : ""}>${s.id}. ${esc(s.name)}</option>`).join("")}</select>
          <button id="btn-bt-strat" class="btn-sm">✨ Kích hoạt</button>
          <button id="btn-bt-defend" class="btn-warning btn-sm">🛡️ Phòng ngự toàn quân</button>
          <button id="btn-clr-bt" class="btn-sm" style="margin-left:auto;">🗑️ Xóa log</button>
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
        auto_capture_boss: $("cb-autocap").checked,
        capture_boss_max_morale: $("cb-capmor").value,
      },
    });
    ["cb-counter", "cb-win", "cb-act", "cb-strat", "cb-skip", "cb-boss", "cb-cleanse", "cb-retreat", "cb-autocap", "cb-capmor"].forEach((id) => ($(id).onchange = syncCb));
    $("btn-bt-notify").onclick = openNotificationModal;
    root.querySelectorAll(".bt-our-row").forEach((tr) => {
      tr.onclick = () => {
        state.selectedBattleOurPos = Number(tr.dataset.pos);
        $("bt-pos").value = String(state.selectedBattleOurPos);
        root.querySelectorAll(".bt-our-row").forEach((r) => r.classList.remove("selected"));
        tr.classList.add("selected");
      };
    });
    $("bt-id").onchange = () => { state.battleIdInput = $("bt-id").value; };
    $("bt-pos").onchange = () => { state.selectedBattleOurPos = Number($("bt-pos").value); };
    $("bt-mform").onchange = () => { state.btManualForm = $("bt-mform").value; };
    $("bt-mstrat").onchange = () => { state.btManualStrat = $("bt-mstrat").value; };
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
          <span id="nt-status-lbl" class="pill">${esc(ntStatusText())}</span>
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

  // TAB 8: CƯỜNG HÓA TRANG BỊ & HỦY ĐỒ (ADR-0045)
  function getEnhanceUi(key = state.currentKey) {
    if (!key) return null;
    if (!state.enhanceUi[key]) {
      state.enhanceUi[key] = {
        equipType: 1,
        roleTab: "vo",
        filterText: "",
        itemsByRole: { vo: [], van: [] },
        autoLoaded: false,
        selectedItem: null,
        materials: [],
        targetLevel: 7,
        protectFrom: "7",
        materialFrom: "1",
        mat1: "",
        mat2: "",
        mat3: "",
        loopCount: "1",
        wasRunning: false,
      };
    }
    return state.enhanceUi[key];
  }

  async function loadEnhanceResources() {
    if (!state.currentKey) return;
    try {
      const res = await api(`/api/accounts/${encodeURIComponent(state.currentKey)}/enhance/resources`);
      if (state.snapshot?.aux) {
        state.snapshot.aux.enhance_resources = res.resources;
      }
      updateEnhanceAuxDom(state.snapshot?.aux);
    } catch (e) {
      showToast("Lỗi tải tài nguyên", e.message, "error");
    }
  }

  async function loadEnhanceItems(equipType) {
    const ui = getEnhanceUi();
    if (!ui || !state.currentKey) return;
    ui.equipType = equipType;
    try {
      const data = await api(`/api/accounts/${encodeURIComponent(state.currentKey)}/enhance/items?equip_type=${equipType}`);
      ui.itemsByRole = { vo: data.vo || [], van: data.van || [] };
      if (ui.selectedItem) {
        const list = ui.itemsByRole[ui.roleTab] || [];
        const match = list.find((it) => it.item_id === ui.selectedItem.item_id);
        ui.selectedItem = match || null;
        if (match) {
          if (ui.targetLevel <= match.level) {
            ui.targetLevel = Math.min(15, match.level + 1);
          }
        } else {
          ui.materials = [];
        }
      }
      if (state.activeTab === "enhance") renderActiveTab();
    } catch (e) {
      showToast("Lỗi tải kho trang bị", e.message, "error");
    }
  }

  async function loadEnhanceMaterials(itemId) {
    const ui = getEnhanceUi();
    if (!ui || !state.currentKey || !itemId) return;
    try {
      const data = await api(`/api/accounts/${encodeURIComponent(state.currentKey)}/enhance/materials?item_id=${itemId}`);
      ui.materials = data.groups || [];
      const keys = new Set(ui.materials.map((g) => g.key));
      if (!keys.has(ui.mat1)) ui.mat1 = "";
      if (!keys.has(ui.mat2)) ui.mat2 = "";
      if (!keys.has(ui.mat3)) ui.mat3 = "";
      if (state.activeTab === "enhance") renderActiveTab();
    } catch (e) {
      showToast("Lỗi tải Phôi Cường Hóa", e.message, "error");
    }
  }

  function updateEnhanceAuxDom(aux) {
    if (!aux) return;
    const res = aux.enhance_resources || aux.enhance_progress?.resources || {};
    const prog = aux.enhance_progress || {};
    const running = !!(aux.enhance_running || prog.running);

    const ironEl = $("enh-res-iron");
    if (ironEl) ironEl.textContent = Number(res.iron || 0).toLocaleString("vi-VN");
    const hamEl = $("enh-res-hammer");
    if (hamEl) hamEl.textContent = Number(res.hammer || 0).toLocaleString("vi-VN");
    const cryEl = $("enh-res-crystal");
    if (cryEl) cryEl.textContent = Number(res.crystal || 0).toLocaleString("vi-VN");

    const stEl = $("enh-status-lbl");
    if (stEl) stEl.textContent = prog.status || "Sẵn sàng";
    const pctEl = $("enh-progress-pct");
    if (pctEl) pctEl.textContent = `${Number(prog.pct || 0)}%`;
    const fillEl = $("enh-progress-fill");
    if (fillEl) fillEl.style.width = `${Number(prog.pct || 0)}%`;

    const itemEl = $("enh-stat-item");
    if (itemEl) {
      itemEl.textContent = prog.mode === "destroy"
        ? `Hủy: ${prog.destroyed_count || 0}/${prog.destroy_total || 0}`
        : `Món: ${prog.item_index || 0}/${prog.total_items || 0} (Hoàn tất: ${prog.completed_items || 0})`;
    }
    const lvlEl = $("enh-stat-lvl");
    if (lvlEl) {
      lvlEl.textContent = prog.target_level
        ? `Cấp: ${prog.current_level || 0}/${prog.target_level}`
        : "Cấp: -";
    }
    const attEl = $("enh-stat-attempts");
    if (attEl) {
      attEl.textContent = `Lượt ép: ${prog.total_attempts || 0} (✅ ${prog.success_attempts || 0} / ❌ ${prog.fail_attempts || 0})`;
    }
    const usedEl = $("enh-stat-used");
    if (usedEl) {
      usedEl.textContent = `Tiêu hao: Sắt ${prog.iron_used || 0} | Búa ${prog.hammer_used || 0} | Pha Lê ${prog.crystal_used || 0} | Phôi ${prog.material_used || 0}`;
    }

    const startBtn = $("btn-enh-start");
    const stopBtn = $("btn-enh-stop");
    const delBtn = $("btn-enh-destroy");
    if (startBtn) startBtn.disabled = running;
    if (delBtn) delBtn.disabled = running;
    if (stopBtn) stopBtn.disabled = !running;
    ["enh-target-lvl", "enh-protect-from", "enh-loop-count", "enh-mat-from", "enh-mat-1", "enh-mat-2", "enh-mat-3"].forEach((id) => {
      const el = $(id);
      if (el) el.disabled = running;
    });

    const ui = getEnhanceUi();
    if (ui) {
      const finishedJustNow = ui.wasRunning && !running;
      ui.wasRunning = running;
      if (finishedJustNow && state.activeTab === "enhance") {
        loadEnhanceItems(ui.equipType);
      }
    }
  }

  function openEnhanceDestroyModal(ui) {
    const item = ui.selectedItem;
    if (!item) {
      showToast("Chưa chọn trang bị", "Vui lòng chọn một trang bị trong kho để hủy.", "warn");
      return;
    }
    const allSame = (ui.itemsByRole[ui.roleTab] || []).filter(
      (it) => it.item_type_id === item.item_type_id && it.level === item.level
    );
    const totalStock = Math.max(1, allSame.reduce((acc, it) => acc + Number(it.quantity || 1), 0));
    const isHigh = Number(item.level) >= 7;

    openModal(
      "🔥 Xác Nhận Hủy Trang Bị",
      `<div style="line-height:1.6;">
        <div><strong>Trang bị:</strong> ${esc(item.name)}</div>
        <div><strong>Cấp độ:</strong> Cấp ${item.level} (ID: ${item.item_id})</div>
        <div><strong>Tồn kho cùng loại & cấp:</strong> ${totalStock}</div>
      </div>
      ${isHigh ? `<div class="danger-box">
        <strong>⚠️ CẢNH BÁO ĐỒ CẤP CAO (Cấp ${item.level} ≥ 7):</strong><br/>
        Hành động hủy sẽ xóa vĩnh viễn trang bị này và không thể hoàn tác!
        <label style="display:flex;align-items:center;gap:6px;margin-top:8px;cursor:pointer;">
          <input id="enh-del-confirm" type="checkbox" /> Tôi xác nhận muốn hủy vĩnh viễn trang bị cấp ${item.level}
        </label>
      </div>` : ""}
      <div class="field" style="margin-top:10px;">
        <label>Số lượng cần hủy (tối đa ${totalStock}):</label>
        <input id="enh-del-qty" type="number" min="1" max="${totalStock}" value="1" />
      </div>`,
      `<button id="btn-enh-del-ok" class="btn-danger" ${isHigh ? "disabled" : ""}>🔥 Xác nhận hủy</button>
       <button id="btn-enh-del-cancel" class="btn-sm">Đóng</button>`
    );

    if (isHigh) {
      $("enh-del-confirm").onchange = () => {
        $("btn-enh-del-ok").disabled = !$("enh-del-confirm").checked;
      };
    }
    $("btn-enh-del-cancel").onclick = closeModal;
    $("btn-enh-del-ok").onclick = async () => {
      const qty = Math.max(1, Math.min(totalStock, Number($("enh-del-qty").value || 1)));
      const confirmed = isHigh ? !!$("enh-del-confirm")?.checked : true;
      try {
        await api(`/api/accounts/${encodeURIComponent(state.currentKey)}/enhance/destroy`, {
          method: "POST",
          body: {
            equip_type: ui.equipType,
            role: ui.roleTab,
            item_id: item.item_id,
            item_type_id: item.item_type_id,
            level: item.level,
            quantity: qty,
            confirm_high_level: confirmed,
          },
        });
        closeModal();
        showToast("Đã bắt đầu hủy trang bị", `${item.name} (x${qty})`, "ok");
      } catch (e) {
        showToast("Không thể hủy trang bị", e.message, "error");
      }
    };
  }

  function renderEnhanceTab(root) {
    const snap = state.snapshot;
    const ui = getEnhanceUi();
    if (!ui) return;

    if (!ui.autoLoaded && state.currentKey) {
      ui.autoLoaded = true;
      loadEnhanceResources();
      loadEnhanceItems(ui.equipType);
    }

    const eqTypes = [
      { id: 1, label: "🪖 Mũ" },
      { id: 2, label: "⚔️ Vũ khí" },
      { id: 3, label: "🛡️ Giáp" },
      { id: 4, label: "🐎 Ngựa" },
    ];
    const voList = ui.itemsByRole.vo || [];
    const vanList = ui.itemsByRole.van || [];
    const activeList = ui.roleTab === "van" ? vanList : voList;
    const q = (ui.filterText || "").trim().toLowerCase();
    const filteredList = q
      ? activeList.filter(
          (it) =>
            String(it.name || "").toLowerCase().includes(q) ||
            String(it.level).includes(q) ||
            String(it.item_id).includes(q)
        )
      : activeList;

    const sel = ui.selectedItem;
    const curLvl = sel ? Number(sel.level) : 1;
    const targetOpts = [];
    if (sel && curLvl < 15) {
      for (let lv = curLvl + 1; lv <= 15; lv++) {
        targetOpts.push(`<option value="${lv}" ${Number(ui.targetLevel) === lv ? "selected" : ""}>Cấp ${lv}</option>`);
      }
    } else if (sel) {
      targetOpts.push(`<option value="">Đã tối đa (Cấp 15)</option>`);
    } else {
      targetOpts.push(`<option value="">-- Chọn trang bị --</option>`);
    }

    const protectOpts = [`<option value="" ${ui.protectFrom === "" ? "selected" : ""}>Không dùng Búa</option>`];
    for (let lv = 2; lv <= 8; lv++) {
      protectOpts.push(`<option value="${lv}" ${String(ui.protectFrom) === String(lv) ? "selected" : ""}>Từ cấp ${lv}</option>`);
    }

    const matFromOpts = [];
    for (let lv = 1; lv <= 8; lv++) {
      matFromOpts.push(`<option value="${lv}" ${String(ui.materialFrom) === String(lv) ? "selected" : ""}>Từ cấp ${lv}</option>`);
    }

    const buildMatOpts = (selectedVal) => {
      const opts = [`<option value="" ${!selectedVal ? "selected" : ""}>Không dùng phôi</option>`];
      for (const grp of ui.materials || []) {
        opts.push(`<option value="${esc(grp.key)}" ${selectedVal === grp.key ? "selected" : ""}>${esc(grp.display_label)}</option>`);
      }
      return opts.join("");
    };

    root.innerHTML = `
      <div class="grid-2">
        <div>
          <div class="card">
            <div class="card-title">
              <span>1. Kho Trang Bị (Chưa Mặc)</span>
              <button id="btn-enh-reload" class="btn-sm">🔄 Tải kho</button>
            </div>
            <div class="form-row">
              ${eqTypes
                .map(
                  (t) =>
                    `<button class="btn-sm enh-type-btn ${ui.equipType === t.id ? "btn-primary" : ""}" data-type="${t.id}">${t.label}</button>`
                )
                .join("")}
              <input id="enh-filter" type="text" value="${esc(ui.filterText)}" placeholder="Lọc tên / cấp / ID..." style="flex:1;min-width:130px;" />
            </div>
            <div class="form-row" style="margin-bottom:6px;">
              <button id="btn-enh-role-vo" class="btn-sm ${ui.roleTab === "vo" ? "btn-primary" : ""}">⚔️ Võ Tướng (${voList.length})</button>
              <button id="btn-enh-role-van" class="btn-sm ${ui.roleTab === "van" ? "btn-primary" : ""}">📜 Văn Quan (${vanList.length})</button>
            </div>
            <div class="table-wrap" style="max-height:250px;">
              <table>
                <thead><tr><th>Tên trang bị</th><th>Cấp</th><th>SL</th><th>ID</th></tr></thead>
                <tbody>
                  ${
                    filteredList.length
                      ? filteredList
                          .map(
                            (it) => `<tr class="enh-item-row row-clickable ${sel && sel.item_id === it.item_id ? "selected" : ""}" data-id="${it.item_id}">
                              <td>${esc(it.name)}</td>
                              <td>Cấp ${it.level}</td>
                              <td>${it.quantity}</td>
                              <td>${it.item_id}</td>
                            </tr>`
                          )
                          .join("")
                      : `<tr><td colspan="4" style="color:var(--muted);text-align:center;">Không có trang bị chưa mặc</td></tr>`
                  }
                </tbody>
              </table>
            </div>
          </div>

          <div class="card">
            <div class="card-title">2. Thiết Lập Cường Hóa</div>
            <div id="enh-selected-lbl" style="font-size:12.5px;color:var(--info);margin-bottom:8px;">
              ${sel ? `Đang chọn: <strong>${esc(sel.name)}</strong> — Cấp ${sel.level} (ID: ${sel.item_id}, SL: ${sel.quantity})` : "Chưa chọn trang bị trong kho"}
            </div>
            <div class="form-row">
              <label>Cấp mục tiêu
                <select id="enh-target-lvl">${targetOpts.join("")}</select>
              </label>
              <label>Kẹp Búa Bảo Hộ
                <select id="enh-protect-from" ${sel && curLvl >= 9 ? "disabled" : ""}>${protectOpts.join("")}</select>
              </label>
              <label>Số lượng món
                <input id="enh-loop-count" type="number" min="1" max="99999" value="${esc(ui.loopCount)}" style="width:82px;" />
              </label>
            </div>
          </div>

          <div class="card">
            <div class="card-title">
              <span>3. Phôi Cường Hóa (Chặng cấp 1→8)</span>
              <button id="btn-enh-refresh-mats" class="btn-sm" ${!sel ? "disabled" : ""}>🔄 Tải Phôi</button>
            </div>
            <div class="form-row">
              <label>Dùng Phôi từ cấp <select id="enh-mat-from">${matFromOpts.join("")}</select></label>
            </div>
            <div class="form-grid" style="gap:6px 10px;">
              <label>Phôi 1:</label><select id="enh-mat-1">${buildMatOpts(ui.mat1)}</select>
              <label>Phôi 2:</label><select id="enh-mat-2">${buildMatOpts(ui.mat2)}</select>
              <label>Phôi 3:</label><select id="enh-mat-3">${buildMatOpts(ui.mat3)}</select>
            </div>
            <div class="form-row" style="margin-top:12px;margin-bottom:0;">
              <button id="btn-enh-start" class="btn-success">🔨 Nâng Cấp</button>
              <button id="btn-enh-stop" class="btn-danger" disabled>⏹️ Dừng</button>
              <button id="btn-enh-destroy" class="btn-warning">🔥 Hủy Đồ</button>
            </div>
          </div>
        </div>

        <div>
          <div class="card">
            <div class="card-title">
              <span>Tài Nguyên Hiện Có</span>
              <button id="btn-enh-refresh-res" class="btn-sm">🔄 Cập nhật tài nguyên</button>
            </div>
            <div class="res-grid">
              <div class="res-pill"><span class="lbl">Huyền Thiết (341)</span><span id="enh-res-iron" class="val">0</span></div>
              <div class="res-pill"><span class="lbl">Búa Bảo Hộ (342)</span><span id="enh-res-hammer" class="val">0</span></div>
              <div class="res-pill"><span class="lbl">Pha Lê (354)</span><span id="enh-res-crystal" class="val">0</span></div>
            </div>
          </div>

          <div class="card">
            <div class="card-title">
              <span>Quá Trình & Thống Kê</span>
              <span id="enh-progress-pct" class="pill">0%</span>
            </div>
            <div class="progress-track"><div id="enh-progress-fill" class="progress-fill"></div></div>
            <div id="enh-status-lbl" style="font-size:12.5px;color:var(--accent);margin-top:6px;font-weight:600;">Sẵn sàng</div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-top:8px;font-size:12.5px;">
              <div id="enh-stat-item">Món: 0/0</div>
              <div id="enh-stat-lvl">Cấp: -</div>
              <div id="enh-stat-attempts">Lượt ép: 0</div>
              <div id="enh-stat-used">Tiêu hao: Sắt 0 | Búa 0 | Pha Lê 0 | Phôi 0</div>
            </div>
          </div>

          <div class="card">
            <div class="card-title"><span>Nhật Ký Cường Hóa</span><button id="btn-clr-enh" class="btn-sm">🗑️ Xóa</button></div>
            <div id="log-enhance" class="log-box" style="height:280px;">${esc((snap.logs.enhance || []).join("\n"))}</div>
          </div>
        </div>
      </div>`;

    root.querySelectorAll(".enh-type-btn").forEach((btn) => {
      btn.onclick = () => loadEnhanceItems(Number(btn.dataset.type));
    });
    $("btn-enh-reload").onclick = () => loadEnhanceItems(ui.equipType);
    $("btn-enh-role-vo").onclick = () => {
      ui.roleTab = "vo";
      ui.selectedItem = null;
      ui.materials = [];
      renderActiveTab();
    };
    $("btn-enh-role-van").onclick = () => {
      ui.roleTab = "van";
      ui.selectedItem = null;
      ui.materials = [];
      renderActiveTab();
    };
    $("enh-filter").oninput = () => {
      ui.filterText = $("enh-filter").value;
      renderActiveTab();
    };

    root.querySelectorAll(".enh-item-row").forEach((row) => {
      row.onclick = () => {
        const id = Number(row.dataset.id);
        const found = activeList.find((it) => it.item_id === id);
        if (!found) return;
        ui.selectedItem = found;
        const lv = Number(found.level);
        if (lv >= 15) {
          ui.targetLevel = 15;
          ui.protectFrom = "";
        } else {
          ui.targetLevel = lv < 7 ? 7 : Math.min(15, lv + 1);
          ui.protectFrom = ui.targetLevel >= 7 && lv < 9 ? "7" : "";
        }
        renderActiveTab();
        if (lv < 9) loadEnhanceMaterials(found.item_id);
      };
    });

    $("enh-target-lvl").onchange = () => {
      const val = Number($("enh-target-lvl").value || 0);
      ui.targetLevel = val;
      if (val >= 7 && ui.protectFrom === "" && (!sel || sel.level < 9)) {
        ui.protectFrom = "7";
        $("enh-protect-from").value = "7";
      }
    };
    $("enh-protect-from").onchange = () => (ui.protectFrom = $("enh-protect-from").value);
    $("enh-loop-count").oninput = () => (ui.loopCount = $("enh-loop-count").value);
    $("enh-mat-from").onchange = () => (ui.materialFrom = $("enh-mat-from").value);
    $("enh-mat-1").onchange = () => (ui.mat1 = $("enh-mat-1").value);
    $("enh-mat-2").onchange = () => (ui.mat2 = $("enh-mat-2").value);
    $("enh-mat-3").onchange = () => (ui.mat3 = $("enh-mat-3").value);

    $("btn-enh-refresh-mats").onclick = () => sel && loadEnhanceMaterials(sel.item_id);
    $("btn-enh-refresh-res").onclick = loadEnhanceResources;
    $("btn-clr-enh").onclick = () =>
      api(`/api/accounts/${encodeURIComponent(state.currentKey)}/logs/clear`, { method: "POST", body: { channel: "enhance" } });
    $("btn-enh-stop").onclick = () =>
      api(`/api/accounts/${encodeURIComponent(state.currentKey)}/enhance/stop`, { method: "POST" });
    $("btn-enh-destroy").onclick = () => openEnhanceDestroyModal(ui);

    $("btn-enh-start").onclick = async () => {
      if (!ui.selectedItem) {
        showToast("Chưa chọn trang bị", "Vui lòng chọn trang bị cần cường hóa.", "warn");
        return;
      }
      try {
        await api(`/api/accounts/${encodeURIComponent(state.currentKey)}/enhance/start`, {
          method: "POST",
          body: {
            equip_type: ui.equipType,
            role: ui.roleTab,
            item_id: ui.selectedItem.item_id,
            item_type_id: ui.selectedItem.item_type_id,
            start_level: ui.selectedItem.level,
            target_level: Number($("enh-target-lvl").value || ui.targetLevel),
            protect_from_level: $("enh-protect-from").value ? Number($("enh-protect-from").value) : null,
            material_from_level: Number($("enh-mat-from").value || 1),
            material_keys: [ui.mat1, ui.mat2, ui.mat3],
            loop_count: Number($("enh-loop-count").value || 1),
          },
        });
      } catch (e) {
        showToast("Không thể bắt đầu cường hóa", e.message, "error");
      }
    };

    updateEnhanceAuxDom(snap.aux);
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
    const actTh = isEnemy ? "" : "<th>Lệnh đánh</th>";
    return `<table><thead><tr><th>Ô</th><th>Tướng</th><th>Quân</th><th>SK</th><th>Trận hình</th><th>Trạng thái</th>${actTh}<th>Mục tiêu</th></tr></thead>
      <tbody>${troops.map((t) => {
      const cls = isEnemy ? (t.is_boss ? "row-boss" : "") : `bt-our-row row-clickable ${state.selectedBattleOurPos === t.position ? "selected" : ""}`;
      const actTd = isEnemy ? "" : `<td>${esc(t.attack_action_name || "-")}</td>`;
      return `<tr class="${cls}" data-pos="${t.position}">
          <td>${t.position}</td><td>${esc(t.general_name)} ${t.is_boss ? "👑" : ""}</td><td>${t.soldiers}/${t.initial_soldiers}</td>
          <td>${t.morale}</td><td>${esc(t.formation_name)}</td><td>${esc(t.status_text)}</td>${actTd}<td>${t.target_id || "Tùy chọn"}</td>
        </tr>`;
    }).join("")}</tbody></table>`;
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

  function openInternalLogModal() {
    const snap = state.snapshot;
    const lines = [...(snap.logs.building || []), ...(snap.logs.logistics || [])].slice(-500);
    openModal(
      "📜 Nhật ký Nội Chính & Hậu Cần",
      `<div id="log-modal-box" class="log-box" style="height:60vh;">${esc(lines.join("\n"))}</div>`,
      `<button class="btn-sm" onclick="document.getElementById('modal-backdrop').classList.add('hidden')">Đóng</button>`
    );
    const box = $("log-modal-box");
    if (box) box.scrollTop = box.scrollHeight;
  }

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
         <label><input id="nf-visit" type="checkbox" ${np.telegram_alert_general_visit !== false ? "checked" : ""}/> Báo Danh tướng viếng thăm qua Telegram</label>
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
          telegram_alert_general_visit: $("nf-visit").checked,
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

  let renderTacticianModalBody = null;

  function openTacticianModal() {
    const bases = state.snapshot.roster.bases || [];
    const allGens = state.snapshot.roster.generals || [];
    const selectedTacIds = new Set(allGens.filter((g) => g.role === "vo" && (g.tactician_id || 0) <= 0).map((g) => g.id));
    if (!selectedTacIds.size) allGens.filter((g) => g.role === "vo").forEach((g) => selectedTacIds.add(g.id));
    const initCity = state.selectedOverviewCityId && bases.some((b) => b.id === state.selectedOverviewCityId)
      ? String(state.selectedOverviewCityId)
      : "all";

    openModal(
      "🧠 Thiết Lập Mưu Sĩ Cho Võ Tướng",
      `<div class="form-row">
         <label>Thành / Trại <select id="tac-city">
           <option value="all">🌟 Tất cả các thành</option>
           ${bases.map((b) => `<option value="${b.id}" ${String(b.id) === initCity ? "selected" : ""}>${esc(b.display_name || b.name)}</option>`).join("")}
         </select></label>
         <button id="btn-tac-all" class="btn-sm">☑ Tất cả</button>
         <button id="btn-tac-none" class="btn-sm">☐ Bỏ chọn</button>
         <button id="btn-tac-unassigned" class="btn-sm">✨ Chỉ chưa có MS</button>
         <button id="btn-tac-reload" class="btn-sm">🔄 Làm mới</button>
       </div>
       <div id="tac-summary" style="font-size:12px;color:var(--muted);margin-bottom:6px;"></div>
       <div class="form-row"><label><input id="tac-reassign" type="checkbox"/> Đổi mưu sĩ (tháo Mưu sĩ hiện tại để chia lại; trừ Thái thú / bận)</label></div>
       <div class="table-wrap" style="max-height:260px;">
         <table><thead><tr><th><input id="tac-all" type="checkbox"/></th><th>Võ tướng</th><th>Thành / Trại</th><th>Cấp</th><th>Mưu sĩ hiện tại</th><th>Trạng thái</th></tr></thead>
         <tbody id="tac-tbody"></tbody></table>
       </div>
       <div id="tac-status-lbl" style="font-size:12px;color:var(--accent);margin-top:6px;">${esc(state.snapshot.aux?.tactician_status || "Sẵn sàng")}</div>
       <div id="log-tactician" class="log-box" style="height:120px;margin-top:6px;">${esc((state.snapshot.logs.tactician || []).join("\n"))}</div>`,
      `<button class="btn-success btn-sm tac-run" data-mode="by_level">📈 Theo cấp</button>
       <button class="btn-sm tac-run" data-mode="by_name">🏷️ Theo tên</button>
       <button class="btn-sm tac-run" data-mode="sequential">🔢 Tuần tự</button>
       <button class="btn-warning btn-sm tac-run" data-mode="remove">🔓 Tháo MS</button>
       <button id="btn-tac-stop" class="btn-danger btn-sm">⏹ Dừng</button>`
    );

    const getVisibleVos = () => {
      const cityVal = $("tac-city")?.value || "all";
      const gens = state.snapshot.roster.generals || [];
      return gens.filter((g) => g.role === "vo" && (cityVal === "all" || String(g.city_id) === cityVal));
    };

    const updateSummary = () => {
      const cityVal = $("tac-city")?.value || "all";
      const gens = state.snapshot.roster.generals || [];
      const vos = getVisibleVos();
      const freeCivs = gens.filter(
        (g) =>
          g.role === "van" &&
          (cityVal === "all" || String(g.city_id) === cityVal) &&
          (g.is_available_tactician ?? (g.status === 0 && !g.is_mayor && !g.is_tactician))
      ).length;
      const selVisible = vos.filter((g) => selectedTacIds.has(g.id)).length;
      const sumEl = $("tac-summary");
      if (sumEl) {
        sumEl.textContent = `Võ tướng hiển thị: ${vos.length} • Đang chọn: ${selVisible} (Tổng: ${selectedTacIds.size}) • Văn quan sẵn sàng làm Mưu sĩ: ${freeCivs}`;
      }
      const allChk = $("tac-all");
      if (allChk) allChk.checked = vos.length > 0 && selVisible === vos.length;
    };

    renderTacticianModalBody = () => {
      const tbody = $("tac-tbody");
      if (!tbody) return;
      const curBases = state.snapshot.roster.bases || [];
      const vos = getVisibleVos();
      tbody.innerHTML = vos
        .map((g) => {
          const bname = curBases.find((b) => b.id === g.city_id)?.name || g.city_id;
          const chk = selectedTacIds.has(g.id) ? "checked" : "";
          return `<tr><td><input type="checkbox" class="tac-chk" data-gid="${g.id}" ${chk}/></td><td>${esc(g.name)}</td><td>${esc(bname)}</td><td>${g.level}</td><td>${esc(g.tactician_name || "-")}</td><td>${esc(g.status_text || "-")}</td></tr>`;
        })
        .join("");
      tbody.querySelectorAll(".tac-chk").forEach((c) => {
        c.onchange = () => {
          const gid = Number(c.dataset.gid);
          if (c.checked) selectedTacIds.add(gid);
          else selectedTacIds.delete(gid);
          updateSummary();
        };
      });
      updateSummary();
    };

    $("tac-city").onchange = renderTacticianModalBody;
    $("tac-all").onchange = () => {
      const checked = $("tac-all").checked;
      getVisibleVos().forEach((g) => (checked ? selectedTacIds.add(g.id) : selectedTacIds.delete(g.id)));
      renderTacticianModalBody();
    };
    $("btn-tac-all").onclick = () => {
      getVisibleVos().forEach((g) => selectedTacIds.add(g.id));
      renderTacticianModalBody();
    };
    $("btn-tac-none").onclick = () => {
      getVisibleVos().forEach((g) => selectedTacIds.delete(g.id));
      renderTacticianModalBody();
    };
    $("btn-tac-unassigned").onclick = () => {
      getVisibleVos().forEach((g) => ((g.tactician_id || 0) <= 0 ? selectedTacIds.add(g.id) : selectedTacIds.delete(g.id)));
      renderTacticianModalBody();
    };
    $("btn-tac-reload").onclick = () => {
      api(`/api/accounts/${encodeURIComponent(state.currentKey)}/roster/reload`, { method: "POST" })
        .then(() => showToast("Làm mới", "Đã đồng bộ danh sách tướng & Mưu sĩ."))
        .catch((e) => showToast("Lỗi", e.message, "error"));
    };
    document.querySelectorAll(".tac-run").forEach((b) => (b.onclick = () => {
      const ids = [...selectedTacIds];
      api(`/api/accounts/${encodeURIComponent(state.currentKey)}/tactician/run`, {
        method: "POST", body: { mode: b.dataset.mode, general_ids: ids, reassign: $("tac-reassign").checked },
      }).then(() => showToast("Mưu sĩ", "Đang xử lý trong nền...")).catch((e) => showToast("Lỗi", e.message, "error"));
    }));
    $("btn-tac-stop").onclick = () => api(`/api/accounts/${encodeURIComponent(state.currentKey)}/tactician/stop`, { method: "POST" });

    renderTacticianModalBody();
  }

  let renderEquipModalBody = null;
  let renderArmamentModalBody = null;
  let renderRenameModalBody = null;
  let renderAddPointsModalBody = null;
  let renderTrainingModalBody = null;
  let renderTrainingModalSlots = null;

  async function openEquipModal() {
    const bases = state.snapshot.roster.bases || [];
    const selectedIds = new Set();
    let inv = null;
    try { inv = (await api(`/api/accounts/${encodeURIComponent(state.currentKey)}/equip/inventory`)).inventory; } catch { }
    const initCity = state.selectedOverviewCityId && bases.some((b) => b.id === state.selectedOverviewCityId) ? String(state.selectedOverviewCityId) : "all";

    openModal(
      "🛡️ Tự Động Trang Bị Quan Văn & Võ Tướng",
      `<div class="form-row">
         <label>Thành / Trại <select id="eq-city"><option value="all">🌟 Tất cả các thành</option>${bases.map((b) => `<option value="${b.id}" ${String(b.id) === initCity ? "selected" : ""}>${esc(b.display_name || b.name)}</option>`).join("")}</select></label>
         <label>Phân hệ <select id="eq-role"><option value="all">Tất cả (Võ & Văn)</option><option value="vo">Võ tướng</option><option value="van">Văn quan</option></select></label>
         <button id="btn-eq-reload" class="btn-sm" style="margin-left:auto;">🔄 Tải kho & trang bị</button>
       </div>
       <div class="form-row">
         <button id="btn-eq-all" class="btn-sm">☑ Tất cả</button>
         <button id="btn-eq-none" class="btn-sm">☐ Bỏ chọn</button>
         <button id="btn-eq-vo" class="btn-sm">⚔️ Chọn Võ</button>
         <button id="btn-eq-van" class="btn-sm">📜 Chọn Văn</button>
         <button id="btn-eq-miss" class="btn-sm">✨ Thiếu đồ</button>
       </div>
       <div id="eq-summary" style="font-size:12px;color:var(--muted);margin-bottom:6px;"></div>
       <div class="form-row"><label><input id="eq-reassign" type="checkbox"/> Đổi trang bị (tháo toàn bộ đồ của các tướng đã chọn về kho để chia lại từ đầu theo cấp Cao → Thấp)</label></div>
       <div class="table-wrap" style="max-height:260px;">
         <table><thead><tr><th><input id="eq-all" type="checkbox"/></th><th>Tên tướng</th><th>Chức vụ</th><th>Thành / Trại</th><th>Cấp</th><th>Mũ</th><th>Vũ khí</th><th>Giáp</th><th>Thú cưỡi</th><th>Trạng thái</th></tr></thead>
         <tbody id="eq-tbody"></tbody></table>
       </div>
       <div id="eq-status-lbl" style="font-size:12px;color:var(--accent);margin-top:6px;">${esc(state.snapshot.aux?.equip_status || "Sẵn sàng")}</div>
       <div id="log-equip" class="log-box" style="height:120px;margin-top:6px;">${esc((state.snapshot.logs.equip || []).join("\n"))}</div>`,
      `<button id="btn-eq-assign" class="btn-success btn-sm">🛡️ Tự Động Trang Bị (Cao → Thấp)</button>
       <button id="btn-eq-remove" class="btn-warning btn-sm">🔓 Tháo Trang Bị</button>
       <button id="btn-eq-stop" class="btn-danger btn-sm">⏹ Dừng</button>`
    );

    const visibleGens = () => {
      const c = $("eq-city")?.value || "all";
      const r = $("eq-role")?.value || "all";
      const seen = new Set();
      const cur = (state.snapshot.roster.generals || []).filter(
        (g) => !seen.has(g.id) && seen.add(g.id) && (g.role === "vo" || g.role === "van") && (c === "all" || String(g.city_id) === c) && (r === "all" || g.role === r)
      );
      const tier = (g) => (g.role === "van" ? (g.is_mayor ? 0 : g.is_tactician ? 1 : 2) : 2);
      return [...cur].sort((a, b) => tier(a) - tier(b) || b.level - a.level || a.id - b.id);
    };
    const pruneSelectedIds = () => {
      const validIds = new Set(
        (state.snapshot.roster.generals || [])
          .filter((g) => g.role === "vo" || g.role === "van")
          .map((g) => g.id)
      );
      for (const gid of [...selectedIds]) {
        if (!validIds.has(gid)) selectedIds.delete(gid);
      }
    };
    const updateEqSummary = (shown) => {
      pruneSelectedIds();
      const vis = visibleGens();
      const selVis = vis.filter((g) => selectedIds.has(g.id)).length;
      const hiddenSel = Math.max(0, selectedIds.size - selVis);
      const totalPart = hiddenSel > 0
        ? ` (Tổng chọn: ${selectedIds.size}, gồm ${hiddenSel} tướng đang ẩn bởi bộ lọc)`
        : ` (Tổng chọn: ${selectedIds.size})`;
      const invPart = inv
        ? ` • Kho Võ (Mũ/VK/Giáp/Ngựa): ${(inv.free_vo || []).join("/")} • Kho Văn (Mũ/VK/Giáp/Ngựa): ${(inv.free_van || []).join("/")}`
        : " • (Chưa tải kho trang bị)";
      const el = $("eq-summary");
      if (el) el.textContent = `Tướng hiển thị: ${shown ?? vis.length} • Đang chọn: ${selVis}${totalPart}${invPart}`;
      const chkAll = $("eq-all");
      if (chkAll) chkAll.checked = vis.length > 0 && selVis === vis.length;
    };

    renderEquipModalBody = () => {
      const tbody = $("eq-tbody");
      if (!tbody) return;
      const curBases = state.snapshot.roster.bases || [];
      const rows = visibleGens();
      tbody.innerHTML = rows.map((g) => {
        const bname = curBases.find((b) => b.id === g.city_id)?.name || g.city_id;
        const eq = inv?.equipped_by_general?.[String(g.id)] || {};
        const roleTxt = g.is_mayor ? "Thái thú" : (g.role === "van" ? "Văn quan" : "Võ tướng");
        return `<tr><td><input type="checkbox" class="eq-chk" data-gid="${g.id}" ${selectedIds.has(g.id) ? "checked" : ""}/></td><td>${esc(g.name)}</td><td>${esc(roleTxt)}</td><td>${esc(bname)}</td><td>${g.level}</td><td>${esc(eq["1"] || "-")}</td><td>${esc(eq["2"] || "-")}</td><td>${esc(eq["3"] || "-")}</td><td>${esc(eq["4"] || "-")}</td><td>${esc(g.status_text || "-")}</td></tr>`;
      }).join("");
      tbody.querySelectorAll(".eq-chk").forEach((c) => (c.onchange = () => {
        const gid = Number(c.dataset.gid);
        if (c.checked) selectedIds.add(gid); else selectedIds.delete(gid);
        updateEqSummary(rows.length);
      }));
      updateEqSummary(rows.length);
    };

    $("eq-city").onchange = renderEquipModalBody;
    $("eq-role").onchange = renderEquipModalBody;
    $("eq-all").onchange = () => { const ch = $("eq-all").checked; visibleGens().forEach((g) => (ch ? selectedIds.add(g.id) : selectedIds.delete(g.id))); renderEquipModalBody(); };
    $("btn-eq-all").onclick = () => { visibleGens().forEach((g) => selectedIds.add(g.id)); renderEquipModalBody(); };
    $("btn-eq-none").onclick = () => { selectedIds.clear(); renderEquipModalBody(); };
    $("btn-eq-vo").onclick = () => { visibleGens().forEach((g) => (g.role === "vo" ? selectedIds.add(g.id) : selectedIds.delete(g.id))); renderEquipModalBody(); };
    $("btn-eq-van").onclick = () => { visibleGens().forEach((g) => (g.role === "van" ? selectedIds.add(g.id) : selectedIds.delete(g.id))); renderEquipModalBody(); };
    $("btn-eq-miss").onclick = () => {
      visibleGens().forEach((g) => {
        const eq = inv?.equipped_by_general?.[String(g.id)] || {};
        const miss = ["1", "2", "3", "4"].some((s) => !eq[s]);
        if (miss) selectedIds.add(g.id); else selectedIds.delete(g.id);
      });
      renderEquipModalBody();
    };
    $("btn-eq-reload").onclick = async () => {
      try {
        await api(`/api/accounts/${encodeURIComponent(state.currentKey)}/roster/reload`, { method: "POST" });
        inv = (await api(`/api/accounts/${encodeURIComponent(state.currentKey)}/equip/inventory`)).inventory;
        renderEquipModalBody();
        showToast("Làm mới", "Đã tải lại kho & trang bị.");
      } catch (e) { showToast("Lỗi", e.message, "error"); }
    };
    const submitEquip = (mode, toastMsg) => {
      pruneSelectedIds();
      const ids = [...selectedIds];
      if (!ids.length) {
        showToast("Trang bị", "Vui lòng chọn ít nhất 1 Quan văn hoặc Võ tướng.", "warn");
        return;
      }
      const visIds = new Set(visibleGens().map((g) => g.id));
      const hiddenCount = ids.filter((id) => !visIds.has(id)).length;
      if (hiddenCount > 0) {
        const actionLabel = mode === "unequip" ? "tháo trang bị" : "tự động trang bị";
        if (!confirm(`Đang chọn tổng cộng ${ids.length} tướng (trong đó có ${hiddenCount} tướng đang ẩn bởi bộ lọc Thành/Phân hệ).\nTiếp tục ${actionLabel} cho tất cả ${ids.length} tướng?`)) {
          return;
        }
      }
      api(`/api/accounts/${encodeURIComponent(state.currentKey)}/equip/run`, {
        method: "POST",
        body: { mode, general_ids: ids, reassign: mode === "assign" ? $("eq-reassign").checked : false },
      })
        .then(() => showToast("Trang bị", toastMsg))
        .catch((e) => showToast("Lỗi", e.message, "error"));
    };
    $("btn-eq-assign").onclick = () => submitEquip("assign", "Đang xử lý trong nền...");
    $("btn-eq-remove").onclick = () => submitEquip("unequip", "Đang tháo trang bị...");
    $("btn-eq-stop").onclick = () => api(`/api/accounts/${encodeURIComponent(state.currentKey)}/equip/stop`, { method: "POST" });
    renderEquipModalBody();
  }

  async function openArmamentModal() {
    const bases = state.snapshot.roster.bases || [];
    const scopesMeta = state.meta?.armament_scopes || [
      { id: "infantry", name: "Bộ binh" },
      { id: "cavalry", name: "Kỵ binh" },
      { id: "bowman", name: "Cung binh" },
      { id: "mangonel", name: "Xe ném đá" },
    ];
    const voList = () => {
      const seen = new Set();
      return (state.snapshot.roster.generals || []).filter((g) => g.role === "vo" && !seen.has(g.id) && seen.add(g.id))
        .sort((a, b) => b.level - a.level || a.id - b.id);
    };
    const initVos = voList();
    let snaps = {};
    try { snaps = (await api(`/api/accounts/${encodeURIComponent(state.currentKey)}/armament/snapshots`)).snapshots || {}; } catch { }
    const selectedIds = new Set();

    openModal(
      "⚔️ Đồng Bộ Quân Giới Võ Tướng",
      `<div class="card" style="padding:10px;margin-bottom:8px;">
         <div class="form-row">
           <label>Võ tướng mẫu <select id="arm-tpl">${initVos.map((g) => `<option value="${g.id}">${esc(g.name)} (Cấp ${g.level}) - ${esc(bases.find((b) => b.id === g.city_id)?.name || g.city_id)} #${g.id}</option>`).join("")}</select></label>
           <button id="btn-arm-reload" class="btn-sm" style="margin-left:auto;">🔄 Tải lại</button>
         </div>
         <div id="arm-tpl-preview" style="font-size:12px;color:var(--accent);margin-bottom:6px;"></div>
         <div class="form-row" style="margin-bottom:0;">
           <strong style="font-size:12px;">Phạm vi:</strong>
           ${scopesMeta.map((s) => `<label style="font-size:12.5px;"><input type="checkbox" class="arm-scope" value="${s.id}" checked/> ${esc(s.name)}</label>`).join("")}
           <label style="font-size:12.5px;"><input id="arm-form" type="checkbox"/> Trận hình</label>
         </div>
       </div>
       <div class="form-row">
         <label>Thành / Trại <select id="arm-city"><option value="all">🌟 Tất cả các thành</option>${bases.map((b) => `<option value="${b.id}">${esc(b.display_name || b.name)}</option>`).join("")}</select></label>
         <button id="btn-arm-all" class="btn-sm">☑ Tất cả</button>
         <button id="btn-arm-none" class="btn-sm">☐ Bỏ chọn</button>
         <button id="btn-arm-mismatch" class="btn-sm">✨ Chưa khớp mẫu</button>
       </div>
       <div id="arm-summary" style="font-size:12px;color:var(--muted);margin-bottom:6px;"></div>
       <div class="table-wrap" style="max-height:240px;">
         <table><thead><tr><th><input id="arm-all-chk" type="checkbox"/></th><th>Võ tướng</th><th>Thành / Trại</th><th>Bộ binh</th><th>Kỵ binh</th><th>Cung binh</th><th>Xe ném đá</th><th>Trận</th><th>Trạng thái</th></tr></thead>
         <tbody id="arm-tbody"></tbody></table>
       </div>
       <div id="arm-status-lbl" style="font-size:12px;color:var(--accent);margin-top:6px;">${esc(state.snapshot.aux?.armament_status || "Sẵn sàng")}</div>
       <div id="log-armament" class="log-box" style="height:110px;margin-top:6px;">${esc((state.snapshot.logs.armament || []).join("\n"))}</div>`,
      `<button id="btn-arm-run" class="btn-success btn-sm">🔄 Đồng Bộ Quân Giới</button>
       <button id="btn-arm-stop" class="btn-danger btn-sm">⏹ Dừng</button>`
    );

    const activeScopes = () => [...document.querySelectorAll(".arm-scope:checked")].map((c) => c.value);
    const isMatch = (gid) => {
      const tid = Number($("arm-tpl")?.value || 0);
      const cur = snaps[String(gid)];
      const tpl = snaps[String(tid)];
      if (!cur || !tpl) return null;
      for (const s of activeScopes()) {
        if (JSON.stringify(cur.eids?.[s] || []) !== JSON.stringify(tpl.eids?.[s] || [])) return false;
      }
      if ($("arm-form")?.checked && cur.battle_array !== tpl.battle_array) return false;
      return true;
    };
    const visibleVos = () => {
      const c = $("arm-city")?.value || "all";
      return voList().filter((g) => c === "all" || String(g.city_id) === c);
    };

    renderArmamentModalBody = () => {
      const tid = Number($("arm-tpl")?.value || 0);
      const tplSnap = snaps[String(tid)];
      const prev = $("arm-tpl-preview");
      if (prev) prev.textContent = tplSnap ? tplSnap.description : "Chưa tải cấu hình tướng mẫu.";
      const curBases = state.snapshot.roster.bases || [];
      const rows = visibleVos();
      const tbody = $("arm-tbody");
      if (!tbody) return;
      tbody.innerHTML = rows.map((g) => {
        const s = snaps[String(g.id)];
        const bname = curBases.find((b) => b.id === g.city_id)?.name || g.city_id;
        const m = isMatch(g.id);
        const st = g.id === tid ? "Tướng mẫu" : (g.status !== 0 ? g.status_text : (m === null ? "-" : (m ? "✅ Khớp" : "⚠️ Lệch")));
        return `<tr><td><input type="checkbox" class="arm-chk" data-gid="${g.id}" ${selectedIds.has(g.id) ? "checked" : ""}/></td><td>${esc(g.name)}</td><td>${esc(bname)}</td><td>${esc(s?.labels?.infantry || "-")}</td><td>${esc(s?.labels?.cavalry || "-")}</td><td>${esc(s?.labels?.bowman || "-")}</td><td>${esc(s?.labels?.mangonel || "-")}</td><td>${s?.battle_array ?? "-"}</td><td>${esc(st)}</td></tr>`;
      }).join("");
      tbody.querySelectorAll(".arm-chk").forEach((c) => (c.onchange = () => {
        const gid = Number(c.dataset.gid);
        if (c.checked) selectedIds.add(gid); else selectedIds.delete(gid);
        const sum = $("arm-summary");
        if (sum) sum.textContent = `Võ tướng hiển thị: ${rows.length} • Đang chọn: ${selectedIds.size}`;
      }));
      const sum = $("arm-summary");
      if (sum) sum.textContent = `Võ tướng hiển thị: ${rows.length} • Đang chọn: ${selectedIds.size}`;
    };

    $("arm-tpl").onchange = renderArmamentModalBody;
    $("arm-city").onchange = renderArmamentModalBody;
    $("arm-form").onchange = renderArmamentModalBody;
    document.querySelectorAll(".arm-scope").forEach((c) => (c.onchange = renderArmamentModalBody));
    $("arm-all-chk").onchange = () => { const ch = $("arm-all-chk").checked; const tid = Number($("arm-tpl").value); visibleVos().forEach((g) => (ch && g.id !== tid ? selectedIds.add(g.id) : selectedIds.delete(g.id))); renderArmamentModalBody(); };
    $("btn-arm-all").onclick = () => { const tid = Number($("arm-tpl").value); visibleVos().forEach((g) => { if (g.id !== tid) selectedIds.add(g.id); }); renderArmamentModalBody(); };
    $("btn-arm-none").onclick = () => { visibleVos().forEach((g) => selectedIds.delete(g.id)); renderArmamentModalBody(); };
    $("btn-arm-mismatch").onclick = () => { const tid = Number($("arm-tpl").value); visibleVos().forEach((g) => { if (g.id !== tid && isMatch(g.id) === false) selectedIds.add(g.id); else selectedIds.delete(g.id); }); renderArmamentModalBody(); };
    $("btn-arm-reload").onclick = async () => {
      try {
        await api(`/api/accounts/${encodeURIComponent(state.currentKey)}/roster/reload`, { method: "POST" });
        snaps = (await api(`/api/accounts/${encodeURIComponent(state.currentKey)}/armament/snapshots`)).snapshots || {};
        renderArmamentModalBody();
        showToast("Làm mới", "Đã tải lại cấu hình Quân Giới.");
      } catch (e) { showToast("Lỗi", e.message, "error"); }
    };
    $("btn-arm-run").onclick = () => api(`/api/accounts/${encodeURIComponent(state.currentKey)}/armament/run`, {
      method: "POST",
      body: { template_id: Number($("arm-tpl").value), general_ids: [...selectedIds], scopes: activeScopes(), sync_formation: $("arm-form").checked },
    }).then(() => showToast("Quân Giới", "Đang đồng bộ trong nền...")).catch((e) => showToast("Lỗi", e.message, "error"));
    $("btn-arm-stop").onclick = () => api(`/api/accounts/${encodeURIComponent(state.currentKey)}/armament/stop`, { method: "POST" });
    renderArmamentModalBody();
  }

  function openRenameModal() {
    const bases = state.snapshot.roster.bases || [];
    const maxW = state.meta?.rename_max_width || 17;
    const blockedStatus = state.meta?.rename_status_blocked || 35;
    const selectedIds = new Set();
    const initCity = state.selectedOverviewCityId && bases.some((b) => b.id === state.selectedOverviewCityId) ? String(state.selectedOverviewCityId) : "all";
    const nameWidth = (s) => [...String(s || "")].reduce((acc, ch) => acc + (ch.charCodeAt(0) < 128 ? 1 : 2), 0);

    openModal(
      "✏️ Đổi Tên Văn Quan & Võ Tướng",
      `<div class="card" style="padding:10px;margin-bottom:8px;">
         <div class="form-row">
           <label>Tiền tố / Tên mới <input id="ren-prefix" type="text" value="DT_" style="width:150px;"/></label>
           <label><input id="ren-numbered" type="checkbox" checked/> Đánh số thứ tự (01, 02...)</label>
           <label>Bắt đầu từ <input id="ren-start" type="number" min="1" value="1" style="width:65px;"/></label>
           <span id="ren-example" style="font-size:12px;color:var(--accent);font-weight:700;"></span>
         </div>
         <div style="font-size:11.5px;color:var(--muted);">Nhập tiền tố (vd 'DT_') để đổi thành DT_01, DT_02... theo thứ tự bảng. Bỏ tick 'Đánh số thứ tự' để đặt cùng 1 tên cố định. Giới hạn ≤ ${maxW} đơn vị (chữ Hán/có dấu tính 2).</div>
       </div>
       <div class="form-row">
         <label>Thành / Trại <select id="ren-city"><option value="all">🌟 Tất cả các thành</option>${bases.map((b) => `<option value="${b.id}" ${String(b.id) === initCity ? "selected" : ""}>${esc(b.display_name || b.name)}</option>`).join("")}</select></label>
         <label>Phân hệ <select id="ren-role"><option value="all">Tất cả (Võ & Văn)</option><option value="vo">Võ tướng</option><option value="van">Văn quan</option></select></label>
         <button id="btn-ren-all" class="btn-sm">☑ Tất cả</button>
         <button id="btn-ren-none" class="btn-sm">☐ Bỏ chọn</button>
         <button id="btn-ren-vo" class="btn-sm">⚔️ Chọn Võ</button>
         <button id="btn-ren-van" class="btn-sm">📜 Chọn Văn</button>
         <button id="btn-ren-reload" class="btn-sm" style="margin-left:auto;">🔄 Làm mới</button>
       </div>
       <div id="ren-summary" style="font-size:12px;color:var(--muted);margin-bottom:6px;"></div>
       <div class="table-wrap" style="max-height:240px;">
         <table><thead><tr><th><input id="ren-all-chk" type="checkbox"/></th><th>Tên hiện tại</th><th>Chức vụ</th><th>Thành / Trại</th><th>Cấp</th><th>Tên mới (Xem trước)</th><th>Trạng thái</th></tr></thead>
         <tbody id="ren-tbody"></tbody></table>
       </div>
       <div id="ren-status-lbl" style="font-size:12px;color:var(--accent);margin-top:6px;">${esc(state.snapshot.aux?.rename_status || "Sẵn sàng")}</div>
       <div id="log-rename" class="log-box" style="height:105px;margin-top:6px;">${esc((state.snapshot.logs.rename || []).join("\n"))}</div>`,
      `<button id="btn-ren-run" class="btn-success btn-sm">✏️ Thực Hiện Đổi Tên</button>
       <button id="btn-ren-stop" class="btn-danger btn-sm">⏹ Dừng</button>`
    );

    const visibleGens = () => {
      const c = $("ren-city")?.value || "all";
      const r = $("ren-role")?.value || "all";
      const seen = new Set();
      return (state.snapshot.roster.generals || []).filter(
        (g) => !seen.has(g.id) && seen.add(g.id) && (c === "all" || String(g.city_id) === c) && (r === "all" || g.role === r)
      );
    };
    const buildPlanMap = (rows) => {
      const raw = ($("ren-prefix")?.value || "").trim().replace(/'/g, "’").replace(/"/g, "’");
      const numbered = !!$("ren-numbered")?.checked;
      const start = Math.max(1, Number($("ren-start")?.value || 1));
      const chosen = rows.filter((g) => selectedIds.has(g.id));
      const pad = Math.max(2, String(start + Math.max(0, chosen.length - 1)).length);
      const map = {};
      chosen.forEach((g, idx) => {
        if (!raw) map[g.id] = "";
        else if (!numbered) map[g.id] = raw;
        else map[g.id] = `${raw}${String(start + idx).padStart(pad, "0")}`;
      });
      return { raw, numbered, start, map };
    };

    renderRenameModalBody = () => {
      const rows = visibleGens();
      const { raw, numbered, start, map } = buildPlanMap(rows);
      if ($("ren-start")) $("ren-start").disabled = !numbered;
      const ex = numbered && raw ? `${raw}${String(start).padStart(2, "0")}` : (raw || "-");
      if ($("ren-example")) $("ren-example").textContent = `Ví dụ: ${ex}`;
      const curBases = state.snapshot.roster.bases || [];
      const tbody = $("ren-tbody");
      if (!tbody) return;
      tbody.innerHTML = rows.map((g) => {
        const bname = curBases.find((b) => b.id === g.city_id)?.name || g.city_id;
        const roleTxt = g.is_mayor ? "Thái thú" : (g.role === "van" ? "Văn quan" : "Võ tướng");
        const prevName = selectedIds.has(g.id) ? (map[g.id] || "(trống)") : "-";
        const w = selectedIds.has(g.id) ? nameWidth(map[g.id] || "") : 0;
        const bad = selectedIds.has(g.id) && (!map[g.id] || w > maxW);
        const st = g.status === blockedStatus ? `⚠️ Bị chặn (${g.status})` : (bad ? `❌ Quá dài (${w}/${maxW})` : (g.status_text || "Rảnh"));
        return `<tr style="${bad ? "color:#f87171;" : ""}"><td><input type="checkbox" class="ren-chk" data-gid="${g.id}" ${selectedIds.has(g.id) ? "checked" : ""}/></td><td>${esc(g.name)}</td><td>${esc(roleTxt)}</td><td>${esc(bname)}</td><td>${g.level}</td><td>${esc(prevName)}</td><td>${esc(st)}</td></tr>`;
      }).join("");
      tbody.querySelectorAll(".ren-chk").forEach((c) => (c.onchange = () => {
        const gid = Number(c.dataset.gid);
        if (c.checked) selectedIds.add(gid); else selectedIds.delete(gid);
        renderRenameModalBody();
      }));
      const selVis = rows.filter((g) => selectedIds.has(g.id)).length;
      if ($("ren-summary")) $("ren-summary").textContent = `Tướng hiển thị: ${rows.length} • Đang chọn: ${selVis} (Tổng: ${selectedIds.size})`;
      if ($("ren-all-chk")) $("ren-all-chk").checked = rows.length > 0 && selVis === rows.length;
    };

    $("ren-prefix").oninput = renderRenameModalBody;
    $("ren-numbered").onchange = renderRenameModalBody;
    $("ren-start").oninput = renderRenameModalBody;
    $("ren-city").onchange = renderRenameModalBody;
    $("ren-role").onchange = renderRenameModalBody;
    $("ren-all-chk").onchange = () => { const ch = $("ren-all-chk").checked; visibleGens().forEach((g) => (ch ? selectedIds.add(g.id) : selectedIds.delete(g.id))); renderRenameModalBody(); };
    $("btn-ren-all").onclick = () => { visibleGens().forEach((g) => selectedIds.add(g.id)); renderRenameModalBody(); };
    $("btn-ren-none").onclick = () => { visibleGens().forEach((g) => selectedIds.delete(g.id)); renderRenameModalBody(); };
    $("btn-ren-vo").onclick = () => { visibleGens().forEach((g) => (g.role === "vo" ? selectedIds.add(g.id) : selectedIds.delete(g.id))); renderRenameModalBody(); };
    $("btn-ren-van").onclick = () => { visibleGens().forEach((g) => (g.role === "van" ? selectedIds.add(g.id) : selectedIds.delete(g.id))); renderRenameModalBody(); };
    $("btn-ren-reload").onclick = () => api(`/api/accounts/${encodeURIComponent(state.currentKey)}/roster/reload`, { method: "POST" }).then(() => showToast("Làm mới", "Đã đồng bộ danh sách tướng."));
    $("btn-ren-run").onclick = () => {
      const rows = visibleGens();
      const { map } = buildPlanMap(rows);
      const items = rows.filter((g) => selectedIds.has(g.id)).map((g) => ({ general_id: g.id, new_name: map[g.id] || "" }));
      if (!items.length) return showToast("Đổi tên", "Vui lòng chọn ít nhất 1 tướng.", "warn");
      api(`/api/accounts/${encodeURIComponent(state.currentKey)}/rename/run`, { method: "POST", body: { items } })
        .then(() => showToast("Đổi tên", "Đang thực thi đổi tên trong nền...")).catch((e) => showToast("Lỗi", e.message, "error"));
    };
    $("btn-ren-stop").onclick = () => api(`/api/accounts/${encodeURIComponent(state.currentKey)}/rename/stop`, { method: "POST" });
    renderRenameModalBody();
  }

  function openAddPointsModal() {
    const bases = state.snapshot.roster.bases || [];
    const modes = state.meta?.add_point_modes || [
      { id: "pair_1_3", label: "Cộng 1 & 3 (SM/Mị & TL/Nội)", is_max: false },
      { id: "pair_1_2", label: "Cộng 1 & 2 (SM/Mị & NN/Mưu)", is_max: false },
      { id: "pair_2_3", label: "Cộng 2 & 3 (NN/Mưu & TL/Nội)", is_max: false },
      { id: "max_1", label: "Max 1 (Sức Mạnh / Mị Lực)", is_max: true },
      { id: "max_2", label: "Max 2 (Nhanh Nhẹn / Mưu Trí)", is_max: true },
      { id: "max_3", label: "Max 3 (Thống Lĩnh / Nội Chính)", is_max: true },
    ];
    const minStep = state.meta?.add_points_min_step || 1;
    const maxStep = state.meta?.add_points_max_step || 500;
    const selectedIds = new Set();
    const initCity = state.selectedOverviewCityId && bases.some((b) => b.id === state.selectedOverviewCityId) ? String(state.selectedOverviewCityId) : "all";

    openModal(
      "✨ Cộng Điểm Văn Quan & Võ Tướng",
      `<div class="card" style="padding:10px;margin-bottom:8px;">
         <div class="form-row">
           <label>Loại cộng <select id="ap-mode">${modes.map((m) => `<option value="${esc(m.id)}">${esc(m.label)}</option>`).join("")}</select></label>
           <label><input id="ap-add-all" type="checkbox"/> Cộng hết điểm (+10 → +3 → +1)</label>
           <label>Điểm/lần <input id="ap-points" type="number" min="${minStep}" max="${maxStep}" value="10" style="width:72px;"/></label>
           <label>Số lần mỗi loại <input id="ap-times" type="number" min="1" value="1" style="width:65px;"/></label>
         </div>
         <div id="ap-hint" style="font-size:11.5px;color:var(--accent);"></div>
       </div>
       <div class="form-row">
         <label>Thành / Trại <select id="ap-city"><option value="all">🌟 Tất cả các thành</option>${bases.map((b) => `<option value="${b.id}" ${String(b.id) === initCity ? "selected" : ""}>${esc(b.display_name || b.name)}</option>`).join("")}</select></label>
         <label>Phân hệ <select id="ap-role"><option value="all">Tất cả (Võ & Văn)</option><option value="vo">Võ tướng</option><option value="van">Văn quan</option></select></label>
         <label>Tìm tên <input id="ap-search" type="text" placeholder="Lọc theo tên..." style="width:130px;"/></label>
         <label><input id="ap-only-avail" type="checkbox"/> Chỉ hiện còn điểm &gt; 0</label>
         <button id="btn-ap-reload" class="btn-sm" style="margin-left:auto;">🔄 Làm mới</button>
       </div>
       <div class="form-row">
         <button id="btn-ap-all" class="btn-sm">☑ Tất cả</button>
         <button id="btn-ap-none" class="btn-sm">☐ Bỏ chọn</button>
         <button id="btn-ap-vo" class="btn-sm">⚔️ Chọn Võ</button>
         <button id="btn-ap-van" class="btn-sm">📜 Chọn Văn</button>
         <button id="btn-ap-avail" class="btn-sm">✨ Chọn Còn Điểm</button>
       </div>
       <div id="ap-summary" style="font-size:12px;color:var(--muted);margin-bottom:6px;"></div>
       <div class="table-wrap" style="max-height:240px;">
         <table><thead><tr><th><input id="ap-all-chk" type="checkbox"/></th><th>Tên tướng</th><th>Chức vụ</th><th>Thành / Trại</th><th>Cấp</th><th>SM / Mị</th><th>NN / Mưu</th><th>TL / Nội</th><th>Tiềm năng</th><th>Trạng thái</th></tr></thead>
         <tbody id="ap-tbody"></tbody></table>
       </div>
       <div id="ap-status-lbl" style="font-size:12px;color:var(--accent);margin-top:6px;">${esc(state.snapshot.aux?.add_points_status || "Sẵn sàng")}</div>
       <div id="log-add-points" class="log-box" style="height:105px;margin-top:6px;">${esc((state.snapshot.logs.add_points || []).join("\n"))}</div>`,
      `<button id="btn-ap-run" class="btn-success btn-sm">✨ Thực Hiện Cộng Điểm</button>
       <button id="btn-ap-stop" class="btn-danger btn-sm">⏹ Dừng</button>`
    );

    const isMaxMode = (modeId) => {
      const m = modes.find((x) => x.id === modeId);
      return m ? !!m.is_max : String(modeId || "").startsWith("max_");
    };
    const updateApConfigUi = () => {
      const mode = $("ap-mode")?.value || "pair_1_3";
      const addAll = !!$("ap-add-all")?.checked;
      const isMax = isMaxMode(mode);
      if ($("ap-points")) $("ap-points").disabled = addAll;
      if ($("ap-times")) $("ap-times").disabled = addAll || isMax;
      if ($("ap-hint")) {
        if (addAll) {
          $("ap-hint").textContent = isMax
            ? "Cộng hết điểm: tự động cộng +10 liên tiếp rồi hạ +3 và +1 cho đến khi hết Điểm Tiềm Năng hoặc chạm trần (ret=77)."
            : "Cộng hết điểm theo cặp: cộng xen kẽ 2 chỉ số theo bậc +10 → +3 → +1; nếu 1 chỉ số chạm trần (ret=77) sẽ tiếp tục thử chỉ số kia.";
        } else {
          const pts = Number($("ap-points")?.value || 0);
          const times = Number($("ap-times")?.value || 0);
          if (!Number.isInteger(pts) || pts < minStep || pts > maxStep) {
            $("ap-hint").textContent = `⚠️ Điểm/lần phải là số nguyên từ ${minStep} đến ${maxStep}.`;
          } else if (isMax) {
            $("ap-hint").textContent = `Dự kiến mỗi tướng: lặp +${pts} điểm/lần vào chỉ số đã chọn đến khi không đủ +${pts} hoặc chạm trần.`;
          } else if (!Number.isInteger(times) || times < 1) {
            $("ap-hint").textContent = "⚠️ Số lần mỗi loại phải là số nguyên ≥ 1.";
          } else {
            $("ap-hint").textContent = `Dự kiến mỗi tướng: +${pts} điểm × 2 chỉ số × ${times} lần = tối đa ${pts * 2 * times} điểm.`;
          }
        }
      }
    };

    const visibleGens = () => {
      const c = $("ap-city")?.value || "all";
      const r = $("ap-role")?.value || "all";
      const q = ($("ap-search")?.value || "").trim().toLowerCase();
      const onlyAvail = !!$("ap-only-avail")?.checked;
      const seen = new Set();
      return (state.snapshot.roster.generals || []).filter((g) => {
        if (seen.has(g.id) || !seen.add(g.id)) return false;
        if (c !== "all" && String(g.city_id) !== c) return false;
        if (r !== "all" && g.role !== r) return false;
        if (onlyAvail && Number(g.skill_point || 0) <= 0) return false;
        if (q && !String(g.name || "").toLowerCase().includes(q)) return false;
        return true;
      }).sort((a, b) => (Number(b.skill_point || 0) - Number(a.skill_point || 0)) || (b.level - a.level) || (a.id - b.id));
    };

    renderAddPointsModalBody = () => {
      updateApConfigUi();
      const rows = visibleGens();
      const curBases = state.snapshot.roster.bases || [];
      const tbody = $("ap-tbody");
      if (!tbody) return;
      let totalSp = 0;
      tbody.innerHTML = rows.map((g) => {
        const sp = Number(g.skill_point || 0);
        totalSp += Math.max(0, sp);
        const bname = curBases.find((b) => b.id === g.city_id)?.name || g.city_id;
        const roleTxt = g.is_mayor ? "Thái thú" : (g.role === "van" ? "Văn quan" : "Võ tướng");
        return `<tr><td><input type="checkbox" class="ap-chk" data-gid="${g.id}" ${selectedIds.has(g.id) ? "checked" : ""}/></td><td>${esc(g.name)}</td><td>${esc(roleTxt)}</td><td>${esc(bname)}</td><td>${g.level}</td><td style="text-align:right;">${g.stat1 ?? 0}</td><td style="text-align:right;">${g.stat2 ?? 0}</td><td style="text-align:right;">${g.stat3 ?? 0}</td><td style="text-align:right;font-weight:700;color:${sp > 0 ? "var(--accent)" : "var(--muted)"};">${sp}</td><td>${esc(g.status_text || "Rảnh")}</td></tr>`;
      }).join("");
      tbody.querySelectorAll(".ap-chk").forEach((c) => (c.onchange = () => {
        const gid = Number(c.dataset.gid);
        if (c.checked) selectedIds.add(gid); else selectedIds.delete(gid);
        renderAddPointsModalBody();
      }));
      const selVis = rows.filter((g) => selectedIds.has(g.id)).length;
      if ($("ap-summary")) $("ap-summary").textContent = `Tướng hiển thị: ${rows.length} (Tổng Điểm Tiềm Năng: ${totalSp.toLocaleString()}) • Đang chọn: ${selVis}`;
      if ($("ap-all-chk")) $("ap-all-chk").checked = rows.length > 0 && selVis === rows.length;
    };

    $("ap-mode").onchange = updateApConfigUi;
    $("ap-add-all").onchange = updateApConfigUi;
    $("ap-points").oninput = updateApConfigUi;
    $("ap-times").oninput = updateApConfigUi;
    $("ap-city").onchange = renderAddPointsModalBody;
    $("ap-role").onchange = renderAddPointsModalBody;
    $("ap-search").oninput = renderAddPointsModalBody;
    $("ap-only-avail").onchange = renderAddPointsModalBody;
    $("ap-all-chk").onchange = () => { const ch = $("ap-all-chk").checked; visibleGens().forEach((g) => (ch ? selectedIds.add(g.id) : selectedIds.delete(g.id))); renderAddPointsModalBody(); };
    $("btn-ap-all").onclick = () => { visibleGens().forEach((g) => selectedIds.add(g.id)); renderAddPointsModalBody(); };
    $("btn-ap-none").onclick = () => { visibleGens().forEach((g) => selectedIds.delete(g.id)); renderAddPointsModalBody(); };
    $("btn-ap-vo").onclick = () => { visibleGens().forEach((g) => (g.role === "vo" ? selectedIds.add(g.id) : selectedIds.delete(g.id))); renderAddPointsModalBody(); };
    $("btn-ap-van").onclick = () => { visibleGens().forEach((g) => (g.role === "van" ? selectedIds.add(g.id) : selectedIds.delete(g.id))); renderAddPointsModalBody(); };
    $("btn-ap-avail").onclick = () => { visibleGens().forEach((g) => (Number(g.skill_point || 0) > 0 ? selectedIds.add(g.id) : selectedIds.delete(g.id))); renderAddPointsModalBody(); };
    $("btn-ap-reload").onclick = () => api(`/api/accounts/${encodeURIComponent(state.currentKey)}/roster/reload`, { method: "POST" }).then(() => showToast("Làm mới", "Đã đồng bộ danh sách tướng."));
    $("btn-ap-run").onclick = () => {
      const rows = visibleGens();
      const generalIds = rows.filter((g) => selectedIds.has(g.id)).map((g) => g.id);
      if (!generalIds.length) return showToast("Cộng điểm", "Vui lòng chọn ít nhất 1 tướng.", "warn");
      const mode = $("ap-mode")?.value || "pair_1_3";
      const addAll = !!$("ap-add-all")?.checked;
      const pointsPerAdd = Number($("ap-points")?.value || 10);
      const times = Number($("ap-times")?.value || 1);
      api(`/api/accounts/${encodeURIComponent(state.currentKey)}/add-points/run`, {
        method: "POST",
        body: { general_ids: generalIds, mode, points_per_add: pointsPerAdd, times, add_all: addAll },
      }).then(() => showToast("Cộng điểm", "Đang thực thi cộng điểm tướng trong nền...")).catch((e) => showToast("Lỗi", e.message, "error"));
    };
    $("btn-ap-stop").onclick = () => api(`/api/accounts/${encodeURIComponent(state.currentKey)}/add-points/stop`, { method: "POST" });
    renderAddPointsModalBody();
  }

  function openTrainingModal() {
    const bases = state.snapshot.roster.bases || [];
    const trn = state.snapshot.profile.training || { enabled: false, vo_general_ids: [], van_general_ids: [] };
    state.snapshot.profile.training = {
      enabled: !!trn.enabled,
      vo_general_ids: [...(trn.vo_general_ids || [])],
      van_general_ids: [...(trn.van_general_ids || [])],
    };
    let activeHall = "vo";
    const initCity = state.selectedOverviewCityId && bases.some((b) => b.id === state.selectedOverviewCityId) ? String(state.selectedOverviewCityId) : "all";

    openModal(
      "🎓 Đào Tạo Tướng (Điểm Tướng Đài & Tụ Hiền Lâu)",
      `<div class="form-row">
         <label><input id="trn-enabled" type="checkbox" ${state.snapshot.profile.training.enabled ? "checked" : ""}/> 🔄 Tự động đào tạo hàng ngày (tự lặp lại mỗi 24h khi ô hồi xong)</label>
         <button id="btn-trn-refresh" class="btn-sm" style="margin-left:auto;">🔄 Tải trạng thái</button>
         <button id="btn-trn-run" class="btn-success btn-sm">🎓 Đào tạo ngay</button>
       </div>
       <div class="form-row">
         <button id="btn-trn-hall-vo" class="btn-primary btn-sm">⚔️ Điểm Tướng Đài (Võ tướng)</button>
         <button id="btn-trn-hall-van" class="btn-sm">📜 Tụ Hiền Lâu (Văn quan)</button>
       </div>
       <div id="trn-slots-grid" class="train-slots-grid"></div>
       <div class="card" style="padding:8px 10px;margin-bottom:8px;">
         <div style="font-size:12px;font-weight:700;margin-bottom:4px;">📋 Thứ tự ưu tiên đã chọn (<span id="trn-prio-title">Điểm Tướng Đài</span>):</div>
         <div id="trn-prio-list" class="train-chip-list"></div>
         <div style="font-size:11.5px;color:var(--muted);margin-top:4px;">Ô trống sẽ lấy lần lượt theo thứ tự ưu tiên trên; nếu tướng đạt cấp tối đa hoặc không thể đào tạo, bot tự chuyển sang tướng kế tiếp.</div>
       </div>
       <div class="form-row">
         <label>Thành / Trại <select id="trn-city"><option value="all">🌟 Tất cả căn cứ</option>${bases.map((b) => `<option value="${b.id}" ${String(b.id) === initCity ? "selected" : ""}>${esc(b.display_name || b.name)}</option>`).join("")}</select></label>
         <label>Tìm <input id="trn-search" type="text" placeholder="Tên tướng..." style="width:130px;"/></label>
         <label>Sắp xếp <select id="trn-sort"><option value="level_desc">Cấp Cao → Thấp</option><option value="level_asc">Cấp Thấp → Cao</option></select></label>
         <button id="btn-trn-clear" class="btn-sm" style="margin-left:auto;">☐ Bỏ chọn mục này</button>
       </div>
       <div id="trn-summary" style="font-size:12px;color:var(--muted);margin-bottom:6px;"></div>
       <div class="table-wrap" style="max-height:220px;">
         <table><thead><tr><th>Chọn</th><th>Tên tướng</th><th>Thành / Trại</th><th>Cấp</th><th>Chức vụ</th><th>Trạng thái</th></tr></thead>
         <tbody id="trn-tbody"></tbody></table>
       </div>
       <div id="train-status-lbl" style="font-size:12px;color:var(--accent);margin-top:6px;">${esc(state.snapshot.aux?.training_status || "Sẵn sàng")}</div>
       <div id="log-training" class="log-box" style="height:105px;margin-top:6px;">${esc((state.snapshot.logs.training || []).join("\n"))}</div>`,
      `<button class="btn-sm" onclick="document.getElementById('modal-backdrop').classList.add('hidden')">Đóng</button>`
    );

    const getHallKey = () => (activeHall === "van" ? "van" : "vo");
    const getListField = () => (activeHall === "van" ? "van_general_ids" : "vo_general_ids");
    const getSelectedList = () => {
      const t = state.snapshot.profile.training || {};
      return [...(t[getListField()] || [])];
    };
    const saveTrainingPatch = (patch) => {
      const next = { ...(state.snapshot.profile.training || {}), ...patch };
      state.snapshot.profile.training = next;
      if ($("aux-training")) $("aux-training").checked = !!next.enabled;
      scheduleProfileSave({ training: next });
    };

    const getAllHallGenerals = () => {
      const seen = new Set();
      return (state.snapshot.roster.generals || []).filter(
        (g) => g.role === getHallKey() && !seen.has(g.id) && seen.add(g.id)
      );
    };

    const getActiveTrainingIds = () => {
      const hall = state.snapshot.aux?.training?.[getHallKey()];
      if (!hall || !Array.isArray(hall.slots)) return new Set();
      const elapsed = state.auxSyncedAt ? Math.max(0, Math.floor((Date.now() - state.auxSyncedAt) / 1000)) : 0;
      return new Set(
        hall.slots
          .filter((s) => s.unlocked && Math.max(0, Number(s.remaining_seconds || 0) - elapsed) > 0 && Number(s.hero_id) > 0)
          .map((s) => Number(s.hero_id))
      );
    };

    renderTrainingModalSlots = () => {
      const grid = $("trn-slots-grid");
      if (!grid) return;
      const voCount = (state.snapshot.profile.training?.vo_general_ids || []).length;
      const vanCount = (state.snapshot.profile.training?.van_general_ids || []).length;
      const voSum = getLiveTrainHallSummary("vo");
      const vanSum = getLiveTrainHallSummary("van");
      if ($("btn-trn-hall-vo")) {
        $("btn-trn-hall-vo").className = `${activeHall === "vo" ? "btn-primary" : ""} btn-sm`;
        $("btn-trn-hall-vo").textContent = `⚔️ Điểm Tướng Đài (${voCount})${voSum ? ` • ${voSum.text}` : ""}`;
      }
      if ($("btn-trn-hall-van")) {
        $("btn-trn-hall-van").className = `${activeHall === "van" ? "btn-primary" : ""} btn-sm`;
        $("btn-trn-hall-van").textContent = `📜 Tụ Hiền Lâu (${vanCount})${vanSum ? ` • ${vanSum.text}` : ""}`;
      }
      const hall = state.snapshot.aux?.training?.[getHallKey()];
      if (!hall || !Array.isArray(hall.slots)) {
        grid.innerHTML = Array.from({ length: 5 }, (_, idx) => `<div class="train-slot-card"><strong>Ô ${idx + 1}</strong><span style="color:var(--muted);">Đang tải...</span></div>`).join("");
        return;
      }
      const elapsed = state.auxSyncedAt ? Math.max(0, Math.floor((Date.now() - state.auxSyncedAt) / 1000)) : 0;
      grid.innerHTML = hall.slots.map((s) => {
        if (!s.unlocked) {
          return `<div class="train-slot-card locked"><strong>Ô ${s.pos}</strong><span>🔒 Chưa mở</span></div>`;
        }
        const rem = Math.max(0, Number(s.remaining_seconds || 0) - elapsed);
        if (rem > 0) {
          return `<div class="train-slot-card busy"><strong>Ô ${s.pos}</strong><span>🎓 ${esc(s.hero_name || `#${s.hero_id}`)}</span><span class="train-slot-cd" data-slot-rem="${s.remaining_seconds}" style="color:#93c5fd;">Còn ${fmtSec(rem)}</span></div>`;
        }
        return `<div class="train-slot-card ready"><strong>Ô ${s.pos}</strong><span style="color:#4ade80;">✅ Sẵn sàng</span></div>`;
      }).join("");
    };

    renderTrainingModalBody = () => {
      renderTrainingModalSlots();
      const prioTitle = $("trn-prio-title");
      if (prioTitle) prioTitle.textContent = activeHall === "van" ? "Tụ Hiền Lâu (Văn quan)" : "Điểm Tướng Đài (Võ tướng)";
      const allGens = getAllHallGenerals();
      const genById = new Map(allGens.map((g) => [g.id, g]));
      const selList = getSelectedList();
      const selSet = new Set(selList);

      const prioBox = $("trn-prio-list");
      if (prioBox) {
        if (!selList.length) {
          prioBox.innerHTML = '<span style="font-size:12px;color:var(--muted);">Chưa chọn tướng nào cho phân hệ này.</span>';
        } else {
          prioBox.innerHTML = selList.map((gid, idx) => {
            const g = genById.get(gid);
            const label = g ? `${g.name} (Lv.${g.level})` : `#${gid}`;
            return `<span class="train-chip">${idx + 1}. ${esc(label)} <button class="trn-mv-up" data-idx="${idx}" ${idx === 0 ? "disabled" : ""}>↑</button><button class="trn-mv-dn" data-idx="${idx}" ${idx === selList.length - 1 ? "disabled" : ""}>↓</button><button class="trn-rm" data-gid="${gid}">✕</button></span>`;
          }).join("");
          prioBox.querySelectorAll(".trn-mv-up").forEach((b) => (b.onclick = () => {
            const i = Number(b.dataset.idx);
            if (i > 0) {
              const next = [...selList];
              [next[i - 1], next[i]] = [next[i], next[i - 1]];
              saveTrainingPatch({ [getListField()]: next });
              renderTrainingModalBody();
            }
          }));
          prioBox.querySelectorAll(".trn-mv-dn").forEach((b) => (b.onclick = () => {
            const i = Number(b.dataset.idx);
            if (i < selList.length - 1) {
              const next = [...selList];
              [next[i + 1], next[i]] = [next[i], next[i + 1]];
              saveTrainingPatch({ [getListField()]: next });
              renderTrainingModalBody();
            }
          }));
          prioBox.querySelectorAll(".trn-rm").forEach((b) => (b.onclick = () => {
            const gid = Number(b.dataset.gid);
            saveTrainingPatch({ [getListField()]: selList.filter((x) => x !== gid) });
            renderTrainingModalBody();
          }));
        }
      }

      const c = $("trn-city")?.value || "all";
      const q = ($("trn-search")?.value || "").trim().toLowerCase();
      const sortMode = $("trn-sort")?.value || "level_desc";
      const rows = allGens
        .filter((g) => (c === "all" || String(g.city_id) === c) && (!q || String(g.name || "").toLowerCase().includes(q)))
        .sort((a, b) => (sortMode === "level_asc" ? a.level - b.level : b.level - a.level) || a.id - b.id);

      const curBases = state.snapshot.roster.bases || [];
      const activeIds = getActiveTrainingIds();
      const tbody = $("trn-tbody");
      if (tbody) {
        tbody.innerHTML = rows.map((g) => {
          const bname = curBases.find((b) => b.id === g.city_id)?.name || g.city_id;
          const roleTxt = g.is_mayor ? "Thái thú" : (g.role === "van" ? "Văn quan" : "Võ tướng");
          const stTxt = activeIds.has(g.id) ? "🎓 Đang đào tạo" : (g.status_text || "Rảnh rỗi");
          return `<tr><td><input type="checkbox" class="trn-chk" data-gid="${g.id}" ${selSet.has(g.id) ? "checked" : ""}/></td><td>${esc(g.name)}</td><td>${esc(bname)}</td><td>${g.level}</td><td>${esc(roleTxt)}</td><td>${esc(stTxt)}</td></tr>`;
        }).join("");
        tbody.querySelectorAll(".trn-chk").forEach((chk) => (chk.onchange = () => {
          const gid = Number(chk.dataset.gid);
          const cur = getSelectedList();
          const next = chk.checked ? (cur.includes(gid) ? cur : [...cur, gid]) : cur.filter((x) => x !== gid);
          saveTrainingPatch({ [getListField()]: next });
          renderTrainingModalBody();
        }));
      }
      if ($("trn-summary")) {
        $("trn-summary").textContent = `Hiển thị: ${rows.length} tướng • Đã chọn ưu tiên: ${selList.length} tướng`;
      }
    };

    const loadTrainingStatus = async () => {
      try {
        const res = await api(`/api/accounts/${encodeURIComponent(state.currentKey)}/training/status`);
        if (res.training) {
          state.snapshot.aux = state.snapshot.aux || {};
          state.snapshot.aux.training = res.training;
          state.auxSyncedAt = Date.now();
          renderAuxDomOnly();
          renderTrainingModalBody();
        }
      } catch (e) {
        showToast("Lỗi tải trạng thái đào tạo", e.message, "error");
      }
    };

    $("trn-enabled").onchange = () => saveTrainingPatch({ enabled: $("trn-enabled").checked });
    $("btn-trn-hall-vo").onclick = () => { activeHall = "vo"; renderTrainingModalBody(); };
    $("btn-trn-hall-van").onclick = () => { activeHall = "van"; renderTrainingModalBody(); };
    $("trn-city").onchange = renderTrainingModalBody;
    $("trn-search").oninput = renderTrainingModalBody;
    $("trn-sort").onchange = renderTrainingModalBody;
    $("btn-trn-clear").onclick = () => { saveTrainingPatch({ [getListField()]: [] }); renderTrainingModalBody(); };
    $("btn-trn-refresh").onclick = loadTrainingStatus;
    $("btn-trn-run").onclick = async () => {
      try {
        await saveProfileImmediate({ training: state.snapshot.profile.training });
        await api(`/api/accounts/${encodeURIComponent(state.currentKey)}/training/run`, { method: "POST", body: {} });
        showToast("Đào Tạo Tướng", "Đang kiểm tra & thực thi đào tạo...");
      } catch (e) { showToast("Lỗi Đào Tạo Tướng", e.message, "error"); }
    };

    renderTrainingModalBody();
    loadTrainingStatus();
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
    $("btn-relogin").onclick = async () => {
      if (!state.currentKey) return;
      try {
        const r = await api(`/api/accounts/${encodeURIComponent(state.currentKey)}/relogin`, { method: "POST" });
        showToast("Re-Login", r.ok ? "Đã đăng nhập lại thành công." : "Đăng nhập lại thất bại.", r.ok ? "info" : "error");
      } catch (e) { showToast("Re-Login", e.message, "error"); }
    };
    $("hdr-profile-save").onclick = async () => {
      if (!state.currentKey || !state.snapshot) return;
      try {
        await saveProfileImmediate(state.snapshot.profile);
        showToast("Đã lưu", "Hồ sơ cấu hình đã được lưu.");
      } catch (e) { showToast("Lỗi lưu hồ sơ", e.message, "error"); }
    };
    $("gl-server").oninput = updateServerHint;
    $("gl-proxy").onchange = autoSplitProxyInput;
    $("gl-proxy").onpaste = () => setTimeout(autoSplitProxyInput, 0);
    document.addEventListener("click", hideAccountContextMenu);
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
