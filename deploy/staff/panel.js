// The staff page's controls: the tabs, and the Console, Files, Players and Server views (tools/staff_panel.py answers
// the /api/ calls). The Status tab is staff.js and does not come through here. Everything from the server goes in with
// textContent, nothing here may use a style attribute, a form, or confirm() and alert(): Caddy's Content-Security-Policy
// refuses the first two, and a confirm step is two buttons on the page (deploy/Caddyfile.staff).
"use strict";

(() => {
  const TABS = ["status", "console", "files", "players", "server", "settings", "mods", "users"];   // users: users.js fills it
  const CONSOLE_MS = 2_000;        // how often the log is asked for new lines while its tab is open
  const POWER_MS = 5_000;          // how often the server's state is asked again on the Server tab
  const LOG_LINES = 1500;          // older lines drop off the top of the console
  const HISTORY_CMDS = 100;
  const MAX_UPLOAD = 64 * 1048576;
  const NAME = /^[A-Za-z0-9_]{3,16}$/;
  const FILE_NAME = /^[A-Za-z0-9._+-]+$/;

  const $ = (id) => document.getElementById(id);
  let current = "status";

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function button(label, className, onClick) {
    const node = el("button", `btn ${className || ""}`.trim(), label);
    node.type = "button";
    node.addEventListener("click", onClick);
    return node;
  }

  function link(label, onClick) {
    const node = el("button", "link", label);
    node.type = "button";
    node.addEventListener("click", onClick);
    return node;
  }

  // One call to the panel. A failure comes back as an Error whose message is a sentence for the page.
  async function api(method, url, body, raw) {
    const headers = { "X-Monkey-Staff": "1" };
    let payload;
    if (raw) {
      headers["Content-Type"] = "application/octet-stream";
      payload = raw;
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
      const failure = new Error((data && data.error) || `That didn't work (error ${answer.status}).`);
      failure.status = answer.status;
      throw failure;
    }
    return data || {};
  }

  const query = (params) => new URLSearchParams(params).toString();
  const list = (data, key) => (Array.isArray(data[key]) ? data[key] : Array.isArray(data) ? data : []);

  // One line in a tab, in place of an alert: an error (red-free, bone on stone) or a quiet note.
  function fail(tab, error) {
    const node = $(`${tab}-error`);
    node.hidden = !error;
    node.textContent = error ? (error.message || String(error)) : "";
  }

  function note(tab, text) {
    const node = $(`${tab}-note`);
    node.hidden = !text;
    node.textContent = text || "";
  }

  // The in-page confirm step: what will happen, a button that does it, and one that doesn't.
  function confirmStep(tab, message, yes, onYes) {
    const box = $(`${tab}-confirm`);
    const close = () => {
      box.hidden = true;
      box.replaceChildren();
    };
    const row = el("div", "actions");
    row.append(button(yes, "primary", () => {
      close();
      onYes();
    }), button("Cancel", "", close));
    box.replaceChildren(el("p", "", message), row);
    box.hidden = false;
    row.firstElementChild.focus();
  }

  const MONTH_CLOCK = new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });

  // A time as the server sends it: seconds or milliseconds since 1970, or text.
  function when(value) {
    if (value === null || value === undefined || value === "") return "never";
    let ms = typeof value === "number" ? (value > 1e11 ? value : value * 1000) : Date.parse(value);
    if (Number.isNaN(ms)) return String(value);
    return MONTH_CLOCK.format(new Date(ms));
  }

  function size(bytes) {
    if (typeof bytes !== "number") return "";
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1048576).toFixed(1)} MB`;
  }

  const emptyRow = (text) => el("li", "empty-row", text);

  // ---------------------------------------------------------------- the console

  const consoleState = { offset: null, busy: false, timer: null, history: [], at: 0 };

  function consoleActive() {
    return current === "console" && !document.hidden;
  }

  function addLines(lines, kind) {
    const log = $("log");
    const stuck = log.scrollHeight - log.scrollTop - log.clientHeight < 40;
    for (const text of lines) log.appendChild(el("div", `line ${kind || ""}`.trim(), text));
    while (log.childElementCount > LOG_LINES) log.firstElementChild.remove();
    if (stuck) log.scrollTop = log.scrollHeight;
  }

  async function pollConsole() {
    clearTimeout(consoleState.timer);
    if (consoleState.busy || !consoleActive()) return;
    consoleState.busy = true;
    try {
      const after = consoleState.offset === null ? "" : `?${query({ after: consoleState.offset })}`;
      const data = await api("GET", `/api/console${after}`);
      if (data.reset) $("log").replaceChildren();
      addLines(data.lines || []);
      consoleState.offset = data.offset;
      fail("console", null);
    } catch (error) {
      fail("console", error);
    }
    consoleState.busy = false;
    if (consoleActive()) consoleState.timer = setTimeout(pollConsole, CONSOLE_MS);
  }

  async function sendCommand() {
    const input = $("cmd");
    const command = input.value.trim();
    if (!command) return;
    const history = consoleState.history;
    if (history[history.length - 1] !== command) history.push(command);
    if (history.length > HISTORY_CMDS) history.shift();
    consoleState.at = history.length;
    input.value = "";
    addLines([`> ${command}`], "cmd");
    const first = command.replace(/^\//, "").split(/\s+/)[0].toLowerCase();
    if (first === "stop") {
      addLines(["Not sent. Use the Server tab to stop or restart the server."], "out");
      return;
    }
    if (first === "seed") {
      addLines(["Not sent. The world seed is kept secret."], "out");
      return;
    }
    $("send").disabled = true;
    try {
      const data = await api("POST", "/api/command", { command });
      const output = String(data.output || "").split("\n").filter((line) => line.trim());
      addLines(output.length ? output : ["(no output)"], "out");
      fail("console", null);
    } catch (error) {
      fail("console", error);
    }
    $("send").disabled = false;
    input.focus();
  }

  $("send").addEventListener("click", sendCommand);
  $("cmd").addEventListener("keydown", (e) => {
    const history = consoleState.history;
    if (e.key === "Enter") {
      e.preventDefault();
      sendCommand();
    } else if (e.key === "ArrowUp" && history.length) {
      e.preventDefault();
      consoleState.at = Math.max(0, consoleState.at - 1);
      $("cmd").value = history[consoleState.at];
    } else if (e.key === "ArrowDown" && history.length) {
      e.preventDefault();
      consoleState.at = Math.min(history.length, consoleState.at + 1);
      $("cmd").value = history[consoleState.at] || "";
    }
  });

  // ---------------------------------------------------------------- files

  const files = { dir: "", writableDir: true, file: null };
  const join = (dir, name) => (dir ? `${dir}/${name}` : name);

  function renderCrumbs() {
    const parts = files.dir ? files.dir.split("/") : [];
    const nodes = [link("server", () => loadDir(""))];
    let path = "";
    for (const part of parts) {
      path = join(path, part);
      const target = path;
      nodes.push(el("span", "", "/"), link(part, () => loadDir(target)));
    }
    $("crumbs").replaceChildren(...nodes);
  }

  async function loadDir(dir) {
    fail("files", null);
    try {
      const data = await api("GET", `/api/files?${query({ path: dir })}`);
      files.dir = data.path === undefined ? dir : data.path;
      files.writableDir = data.writable !== false;
      files.file = null;
      $("editor").hidden = true;
      $("browser").hidden = false;
      renderCrumbs();
      const rows = list(data, "entries").map((entry) => {
        const item = el("li");
        const what = el("span", "what");
        const full = join(files.dir, entry.name);
        what.appendChild(entry.dir ? link(`${entry.name}/`, () => loadDir(full)) : link(entry.name, () => openFile(full, entry.writable)));
        const meta = [entry.dir ? "" : size(entry.size), when(entry.mtime), entry.writable ? "" : "read only"].filter(Boolean);
        item.append(what, el("span", "meta", meta.join(", ")));
        return item;
      });
      $("entries").replaceChildren(...(rows.length ? rows : [emptyRow("Nothing in this folder.")]));
      $("upload-bar").hidden = !files.writableDir;
    } catch (error) {
      fail("files", error);
    }
  }

  async function openFile(path, writable) {
    fail("files", null);
    note("files", "");
    try {
      const data = await api("GET", `/api/file?${query({ path })}`);
      files.file = { path, mtime: data.mtime, writable: writable !== false, text: data.text };
      $("browser").hidden = true;
      $("editor").hidden = false;
      $("editor-name").textContent = path;
      $("editor-meta").textContent = `${size(data.size)}, saved ${when(data.mtime)}${files.file.writable ? "" : ". Read only."}`;
      const box = $("editor-text");
      box.value = data.text;
      box.readOnly = !files.file.writable;
      $("save").hidden = !files.file.writable;
      $("delete").hidden = !files.file.writable;
      $("download").href = `/api/download?${query({ path })}`;
      box.scrollTop = 0;
    } catch (error) {
      fail("files", error);
      // Too big or not text: the editor won't open it, but it can still be downloaded.
      if (error && (error.status === 413 || error.status === 415)) {
        const a = el("a", "", "Download it");
        a.href = `/api/download?${query({ path })}`;
        $("files-error").append(" ", a);
      }
    }
  }

  async function saveFile() {
    const f = files.file;
    if (!f) return;
    fail("files", null);
    $("save").disabled = true;
    try {
      const text = $("editor-text").value;
      const data = await api("PUT", "/api/file", { path: f.path, text, mtime: f.mtime });
      f.text = text;
      f.mtime = data.mtime !== undefined ? data.mtime : (await api("GET", `/api/file?${query({ path: f.path })}`)).mtime;
      $("editor-meta").textContent = `${size(data.size)}, saved ${when(f.mtime)}`;
      note("files", "Saved. Most changes take effect after a restart.");
    } catch (error) {
      fail("files", error);
    }
    $("save").disabled = false;
  }

  function closeFile() {
    const f = files.file;
    if (f && f.writable && $("editor-text").value !== f.text) {
      confirmStep("files", `Close ${f.path} without saving? Your changes are lost.`, "Yes, close", () => loadDir(files.dir));
      return;
    }
    loadDir(files.dir);
  }

  function deleteFile() {
    const f = files.file;
    if (!f) return;
    confirmStep("files", `Delete ${f.path}? It moves to history, so it can be restored from there.`, "Yes, delete", async () => {
      fail("files", null);
      try {
        await api("POST", "/api/delete", { path: f.path });
        await loadDir(files.dir);
        note("files", `Deleted ${f.path}. It is in the history below.`);
      } catch (error) {
        fail("files", error);
      }
    });
  }

  async function upload(file) {
    fail("files", null);
    note("files", "");
    if (!FILE_NAME.test(file.name)) {
      fail("files", new Error("That file's name can only have letters, digits and . _ + -"));
      return;
    }
    if (file.size > MAX_UPLOAD) {
      fail("files", new Error("That file is over 64 MB, which is the most that can be uploaded here."));
      return;
    }
    $("upload-btn").disabled = true;
    try {
      await api("POST", `/api/upload?${query({ path: files.dir, name: file.name })}`, undefined, file);
      await loadDir(files.dir);
      note("files", `Uploaded ${file.name}. Most changes take effect after a restart.`);
    } catch (error) {
      fail("files", error);
    }
    $("upload-btn").disabled = false;
  }

  async function loadHistory() {
    if (!$("history-box").open) return;
    try {
      const data = await api("GET", "/api/history");
      const rows = list(data, "entries").map((raw) => {
        const h = typeof raw === "string" ? { entry: raw } : raw;
        const entry = h.entry || h.id || h.name || "";
        const path = h.path || "";
        const item = el("li");
        item.appendChild(el("span", "what", path || entry));
        const meta = [h.user, h.time ? when(h.time) : "", path ? entry : ""].filter(Boolean).join(", ");
        const right = el("span", "actions");
        if (meta) right.appendChild(el("span", "meta", meta));
        if (entry && path) {
          right.appendChild(button("Restore", "", () => confirmStep("files", `Put back ${path} from this entry? The file as it is now goes to history first.`, "Yes, restore", async () => {
            fail("files", null);
            try {
              await api("POST", "/api/restore", { entry, path });
              note("files", `Restored ${path}. Most changes take effect after a restart.`);
              loadHistory();
            } catch (error) {
              fail("files", error);
            }
          })));
        }
        item.appendChild(right);
        return item;
      });
      $("file-history").replaceChildren(...(rows.length ? rows : [emptyRow("No changes yet.")]));
    } catch (error) {
      fail("files", error);
    }
  }

  $("save").addEventListener("click", saveFile);
  $("cancel").addEventListener("click", closeFile);
  $("delete").addEventListener("click", deleteFile);
  $("upload-btn").addEventListener("click", () => $("upload").click());
  $("upload").addEventListener("change", () => {
    const file = $("upload").files[0];
    $("upload").value = "";
    if (file) upload(file);
  });
  $("history-box").addEventListener("toggle", loadHistory);
  $("editor-text").addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "s" && files.file && files.file.writable) {
      e.preventDefault();
      saveFile();
    }
  });
  window.addEventListener("beforeunload", (e) => {
    const f = files.file;
    if (f && f.writable && !$("editor").hidden && $("editor-text").value !== f.text) e.preventDefault();
  });

  // ---------------------------------------------------------------- players

  const nameOf = (item) => (typeof item === "string" ? item : item && item.name) || "";
  const reasonOf = (item) => (item && typeof item === "object" && item.reason) || "";

  async function command(text) {
    fail("players", null);
    note("players", "");
    try {
      const data = await api("POST", "/api/command", { command: text });
      const out = String(data.output || "").trim();
      note("players", out ? `Done. The server said: ${out}` : "Done.");
      await loadPlayers();
    } catch (error) {
      fail("players", error);
    }
  }

  // A box with a name per row and a button on each, and a field to add one. ask: confirm text for adding, or null.
  function group(title, names, spec) {
    const box = el("section", "box");
    box.appendChild(el("h3", "", title));
    const ul = el("ul", "entries");
    for (const item of names) {
      const name = nameOf(item);
      if (!name) continue;
      const row = el("li");
      const what = el("span", "what", name);
      if (reasonOf(item)) what.appendChild(el("span", "meta", ` (${reasonOf(item)})`));
      row.appendChild(what);
      if (spec.remove) row.appendChild(button(spec.remove.label, "", () => spec.remove.run(name)));
      if (spec.extra) row.appendChild(button(spec.extra.label, "", () => spec.extra.run(name)));
      ul.appendChild(row);
    }
    if (!ul.childElementCount) ul.appendChild(emptyRow(spec.none));
    box.appendChild(ul);
    if (spec.add) {
      const add = el("div", "add");
      const input = el("input");
      input.type = "text";
      input.maxLength = 16;
      input.placeholder = "Player name";
      input.setAttribute("aria-label", `${spec.add.label}: player name`);
      input.autocomplete = "off";
      input.autocapitalize = "off";
      input.spellcheck = false;
      let reason = null;
      if (spec.add.reason) {
        reason = el("input");
        reason.type = "text";
        reason.maxLength = 120;
        reason.placeholder = "Reason (optional)";
        reason.setAttribute("aria-label", "Reason");
        reason.autocomplete = "off";
      }
      const go = button(spec.add.label, "primary", () => {
        const typed = input.value.trim();
        if (!NAME.test(typed)) {
          fail("players", new Error("A name is 3 to 16 letters, digits or underscores."));
          return;
        }
        fail("players", null);
        spec.add.run(typed, reason ? reason.value.replace(/\s+/g, " ").trim() : "");
      });
      for (const field of [input, reason]) {
        if (field) field.addEventListener("keydown", (e) => { if (e.key === "Enter") go.click(); });
      }
      add.append(input);
      if (reason) add.append(reason);
      add.append(go);
      box.appendChild(add);
    }
    return box;
  }

  async function loadPlayers() {
    try {
      const data = await api("GET", "/api/players");
      const run = (text) => () => command(text);
      $("players-body").replaceChildren(
        group("Online now", data.online || [], {
          none: "Nobody is on.",
          remove: { label: "Kick", run: (name) => command(`kick ${name}`) },
        }),
        group("Whitelist", data.whitelist || [], {
          none: "Nobody is on the whitelist.",
          remove: { label: "Remove", run: (name) => command(`whitelist remove ${name}`) },
          add: { label: "Add", run: (name) => command(`whitelist add ${name}`) },
        }),
        group("Operators", data.ops || [], {
          none: "There are no operators.",
          remove: { label: "Deop", run: (name) => command(`deop ${name}`) },
          add: {
            label: "Make operator",
            run: (name) => confirmStep("players", `Make ${name} an operator? Operators can run most commands in the game.`, `Yes, make ${name} operator`, run(`op ${name}`)),
          },
        }),
        group("Banned", data.banned || data.bans || [], {
          none: "Nobody is banned.",
          remove: { label: "Pardon", run: (name) => command(`pardon ${name}`) },
          add: {
            label: "Ban", reason: true,
            run: (name, why) => confirmStep("players", `Ban ${name}${why ? ` for "${why}"` : ""}? They can't join until pardoned.`, `Yes, ban ${name}`, run(`ban ${name}${why ? ` ${why}` : ""}`)),
          },
        }),
      );
    } catch (error) {
      fail("players", error);
    }
  }

  // ---------------------------------------------------------------- the server

  const MARKS = {
    running: ["good", "M1 1h10v10H1z", "Running"],
    stopped: ["off", "M1 1h10v10H1zM3 3v6h6V3z", "Stopped"],
    restarting: ["busy", "M5 1h2v2h1v2h1v2h1v2h1v2H1V9h1V7h1V5h1V3h1z", "Restarting"],
  };
  const POWER = {
    "restart": ["Restart in 5 minutes? Players get a warning in chat, then the server restarts and is back after a few minutes.", "Yes, restart", "Restart with a 5-minute warning started."],
    "restart-now": ["Restart right now? Nobody gets a warning: players are disconnected at once and can rejoin after a few minutes.", "Yes, restart now", "Restarting now."],
    "stop": ["Stop the server? Players are disconnected, and it stays off until someone presses Start.", "Yes, stop", "Stopping."],
    "start": ["Start the server? It takes a few minutes before players can join.", "Yes, start", "Starting."],
  };
  const powerState = { timer: null, errorsAt: 0 };
  const STARTED_KEY = "monkey-panel-started";   // when this browser last restarted or started the server (ms)
  const ERRORS_SHOWN = 8;

  // The errors logged since a restart or start pressed here: staff.json's groups (tools/staff_status.py), whose last
  // line came after it. The file is written every 2 minutes, so it lags; errors while the server starts aren't kept.
  async function loadPowerErrors() {
    const since = Number(sessionStorage.getItem(STARTED_KEY)) || 0;
    $("power-errors").hidden = !since;
    if (!since || Date.now() - powerState.errorsAt < 60_000) return;
    powerState.errorsAt = Date.now();
    let errors;
    try {
      const answer = await fetch("staff.json", { cache: "no-store" });
      if (!answer.ok) throw new Error();
      const data = await answer.json();
      errors = ((data.problems && data.problems.errors) || []).filter((e) => Date.parse(e.last) >= since);
    } catch {
      $("power-errors-head").textContent = "The errors since your restart can't be read right now.";
      $("power-errors-list").replaceChildren();
      return;
    }
    $("power-errors-head").textContent = errors.length
      ? `Errors logged since you restarted it at ${when(since)}, after it finished starting:`
      : `No errors logged since you restarted it at ${when(since)}, after it finished starting. The list updates every 2 minutes.`;
    $("power-errors-list").replaceChildren(...errors.slice(0, ERRORS_SHOWN).map((e) =>
      el("li", "", `${e.text}${e.count > 1 ? ` (${e.count} times)` : ""}`)));
  }

  async function loadPower() {
    clearTimeout(powerState.timer);
    try {
      const data = await api("GET", "/api/power");
      const [kind, shape, word] = MARKS[data.state] || ["unknown", "M1 1h10v10H1zM3 3v6h6V3zM5 5h2v2H5z", "Unknown"];
      $("power-mark").setAttribute("class", `mark ${kind}`);
      $("power-mark").firstElementChild.setAttribute("d", shape);
      $("power-word").textContent = data.since ? `${word}, since ${when(data.since)}` : word;
      fail("server", null);
    } catch (error) {
      fail("server", error);
    }
    loadPowerErrors();
    if (current === "server" && !document.hidden) powerState.timer = setTimeout(loadPower, POWER_MS);
  }

  async function doPower(action) {
    fail("server", null);
    note("server", "");
    try {
      await api("POST", "/api/power", { action });
      note("server", POWER[action][2]);
      if (action !== "stop") {
        sessionStorage.setItem(STARTED_KEY, String(Date.now()));
        powerState.errorsAt = 0;
      }
    } catch (error) {
      fail("server", error);
    }
    loadPower();
    loadActions();
  }

  async function loadBackup() {
    try {
      const data = await api("GET", "/api/backups");
      const b = data.backups || data;
      const dl = $("backup");
      // The hourly backups go off-site; the copy on this machine is the one a deploy takes before it updates.
      const offsite = { on: "On, every hour", failing: "Failing", "not set up": "Not set up" }[b.offsite];
      const rows = [["Off-site", offsite || b.offsite || "Unknown"],
                    ["Copy before the last update", b.local ? when(b.local) : "None found"]];
      dl.replaceChildren(...rows.map(([label, value]) => {
        const row = el("div", "row");
        row.append(el("dt", "", label), el("dd", "", value));
        return row;
      }));
    } catch (error) {
      fail("server", error);
    }
  }

  async function loadTimers() {
    try {
      const rows = list(await api("GET", "/api/timers"), "timers").map((t) => {
        const tr = el("tr");
        tr.append(el("td", "", String(t.name || "").replace(/\.timer$/, "")), el("td", "", when(t.next)), el("td", "", when(t.last)));
        return tr;
      });
      if (!rows.length) {
        const tr = el("tr");
        tr.appendChild(el("td", "", "No schedules found."));
        rows.push(tr);
      }
      $("timers").replaceChildren(...rows);
    } catch (error) {
      fail("server", error);
    }
  }

  async function loadActions() {
    try {
      const rows = list(await api("GET", "/api/actions"), "actions").map((a) => {
        const item = el("li");
        if (typeof a === "string") {
          item.appendChild(el("span", "what", a));
        } else {
          item.append(el("span", "what", [a.action, a.target].filter(Boolean).join(" ")),
            el("span", "meta", [a.user, when(a.time)].filter(Boolean).join(", ")));
        }
        return item;
      });
      $("actions").replaceChildren(...(rows.length ? rows : [emptyRow("Nothing yet.")]));
    } catch (error) {
      fail("server", error);
    }
  }

  for (const node of document.querySelectorAll("[data-power]")) {
    node.addEventListener("click", () => {
      const action = node.dataset.power;
      confirmStep("server", POWER[action][0], POWER[action][1], () => doPower(action));
    });
  }

  // ---------------------------------------------------------------- the tabs

  const VIEWS = {
    console: () => pollConsole(),
    files: () => {
      if (!files.file) loadDir(files.dir);
      loadHistory();
    },
    players: () => loadPlayers(),
    server: () => {
      loadPower();
      loadBackup();
      loadTimers();
      loadActions();
    },
  };

  function show() {
    const wanted = location.hash.slice(1);
    current = TABS.includes(wanted) ? wanted : "status";
    for (const name of TABS) {
      $(`tab-${name}`).hidden = name !== current;
    }
    for (const a of $("tabs").children) {
      if (a.dataset.tab === current) a.setAttribute("aria-current", "page");
      else a.removeAttribute("aria-current");
    }
    $("foot").hidden = current !== "status";
    if (VIEWS[current]) VIEWS[current]();
  }

  window.addEventListener("hashchange", show);
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) return;
    if (current === "console") pollConsole();
    if (current === "server") loadPower();
  });
  show();
})();
