// The staff page's hosting-panel controls (tools/staff_apex.py answers them): the Settings and Mods tabs, and on the
// Players and Server tabs the bans by address, backups from the page, the page's own schedules, the world download,
// and (tools/staff_host.py) the mod manager, the version switch, the world reset and upload, and the SFTP card.
// The same rules as panel.js: everything from the server goes in with textContent, no style attributes, no forms, no
// confirm() or alert(). The panel itself checks every role; GET /api/me only greys out or hides what a login can't use.
"use strict";

(() => {
  const RANK = { moderator: 0, admin: 1, owner: 2 };
  const HELPER_POLL_MS = 3_000;
  const HELPER_POLL_MAX = 100;     // about 5 minutes
  const HELPER_POLL_TRIES = 3;     // a failed poll is tried this many times before it counts as an error
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

  // A File as the body goes as application/octet-stream (the jar and world uploads); anything else as JSON.
  async function api(method, url, body) {
    const headers = { "X-Monkey-Staff": "1" };
    let payload;
    if (body instanceof Blob) {
      headers["Content-Type"] = "application/octet-stream";
      payload = body;
    } else if (body !== undefined) {
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

  // A list row with a title, a line of facts, an optional description and its buttons on the right.
  function item(title, facts, about, buttons) {
    const li = el("li", "item");
    const main = el("div", "item-main");
    const what = el("span", "what", title);
    if (facts) what.appendChild(el("span", "meta", ` ${facts}`));
    main.appendChild(what);
    if (about) main.appendChild(el("span", "about", about));
    li.appendChild(main);
    if (buttons && buttons.length) {
      const side = el("div", "item-actions");
      side.append(...buttons);
      li.appendChild(side);
    }
    return li;
  }

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
      node = input("text", { value: field.value, maxLength: field.max || 500, spellcheck: false, className: "mono" });
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

  // How many settings differ from the file, on the bar with the Save button.
  function countChanges() {
    const n = $("settings-fields").querySelectorAll(".field.changed").length;
    $("settings-count").textContent = n ? `${n} unsaved change${n === 1 ? "" : "s"}.` : "No unsaved changes.";
    $("settings-bar").classList.toggle("dirty", n > 0);
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
        const node = control(field);
        const row = el("div", node.type === "text" ? "field long" : "field");
        const label = el("label", "", field.key);
        label.htmlFor = `set-${field.key}`;
        const holder = el("div", "control");
        node.dataset.key = field.key;
        const mark = () => {
          row.classList.toggle("changed", current(field, node) !== field.value);
          countChanges();
        };
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
      box.appendChild(el("h3", "", "Locked here, and other keys"));
      const ul = el("ul", "other");
      for (const row of data.other) {
        const li = el("li");
        li.append(el("code", "", `${row.key}=${row.value}`), el("span", "", row.locked));
        ul.appendChild(li);
      }
      box.appendChild(ul);
      boxes.push(box);
    }
    $("settings-fields").replaceChildren(...boxes);
    $("settings-save").disabled = !can("admin");
    countChanges();
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
      if (value === field.value) continue;
      if (field.type === "int") {
        if (value === "") continue; // a cleared box is not a 0
        const n = Number(value);
        if (Number.isNaN(n)) {
          say("settings-note", null);
          say("settings-error", `${field.key}: type a number.`);
          return;
        }
        values[field.key] = n;
      } else {
        values[field.key] = value;
      }
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
          holder.append(node, button("Set", "", () => {
            const text = node.value.trim();
            const n = Number(text);
            if (text === "" || Number.isNaN(n)) {
              say("settings-error", "Type a number.");
              return;
            }
            setRule(rule, n);
          }, "admin"));
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

  // The typed step for a change to one jar: the jar's file name is the word to type.
  function modStep(message, yes, file, onYes) {
    confirmIn("mods-confirm", `${message} Type ${file} to confirm.`, yes, (typed) => {
      if (typed !== file) {
        say("mods-error", `Nothing changed: type ${file} exactly.`);
        return;
      }
      onYes(typed);
    }, { label: "Jar file name", placeholder: file });
  }

  const PINNED_NOTE = " It is one of this release's pinned mods, so the server puts the pinned jar back when it next starts.";

  function modDone(text, done) {
    say("mods-note", `${text}${done.kept_in ? ` The old file is kept in ${done.kept_in}.` : ""}${done.pinned ? PINNED_NOTE : ""} Restart the server (Server tab) for it to take effect.`);
    loadMods();
  }

  async function modCall(url, body, words) {
    say("mods-error", null);
    say("mods-note", null);
    try {
      modDone(words, await api("POST", url, body));
    } catch (error) {
      say("mods-error", error);
    }
  }

  function modButtons(m) {
    const on = m.enabled !== false;
    return [
      button(on ? "Turn off" : "Turn on", "", () => modStep(on
        ? `Turn off ${m.file}? It is renamed to .jar.disabled and the server stops loading it at the next restart.`
        : `Turn ${m.file} back on?`, on ? "Turn off" : "Turn on", m.file,
      (typed) => modCall("/api/mod-toggle", { file: m.file, enabled: !on, confirm: typed }, on ? "Turned off." : "Turned on.")), "admin"),
      button("Remove", "", () => modStep(`Remove ${m.file}? It is moved to mods-removed/ on the machine, never deleted.`,
        "Remove", m.file, (typed) => modCall("/api/mod-remove", { file: m.file, confirm: typed }, "Removed.")), "admin"),
    ];
  }

  function renderMods() {
    const typed = $("mods-search").value.trim().toLowerCase();
    const rows = mods.rows.filter((m) => !typed || [m.name, m.id, m.file, m.description].join(" ").toLowerCase().includes(typed));
    const items = rows.map((m) => {
      const side = { client: "client only", server: "server only", both: "client and server" }[m.environment] || "";
      const flags = [m.enabled === false ? "off" : "", m.pinned ? "pinned" : ""].filter(Boolean);
      return item(m.error ? m.file : `${m.name} ${m.version || ""}`.trim(),
        m.error ? `(${m.error})` : `(${[m.id, side, size(m.size), ...flags].filter(Boolean).join(", ")})`,
        m.description, can("admin") && m.file ? modButtons(m) : []);
    });
    $("mods-list").replaceChildren(...(items.length ? items : [emptyRow(typed ? "No mod matches." : "No mods found.")]));
    $("mods-count").textContent = typed ? `(${rows.length} of ${mods.rows.length})` : `(${mods.rows.length})`;
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

  function uploadJar() {
    const file = $("mod-file").files[0];
    say("mods-error", null);
    say("mods-note", null);
    if (!file) {
      say("mods-error", "Pick a .jar file first.");
      return;
    }
    if (!/^[A-Za-z0-9][A-Za-z0-9._+-]{0,123}\.jar$/.test(file.name)) {
      say("mods-error", "A jar's name has letters, digits, . _ + - only and ends in .jar: rename the file first.");
      return;
    }
    modStep(`Put ${file.name} (${size(file.size)}) in the server's mods folder? A jar with the same name or the same mod id is moved to mods-removed/ first.`,
      "Upload the mod", file.name, async (typed) => {
        try {
          const done = await api("POST", `/api/mod-upload?${new URLSearchParams({ name: file.name, confirm: typed })}`, file);
          $("mod-file").value = "";
          modDone(`Installed ${done.name} ${done.version || ""}.`, done);
        } catch (error) {
          say("mods-error", error);
        }
      });
  }

  async function searchModrinth() {
    const q = $("modrinth-q").value.trim();
    say("mods-error", null);
    if (!q) return;
    $("modrinth-list").replaceChildren(emptyRow("Searching..."));
    try {
      const data = await api("GET", `/api/modrinth?${new URLSearchParams({ q })}`);
      $("modrinth-version").textContent = `Fabric mods for ${data.game_version} that run on a server.`;
      const items = (data.hits || []).map((h) => item(`${h.title} (${h.slug})`,
        [h.downloads !== null ? `${h.downloads} downloads` : "", `players need it: ${h.client_side}`].filter(Boolean).join(", "),
        h.description,
        [button("Install", "", () => modStep(`Install ${h.title} from Modrinth? The newest release for this game version is downloaded and its sha512 checked.`,
          "Install", h.slug, (typed) => installModrinth(h.slug, typed)), "admin")]));
      $("modrinth-list").replaceChildren(...(items.length ? items : [emptyRow("No Fabric mod for this version matches.")]));
    } catch (error) {
      $("modrinth-list").replaceChildren();
      say("mods-error", error);
    }
  }

  async function installModrinth(project, typed) {
    say("mods-note", "Downloading from Modrinth...");
    try {
      const done = await api("POST", "/api/modrinth-install", { project, confirm: typed });
      const needs = (done.requires || []).length ? ` It needs these mods too (Modrinth IDs): ${done.requires.join(", ")}.` : "";
      modDone(`Installed ${done.name} ${done.version || ""}.${needs}`, done);
    } catch (error) {
      say("mods-note", null);
      say("mods-error", error);
    }
  }

  function installPack() {
    const file = $("mrpack-file").files[0];
    say("mods-error", null);
    say("mods-note", null);
    if (!file) {
      say("mods-error", "Pick a .mrpack file first.");
      return;
    }
    if (!/^[A-Za-z0-9][A-Za-z0-9 ._+()-]{0,123}\.mrpack$/.test(file.name)) {
      say("mods-error", "A modpack's name has letters, digits, spaces and . _ + ( ) - only and ends in .mrpack: rename the file first.");
      return;
    }
    modStep(`Install the server mods from ${file.name} (${size(file.size)})? A jar with the same name or mod id is moved to mods-removed/ first.`,
      "Install the pack", file.name, async (typed) => {
        say("mods-note", "Downloading and checking every mod... keep this page open.");
        $("mrpack-go").disabled = true;
        try {
          const done = await api("POST", `/api/modpack?${new URLSearchParams({ name: file.name, confirm: typed })}`, file);
          $("mrpack-file").value = "";
          const skipped = done.skipped ? ` ${done.skipped} client-only mod(s) skipped.` : "";
          modDone(`Installed ${done.installed.length} mod(s) from ${done.pack}.${skipped}`, {});
        } catch (error) {
          say("mods-note", null);
          say("mods-error", error);
        }
        $("mrpack-go").disabled = false;
      });
  }

  // ---------------------------------------------------------------- data packs (Mods tab)

  function packStep(message, yes, name, onYes) {
    confirmIn("packs-confirm", `${message} Type ${name} to confirm.`, yes, (typed) => {
      if (typed !== name) {
        say("packs-error", `Nothing changed: type ${name} exactly.`);
        return;
      }
      onYes(typed);
    }, { label: "Data pack name", placeholder: name });
  }

  async function packCall(url, body, words) {
    say("packs-error", null);
    say("packs-note", null);
    try {
      const done = await api("POST", url, body);
      say("packs-note", `${words}${done.kept_in ? ` The old copy is kept in ${done.kept_in}.` : ""}`);
    } catch (error) {
      say("packs-error", error);
    }
    loadPacks();
  }

  function packButtons(p, running) {
    const out = [];
    if (running && p.enabled !== null) {
      out.push(button(p.enabled ? "Turn off" : "Turn on", "", () => packCall("/api/datapack-toggle",
        { name: p.name, enabled: !p.enabled }, p.enabled ? "Turned off." : "Turned on."), "admin"));
    }
    if (!p.release) {
      out.push(button("Remove", "", () => packStep(`Remove ${p.name}? It is moved to staff-removed/ on the machine, never deleted. Its changes to the world stay until the server reloads.`,
        "Remove", p.name, (typed) => packCall("/api/datapack-remove", { name: p.name, confirm: typed }, "Removed. Press Reload to unload it.")), "admin"));
    }
    return out;
  }

  async function loadPacks() {
    try {
      const data = await api("GET", "/api/datapacks");
      const packs = data.packs || [];
      const items = packs.map((p) => {
        const state = p.enabled === null ? "" : p.enabled ? "on" : "off";
        const facts = [p.kind === "folder" ? "folder" : size(p.size), state, p.release ? "release" : ""].filter(Boolean);
        return item(p.name, `(${facts.join(", ")})`, p.description, can("admin") ? packButtons(p, data.running) : []);
      });
      $("packs-list").replaceChildren(...(items.length ? items : [emptyRow("No data packs in this world.")]));
      $("packs-count").textContent = `(${packs.length})`;
      $("packs-reload").disabled = !data.running || !can("admin");
      $("packs-reload").title = data.running ? "" : "The server isn't running.";
      // Its own line, so a reload after an action never wipes that action's error.
      say("packs-running", data.running ? null : "The server isn't running, so on and off can't be read or changed. Uploads and removals still work.");
    } catch (error) {
      $("packs-list").replaceChildren();
      if ($("packs-error").hidden) say("packs-error", error);
    }
  }

  function uploadPack() {
    const file = $("pack-file").files[0];
    say("packs-error", null);
    say("packs-note", null);
    if (!file) {
      say("packs-error", "Pick a data pack .zip first.");
      return;
    }
    if (!/^[A-Za-z0-9][A-Za-z0-9._+-]{0,123}\.zip$/.test(file.name)) {
      say("packs-error", "A data pack's name has letters, digits, . _ + - only and ends in .zip: rename the file first.");
      return;
    }
    packStep(`Put ${file.name} (${size(file.size)}) in the world's datapacks folder? A pack with the same name is moved to staff-removed/ first.`,
      "Upload the pack", file.name, async (typed) => {
        try {
          const done = await api("POST", `/api/datapack-upload?${new URLSearchParams({ name: file.name, confirm: typed })}`, file);
          $("pack-file").value = "";
          say("packs-note", `Added ${done.name}.${done.kept_in ? ` The old copy is kept in ${done.kept_in}.` : ""} ${done.running ? "Press Reload data packs to turn it on." : "It is turned on when the server starts."}`);
        } catch (error) {
          say("packs-error", error);
        }
        loadPacks();
      });
  }

  // ---------------------------------------------------------------- server icon (Settings tab)

  function renderIcon(data) {
    const has = Boolean(data.icon);
    $("icon-none").hidden = has;
    $("icon-remove").hidden = !has;
    // Made here, not in the page, so the page never has an <img> without a picture.
    document.querySelector("#icon-box .server-icon")?.remove();
    if (has) {
      const img = el("img", "server-icon");
      img.width = img.height = 64;
      img.alt = "The server icon now";
      img.src = data.icon;
      $("icon-none").before(img);
    }
  }

  async function loadIcon() {
    try {
      renderIcon(await api("GET", "/api/server-icon"));
      say("icon-error", null);
    } catch (error) {
      say("icon-error", error);
    }
  }

  async function iconCall(url, body, words) {
    say("icon-error", null);
    say("icon-note", null);
    try {
      const done = await api("POST", url, body);
      renderIcon(done);
      say("icon-note", `${words}${done.kept_in ? ` The old icon is kept in ${done.kept_in}.` : ""} It shows after the next restart.`);
    } catch (error) {
      say("icon-error", error);
    }
  }

  async function uploadIcon() {
    const file = $("icon-file").files[0];
    say("icon-error", null);
    if (!file) {
      say("icon-error", "Pick a PNG first.");
      return;
    }
    if (file.size > 1048576) {
      say("icon-error", "An icon is at most 1 MB.");
      return;
    }
    await iconCall("/api/server-icon", file, "Icon saved.");
    $("icon-file").value = "";
  }

  // ---------------------------------------------------------------- Java and memory (Server tab)

  async function loadJava() {
    try {
      const data = await api("GET", "/api/java");
      $("java-state").textContent = `${data.java || "Java"}, pinned by the release.${data.total_gb ? ` The machine has ${data.total_gb} GB.` : ""}`;
      const memory = $("java-memory");
      memory.max = String(data.most_gb);
      memory.placeholder = String(data.default_gb);
      memory.value = data.memory_gb === null ? "" : String(data.memory_gb);
      $("java-memory-about").textContent = data.total_gb
        ? `Empty: picked from the machine (${data.default_gb} GB now). At most ${data.most_gb}: the machine keeps 2 GB for itself.`
        : `Empty: picked from the machine at each start. At most ${data.most_gb}.`;
      $("java-flags").value = (data.flags || []).join("\n");
      say("java-error", null);
    } catch (error) {
      say("java-error", error);
    }
  }

  async function saveJava() {
    say("java-error", null);
    say("java-note", null);
    const typed = $("java-memory").value.trim();
    if (typed && !/^\d+$/.test(typed)) {
      say("java-error", "Memory is a whole number of GB, or empty.");
      return;
    }
    const body = {
      memory_gb: typed ? Number(typed) : null,
      flags: $("java-flags").value.split("\n").map((f) => f.trim()).filter(Boolean),
    };
    try {
      const done = await api("PUT", "/api/java", body);
      say("java-note", `Saved.${done.running ? " Restart the server for it to take effect." : " It is used when the server starts."}`);
      loadJava();
    } catch (error) {
      say("java-error", error);
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
      let data = null;
      for (let attempt = 0; attempt < HELPER_POLL_TRIES && !data; attempt += 1) {
        try {
          data = await api("GET", "/api/helper");
        } catch (error) {
          if (attempt === HELPER_POLL_TRIES - 1) throw error;
          await new Promise((resolve) => { setTimeout(resolve, HELPER_POLL_MS); });
        }
      }
      renderJobs(data);
      const job = (data.jobs || []).find((j) => j.id === request);
      if (job && job.state !== "running") return job;
    }
    return null;
  }

  const HELPER_BAD = ["failed", "refused", "stopped"];

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

  // Asks the root helper for a job and waits for its result; `box` names the box's -note and -error lines.
  async function ask(url, body, words, box = "helper") {
    say(`${box}-error`, null);
    say(`${box}-note`, null);
    try {
      const done = await api("POST", url, body || {});
      say(`${box}-note`, `${words} The helper picks it up in a few seconds.`);
      const job = await waitFor(done.request);
      if (job) say(`${box}-${HELPER_BAD.includes(job.state) ? "error" : "note"}`, job.message);
      else say(`${box}-note`, "Still running: see the jobs list.");
      return job;
    } catch (error) {
      say(`${box}-error`, error);
      return null;
    }
  }

  // The typed step for a big world or version job: `word` must be typed exactly.
  function bigStep(box, message, yes, word, onYes) {
    confirmIn(`${box}-confirm`, `${message} Type ${word} to confirm.`, yes, (typed) => {
      if (typed !== word) {
        say(`${box}-error`, `Nothing done: type ${word} exactly.`);
        return;
      }
      onYes(typed);
    }, { label: "Confirmation", placeholder: word });
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
      say("world-note", "The download was asked for: check your browser's downloads bar. If it shows as failed there, the server refused it (it must be running, and no other job can be busy). Saving is off while it runs and comes back on when it ends.");
    } catch (error) {
      say("world-error", error);
    }
  }

  // ---------------------------------------------------------------- version switch (Server tab)

  async function loadVersions() {
    if (!can("admin")) return;
    try {
      const data = await api("GET", "/api/versions");
      const live = (data.tags || []).find((t) => t.live);
      $("versions-state").textContent = [
        live ? `Running ${live.tag}.` : (data.deployed ? `Running commit ${data.deployed}.` : "Nothing deployed yet."),
        data.newest ? `Newest release: ${data.newest}.` : "",
        data.pinned ? `Pinned to ${data.pinned}: the nightly deploy stays on it until the newest release is picked.` : "",
      ].filter(Boolean).join(" ");
      $("version-tag").replaceChildren(...(data.tags || []).map((t) => {
        const o = el("option", "", `${t.tag}${t.live ? " (running)" : ""}${t.tag === data.newest ? " (newest)" : ""}`);
        o.value = t.tag;
        return o;
      }));
      $("version-tag").hidden = $("version-go").hidden = !(data.tags || []).length;
      $("version-go").disabled = !data.installed || !(data.tags || []).length;
      $("version-missing").hidden = data.installed;
    } catch (error) {
      say("versions-error", error);
    }
  }

  function switchVersion() {
    const tag = $("version-tag").value;
    if (!tag) return;
    bigStep("versions", `Switch the server to ${tag}? Players are warned, the server restarts on that release's files, and its pinned mods come back. An older release stays until the newest one is picked again.`,
      "Switch version", tag, (typed) => ask("/api/version-switch", { tag, confirm: typed }, `Switch to ${tag} asked for.`, "versions").then(loadVersions));
  }

  // ---------------------------------------------------------------- world reset and upload (Server tab)

  function resetWorld() {
    const seed = $("reset-seed").value.trim();
    bigStep("reset", `Reset the world${seed ? " with a new seed" : ""}? Players are warned, the server stops, the overworld, nether and end move aside (kept in backups/ on the machine), and a new world is made when it starts.`,
      "Reset the world", "RESET", (typed) => {
        $("reset-seed").value = "";
        ask("/api/world-reset", seed ? { confirm: typed, seed } : { confirm: typed }, "Reset asked for.", "reset");
      });
  }

  const uploaded = { id: null };

  function renderUpload(data) {
    uploaded.id = data.upload || null;
    $("upload-waiting").hidden = !data.upload;
    $("upload-apply").disabled = !data.upload;
    $("upload-waiting").textContent = data.upload
      ? `Waiting to be swapped in: an upload from ${when(data.time)}, ${size(data.size)}${data.files ? `, ${data.files} files` : ""}.`
      : "";
  }

  async function loadUpload() {
    if (!can("admin")) return;
    try {
      renderUpload(await api("GET", "/api/world-upload"));
    } catch (error) {
      say("upload-error", error);
    }
  }

  async function uploadWorld() {
    const file = $("upload-file").files[0];
    say("upload-error", null);
    say("upload-note", null);
    if (!file) {
      say("upload-error", "Pick a .zip of a world folder first.");
      return;
    }
    if (file.size > 8_000_000_000) {
      say("upload-error", "A world upload is at most 8 GB.");
      return;
    }
    $("upload-send").disabled = true;
    say("upload-note", `Uploading ${size(file.size)}... keep this page open.`);
    try {
      const done = await api("POST", "/api/world-upload", file);
      $("upload-file").value = "";
      say("upload-note", `Uploaded and checked: ${done.files} files${done.folder ? ` in ${done.folder}/` : ""}. Nothing has changed yet: press Swap it in.`);
    } catch (error) {
      say("upload-note", null);
      say("upload-error", error);
    }
    $("upload-send").disabled = false;
    loadUpload();
  }

  function applyUpload() {
    const id = uploaded.id;
    if (!id) return;
    bigStep("upload", "Replace the live world with the uploaded one? Players are warned, the server stops, the current world is kept in backups/ on the machine, and the server starts on the uploaded world.",
      "Swap it in", "REPLACE", (typed) => ask("/api/world-upload-apply", { upload: id, confirm: typed }, "Swap asked for.", "upload").then(loadUpload));
  }

  // ---------------------------------------------------------------- SFTP (Server tab)

  async function loadSftp() {
    if (!can("admin")) return;
    try {
      const data = await api("GET", "/api/sftp");
      $("sftp-missing").hidden = data.set_up;
      $("sftp-info").hidden = !data.set_up;
      if (!data.set_up) return;
      const rows = [["Host", data.host], ["Port", String(data.port)], ["Users", data.users.join(", ")]];
      $("sftp-info").replaceChildren(...rows.flatMap(([k, v]) => [el("dt", "", k), el("dd", "", v)]));
    } catch (error) {
      say("sftp-error", error);
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
    $("mod-upload").addEventListener("click", uploadJar);
    $("modrinth-go").addEventListener("click", searchModrinth);
    $("modrinth-q").addEventListener("keydown", (event) => { if (event.key === "Enter") searchModrinth(); });
    $("mrpack-go").addEventListener("click", installPack);
    $("pack-upload").addEventListener("click", uploadPack);
    $("packs-reload").addEventListener("click", () => packCall("/api/datapack-reload", {}, "Reloaded."));
    // Settings tab: the icon
    $("icon-upload").addEventListener("click", uploadIcon);
    $("icon-remove").addEventListener("click", () => confirmIn("icon-confirm",
      "Remove the server icon? It is moved to staff-removed/ on the machine.", "Remove", () => iconCall("/api/server-icon-remove", {}, "Icon removed.")));
    // Server tab: Java and memory
    $("java-save").addEventListener("click", saveJava);
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
    $("version-go").addEventListener("click", switchVersion);
    $("reset-go").addEventListener("click", resetWorld);
    $("upload-send").addEventListener("click", uploadWorld);
    $("upload-apply").addEventListener("click", applyUpload);
    // Boxes whose reads are admin-only too: a moderator would see only an error in them.
    for (const id of ["icon-box", "packs-box", "java-box"]) $(id).hidden = !can("admin");
    // What this login can't do is greyed out or, for owners only, hidden.
    for (const node of document.querySelectorAll("[data-need]")) {
      if (can(node.dataset.need)) continue;
      if (node.dataset.need === "owner") node.hidden = true;
      else node.disabled = true;
    }
  }

  const VIEWS = {
    // The icon, data packs and Java boxes are admin-only (hidden in build() otherwise), so only admins load them.
    settings: () => {
      loadSettings();
      if (can("admin")) loadIcon();
    },
    mods: () => {
      loadMods();
      if (can("admin")) loadPacks();
    },
    players: loadIpBans,
    server: () => {
      if (can("admin")) loadJava();
      loadHelper();
      loadSchedules();
      loadVersions();
      loadUpload();
      loadSftp();
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
