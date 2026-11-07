// The staff page's event controls on the Server tab (tools/staff_events.py answers them): the event timer and the
// leaderboard update. Admins only: the box stays hidden for a moderator, and the panel checks the role anyway.
// The same rules as panel.js: everything from the server goes in with textContent, no style attributes, no forms, no
// confirm() or alert().
"use strict";

(() => {
  const RANK = { moderator: 0, admin: 1, owner: 2 };
  const POLL_MS = 15_000;
  const $ = (id) => document.getElementById(id);
  let timer = null;
  let busy = false;

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

  function confirmIn(message, yes, onYes) {
    const box = $("events-confirm");
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

  function render() {
    const running = Boolean(timer && timer.running);
    if (!timer) $("timer-state").textContent = "The timer's state isn't known.";
    else if (running) {
      const left = timer.minutes === 1 ? "1 min left" : `${timer.minutes} min left`;
      $("timer-state").textContent = `Running: ${timer.name || "an event"}, ${left}.`;
    } else $("timer-state").textContent = "No event timer is running.";
    $("timer-start").disabled = busy || running;
    $("timer-finish").disabled = busy || !running;
    $("timer-stop").disabled = busy || !running;
  }

  async function load() {
    try {
      timer = (await api("GET", "/api/event-timer")).timer;
      say("events-error", "");
    } catch (e) {
      timer = null;
      say("events-error", e);
    }
    render();
  }

  async function act(body) {
    busy = true;
    render();
    say("events-error", "");
    say("events-note", "");
    try {
      const done = await api("POST", "/api/event-timer", body);
      timer = done.timer;
      say("events-note", done.note || "Stopped.");
    } catch (e) {
      say("events-error", e);
    }
    busy = false;
    render();
  }

  function start() {
    const name = $("timer-name").value.trim();
    const minutes = Number($("timer-minutes").value);
    if (!name) {
      say("events-error", "Type the event's name.");
      return;
    }
    if (!Number.isInteger(minutes) || minutes < 1 || minutes > 600) {
      say("events-error", "Minutes: a whole number from 1 to 600.");
      return;
    }
    act({ action: "start", name, minutes });
  }

  async function updateBoard() {
    const go = $("board-update");
    go.disabled = true;
    say("events-error", "");
    say("events-note", "Saving the world, then updating the leaderboard. This can take a minute.");
    try {
      say("events-note", (await api("POST", "/api/leaderboard", {})).note);
    } catch (e) {
      say("events-note", "");
      say("events-error", e);
    }
    go.disabled = false;
  }

  let poll = null;
  function show() {
    clearInterval(poll);
    poll = null;
    if (location.hash !== "#server") return;
    load();
    poll = setInterval(() => {
      if (!busy && !document.hidden) load();
    }, POLL_MS);
  }

  async function begin() {
    let role = "moderator";
    try {
      const me = await api("GET", "/api/me");
      if (me.role in RANK) role = me.role;
    } catch {
      // the safe guess: the box stays hidden
    }
    if (RANK[role] < RANK.admin) return;
    $("events-box").hidden = false;
    $("timer-start").addEventListener("click", start);
    $("timer-finish").addEventListener("click", () => confirmIn(
      "End the event now? Everyone sees \"Event over\".", "End it", () => act({ action: "finish" })));
    $("timer-stop").addEventListener("click", () => confirmIn(
      "Stop the timer? It goes away with no \"Event over\".", "Stop it", () => act({ action: "stop" })));
    $("board-update").addEventListener("click", updateBoard);
    render();
    window.addEventListener("hashchange", show);
    show();
  }

  begin();
})();
