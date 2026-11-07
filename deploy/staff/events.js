// The staff page's event controls on the Server tab (tools/staff_events.py answers them): the event timer, the
// leaderboard update and the event nights (the monkey-nights pack). Admins only: the box stays hidden for a moderator, and the panel checks the role anyway.
// The same rules as panel.js: everything from the server goes in with textContent, no style attributes, no forms, no
// confirm() or alert().
"use strict";

(() => {
  const RANK = { moderator: 0, admin: 1, owner: 2 };
  const POLL_MS = 15_000;
  const $ = (id) => document.getElementById(id);
  let timer = null;
  let busy = false;
  let nights = null;
  let nightBusy = false;

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

  function confirmIn(message, yes, onYes, where = "events-confirm") {
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
    try {
      nights = (await api("GET", "/api/nights")).nights;
      say("nights-error", "");
    } catch (e) {
      nights = null;
      say("nights-error", e);
    }
    renderNights();
  }

  // ------------------------------------------------ event nights

  // Which phases each step may run in, as tools/staff_events.py's STEPS has them.
  const NIGHT_STEPS = {
    "grace/start": ["idle"], "grace/end": ["grace"], "build/start": ["idle"], "build/end": ["build"],
    stop: ["grace", "build"], minutes: ["grace", "build"], call: ["idle", "grace", "build"],
  };
  const NIGHT_BUTTONS = {
    "grace/start": "nights-grace-start", "grace/end": "nights-grace-end", "build/start": "nights-build-start",
    "build/end": "nights-build-end", stop: "nights-stop", minutes: "nights-minutes-go", call: "nights-call-go",
  };
  const NIGHT_ASK = {
    "grace/start": ["Start the grace period now? Everyone on the server sees it.", "Start grace"],
    "grace/end": ["End the grace period and start the build battle now?", "End grace"],
    "build/start": ["Start the build battle now, with no grace period?", "Start the build"],
    "build/end": ["End the build battle now?", "End the build"],
    stop: ["Stop the event night now? The timer and the phase go back to idle.", "Stop it"],
  };

  function renderNights() {
    const phase = nights ? nights.phase : null;
    let text = "The event night's state isn't known.";
    if (nights && !nights.set_up) text = "Nothing is running (the pack hasn't set itself up yet: it does on the first step).";
    else if (phase === "idle") text = "Nothing is running.";
    else if (phase === "grace" || phase === "build") {
      const what = phase === "grace" ? "Grace period" : "Build battle";
      text = `${what}: ${nights.minutes === 1 ? "1 min" : `${nights.minutes} min`} left.`;
    } else if (phase) text = `The phase is ${phase}: stop it, then start again.`;
    $("nights-state").textContent = text;
    for (const [step, id] of Object.entries(NIGHT_BUTTONS)) {
      $(id).disabled = nightBusy || !phase || !NIGHT_STEPS[step].includes(phase);
    }
  }

  async function night(body) {
    nightBusy = true;
    renderNights();
    say("nights-error", "");
    say("nights-note", "");
    try {
      const done = await api("POST", "/api/nights", body);
      nights = done.nights;
      say("nights-note", done.note || "Done.");
    } catch (e) {
      say("nights-error", e);
    }
    nightBusy = false;
    renderNights();
  }

  function nightStep(step) {
    const [message, yes] = NIGHT_ASK[step];
    confirmIn(message, yes, () => night({ action: step }), "nights-confirm");
  }

  function nightMinutes() {
    const minutes = Number($("nights-minutes").value);
    if (!Number.isInteger(minutes) || minutes < 1 || minutes > 600) {
      say("nights-error", "Minutes: a whole number from 1 to 600.");
      return;
    }
    night({ action: "minutes", minutes });
  }

  function nightCall() {
    const block = $("nights-block").value.trim();
    if (!block) {
      say("nights-error", "Type the block's name.");
      return;
    }
    night({ action: "call", block });
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
      if (!busy && !nightBusy && !document.hidden) load();
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
    $("nights-box").hidden = false;
    for (const step of Object.keys(NIGHT_ASK)) $(NIGHT_BUTTONS[step]).addEventListener("click", () => nightStep(step));
    $("nights-minutes-go").addEventListener("click", nightMinutes);
    $("nights-call-go").addEventListener("click", nightCall);
    renderNights();
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
