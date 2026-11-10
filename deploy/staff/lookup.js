// Look-ups for staff (tools/staff_lookup.py answers them): the commands a moderator login may run (Console tab), a
// player's whole history and who changed a block, from Ledger (Players tab), and which mods have a newer file on
// Modrinth (Mods tab).
// The same rules as panel.js: everything from the server goes in with textContent, no style attributes, no forms, no
// confirm() or alert(). The panel checks every role; GET /api/me only hides what a login can't use.
"use strict";

(() => {
  const RANK = { moderator: 0, admin: 1, owner: 2 };
  const NAME = /^[A-Za-z0-9_]{3,16}$/;
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

  const CLOCK = new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit" });

  // A time from the server: seconds since 1970, or text such as 2026-11-10T12:00:00Z. Text with no zone is shown as it is.
  function when(value) {
    if (value === null || value === undefined || value === "") return "never";
    if (typeof value === "number") return CLOCK.format(new Date(value > 1e11 ? value : value * 1000));
    if (!/(Z|[+-]\d\d:?\d\d)$/.test(value)) return String(value).replace("T", " ");
    const ms = Date.parse(value);
    return Number.isNaN(ms) ? String(value) : CLOCK.format(new Date(ms));
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
  const plural = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;

  // ---------------------------------------------------------------- commands moderators can run (Console tab)

  async function loadModCommands() {
    say("modcmds-error", null);
    $("modcmds-edit").hidden = !can("owner");
    try {
      const data = await api("GET", "/api/mod-commands");
      const rows = data.commands || [];
      const who = data.default ? " (the standard list)" : data.broken ? "" : data.by ? ` (set by ${data.by}, ${when(data.at)})` : "";
      $("modcmds-list").textContent = rows.length ? `${rows.join(", ")}${who}` : "None: a moderator login can't use the console.";
      if (data.broken) say("modcmds-error", "mod-commands.json can't be read, so moderators can run nothing. Save the list again to fix it.");
      $("modcmds-input").value = rows.join(", ");
      $("modcmds-input").title = `Never allowed: ${(data.never || []).join(", ")}`;
    } catch (error) {
      say("modcmds-error", error);
    }
  }

  async function saveModCommands() {
    say("modcmds-error", null);
    say("modcmds-note", null);
    const commands = $("modcmds-input").value.split(/[,\n]/).map((s) => s.trim()).filter(Boolean);
    $("modcmds-save").disabled = true;
    try {
      const done = await api("PUT", "/api/mod-commands", { commands });
      say("modcmds-note", done.commands.length ? `Saved. Moderators can run: ${done.commands.join(", ")}.` : "Saved. Moderators can't use the console now.");
      loadModCommands();
    } catch (error) {
      say("modcmds-error", error);
    } finally {
      $("modcmds-save").disabled = false;
    }
  }

  // ---------------------------------------------------------------- a player's history (Players tab)

  async function playerHistory() {
    const name = $("phist-name").value.trim();
    say("phist-error", null);
    $("phist-summary").textContent = "";
    $("phist-list").replaceChildren();
    if (!NAME.test(name)) {
      say("phist-error", "A player name is 3 to 16 letters, digits or _.");
      return;
    }
    $("phist-go").disabled = true;
    try {
      const h = await api("GET", `/api/player-history?name=${encodeURIComponent(name)}`);
      const facts = [];
      facts.push(h.known ? `Has joined. Last seen ${when(h.last_seen)}.` : "Has never joined (or joined before the server kept a record).");
      if (typeof h.hours === "number") facts.push(`Played ${h.hours} hours.`);
      facts.push(h.whitelisted ? "On the whitelist." : "Not on the whitelist.");
      if (h.op) facts.push("An operator.");
      $("phist-summary").textContent = `${h.name}: ${facts.join(" ")}`;
      const rows = [];
      if (h.ban) {
        rows.push(item(`Banned: ${h.ban.reason || "no reason given"}`,
          `by ${h.ban.source || "?"}, ${h.ban.created || "?"}${h.ban.expires && h.ban.expires !== "forever" ? `, until ${h.ban.expires}` : ""}`));
      }
      if (h.tempban) {
        rows.push(item(`Temporary ban until ${when(h.tempban.until)}${h.tempban.reason ? `: ${h.tempban.reason}` : ""}`,
          `by ${h.tempban.by || "?"}, ${when(h.tempban.at)}`));
      }
      for (const n of h.notes || []) rows.push(item(`Note: ${n.text}`, `by ${n.by || "?"}, ${when(n.at)}`));
      for (const c of h.changes || []) rows.push(item(`${c.action}: ${c.target}`, `by ${c.user}, ${when(c.time)}`));
      if (h.cut) rows.push(emptyRow("Older changes are in the record's earlier files on the server (actions.log.1 and older)."));
      $("phist-list").replaceChildren(...(rows.length ? rows : [emptyRow("No ban, notes or staff changes for this player.")]));
    } catch (error) {
      say("phist-error", error);
    } finally {
      $("phist-go").disabled = false;
    }
  }

  // ---------------------------------------------------------------- who changed this block (Players tab)

  const ACTIONS = {
    "block-break": "broke", "block-place": "placed", "block-change": "changed", "item-insert": "put in",
    "item-remove": "took out", "entity-kill": "killed", "item-pick-up": "picked up", "item-drop": "dropped",
  };

  async function blockHistory() {
    say("blocks-error", null);
    $("blocks-summary").textContent = "";
    $("blocks-list").replaceChildren();
    const q = new URLSearchParams();
    for (const key of ["x", "y", "z"]) {
      const value = $(`blocks-${key}`).value.trim();
      if (!/^-?\d+$/.test(value)) {
        say("blocks-error", `Type the block's ${key.toUpperCase()} as a whole number (F3 shows it in game).`);
        return;
      }
      q.set(key, value);
    }
    for (const key of ["world", "radius", "hours", "kind"]) q.set(key, $(`blocks-${key}`).value);
    const player = $("blocks-player").value.trim();
    if (player) {
      if (!NAME.test(player)) {
        say("blocks-error", "A player name is 3 to 16 letters, digits or _.");
        return;
      }
      q.set("player", player);
    }
    $("blocks-go").disabled = true;
    $("blocks-summary").textContent = "Reading Ledger's record...";
    try {
      const data = await api("GET", `/api/block-history?${q}`);
      const rows = data.rows || [];
      const box = data.box;
      let text = data.note || (box
        ? `${plural(rows.length, "change")} within ${box.radius} of ${box.x} ${box.y} ${box.z} in the ${box.world}, last ${plural(box.hours, "hour")}. Times are ${data.zone || "Pacific"}, newest first.`
        : "");
      if (data.more) text += " There are more: pick a smaller area or a shorter time.";
      if (data.stopped) text += " The look-up stopped early so the game doesn't slow down: pick a smaller area or a shorter time.";
      $("blocks-summary").textContent = text;
      $("blocks-list").replaceChildren(...(rows.length ? rows.map((r) => {
        const verb = ACTIONS[r.action] || r.action;
        // Ledger keeps a broken block in old (object is then air), and a changed one as old to object.
        const what = r.action === "block-break" ? (r.old || r.object)
          : r.action === "block-change" && r.old && r.old !== r.object ? `${r.old} to ${r.object}` : r.object;
        return item(`${r.who} ${verb} ${what}${r.rolled_back ? " (rolled back)" : ""}`, `${r.time} at ${r.x} ${r.y} ${r.z}`);
      }) : [emptyRow("No changes there in that time.")]));
    } catch (error) {
      $("blocks-summary").textContent = "";
      say("blocks-error", error);
    } finally {
      $("blocks-go").disabled = false;
    }
  }

  // ---------------------------------------------------------------- updates on Modrinth (Mods tab)

  function askUpdate(row) {
    const box = $("updates-confirm");
    const close = () => {
      box.hidden = true;
      box.replaceChildren();
    };
    const input = el("input");
    input.type = "text";
    input.autocomplete = "off";
    input.spellcheck = false;
    input.placeholder = row.slug;
    input.setAttribute("aria-label", "The mod's short name");
    const actions = el("div", "actions");
    actions.append(button("Update it", "primary", () => {
      const typed = input.value.trim();
      close();
      if (typed !== row.slug) {
        say("updates-error", `Nothing changed: type ${row.slug} exactly.`);
        return;
      }
      update(row);
    }), button("Cancel", "", close));
    box.replaceChildren(el("p", "", `Update ${row.jar} to ${row.version}? The new file is downloaded from Modrinth and checked, and the old jar moves to mods-removed/. Type ${row.slug} to confirm.`), input, actions);
    box.hidden = false;
    input.focus();
  }

  async function update(row) {
    say("updates-error", null);
    say("updates-note", `Downloading ${row.slug} from Modrinth...`);
    try {
      const done = await api("POST", "/api/modrinth-install", { project: row.slug, confirm: row.slug });
      say("updates-note", `Installed ${done.name || row.slug} ${done.version || ""}.${done.kept_in ? ` The old file is kept in ${done.kept_in}.` : ""} Restart the server (Server tab) for it to take effect.`);
      window.dispatchEvent(new Event("monkey-changed"));
      loadUpdates(true);
    } catch (error) {
      say("updates-note", null);
      say("updates-error", error);
    }
  }

  async function loadUpdates(fresh) {
    if (!can("admin")) return;
    say("updates-error", null);
    $("updates-go").disabled = true;
    $("updates-count").textContent = "checking...";
    try {
      const data = await api("GET", `/api/mod-updates${fresh ? "?fresh=1" : ""}`);
      const rows = data.updates || [];
      const unknown = data.unknown ? ` ${plural(data.unknown, "jar")} Modrinth doesn't know (added by hand or from elsewhere).` : "";
      $("updates-count").textContent = `${rows.length} of ${data.checked}`;
      say("updates-note", `Checked ${plural(data.checked, "mod")} for ${data.game}, ${when(data.at)}${data.cached ? " (from the last check: press the button to ask again)" : ""}.${unknown}`);
      $("updates-list").replaceChildren(...(rows.length ? rows.map((r) => {
        const changelog = el("a", "btn", "Changelog");
        changelog.href = r.url;
        changelog.target = "_blank";
        changelog.rel = "noopener noreferrer";
        const about = `${r.jar} now. Newer: ${r.version}${r.type && r.type !== "release" ? ` (${r.type})` : ""}, ${when(r.published)}.${r.pinned ? " Comes with the release: update it in a release, since the server puts the pinned jar back when it starts." : ""}`;
        // The install takes Modrinth's newest release, so a beta or alpha is shown but not offered: the button would
        // install a different file from the one listed.
        const offer = can("owner") && r.slug && !r.pinned && (r.type || "release") === "release";
        return item(r.name || r.slug, `${about}${!r.pinned && r.type && r.type !== "release" ? " Not a release, so it isn't offered here." : ""}`,
          changelog, offer ? button("Update", "", () => askUpdate(r)) : null);
      }) : [emptyRow("Every mod Modrinth knows is up to date.")]));
    } catch (error) {
      $("updates-count").textContent = "";
      say("updates-error", error);
    } finally {
      $("updates-go").disabled = false;
    }
  }

  // ---------------------------------------------------------------- wiring

  let updatesLoaded = false;
  const VIEWS = {
    console: loadModCommands,
    mods: () => {
      // Modrinth is asked only once per page load unless someone presses the button; the panel keeps answers 30 minutes.
      if (!updatesLoaded) loadUpdates(false);
      updatesLoaded = true;
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
      role = "moderator";
    }
    $("updates-box").hidden = !can("admin");
    $("modcmds-edit").hidden = !can("owner");
    $("modcmds-save").addEventListener("click", saveModCommands);
    $("modcmds-input").addEventListener("keydown", (e) => { if (e.key === "Enter") saveModCommands(); });
    $("phist-go").addEventListener("click", playerHistory);
    $("phist-name").addEventListener("keydown", (e) => { if (e.key === "Enter") playerHistory(); });
    $("blocks-go").addEventListener("click", blockHistory);
    for (const id of ["blocks-x", "blocks-y", "blocks-z", "blocks-player"]) {
      $(id).addEventListener("keydown", (e) => { if (e.key === "Enter") blockHistory(); });
    }
    $("updates-go").addEventListener("click", () => loadUpdates(true));
    window.addEventListener("hashchange", show);
    show();
  }

  start();
})();
