// The staff page's hosting-panel controls (tools/staff_apex.py answers them): the Settings and Mods tabs, and on the
// Players and Server tabs the bans by address, backups from the page, the page's own schedules and the world download.
// The same rules as panel.js: everything from the server goes in with textContent, no style attributes, no forms, no
// confirm() or alert(). The panel itself checks every role; GET /api/me only greys out or hides what a login can't use.
"use strict";

(() => {
  const RANK = { moderator: 0, admin: 1, owner: 2 };
  const HELPER_POLL_MS = 3_000;
  const HELPER_POLL_MAX = 100;     // about 5 minutes
  const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
  const $ = (id) => document.getElementById(id);
  let role = "moderator";
  const can = (need) => RANK[role] >= RANK[need];

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function button(label, className, onClick, need) {
    const node = el("button", `btn ${className || ""}`.trim(), label);
    node.type = "button";
    node.addEventListener("click", onClick);
    if (need && !can(need)) {
      node.disabled = true;
      node.title = `Needs an ${need} login.`;
    }
    return node;
  }

  function input(type, attrs) {
    const node = el("input");
    node.type = type;
    node.autocomplete = "off";
    for (const [key, value] of Object.entries(attrs || {})) {
      if (key === "label") node.setAttribute("aria-label", value);
      else node[key] = value;
    }
    return node;
  }

  function select(options, value, label) {
    const node = el("select");
    for (const [v, text] of options) {
      const option = el("option", "", text);
      option.value = String(v);
      node.appendChild(option);
    }
    if (value !== undefined && value !== null) node.value = String(value);
    if (label) node.setAttribute("aria-label", label);
    return node;
  }

  async function api(method, url, body) {
    const headers = { "X-Monkey-Staff": "1" };
    let payload;
    if (body !== undefined) {
      headers["Content-Type"] = "application/json";
      payload = JSON.stringify(body);
    }
    let answer;
    try {
      answer = await fetch(url, { method, headers, body: payload, cache: "no-store" });
    } catch {
      throw new Error("The page can't reach the server's machine right now.");
    }
    let data = null;
    try {
      data = await answer.json();
    } catch {
      data = null;
    }
    if (answer.status === 401) throw new Error("Your login has run out. Reload this page to log in again.");
    if (!answer.ok || (data && data.ok === false)) {
      throw new Error((data && data.error) || `That didn't work (error ${answer.status}).`);
    }
    return data || {};
  }

  function say(id, text) {
    const node = $(id);
    if (!node) return;
    node.hidden = !text;
    node.textContent = text ? (text.message || String(text)) : "";
  }

  // An in-page confirm step in the box `id`: the message, an optional field the answer must be typed into, a button.
  function confirmIn(id, message, yes, onYes, typed) {
    const box = $(id);
    const close = () => {
      box.hidden = true;
      box.replaceChildren();
    };
    const parts = [el("p", "", message)];
    let field = null;
    if (typed) {
      field = input("text", { label: typed.label, placeholder: typed.placeholder, maxLength: 64, spellcheck: false });
      const row = el("div", "typed");
      row.append(field);
      parts.push(row);
    }
    const row = el("div", "actions");
    row.append(button(yes, "primary", () => {
      const value = field ? field.value.trim() : "";
      close();
      onYes(value);
    }), button("Cancel", "", close));
    parts.push(row);
    box.replaceChildren(...parts);
    box.hidden = false;
    (field || row.firstElementChild).focus();
  }

  const CLOCK = new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
  function when(value) {
    if (value === null || value === undefined || value === "") return "never";
    const ms = typeof value === "number" ? value * 1000 : Date.parse(value);
    return Number.isNaN(ms) ? String(value) : CLOCK.format(new Date(ms));
  }

  function size(bytes) {
    if (typeof bytes !== "number") return "";
    if (bytes < 1048576) return `${(bytes / 1024).toFixed(0)} KB`;
    if (bytes < 1073741824) return `${(bytes / 1048576).toFixed(1)} MB`;
    return `${(bytes / 1073741824).toFixed(2)} GB`;
  }

  function entry(what, meta, ...buttons) {
    const li = el("li");
    const span = el("span", "what", what);
    if (meta) span.appendChild(el("span", "meta", ` ${meta}`));
    li.append(span, ...buttons);
    return li;
  }

  const emptyRow = (text) => el("li", "empty-row", text);

  // ---------------------------------------------------------------- settings (server.properties)

  const settings = { data: null };

  function control(field) {
    const editable = field.editable && can("admin");
    let node;
    if (field.type === "bool") {
      node = input("checkbox", { checked: field.value === "true" });
    } else if (field.type === "int") {
      node = input("number", { min: field.min, max: field.max, step: 1, value: field.value });
    } else if (field.type === "enum") {
      const choices = field.choices.includes(field.value) ? field.choices : [field.value, ...field.choices];
      node = select(choices.map((c) => [c, c]), field.value);
    } else {
      node = input("text", { value: field.value, maxLength: field.max || 500, spellcheck: false });
    }
    node.id = `set-${field.key}`;
    node.disabled = !editable;
    return node;
  }

  function current(field, node) {
    if (field.type === "bool") return node.checked ? "true" : "false";
    if (field.type === "int") return node.value.trim();
    return node.value;
  }

  function renderSettings(data) {
    settings.data = data;
    const boxes = [];
    for (const group of data.groups || []) {
      const fields = (data.fields || []).filter((f) => f.group === group);
      if (!fields.length) continue;
      const box = el("section", "box");
      box.appendChild(el("h3", "", group));
      const list = el("div", "fields");
      for (const field of fields) {
        const row = el("div", "field");
        const label = el("label", "", field.key);
        label.htmlFor = `set-${field.key}`;
        const holder = el("div", "control");
        const node = control(field);
        node.dataset.key = field.key;
        const mark = () => row.classList.toggle("changed", current(field, node) !== field.value);
        node.addEventListener("input", mark);
        node.addEventListener("change", mark);
        holder.appendChild(node);
        const about = field.locked ? `${field.about} Locked: ${field.locked}` : field.about;
        row.append(label, holder, el("p", "about", about));
        list.appendChild(row);
      }
      box.appendChild(list);
      boxes.push(box);
    }
    if ((data.other || []).length) {
      const box = el("section", "box");
      box.appendChild(el("h3", "", "Other keys (read-only here)"));
      const ul = el("ul", "entries");
      for (const row of data.other) ul.appendChild(entry(`${row.key} = ${row.value}`, `(${row.locked})`));
      box.appendChild(ul);
      boxes.push(box);
    }
    $("settings-fields").replaceChildren(...boxes);
    $("settings-save").disabled = !can("admin");
  }

  async function loadSettings() {
    if (!can("admin")) {
      say("settings-error", "Settings need an admin login.");
      $("settings-save").disabled = true;
      return;
    }
    try {
      renderSettings(await api("GET", "/api/settings"));
      say("settings-error", null);
    } catch (error) {
      say("settings-error", error);
    }
    loadRules();
  }

  async function saveSettings() {
    const data = settings.data;
    if (!data) return;
    const values = {};
    for (const field of data.fields) {
      const node = $(`set-${field.key}`);
      if (!node || !field.editable) continue;
      const value = current(field, node);
      if (value !== field.value) values[field.key] = field.type === "int" ? Number(value) : value;
    }
    say("settings-note", null);
    say("settings-error", null);
    if (!Object.keys(values).length) {
      say("settings-note", "Nothing changed.");
      return;
    }
    try {
      const done = await api("PUT", "/api/settings", { values, mtime: data.mtime });
      say("settings-note", done.changed.length
        ? `Saved: ${done.changed.join(", ")}. Most settings take effect when the server restarts (Server tab). The old file is in Files, history.`
        : "Nothing changed.");
      renderSettings(await api("GET", "/api/settings"));
    } catch (error) {
      say("settings-error", error);
    }
  }

  // ---------------------------------------------------------------- game rules

  async function setRule(rule, value) {
    say("settings-error", null);
    try {
      const done = await api("POST", "/api/gamerules", { name: rule.name, value });
      say("settings-note", `${rule.name} is ${done.value} now.`);
    } catch (error) {
      say("settings-error", error);
      loadRules();
    }
  }

  async function loadRules() {
    const box = $("gamerules");
    try {
      const data = await api("GET", "/api/gamerules");
      const rows = [];
      for (const rule of data.rules || []) {
        const row = el("div", rule.missing ? "field missing" : "field");
        const label = el("label", "", rule.name);
        label.htmlFor = `rule-${rule.name}`;
        const holder = el("div", "control");
        let node;
        if (rule.type === "bool") {
          node = input("checkbox", { checked: rule.value === true });
          node.addEventListener("change", () => setRule(rule, node.checked));
          holder.appendChild(node);
        } else {
          node = input("number", { min: rule.min, max: rule.max, step: 1, value: rule.value ?? "" });
          holder.append(node, button("Set", "", () => setRule(rule, Number(node.value)), "admin"));
        }
        node.id = `rule-${rule.name}`;
        node.disabled = rule.missing || !can("admin");
        row.append(label, holder, el("p", "about", rule.missing ? `${rule.about} Not on this server.` : rule.about));
        rows.push(row);
      }
      $("gamerules-list").replaceChildren(...rows);
      say("gamerules-error", null);
    } catch (error) {
      $("gamerules-list").replaceChildren();
      say("gamerules-error", error);
    }
    box.hidden = false;
  }

  // ---------------------------------------------------------------- mods

  const mods = { rows: [] };

  function renderMods() {
    const typed = $("mods-search").value.trim().toLowerCase();
    const rows = mods.rows.filter((m) => !typed || [m.name, m.id, m.file, m.description].join(" ").toLowerCase().includes(typed));
    const items = rows.map((m) => {
      const li = el("li");
      const what = el("span", "what", m.error ? m.file : `${m.name} ${m.version || ""}`.trim());
      const side = { client: "client only", server: "server only", both: "client and server" }[m.environment] || "";
      what.appendChild(el("span", "meta", m.error ? ` (${m.error})` : ` (${[m.id, side, size(m.size)].filter(Boolean).join(", ")})`));
      li.appendChild(what);
      if (m.description) li.appendChild(el("span", "meta", m.description));
      return li;
    });
    $("mods-list").replaceChildren(...(items.length ? items : [emptyRow(typed ? "No mod matches." : "No mods found.")]));
    $("mods-count").textContent = `${rows.length} of ${mods.rows.length} mods`;
  }

  async function loadMods() {
    try {
      const data = await api("GET", "/api/mods");
      mods.rows = data.mods || [];
      renderMods();
      say("mods-error", null);
    } catch (error) {
      say("mods-error", error);
    }
  }

  // ---------------------------------------------------------------- bans by address (Players tab)

  async function loadIpBans() {
    if (!can("admin")) {
      $("ipbans").hidden = true;
      return;
    }
    $("ipbans").hidden = false;
    try {
      const data = await api("GET", "/api/ip-bans");
      const ips = data.ips;
      const items = (ips || []).map((b) => entry(b.ip, b.reason ? `(${b.reason})` : "",
        button("Pardon", "", () => ipPardon(b.ip), "admin")));
      $("ipbans-list").replaceChildren(...(items.length ? items : [emptyRow(ips ? "No address is banned." : "banned-ips.json can't be read.")]));
    } catch (error) {
      say("ipbans-error", error);
    }
  }

  async function ipPardon(ip) {
    say("ipbans-error", null);
    try {
      const done = await api("POST", "/api/ip-pardon", { ip });
      say("ipbans-note", done.said ? `Done. The server said: ${done.said}` : "Done.");
    } catch (error) {
      say("ipbans-error", error);
    }
    loadIpBans();
  }

  function ipBan() {
    const target = $("ipban-target").value.trim();
    const reason = $("ipban-reason").value.replace(/\s+/g, " ").trim();
    if (!target) {
      say("ipbans-error", "Type an address, or the name of a player who is online.");
      return;
    }
    say("ipbans-error", null);
    confirmIn("ipbans-confirm", `Ban the address ${target}? Everyone joining from it is refused, even under another name, until it is pardoned.`,
      "Yes, ban the address", async () => {
        try {
          const done = await api("POST", "/api/ip-ban", { target, reason });
          $("ipban-target").value = "";
          $("ipban-reason").value = "";
          say("ipbans-note", done.said ? `Done. The server said: ${done.said}` : "Done.");
        } catch (error) {
          say("ipbans-error", error);
        }
        loadIpBans();
      });
  }

  // ---------------------------------------------------------------- backups through the helper (Server tab)

  const helper = { installed: false, waiting: null };

  async function waitFor(request) {
    for (let i = 0; i < HELPER_POLL_MAX; i += 1) {
      await new Promise((resolve) => { setTimeout(resolve, HELPER_POLL_MS); });
      const data = await api("GET", "/api/helper");
      renderJobs(data);
      const job = (data.jobs || []).find((j) => j.id === request);
      if (job && job.state !== "running") return job;
    }
    return null;
  }

  function renderJobs(data) {
    const items = (data.jobs || []).slice(0, 5).map((j) => entry(`${j.action}: ${j.state}`, `${when(j.time)}. ${j.message}`));
    $("helper-jobs").replaceChildren(...(items.length ? items : [emptyRow("Nothing asked of the helper yet.")]));
  }

  async function loadHelper() {
    try {
      const data = await api("GET", "/api/helper");
      helper.installed = data.installed;
      $("helper-missing").hidden = data.installed;
      $("helper-body").hidden = !data.installed;
      renderJobs(data);
      if (data.installed && can("admin")) loadSnapshots();
    } catch (error) {
      say("helper-error", error);
    }
  }

  async function ask(url, body, words) {
    say("helper-error", null);
    say("helper-note", null);
    try {
      const done = await api("POST", url, body || {});
      say("helper-note", `${words} The helper picks it up in a few seconds.`);
      const job = await waitFor(done.request);
      if (job) say("helper-note", job.message);
      return job;
    } catch (error) {
      say("helper-error", error);
      return null;
    }
  }

  async function loadSnapshots() {
    try {
      const data = await api("GET", "/api/snapshots");
      const items = (data.snapshots || []).slice(0, 60).map((s) => {
        const restore = button("Restore", "", () => restoreStep(s), "owner");
        if (!can("owner")) restore.hidden = true;
        return entry(`${s.short_id} ${when(s.time)}`, [s.tags.join(" "), size(s.size)].filter(Boolean).join(", "), restore);
      });
      $("snapshots").replaceChildren(...(items.length ? items : [emptyRow(data.time ? "No snapshots." : "Not listed yet: press List the snapshots.")]));
      $("snapshots-time").textContent = data.time ? `Listed ${when(data.time)}.` : "";
    } catch (error) {
      say("helper-error", error);
    }
  }

  function restoreStep(snapshot) {
    confirmIn("helper-confirm",
      `Put the world back as it was at ${when(snapshot.time)}? Players are warned, the server stops for a few minutes, and everything built since then is gone from the live world (the current world is kept in backups/ on the machine). Type ${snapshot.short_id} to confirm.`,
      "Restore this snapshot", async (typed) => {
        if (typed !== snapshot.short_id) {
          say("helper-error", `Not restored: type ${snapshot.short_id} exactly.`);
          return;
        }
        await ask("/api/world-restore", { snapshot: snapshot.id, confirm: typed }, "Restore asked for.");
      }, { label: "Snapshot short ID", placeholder: snapshot.short_id });
  }

  // ---------------------------------------------------------------- the world download (Server tab)

  async function download() {
    say("world-error", null);
    try {
      const done = await api("POST", "/api/world-download", {});
      const a = el("a");
      a.href = done.url;
      a.download = "";
      document.body.appendChild(a);
      a.click();
      a.remove();
      say("world-note", "The download started. Saving is off while it runs and comes back on when it ends.");
    } catch (error) {
      say("world-error", error);
    }
  }

  // ---------------------------------------------------------------- schedules (Server tab)

  function describe(s) {
    const words = { command: `runs ${s.command}`, restart: "restarts the server (warnings at 5 min, 1 min, 10 s)", backup: "backs up off-site" }[s.kind];
    return `${words}, ${s.describe}`;
  }

  async function loadSchedules() {
    if (!can("admin")) {
      $("schedules-box").hidden = true;
      return;
    }
    $("schedules-box").hidden = false;
    try {
      const data = await api("GET", "/api/schedules");
      $("schedules-zone").textContent = `Times are the machine's: ${data.timezone}. It is ${data.now} there now.`;
      const items = (data.schedules || []).map((s) => entry(`${s.name}${s.enabled ? "" : " (off)"}`,
        `${describe(s)}. Next: ${s.next || "-"}. Last: ${s.last_run ? `${when(s.last_run)}, ${s.last_result || ""}` : "never"}.`,
        button(s.enabled ? "Turn off" : "Turn on", "", () => editSchedule({ id: s.id, enabled: !s.enabled }), "admin"),
        button("Delete", "", () => confirmIn("schedules-confirm", `Delete the schedule ${s.name}?`, "Yes, delete",
          () => scheduleCall("POST", "/api/schedule-delete", { id: s.id }, "Deleted.")), "admin")));
      $("schedules-list").replaceChildren(...(items.length ? items : [emptyRow("No schedules made here yet.")]));
      $("sched-kind").querySelector('option[value="backup"]').disabled = !data.helper;
    } catch (error) {
      say("schedules-error", error);
    }
  }

  async function scheduleCall(method, url, body, words) {
    say("schedules-error", null);
    try {
      await api(method, url, body);
      say("schedules-note", words);
    } catch (error) {
      say("schedules-error", error);
    }
    loadSchedules();
  }

  const editSchedule = (body) => scheduleCall("PUT", "/api/schedules", body, body.enabled ? "Turned on." : "Turned off.");

  function scheduleForm() {
    const kind = $("sched-kind").value;
    const type = $("sched-when").value;
    $("sched-command").hidden = kind !== "command";
    $("sched-time").hidden = type === "interval";
    $("sched-day").hidden = type !== "weekly";
    $("sched-minutes").hidden = type !== "interval";
  }

  function addSchedule() {
    const kind = $("sched-kind").value;
    const type = $("sched-when").value;
    const at = { type };
    if (type === "interval") at.minutes = Number($("sched-minutes").value);
    else at.time = $("sched-time").value;
    if (type === "weekly") at.day = Number($("sched-day").value);
    const body = { name: $("sched-name").value.trim(), kind, when: at, enabled: true };
    if (kind === "command") body.command = $("sched-command").value.trim();
    scheduleCall("POST", "/api/schedules", body, "Schedule added.");
  }

  // ---------------------------------------------------------------- wiring

  function build() {
    // Settings tab
    $("settings-save").addEventListener("click", saveSettings);
    $("settings-reload").addEventListener("click", loadSettings);
    // Mods tab
    $("mods-search").addEventListener("input", renderMods);
    // Players tab
    $("ipban-go").addEventListener("click", ipBan);
    // Server tab
    const backupNow = $("backup-now");
    backupNow.addEventListener("click", () => ask("/api/backup-now", undefined, "Backup asked for.").then(loadHelper));
    $("snapshots-list").addEventListener("click", () => ask("/api/snapshots", undefined, "Snapshot list asked for.").then(loadSnapshots));
    $("world-download").addEventListener("click", () => confirmIn("world-confirm",
      "Download the whole world as a zip? It is a few GB. Saving stops while it streams (the game keeps running) and comes back on when it ends.",
      "Yes, download", download));
    $("sched-day").replaceChildren(...DAYS.map((d, i) => { const o = el("option", "", d); o.value = String(i); return o; }));
    $("sched-kind").addEventListener("change", scheduleForm);
    $("sched-when").addEventListener("change", scheduleForm);
    $("sched-add").addEventListener("click", addSchedule);
    scheduleForm();
    // What this login can't do is greyed out or, for owners only, hidden.
    for (const node of document.querySelectorAll("[data-need]")) {
      if (can(node.dataset.need)) continue;
      if (node.dataset.need === "owner") node.hidden = true;
      else node.disabled = true;
    }
  }

  const VIEWS = {
    settings: loadSettings,
    mods: loadMods,
    players: loadIpBans,
    server: () => {
      loadHelper();
      loadSchedules();
    },
  };

  function show() {
    const view = VIEWS[location.hash.slice(1)];
    if (view) view();
  }

  async function start() {
    try {
      const me = await api("GET", "/api/me");
      if (me.role in RANK) role = me.role;
    } catch {
      role = "moderator";   // the safe guess: the panel decides anyway
    }
    build();
    window.addEventListener("hashchange", show);
    show();
  }

  start();
})();
