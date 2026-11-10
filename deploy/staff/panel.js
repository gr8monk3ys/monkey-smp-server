// The staff page's controls: the tabs, and the Console, Files, Players and Server views (tools/staff_panel.py answers
// the /api/ calls; desk.js adds the saved commands, everyone who has joined and the record of changes). The Status tab is staff.js and does not come through here. Everything from the server goes in with
// textContent, nothing here may use a style attribute, a form, or confirm() and alert(): Caddy's Content-Security-Policy
// refuses the first two, and a confirm step is two buttons on the page (deploy/Caddyfile.staff).
"use strict";

(() => {
  const TABS = ["status", "console", "files", "players", "server", "settings", "mods", "modcfg", "reports", "users"];   // users: users.js fills it
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

  // One line in a tab, in place of an alert: an error (a coral outline and its mark) or a quiet note. Each is
  // brought into view, so the answer to a button far down a phone's page is not left off screen.
  function fail(tab, error) {
    const node = $(`${tab}-error`);
    const text = error ? (error.message || String(error)) : "";
    const fresh = text && (node.hidden || node.textContent !== text);   // a poll that fails again must not scroll again
    node.hidden = !error;
    node.textContent = text;
    if (fresh) node.scrollIntoView({ block: "nearest" });
  }

  function note(tab, text) {
    const node = $(`${tab}-note`);
    node.hidden = !text;
    node.textContent = text || "";
    if (text) node.scrollIntoView({ block: "nearest" });
  }

  // The in-page confirm step: what will happen, a button that does it, and one that doesn't. `field`, when given,
  // is a text box under the message ({label, placeholder, value, max}); what was typed is onYes's argument, and
  // Enter in it presses the button.
  function confirmStep(tab, message, yes, onYes, field) {
    const box = $(`${tab}-confirm`);
    const close = () => {
      box.hidden = true;
      box.replaceChildren();
    };
    const parts = [el("p", "", message)];
    let typed = null;
    if (field) {
      typed = el("input");
      typed.type = "text";
      typed.maxLength = field.max || 120;
      typed.placeholder = field.placeholder || "";
      typed.value = field.value || "";
      typed.setAttribute("aria-label", field.label);
      typed.autocomplete = "off";
      typed.autocapitalize = "off";
      typed.spellcheck = false;
      const line = el("div", "typed");
      line.append(typed);
      parts.push(line);
    }
    const row = el("div", "actions");
    const go = button(yes, "primary", () => {
      const value = typed ? typed.value.replace(/\s+/g, " ").trim() : undefined;
      close();
      onYes(value);
    });
    row.append(go, button("Cancel", "", close));
    if (typed) typed.addEventListener("keydown", (e) => { if (e.key === "Enter") go.click(); });
    box.replaceChildren(...parts, row);
    box.hidden = false;
    box.scrollIntoView({ block: "nearest" });
    (typed || go).focus();
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

  const consoleState = { offset: null, busy: false, timer: null, history: [], at: 0, view: "all", filter: "", level: "" };
  // A line of the log as the game writes it: [12:00:00] [Server thread/INFO]: text. A line without that start
  // belongs to the one before it (a stack trace under its error).
  const LOG_HEAD = /^\[\d\d:\d\d:\d\d\] \[[^\]]*\/(INFO|WARN|ERROR|FATAL)\](?: \[[^\]]*\])?: (.*)$/;
  // What players and the server said, and who came and went: <Name> text, [Server] text, [Name] text (say from a
  // player), with the game's own "[Not Secure] " in front or not.
  const CHAT = /^(?:\[Not Secure\] )?(?:<[^>]{1,40}> |\[Server\] |\[[A-Za-z0-9_]{3,16}\] )|^[A-Za-z0-9_]{3,16} (?:joined|left) the game$/;

  // The classes of a line from the log: its level, and whether it is chat.
  function kindOf(text) {
    const head = LOG_HEAD.exec(text);
    if (!head) return `${consoleState.level} more`;   // a continuation: as the line it hangs under, without its mark
    const level = head[1] === "WARN" ? "warn" : head[1] === "INFO" ? "" : "error";
    consoleState.level = level;
    return level || (CHAT.test(head[2]) ? "chat" : "");
  }

  // Whether a line shows under the view and the filter chosen. The page's own lines (a command, its answer) show
  // under Everything only.
  function lineShows(node) {
    const kinds = node.classList;
    if (consoleState.view === "chat" && !kinds.contains("chat")) return false;
    if (consoleState.view === "problems" && !kinds.contains("warn") && !kinds.contains("error")) return false;
    return !consoleState.filter || node.textContent.toLowerCase().includes(consoleState.filter);
  }

  function countLines() {
    const log = $("log");
    const all = log.childElementCount;
    const shown = all - log.querySelectorAll(".line[hidden]").length;
    const narrowed = consoleState.view !== "all" || consoleState.filter;
    $("console-count").textContent = narrowed ? `${shown} of ${all} lines` : "";
  }

  function refilter() {
    const log = $("log");
    for (const node of log.children) node.hidden = !lineShows(node);
    countLines();
    log.scrollTop = log.scrollHeight;
  }

  function consoleActive() {
    return current === "console" && !document.hidden;
  }

  function addLines(lines, kind) {
    const log = $("log");
    const stuck = log.scrollHeight - log.scrollTop - log.clientHeight < 40;
    for (const text of lines) {
      const node = el("div", `line ${kind === undefined ? kindOf(text) : kind}`.trim(), text);
      node.hidden = !lineShows(node);
      log.appendChild(node);
    }
    while (log.childElementCount > LOG_LINES) log.firstElementChild.remove();
    countLines();
    if (stuck) log.scrollTop = log.scrollHeight;
  }

  async function pollConsole() {
    clearTimeout(consoleState.timer);
    if (consoleState.busy || !consoleActive()) return;
    consoleState.busy = true;
    try {
      const after = consoleState.offset === null ? "" : `?${query({ after: consoleState.offset })}`;
      const data = await api("GET", `/api/console${after}`);
      if (data.reset) {
        $("log").replaceChildren();
        consoleState.level = "";
      }
      addLines(data.lines || []);
      consoleState.offset = data.offset;
      fail("console", null);
    } catch (error) {
      fail("console", error);
    }
    consoleState.busy = false;
    if (consoleActive()) consoleState.timer = setTimeout(pollConsole, CONSOLE_MS);
  }

  // `given`: a saved command (desk.js), sent as it is. Otherwise what is in the box: a command, or under Chat a
  // message for everyone unless it starts with /.
  async function sendCommand(given) {
    const input = $("cmd");
    const typed = typeof given === "string" ? given : input.value.trim();
    if (!typed) return;
    const saying = typeof given !== "string" && consoleState.view === "chat" && !typed.startsWith("/");
    const command = saying ? `say ${typed}` : typed;
    const history = consoleState.history;
    // Kept as a command (with its /), so Up then Enter sends it again as it went, in Chat too: never "say say hi".
    const kept = saying ? `/${command}` : command;
    if (history[history.length - 1] !== kept) history.push(kept);
    if (history.length > HISTORY_CMDS) history.shift();
    consoleState.at = history.length;
    if (typeof given !== "string") input.value = "";
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

  $("send").addEventListener("click", () => sendCommand());
  for (const node of $("console-views").children) {
    node.addEventListener("click", () => {
      consoleState.view = node.dataset.view;
      for (const other of $("console-views").children) other.setAttribute("aria-pressed", String(other === node));
      const chat = consoleState.view === "chat";
      $("cmd").placeholder = chat ? "Say something to everyone" : "list";
      $("cmd-label").textContent = chat ? "Message to everyone, or a command starting with /" : "Command";
      $("send").textContent = chat ? "Say" : "Send";
      $("say-hint").hidden = !chat;
      refilter();
    });
  }
  $("console-filter").addEventListener("input", () => {
    consoleState.filter = $("console-filter").value.trim().toLowerCase();
    refilter();
  });
  // A saved command's Run button (desk.js): sent as if typed here, so it shows in the log with its answer.
  // desk.js: a temporary ban changed the bans list.
  window.addEventListener("monkey-players-changed", () => { if (current === "players") loadPlayers(); });
  window.addEventListener("monkey-run-command", (event) => sendCommand(String(event.detail.command)));
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

  const files = { dir: "", writableDir: true, file: null, names: new Set() };
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
      files.names = new Set(list(data, "entries").map((entry) => String(entry.name).toLowerCase()));
      $("files-filter").value = "";
      const rows = list(data, "entries").map((entry) => {
        const item = el("li");
        item.dataset.name = String(entry.name).toLowerCase();
        const what = el("span", "what");
        const full = join(files.dir, entry.name);
        item.className = entry.dir ? "dir" : "file";
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
      // The server says whether it can be saved: a file opened from elsewhere (a search, Mod settings) may be in logs/.
      files.file = { path, mtime: data.mtime, writable: writable !== false && data.writable !== false, text: data.text };
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
      $("rename").hidden = !files.file.writable;
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

  // A name typed for a new file or folder: the same letters an upload's name may have.
  function typedName(name) {
    if (!FILE_NAME.test(name) || name === "." || name === "..") {
      fail("files", new Error("A name can only have letters, digits and . _ + -"));
      return false;
    }
    if (files.names.has(name.toLowerCase())) {
      fail("files", new Error(`This folder already has something called ${name}.`));
      return false;
    }
    return true;
  }

  function newFile() {
    fail("files", null);
    note("files", "");
    confirmStep("files", `Make a new, empty file in ${files.dir || "server"}/. Give it a name with its ending, like notes.txt.`, "Make the file", async (name) => {
      if (!typedName(name)) return;
      const path = join(files.dir, name);
      try {
        // No mtime: the panel takes that as "there is no such file yet" and refuses one that is there after all.
        await api("PUT", "/api/file", { path, text: "" });
        await loadDir(files.dir);
        await openFile(path, true);
      } catch (error) {
        fail("files", error);
      }
    }, { label: "The new file's name", placeholder: "notes.txt", max: 128 });
  }

  function newFolder() {
    fail("files", null);
    note("files", "");
    confirmStep("files", `Make a new folder in ${files.dir || "server"}/.`, "Make the folder", async (name) => {
      if (!typedName(name)) return;
      try {
        await api("POST", "/api/folder", { path: join(files.dir, name) });
        await loadDir(files.dir);
        note("files", `Made the folder ${name}.`);
      } catch (error) {
        fail("files", error);
      }
    }, { label: "The new folder's name", placeholder: "Folder name", max: 128 });
  }

  function renameFile() {
    const f = files.file;
    if (!f) return;
    fail("files", null);
    note("files", "");
    if (f.writable && $("editor-text").value !== f.text) {
      fail("files", new Error("Save or close your changes first: a rename would leave them behind."));
      return;
    }
    confirmStep("files", `Give ${f.path} a new name, or a path from the server folder to move it (config/old/name.toml). Nothing is replaced: a name already taken is refused.`,
      "Rename", async (to) => {
        if (!to || to === f.path) return;
        try {
          const done = await api("POST", "/api/rename", { path: f.path, to });
          const moved = done.path || to;
          files.dir = moved.includes("/") ? moved.slice(0, moved.lastIndexOf("/")) : "";
          await loadDir(files.dir);
          note("files", `${f.path} is now ${moved}.`);
        } catch (error) {
          fail("files", error);
        }
      }, { label: "The file's new name or path", value: f.path, max: 400 });
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
  $("new-file").addEventListener("click", newFile);
  $("new-folder").addEventListener("click", newFolder);
  $("rename").addEventListener("click", renameFile);
  $("files-filter").addEventListener("input", () => {
    const wanted = $("files-filter").value.trim().toLowerCase();
    for (const item of $("entries").children) {
      if (item.dataset.name !== undefined) item.hidden = Boolean(wanted) && !item.dataset.name.includes(wanted);
    }
  });
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
      window.dispatchEvent(new Event("monkey-changed"));    // desk.js: the lists changed, and so did the record
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
      if (spec.remove) {
        row.appendChild(button(spec.remove.label, spec.remove.danger ? "danger" : "",
          () => confirmStep("players", spec.remove.ask(name), spec.remove.yes(name), (why) => spec.remove.run(name, why),
            spec.remove.reason ? { label: "Reason", placeholder: "Reason they will see (optional)", max: 120 } : undefined)));
      }
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
      const go = button(spec.add.label, spec.add.danger ? "danger" : "primary", () => {
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
          remove: {
            label: "Kick", danger: true, reason: true, run: (name, why) => command(`kick ${name}${why ? ` ${why}` : ""}`),
            ask: (name) => `Kick ${name}? They are disconnected now and can join again at once.`, yes: (name) => `Yes, kick ${name}`,
          },
        }),
        group("Whitelist", data.whitelist || [], {
          none: "Nobody is on the whitelist.",
          remove: {
            label: "Remove", danger: true, run: (name) => command(`whitelist remove ${name}`),
            ask: (name) => `Take ${name} off the whitelist? They can't join until they are added again.`, yes: (name) => `Yes, remove ${name}`,
          },
          add: { label: "Add", run: (name) => command(`whitelist add ${name}`) },
        }),
        group("Operators", data.ops || [], {
          none: "There are no operators.",
          remove: {
            label: "Deop", danger: true, run: (name) => command(`deop ${name}`),
            ask: (name) => `Take operator away from ${name}? They lose the operator commands at once.`, yes: (name) => `Yes, deop ${name}`,
          },
          add: {
            label: "Make operator",
            run: (name) => confirmStep("players", `Make ${name} an operator? Operators can run most commands in the game.`, `Yes, make ${name} operator`, run(`op ${name}`)),
          },
        }),
        group("Banned", data.banned || data.bans || [], {
          none: "Nobody is banned.",
          remove: {
            label: "Pardon", run: (name) => command(`pardon ${name}`),
            ask: (name) => `Pardon ${name}? They can join again at once.`, yes: (name) => `Yes, pardon ${name}`,
          },
          add: {
            label: "Ban", reason: true, danger: true,
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
  const powerState = { timer: null, errorsAt: 0, since: null, state: null };
  // That a restart or start was pressed in this tab, and the server's start time just before it ("before"): the
  // errors shown are those after the server's next start time, which GET /api/power says (its "since" when running).
  // A normal restart waits 5 minutes, so the time of the click is not when the server started.
  const PRESSED_KEY = "monkey-panel-pressed";
  const ERRORS_SHOWN = 8;

  // sessionStorage can throw (storage off, a private window): then the page works without remembering.
  function pressedRead() {
    try {
      const kept = JSON.parse(sessionStorage.getItem(PRESSED_KEY) || "null");
      return kept && typeof kept === "object" ? kept : null;
    } catch {
      return null;
    }
  }

  function pressedWrite(value) {
    try {
      sessionStorage.setItem(PRESSED_KEY, JSON.stringify(value));
    } catch { /* not kept: no error list after this restart */ }
  }

  // The errors logged since the server started after a restart or start pressed here: staff.json's groups
  // (tools/staff_status.py), whose last line came after that start. The file is written every 2 minutes, so it lags.
  async function loadPowerErrors() {
    const pressed = pressedRead();
    $("power-errors").hidden = !pressed;
    if (!pressed) return;
    // Started again since the press: running, with a start time that isn't the one from before it.
    const started = powerState.state === "running" && powerState.since && powerState.since !== pressed.before
      ? Date.parse(powerState.since) : NaN;
    if (Number.isNaN(started)) {
      $("power-errors-head").textContent = "Errors since your restart show here once the server has started again.";
      $("power-errors-list").replaceChildren();
      powerState.errorsAt = 0;
      return;
    }
    if (Date.now() - powerState.errorsAt < 60_000) return;
    powerState.errorsAt = Date.now();
    let errors;
    try {
      const answer = await fetch("staff.json", { cache: "no-store" });
      if (!answer.ok) throw new Error();
      const data = await answer.json();
      errors = ((data.problems && data.problems.errors) || []).filter((e) => Date.parse(e.last) >= started);
    } catch {
      $("power-errors-head").textContent = "The errors since your restart can't be read right now.";
      $("power-errors-list").replaceChildren();
      return;
    }
    $("power-errors-head").textContent = errors.length
      ? `Errors logged since the server started again at ${when(started)}:`
      : `No errors logged since the server started again at ${when(started)}. The list updates every 2 minutes.`;
    // e.count is for the whole window staff.json covers, so only the last time is said, not a count since the start.
    $("power-errors-list").replaceChildren(...errors.slice(0, ERRORS_SHOWN).map((e) =>
      el("li", "", `${e.text} (last seen ${when(e.last)})`)));
  }

  async function loadPower() {
    clearTimeout(powerState.timer);
    try {
      const data = await api("GET", "/api/power");
      const [kind, shape, word] = MARKS[data.state] || ["unknown", "M1 1h10v10H1zM3 3v6h6V3zM5 5h2v2H5z", "Unknown"];
      $("power-mark").setAttribute("class", `mark ${kind}`);
      $("power-mark").firstElementChild.setAttribute("d", shape);
      $("power-word").textContent = data.since ? `${word}, since ${when(data.since)}` : word;
      powerState.state = data.state;
      powerState.since = data.since || null;
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
        pressedWrite({ before: powerState.state === "running" ? powerState.since : null });
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

  // The record of changes is desk.js's: it reads it again when told something changed.
  const loadActions = () => window.dispatchEvent(new Event("monkey-changed"));

  for (const node of document.querySelectorAll("[data-power]")) {
    node.addEventListener("click", () => {
      const action = node.dataset.power;
      // staff.js leaves the latest player count on the body while its reading is fresh. With no fresh reading
      // the step says so: silence would read as "nobody is on".
      const count = document.body.dataset.players;
      const on = Number(count || 0);
      let who = "";
      if (action !== "start") {
        if (count === undefined) who = " The page can't tell how many players are on right now.";
        else if (on > 0) who = ` ${on === 1 ? "1 player is" : `${on} players are`} on right now.`;
      }
      confirmStep("server", POWER[action][0] + who, POWER[action][1], () => doPower(action));
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
    },
  };

  function show() {
    const wanted = location.hash.slice(1);
    current = TABS.includes(wanted) ? wanted : "status";
    for (const name of TABS) {
      $(`tab-${name}`).hidden = name !== current;
    }
    document.body.dataset.tab = current;
    for (const a of $("tabs").children) {
      if (a.dataset.tab === current) {
        a.setAttribute("aria-current", "page");
        // The row of tabs scrolls sideways on a phone. Only the row moves: scrollIntoView would also move the
        // page, because the row is in the sticky bar, inside the page's scroll padding.
        const row = $("tabs").getBoundingClientRect();
        const box = a.getBoundingClientRect();
        if (box.left < row.left) $("tabs").scrollLeft -= row.left - box.left;
        else if (box.right > row.right) $("tabs").scrollLeft += box.right - row.right;
      } else {
        a.removeAttribute("aria-current");
      }
    }
    $("foot").hidden = current !== "status";
    if (VIEWS[current]) VIEWS[current]();
  }

  window.addEventListener("hashchange", show);
  // The Mod settings tab (modcfg.js) opens a file it can't show as a form here, in the raw editor.
  window.addEventListener("monkey-open-file", (event) => {
    location.hash = "#files";
    openFile(String(event.detail.path), event.detail.writable);
  });
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) return;
    if (current === "console") pollConsole();
    if (current === "server") loadPower();
  });
  show();
})();
