// The staff page's player actions on the Players tab (tools/staff_players.py answers them): kick, ban, unban, send to
// spawn, Strength SMP's level, a per-player stat reset and the faction prize. Admins only: the boxes stay hidden for a
// moderator, and the panel checks the role anyway.
// The same rules as panel.js: everything from the server goes in with textContent, no style attributes, no forms, no
// confirm() or alert().
"use strict";

(() => {
  const RANK = { moderator: 0, admin: 1, owner: 2 };
  const NAME = /^[A-Za-z0-9_]{3,16}$/;
  const $ = (id) => document.getElementById(id);
  let who = null;       // the player looked up: {name, online, banned, strength, start, most}
  let busy = false;
  let factions = [];

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
    if (body !== undefined) headers["Content-Type"] = "application/json";
    let answer;
    try {
      answer = await fetch(url, { method, headers, body: body === undefined ? undefined : JSON.stringify(body),
        cache: "no-store" });
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

  function confirmIn(where, message, yes, onYes) {
    const box = $(where);
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

  // ------------------------------------------------ one player

  function render() {
    $("act-body").hidden = !who;
    $("act-look").disabled = busy;
    if (!who) return;
    const state = [who.online ? "online" : "offline", who.banned ? "banned" : ""].filter(Boolean).join(", ");
    $("act-who").textContent = `${who.name}: ${state}.`;
    $("act-strength").textContent = who.strength === null
      ? `No Strength level yet: the mod gives ${who.start} when they next play. +1 sets ${who.start + 1}.`
      : `Strength level ${who.strength} of ${who.most}.`;
    $("act-kick").disabled = busy || !who.online;
    $("act-spawn").disabled = busy || !who.online;
    $("act-ban").disabled = busy || who.banned;
    $("act-unban").disabled = busy || !who.banned;
    for (const id of ["act-level-set", "act-level-add", "act-level-zero"]) $(id).disabled = busy;
    $("act-reset").disabled = busy || who.online;
  }

  async function look() {
    const name = $("act-name").value.trim();
    if (!NAME.test(name)) {
      say("act-error", "A player name is 3 to 16 letters, digits or underscores.");
      return;
    }
    busy = true;
    render();
    say("act-error", "");
    say("act-note", "");
    try {
      who = (await api("GET", `/api/player?name=${encodeURIComponent(name)}`)).player;
      $("act-confirm-name").value = "";
    } catch (e) {
      who = null;
      say("act-error", e);
    }
    busy = false;
    render();
  }

  async function act(body) {
    if (!who) return;
    busy = true;
    render();
    say("act-error", "");
    say("act-note", "");
    try {
      const done = await api("POST", "/api/player", { name: who.name, ...body });
      who = done.player;
      say("act-note", done.note || "Done.");
    } catch (e) {
      say("act-error", e);
    }
    busy = false;
    render();
  }

  function withReason(action, question, yes) {
    const reason = $("act-reason").value.trim();
    if (reason.includes("@")) {
      say("act-error", "A reason can't have @ in it.");
      return;
    }
    confirmIn("act-confirm", question, yes, () => act(reason ? { action, reason } : { action }));
  }

  function setLevel() {
    const level = Number($("act-level").value);
    if (!Number.isInteger(level) || level < 0 || level > 5) {
      say("act-error", "Strength: a whole number from 0 to 5.");
      return;
    }
    confirmIn("act-confirm", `Set ${who.name}'s Strength to ${level}?`, "Set it",
      () => act({ action: "strength-set", level }));
  }

  function reset() {
    const typed = $("act-confirm-name").value.trim();
    if (typed.toLowerCase() !== who.name.toLowerCase()) {
      say("act-error", `Type ${who.name} in the box to confirm the reset.`);
      return;
    }
    confirmIn("act-confirm", `Reset ${who.name}'s Strength, kills and deaths to 0? Only this one player.`,
      "Reset them", () => act({ action: "reset", confirm: typed }));
  }

  // ------------------------------------------------ the faction prize

  function renderFaction() {
    const picked = factions.find((f) => f.id === $("faction-pick").value);
    $("faction-members").textContent = picked
      ? `Members: ${picked.members.join(", ") || "none this page can name"}.`
      : (factions.length ? "" : "No factions saved yet.");
    $("faction-go").disabled = busy || !picked || !picked.members.length;
  }

  async function loadFactions() {
    say("faction-error", "");
    try {
      factions = (await api("GET", "/api/factions")).factions || [];
    } catch (e) {
      factions = [];
      say("faction-error", e);
    }
    const pick = $("faction-pick");
    const kept = pick.value;
    pick.replaceChildren(...factions.map((f) => {
      const option = el("option", "", f.name);
      option.value = f.id;
      return option;
    }));
    if (factions.some((f) => f.id === kept)) pick.value = kept;
    renderFaction();
  }

  function giveFaction() {
    const picked = factions.find((f) => f.id === $("faction-pick").value);
    if (!picked) return;
    confirmIn("faction-confirm", `Give +1 Strength to ${picked.name}: ${picked.members.join(", ")}?`, "Give it",
      async () => {
        busy = true;
        renderFaction();
        say("faction-error", "");
        say("faction-note", "");
        try {
          say("faction-note", (await api("POST", "/api/faction-strength", { party: picked.id })).note);
        } catch (e) {
          say("faction-error", e);
        }
        busy = false;
        renderFaction();
      });
  }

  async function begin() {
    let role = "moderator";
    try {
      const me = await api("GET", "/api/me");
      if (me.role in RANK) role = me.role;
    } catch {
      // the safe guess: the boxes stay hidden
    }
    if (RANK[role] < RANK.admin) return;
    $("act-box").hidden = false;
    $("faction-box").hidden = false;
    $("act-look").addEventListener("click", look);
    $("act-name").addEventListener("keydown", (e) => {
      if (e.key === "Enter") look();
    });
    $("act-kick").addEventListener("click", () => withReason("kick", `Kick ${who.name}?`, "Kick"));
    $("act-ban").addEventListener("click", () => withReason("ban", `Ban ${who.name}?`, "Ban"));
    $("act-unban").addEventListener("click", () => confirmIn("act-confirm", `Unban ${who.name}?`, "Unban",
      () => act({ action: "unban" })));
    $("act-spawn").addEventListener("click", () => confirmIn("act-confirm",
      `Send ${who.name} to the world spawn?`, "Send", () => act({ action: "spawn" })));
    $("act-level-set").addEventListener("click", setLevel);
    $("act-level-add").addEventListener("click", () => confirmIn("act-confirm", `Give ${who.name} +1 Strength?`,
      "Give it", () => act({ action: "strength-add" })));
    $("act-level-zero").addEventListener("click", () => confirmIn("act-confirm",
      `Set ${who.name}'s Strength to 0?`, "Set 0", () => act({ action: "strength-reset" })));
    $("act-reset").addEventListener("click", reset);
    $("faction-pick").addEventListener("change", renderFaction);
    $("faction-load").addEventListener("click", loadFactions);
    $("faction-go").addEventListener("click", giveFaction);
    render();
    loadFactions();
  }

  begin();
})();
