// The staff page's everyday tools (tools/staff_desk.py answers them): the saved commands on the Console tab, everyone
// who has joined (with staff's notes) on the Players tab, and the record of changes with a search on the Server tab.
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
      say("known-error", data.world === false ? "The world has no players folder yet: last seen and play time show once someone has joined." : null);
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

  // ---------------------------------------------------------------- wiring

  const VIEWS = {
    console: loadSaved,
    players: loadKnown,
    server: () => loadActivity(false),
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
    // panel.js says when it changed something: a power action, a player list.
    window.addEventListener("monkey-changed", () => {
      const tab = location.hash.slice(1);
      if (tab === "server") loadActivity(false);
      if (tab === "players") loadKnown();
    });
    window.addEventListener("hashchange", show);
    show();
  }

  start();
})();
