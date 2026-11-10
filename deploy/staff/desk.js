// The staff page's everyday tools (tools/staff_desk.py and tools/staff_spark.py answer them): the saved commands on
// the Console tab; everyone who has joined (with staff's notes) and the temporary bans on the Players tab; the search
// of all files on the Files tab; the lag finder and the record of changes with a search on the Server tab.
// The same rules as panel.js: everything from the server goes in with textContent, no style attributes, no forms, no
// confirm() or alert(). The panel checks every role; GET /api/me only hides what a login can't use.
"use strict";

(() => {
  const RANK = { moderator: 0, admin: 1, owner: 2 };
  const KNOWN_SHOWN = 50;          // players listed before "Show more"
  const SEARCH_MS = 250;           // a pause in typing before the record is searched
  const $ = (id) => document.getElementById(id);
  let role = "moderator";
  const can = (need) => RANK[role] >= RANK[need];

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
    node.hidden = !text;
    node.textContent = text ? (text.message || String(text)) : "";
  }

  // The in-page confirm step in the box `id`: the message, the button that does it, and Cancel.
  function confirmIn(id, message, yes, onYes) {
    const box = $(id);
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
  const DAY = new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", year: "numeric" });

  function when(value) {
    if (value === null || value === undefined || value === "") return "never";
    const ms = typeof value === "number" ? (value > 1e11 ? value : value * 1000) : Date.parse(value);
    return Number.isNaN(ms) ? String(value) : MONTH_CLOCK.format(new Date(ms));
  }

  // How long ago, in words, for a time in seconds since 1970; a date once it is over a week.
  function ago(seconds) {
    if (typeof seconds !== "number") return "never joined";
    const minutes = Math.max(0, Math.round((Date.now() / 1000 - seconds) / 60));
    if (minutes < 2) return "seen just now";
    if (minutes < 60) return `seen ${minutes} minutes ago`;
    const hours = Math.round(minutes / 60);
    if (hours < 24) return `seen ${hours} hour${hours === 1 ? "" : "s"} ago`;
    const days = Math.round(hours / 24);
    if (days <= 7) return `seen ${days} day${days === 1 ? "" : "s"} ago`;
    return `seen ${DAY.format(new Date(seconds * 1000))}`;
  }

  function item(title, about, ...actions) {
    const row = el("li", "item");
    const main = el("div", "item-main");
    main.append(el("span", "what", title));
    if (about) main.append(el("span", "about", about));
    const side = el("div", "item-actions");
    side.append(...actions.filter(Boolean));
    row.append(main, side);
    return row;
  }

  const emptyRow = (text) => el("li", "empty-row", text);

  // ---------------------------------------------------------------- saved commands (Console tab)

  async function loadSaved() {
    $("saved-box").hidden = !can("admin");
    if (!can("admin")) return;
    try {
      const data = await api("GET", "/api/saved-commands");
      const rows = (data.commands || []).map((c) => item(c.label, c.command,
        button("Run", "primary", () => {
          // panel.js sends it, so it shows in the log with the server's answer, as if typed.
          window.dispatchEvent(new CustomEvent("monkey-run-command", { detail: { command: c.command } }));
          say("saved-note", `Sent: ${c.command}`);
        }),
        button("Delete", "danger", () => confirmIn("saved-confirm", `Delete the saved command ${c.label}?`, "Yes, delete",
          () => savedCall("/api/saved-command-delete", { id: c.id }, "Deleted.")))));
      $("saved-list").replaceChildren(...(rows.length ? rows : [emptyRow("No saved commands yet.")]));
      say("saved-error", null);
    } catch (error) {
      say("saved-error", error);
    }
  }

  async function savedCall(url, body, words) {
    say("saved-error", null);
    say("saved-note", null);
    try {
      await api("POST", url, body);
      say("saved-note", words);
      return true;
    } catch (error) {
      say("saved-error", error);
      return false;
    } finally {
      loadSaved();
    }
  }

  async function addSaved() {
    const label = $("saved-label").value.trim();
    const command = $("saved-command").value.trim();
    if (!label || !command) {
      say("saved-error", "Give the command a label, and the command itself.");
      return;
    }
    if (await savedCall("/api/saved-commands", { label, command }, `Saved ${label}.`)) {
      $("saved-label").value = "";
      $("saved-command").value = "";
    }
  }

  // ---------------------------------------------------------------- everyone who has joined (Players tab)

  const known = { rows: [], shown: KNOWN_SHOWN, open: null };

  function marks(p) {
    return [p.op ? "operator" : "", p.whitelisted ? "whitelisted" : "", p.banned ? "banned" : ""].filter(Boolean);
  }

  function renderKnown() {
    const wanted = $("known-search").value.trim().toLowerCase();
    const found = known.rows.filter((p) => !wanted || p.name.toLowerCase().includes(wanted));
    const rows = found.slice(0, known.shown).map((p) => {
      const hours = typeof p.hours === "number" ? `${p.hours} ${p.hours === 1 ? "hour" : "hours"} played` : "";
      const notes = p.notes ? `${p.notes} note${p.notes === 1 ? "" : "s"}` : "";
      const row = item(p.name, [ago(p.last_seen), hours, ...marks(p), notes].filter(Boolean).join(", "),
        button(known.open === p.name ? "Hide notes" : "Notes", "", () => {
          known.open = known.open === p.name ? null : p.name;
          renderKnown();
        }));
      if (known.open === p.name) row.append(notesBox(p.name));
      return row;
    });
    $("known-list").replaceChildren(...(rows.length ? rows
      : [emptyRow(known.rows.length ? "Nobody by that name has joined." : "Nobody has joined yet.")]));
    $("known-more").hidden = found.length <= known.shown;
    $("known-count").textContent = known.rows.length ? `(${known.rows.length})` : "";
  }

  // A player's notes, under their row: the list, newest first, and a box to add one.
  function notesBox(name) {
    const box = el("div", "notes");
    const list = el("ul", "entries");
    list.append(emptyRow("Reading the notes..."));
    const field = el("input");
    field.type = "text";
    field.maxLength = 500;
    field.placeholder = "A note for the staff, e.g. warned about griefing near spawn";
    field.setAttribute("aria-label", `A new note about ${name}`);
    field.autocomplete = "off";
    const add = button("Add note", "primary", async () => {
      const text = field.value.trim();
      if (!text) return;
      add.disabled = true;
      try {
        await api("POST", "/api/player-notes", { name, text });
        field.value = "";
        say("known-note", `Note added for ${name}.`);
        say("known-error", null);
        await loadKnown();        // draws the list again, this player's notes with it
      } catch (error) {
        say("known-error", error);
      }
      add.disabled = false;
    });
    field.addEventListener("keydown", (e) => { if (e.key === "Enter") add.click(); });
    const line = el("div", "add");
    line.append(field, add);
    box.append(list, line);
    fillNotes(name, list);
    return box;
  }

  async function fillNotes(name, list) {
    try {
      const data = await api("GET", `/api/player-notes?${new URLSearchParams({ name })}`);
      const rows = (data.notes || []).map((n) => item(n.text, `${n.by}, ${when(n.at)}`,
        can("admin") && button("Delete", "danger", () => confirmIn("known-confirm", `Delete this note about ${name}? "${n.text}"`,
          "Yes, delete", async () => {
            try {
              await api("POST", "/api/player-note-delete", { name, id: n.id });
              say("known-note", "Note deleted.");
              await loadKnown();
            } catch (error) {
              say("known-error", error);
            }
          }))));
      list.replaceChildren(...(rows.length ? rows : [emptyRow("No notes yet.")]));
    } catch (error) {
      list.replaceChildren(emptyRow(error.message));
    }
  }

  async function loadKnown() {
    try {
      const data = await api("GET", "/api/known-players");
      known.rows = (data.players || []).filter((p) => p && typeof p.name === "string");
      const unnamed = data.unnamed || 0;
      say("known-warning", data.world === false
        ? "The world has no players folder yet: last seen and play time show once someone has joined."
        : unnamed ? `${unnamed} more ${unnamed === 1 ? "player has" : "players have"} joined but the server no longer keeps ${unnamed === 1 ? "their name" : "their names"} (it keeps its 1000 most recent), so ${unnamed === 1 ? "isn't" : "aren't"} listed.`
          : null);
      say("known-error", null);
      renderKnown();
    } catch (error) {
      say("known-error", error);
    }
  }

  // ---------------------------------------------------------------- the record of changes (Server tab)

  const activity = { more: null, timer: null };

  function search() {
    const params = {};
    if ($("activity-user").value) params.user = $("activity-user").value;
    if ($("activity-kind").value) params.action = $("activity-kind").value;
    const q = $("activity-q").value.trim();
    if (q) params.q = q;
    return params;
  }

  // The menus keep what is picked, and gain any login or kind of change that is new.
  function fillMenu(id, values, everything) {
    const menu = $(id);
    const picked = menu.value;
    const options = [["", everything], ...values.map((v) => [v, v])];
    menu.replaceChildren(...options.map(([value, text]) => {
      const option = el("option", "", text);
      option.value = value;
      return option;
    }));
    menu.value = values.includes(picked) ? picked : "";
  }

  async function loadActivity(older) {
    const params = search();
    if (older && activity.more !== null) params.before = String(activity.more);
    try {
      const data = await api("GET", `/api/activity?${new URLSearchParams(params)}`);
      if (!older) {
        fillMenu("activity-user", data.users || [], "Everyone");
        fillMenu("activity-kind", data.kinds || [], "Every kind");
      }
      const rows = (data.actions || []).map((a) => {
        const row = el("li");
        row.append(el("span", "what", [a.action, a.target].filter(Boolean).join(" ")),
          el("span", "meta", [a.user, when(a.time)].filter(Boolean).join(", ")));
        return row;
      });
      if (older) $("actions").append(...rows);
      else $("actions").replaceChildren(...(rows.length ? rows : [emptyRow(Object.keys(params).length ? "No changes match." : "Nothing yet.")]));
      activity.more = data.more;
      $("activity-more").hidden = data.more === null || data.more === undefined;
      $("activity-cut").hidden = !data.cut;
      $("activity-export").href = `/api/activity-export?${new URLSearchParams(search())}`;
      say("activity-error", null);
    } catch (error) {
      say("activity-error", error);
    }
  }

  function searchSoon() {
    clearTimeout(activity.timer);
    activity.timer = setTimeout(() => loadActivity(false), SEARCH_MS);
  }

  // ---------------------------------------------------------------- temporary bans (Players tab)

  async function loadTempbans() {
    $("tempbans-add").hidden = !can("admin");
    try {
      const data = await api("GET", "/api/tempbans");
      const rows = (data.bans || []).map((b) => item(b.name,
        [`until ${when(b.until)}`, b.reason, `by ${b.by}`].filter(Boolean).join(", "),
        can("admin") && button("Lift now", "", () => confirmIn("tempbans-confirm", `Lift ${b.name}'s ban now? They can join at once.`,
          `Yes, lift it`, async () => {
            try {
              const done = await api("POST", "/api/tempban-end", { name: b.name });
              say("tempbans-note", `${b.name}: ${done.result}.`);
              say("tempbans-error", null);
            } catch (error) {
              say("tempbans-error", error);
            }
            loadTempbans();
            window.dispatchEvent(new Event("monkey-players-changed"));
          }))));
      $("tempbans-list").replaceChildren(...(rows.length ? rows : [emptyRow("No temporary bans.")]));
    } catch (error) {
      say("tempbans-error", error);
    }
  }

  function addTempban() {
    const name = $("tempban-name").value.trim();
    const hours = Number($("tempban-hours").value);
    const reason = $("tempban-reason").value.replace(/\s+/g, " ").trim();
    if (!/^[A-Za-z0-9_]{3,16}$/.test(name)) {
      say("tempbans-error", "A name is 3 to 16 letters, digits or underscores.");
      return;
    }
    const length = $("tempban-hours").selectedOptions[0].textContent;
    confirmIn("tempbans-confirm", `Ban ${name} for ${length}${reason ? ` for "${reason}"` : ""}? They are kicked if they are on, and can't join until it ends.`,
      `Yes, ban ${name}`, async () => {
        say("tempbans-error", null);
        try {
          await api("POST", "/api/tempban", { name, hours, reason });
          $("tempban-name").value = "";
          $("tempban-reason").value = "";
          say("tempbans-note", `${name} is banned for ${length}.`);
        } catch (error) {
          say("tempbans-error", error);
        }
        loadTempbans();
        window.dispatchEvent(new Event("monkey-players-changed"));
      });
  }

  // ---------------------------------------------------------------- the search of all files (Files tab)

  async function searchFiles() {
    const q = $("search-q").value.trim();
    if (q.length < 2) {
      say("search-error", "Search for at least 2 characters.");
      return;
    }
    say("search-error", null);
    $("search-go").disabled = true;
    try {
      const data = await api("GET", `/api/file-search?${new URLSearchParams({ q, text: $("search-text").checked ? "1" : "0" })}`);
      const rows = (data.results || []).map((r) => {
        const open = button(r.line ? `${r.path}, line ${r.line}` : r.path, "", () =>
          window.dispatchEvent(new CustomEvent("monkey-open-file", { detail: { path: r.path, writable: true } })));
        open.className = "link";
        const row = el("li", "item");
        const main = el("div", "item-main");
        main.append(open);
        if (r.text) main.append(el("span", "about", r.text));
        row.append(main);
        return row;
      });
      $("search-list").replaceChildren(...(rows.length ? rows : [emptyRow("Nothing found.")]));
      $("search-count").textContent = rows.length
        ? `${rows.length} found${data.cut ? ": the search stopped early, so there may be more. Search for something longer." : "."}`
        : "";
    } catch (error) {
      say("search-error", error);
    }
    $("search-go").disabled = false;
  }

  // ---------------------------------------------------------------- the lag finder (Server tab)

  const SPARK_POLL_MS = 5_000;
  const SPARK_LINK = /^https:\/\/spark\.lucko\.me\/[A-Za-z0-9]{6,32}$/;
  const SPARK_MODES = { cpu: "everything the game does", lag: "lag spikes", memory: "memory" };
  const sparkState = { timer: null };

  async function loadSpark() {
    clearTimeout(sparkState.timer);
    try {
      const data = await api("GET", "/api/spark");
      const run = data.run;
      const link = run && typeof run.link === "string" && SPARK_LINK.test(run.link) ? run.link : null;
      $("spark-result").hidden = !link;
      if (link) $("spark-link").href = link;
      $("spark-start").hidden = data.running;
      $("spark-stop").hidden = !data.running || !can("admin");
      $("spark-start").disabled = !can("admin") || !data.installed;
      let words = data.installed ? "No run yet." : "spark isn't in the server's mods, so this can't run.";
      if (run) {
        const what = `${SPARK_MODES[run.mode] || run.mode}, started by ${run.by} ${when(run.at)}`;
        if (data.running) words = `Running (${what}). It ends at ${when(run.ends)}; the report link shows here then.`;
        else if (link) words = `The last run (${what}) is ready.`;
        else if (data.waiting) words = `Finished (${what}). Waiting for spark to upload the report...`;
        else if (run.lost) words = `The server restarted during the last run (${what}), so it has no report.`;
        else words = `The last run (${what}) left no report link in the log. The Console tab has spark's own words.`;
      }
      $("spark-state").textContent = words;
      say("spark-error", null);
      if ((data.running || data.waiting) && location.hash === "#server" && !document.hidden) {
        sparkState.timer = setTimeout(loadSpark, SPARK_POLL_MS);
      }
    } catch (error) {
      say("spark-error", error);
    }
  }

  async function sparkCall(url, body, words) {
    say("spark-error", null);
    say("spark-note", null);
    try {
      await api("POST", url, body);
      say("spark-note", words);
    } catch (error) {
      say("spark-error", error);
    }
    loadSpark();
    loadActivity(false);
  }

  // ---------------------------------------------------------------- wiring

  const VIEWS = {
    console: loadSaved,
    players: () => {
      loadKnown();
      loadTempbans();
    },
    server: () => {
      loadSpark();
      loadActivity(false);
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
    $("saved-add").addEventListener("click", addSaved);
    $("saved-command").addEventListener("keydown", (e) => { if (e.key === "Enter") addSaved(); });
    $("known-search").addEventListener("input", () => {
      known.shown = KNOWN_SHOWN;
      renderKnown();
    });
    $("known-more").addEventListener("click", () => {
      known.shown += KNOWN_SHOWN;
      renderKnown();
    });
    $("activity-user").addEventListener("change", () => loadActivity(false));
    $("activity-kind").addEventListener("change", () => loadActivity(false));
    $("activity-q").addEventListener("input", searchSoon);
    $("activity-more").addEventListener("click", () => loadActivity(true));
    $("tempban-go").addEventListener("click", addTempban);
    $("search-go").addEventListener("click", searchFiles);
    $("search-q").addEventListener("keydown", (e) => { if (e.key === "Enter") searchFiles(); });
    $("spark-start").addEventListener("click", () => sparkCall("/api/spark",
      { mode: $("spark-mode").value, seconds: Number($("spark-seconds").value) },
      "Started. Keep playing as normal: the report comes when it ends."));
    $("spark-stop").addEventListener("click", () => sparkCall("/api/spark-stop", {}, "Stopped. spark is uploading what it has."));
    // panel.js says when it changed something: a power action, a player list.
    window.addEventListener("monkey-changed", () => {
      const tab = location.hash.slice(1);
      if (tab === "server") loadActivity(false);
      if (tab === "players") {
        loadKnown();
        loadTempbans();
      }
    });
    window.addEventListener("hashchange", show);
    show();
  }

  start();
})();
