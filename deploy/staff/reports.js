// The staff page's Reports tab (tools/staff_report.py answers it): each week's rule check as a grid of players and
// rules, the rows behind a cell, the checks that came back clean, and the week as text to paste into Discord.
// The same rules as panel.js: everything from the server goes in with textContent, no style attributes, no forms, no
// confirm or alert dialogs. It only shows: nothing here punishes, messages or rolls anything back.
"use strict";

(() => {
  const $ = (id) => document.getElementById(id);
  const LEVELS = { clear: "clear in the logs", likely: "likely", unclear: "unclear: worth a look" };
  const DISCORD_MAX = 1990;     // Discord's limit is 2,000 characters a message
  const state = { weeks: null, report: null, picked: null, loaded: false };

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

  async function api(url) {
    let answer;
    try {
      answer = await fetch(url, { headers: { "X-Monkey-Staff": "1" }, cache: "no-store" });
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

  function say(node, text) {
    node.hidden = !text;
    node.textContent = text ? (text.message || String(text)) : "";
  }

  // "2026-11-02 00:00" as "Mon 2 Nov".
  function day(text) {
    const m = /^(\d{4})-(\d\d)-(\d\d)/.exec(text || "");
    if (!m) return text || "";
    const d = new Date(Date.UTC(+m[1], +m[2] - 1, +m[3]));
    return d.toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short", timeZone: "UTC" });
  }

  function span(report) {
    return `${day(report.from)} to ${day(report.to)}, Pacific`;
  }

  // ---------------------------------------------------------------- the week picker

  async function load() {
    state.loaded = true;
    say($("reports-error"), "");
    try {
      const data = await api("/api/reports");
      state.weeks = data.weeks || [];
    } catch (e) {
      state.loaded = false;
      say($("reports-error"), e);
      return;
    }
    const pick = $("reports-week");
    pick.replaceChildren();
    for (const w of state.weeks) {
      const flagged = w.clear + w.likely;
      const option = el("option", "", `${w.week}: ${day(w.from)}, ${w.players} players, ${flagged} clear or likely`);
      option.value = w.week;
      pick.append(option);
    }
    pick.disabled = !state.weeks.length;
    $("reports-copy").disabled = !state.weeks.length;
    $("reports-empty").hidden = state.weeks.length > 0;
    if (!state.weeks.length) {
      $("reports-body").hidden = true;
      return;
    }
    const keep = state.weeks.some((w) => w.week === state.picked) ? state.picked : state.weeks[0].week;
    pick.value = keep;
    open(keep);
  }

  async function open(week) {
    state.picked = week;
    say($("reports-error"), "");
    $("reports-discord").hidden = true;
    let report;
    try {
      report = (await api(`/api/report?week=${encodeURIComponent(week)}`)).report;
    } catch (e) {
      if (state.picked === week) say($("reports-error"), e);
      return;
    }
    if (state.picked !== week) return;    // another week was picked while this one loaded
    state.report = report;
    draw(report);
  }

  // A cell's other levels, as ", also 3 unclear".
  function also(cell) {
    const rest = Object.entries(cell.also || {}).map(([level, n]) => `${n} ${level}`);
    return rest.length ? `, also ${rest.join(", ")}` : "";
  }

  // ---------------------------------------------------------------- the report

  function draw(report) {
    $("reports-body").hidden = false;
    const made = report.made ? new Date(report.made) : null;
    $("reports-span").textContent = `${report.week}: ${span(report)}` +
      (made && !Number.isNaN(made.getTime()) ? `. Written ${made.toLocaleString()}.` : ".") +
      (report.partial ? ` Not a whole week: ${report.partial}.` : "");
    drawGrid(report);
    drawList($("reports-notes"), report.notes || [], (note) => el("li", "", note));
    drawList($("reports-clean"), report.clean || [], (c) => {
      const li = el("li");
      li.append(el("b", "", c.title), el("span", "meta", ` ${c.rule}: ${c.result}`));
      return li;
    }, "Nothing came back clean this week.");
    $("reports-skipped-box").hidden = !(report.skipped || []).length;
    drawList($("reports-skipped"), report.skipped || [], (s) => el("li", "", `${s.title}: ${s.why}`));
    drawMining(report.mining || []);
    $("reports-evidence").hidden = true;
  }

  function drawList(node, items, make, empty) {
    node.replaceChildren(...items.map(make));
    if (!items.length && empty) node.append(el("li", "meta", empty));
  }

  function drawGrid(report) {
    const head = el("tr");
    head.append(el("th", "", "Player"));
    for (const c of report.checks) {
      const th = el("th");
      th.scope = "col";
      th.append(el("span", "rule-title", c.title), el("span", "rule-no", c.rule));
      head.append(th);
    }
    const rows = [];
    for (const p of report.players) {
      const tr = el("tr");
      const name = el("th", "", p.name);
      name.scope = "row";
      tr.append(name);
      for (const c of report.checks) {
        const td = el("td");
        const cell = p.cells[c.id];
        if (cell) {
          const b = button(String(cell.count), `cell ${cell.level}`, () => showCell(p, c, cell, b));
          b.setAttribute("aria-label", `${p.name}, ${c.title} (${c.rule}): ${cell.what} ${cell.count}, ${LEVELS[cell.level]}${also(cell)}`);
          b.title = `${cell.what}: ${cell.count}, ${LEVELS[cell.level]}${also(cell)}`;
          td.append(b);
        }
        tr.append(td);
      }
      rows.push(tr);
    }
    $("reports-head").replaceChildren(head);
    $("reports-rows").replaceChildren(...rows);
    $("reports-none").hidden = report.players.length > 0;
    $("reports-grid").hidden = report.players.length === 0;
  }

  function showCell(player, check, cell, from) {
    for (const b of $("reports-rows").querySelectorAll(".cell[aria-pressed]")) b.removeAttribute("aria-pressed");
    from.setAttribute("aria-pressed", "true");
    $("reports-evidence-title").textContent = `${player.name}: ${check.title} (${check.rule})`;
    $("reports-evidence-sum").textContent =
      `${cell.what}: ${cell.count}, ${LEVELS[cell.level]}${also(cell)}.` + (cell.more ? ` The first ${cell.evidence.length} rows; ${cell.more} more are in the file.` : "");
    const rows = cell.evidence.map((e) => {
      const tr = el("tr");
      tr.append(
        el("td", "", e.time || ""),
        el("td", "", e.world || ""),
        el("td", "mono", e.pos ? e.pos.join(" ") : ""),
        el("td", "what", e.what),
        el("td", "", e.level),
      );
      return tr;
    });
    $("reports-evidence-rows").replaceChildren(...rows);
    $("reports-evidence").hidden = false;
    $("reports-evidence").scrollIntoView({ block: "nearest", behavior: "smooth" });
  }

  function drawMining(rows) {
    $("reports-mining-box").hidden = !rows.length;
    $("reports-mining").replaceChildren(...rows.map((r) => {
      const tr = el("tr");
      tr.append(el("td", "", r.name), el("td", "", String(r.stone)), el("td", "", String(r.diamond)),
        el("td", "", String(r.debris)), el("td", "", r.per_k === null ? "" : String(r.per_k)));
      return tr;
    }));
  }

  // ---------------------------------------------------------------- Copy for Discord

  function pad(text, width) {
    const t = String(text);
    return t.length > width ? `${t.slice(0, width - 1)}~` : t.padEnd(width);
  }

  // The week as Discord messages: code blocks of fixed-width lines, each message under 2,000 characters.
  function discord(report) {
    const top = [`Monkey SMP rule check ${report.week} (${span(report)})`,
      "Only a report: look at the rows on the staff page before acting.",
      "clear = plain in the logs, likely = probably, unclear = worth a look"];
    if (report.partial) top.push(`Not a whole week: ${report.partial}`);
    const lines = [];
    for (const p of report.players) {
      for (const c of report.checks) {
        const cell = p.cells[c.id];
        if (cell) lines.push(`${pad(p.name, 17)}${pad(c.rule, 13)}${pad(`${cell.count} ${c.title}`, 30)}${cell.level}${also(cell)}`);
      }
    }
    if (!lines.length) lines.push("Nobody: every check came back clean.");
    const clean = (report.clean || []).map((c) => `${c.title} (${c.rule})`).join(", ");
    const tail = clean ? [`Checked and clean: ${clean}`] : [];
    const messages = [];
    let body = [];
    const wrap = (text, rows) => `${text}\n\`\`\`\n${rows.join("\n")}\n\`\`\``;
    let head = top.join("\n");
    for (const line of lines) {
      if (body.length && wrap(head, [...body, line]).length > DISCORD_MAX) {
        messages.push(wrap(head, body));
        head = `${report.week}, continued`;
        body = [];
      }
      body.push(line);
    }
    messages.push(wrap(head, body));
    for (const extra of tail) {
      const last = messages.length - 1;
      if (`${messages[last]}\n${extra}`.length <= DISCORD_MAX) messages[last] += `\n${extra}`;
      else messages.push(extra.slice(0, DISCORD_MAX));
    }
    return messages;
  }

  async function copy(text, note) {
    try {
      await navigator.clipboard.writeText(text);
      say(note, "Copied. Paste it into Discord.");
    } catch {
      say(note, "The browser didn't allow copying: select the text and copy it.");
    }
  }

  function showDiscord() {
    if (!state.report) return;
    const messages = discord(state.report);
    const list = $("reports-discord-list");
    list.replaceChildren();
    messages.forEach((text, i) => {
      const box = el("div", "discord-msg");
      const note = el("p", "note", "");
      note.hidden = true;
      note.setAttribute("role", "status");
      const head = el("div", "box-head");
      head.append(el("h4", "", `Message ${i + 1} of ${messages.length}, ${text.length} characters`),
        button("Copy", "", () => copy(text, note)));
      box.append(head, el("pre", "mono", text), note);
      list.append(box);
    });
    $("reports-discord").hidden = false;
    copy(messages[0], list.querySelector(".note"));
  }

  // ---------------------------------------------------------------- the tab

  function show() {
    if (location.hash.slice(1) === "reports" && !state.loaded) load();
  }

  function start() {
    $("reports-week").addEventListener("change", (e) => open(e.target.value));
    $("reports-reload").addEventListener("click", () => {
      state.loaded = false;
      load();
    });
    $("reports-copy").addEventListener("click", showDiscord);
    $("reports-evidence-close").addEventListener("click", () => {
      $("reports-evidence").hidden = true;
      for (const b of $("reports-rows").querySelectorAll(".cell[aria-pressed]")) b.removeAttribute("aria-pressed");
    });
    window.addEventListener("hashchange", show);
    show();
  }

  start();
})();
