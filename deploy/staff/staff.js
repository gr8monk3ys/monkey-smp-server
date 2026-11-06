// The staff page: reads staff.json (tools/staff_status.py) and draws it. It can only read. Everything from the file
// goes in with textContent or as a number on an SVG attribute, and nothing here may use a style attribute or load
// anything from elsewhere: Caddy's Content-Security-Policy refuses both (deploy/Caddyfile.staff).
"use strict";

const POLL_MS = 60_000;          // the file changes every 2 minutes
const CLOCK_MS = 10_000;         // how often "40 seconds ago" and the staleness are worked out again
const STALE_MS = 5 * 60_000;     // more than two readings missed: the numbers are old, whatever they say
const READING_S = 120;
const BUSY_SHARE = 0.8;          // past this share of a tick's time, the server is near its limit
const LOW_DISK = 0.1;
const CRITICAL_DISK = 0.05;
const ERRORS_SHOWN = 8;          // the file keeps up to 30, newest first
const SVG = "http://www.w3.org/2000/svg";
const MARKS = {
  good: "M1 1h10v10H1z",
  busy: "M5 1h2v2h1v2h1v2h1v2h1v2H1V9h1V7h1V5h1V3h1z",
  slow: "M5 0h2v2h2v2h2v4H9v2H7v2H5v-2H3V8H1V4h2V2h2z",
  off: "M1 1h10v10H1zM3 3v6h6V3z",
  unknown: "M1 1h10v10H1zM3 3v6h6V3zM5 5h2v2H5z",
};
const LINE_LABELS = { avg: "Avg", p95: "P95" };

const state = { data: null, hours: 6, hover: null, keyed: false, trouble: null, missing: false };
const charts = {};
const $ = (id) => document.getElementById(id);

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function draw(tag, attrs, parent) {
  const node = document.createElementNS(SVG, tag);
  for (const [name, value] of Object.entries(attrs)) node.setAttribute(name, value);
  if (parent) parent.appendChild(node);
  return node;
}

function mark(kind, label) {
  const svg = draw("svg", { class: `mark ${kind}`, viewBox: "0 0 12 12" });
  if (label) {
    svg.setAttribute("role", "img");
    svg.setAttribute("aria-label", label);
  } else {
    svg.setAttribute("aria-hidden", "true");
  }
  draw("path", { d: MARKS[kind] }, svg);
  return svg;
}

const one = (n) => n.toFixed(1);
const plural = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;

function ago(ms) {
  const s = Math.max(0, Math.round(ms / 1000));
  if (s < 60) return s < 10 ? "just now" : `${plural(s, "second")} ago`;
  const m = Math.round(s / 60);
  if (m < 60) return `${plural(m, "minute")} ago`;
  const h = Math.round(m / 60);
  if (h < 48) return `${plural(h, "hour")} ago`;
  return `${plural(Math.round(h / 24), "day")} ago`;
}

const CLOCK = new Intl.DateTimeFormat(undefined, { hour: "numeric", minute: "2-digit" });
const DAY_CLOCK = new Intl.DateTimeFormat(undefined, { weekday: "short", hour: "numeric", minute: "2-digit" });
const HOUR = new Intl.DateTimeFormat(undefined, { hour: "numeric" });

// ---------------------------------------------------------------- the answer

function verdict(d, now) {
  const age = now - Date.parse(d.checked);
  if (age > STALE_MS) {
    return { kind: "unknown", word: "Not updating",
      text: `The last reading is from ${ago(age)}, so the numbers below are old. The job that takes them, or the whole machine, may be down.` };
  }
  if (!d.online) {
    if (!d.container) {
      return { kind: "unknown", word: "Can't tell",
        text: "Docker didn't answer, so there is no telling whether the server is running." };
    }
    if (d.container.state === "running") {
      return { kind: "busy", word: "Not answering",
        text: "The server is up but isn't answering. It takes a few minutes to start after a restart. If this lasts longer than that, it may be stuck." };
    }
    return { kind: "off", word: "Offline",
      text: "The server isn't running. It stops for its daily restart and for a deploy, and comes back on its own." };
  }
  const t = d.tick;
  if (!t) {
    return { kind: "unknown", word: "Online",
      text: "The server answered, but without its tick numbers, so there is no reading of how it is running." };
  }
  const limit = 1000 / t.target;
  const share = `${one(t.avg)} ms of the ${Math.round(limit)} ms it has`;
  if (t.avg > limit) {
    return { kind: "slow", word: "Slow",
      text: `Falling behind. Each tick takes ${share}, so the game runs at ${one(t.tps)} ticks a second instead of ${Math.round(t.target)}. Players feel this as lag.` };
  }
  if (t.avg >= limit * BUSY_SHARE) {
    return { kind: "busy", word: "Busy",
      text: `Near the limit. Each tick takes ${share}. Players won't notice yet, but there is little room left.` };
  }
  if (t.p95 > limit) {
    return { kind: "busy", word: "Busy",
      text: `Keeping up on average, at ${share}, but 1 tick in 20 takes over ${Math.round(limit)} ms, and players can feel those.` };
  }
  return { kind: "good", word: "Healthy", text: `Keeping up. Each tick takes ${share}.` };
}

function diskShare(d) {
  const disk = d.host && d.host.disk;
  return disk && disk.total ? disk.free / disk.total : null;
}

function renderVerdict(now) {
  const d = state.data;
  let v;
  if (d) {
    v = verdict(d, now);
  } else if (state.missing) {
    v = { kind: "unknown", word: "No reading yet",
      text: "The job writes the first one within 2 minutes of being set up. If this stays, run monkey-staff.sh --check on the server." };
  } else if (state.trouble) {
    v = { kind: "unknown", word: "Can't reach it", text: state.trouble };
  } else {
    return;
  }
  $("mark").setAttribute("class", `mark ${v.kind}`);
  $("mark").firstElementChild.setAttribute("d", MARKS[v.kind]);
  $("word").textContent = v.word;
  $("sentence").textContent = v.text;
  document.title = `${v.word}: Monkey SMP staff`;

  const fresh = d && now - Date.parse(d.checked) <= STALE_MS;
  const nobody = fresh && d.online && d.players && d.players.count === 0;
  $("note").hidden = !nobody;
  $("note").textContent = nobody ? "Nobody is on, so the server has little to do. These numbers will look different with a crowd." : "";

  const alerts = [];
  const crashed = d && d.problems && d.problems.crashes && d.problems.crashes[0];
  if (fresh && crashed) alerts.push(`The server crashed ${ago(now - Date.parse(crashed.when))}.`);
  if (fresh && d.backups && d.backups.offsite === "failing") alerts.push("Off-site backups are failing.");
  const free = d ? diskShare(d) : null;
  if (fresh && free !== null && free < LOW_DISK) alerts.push(`The disk is nearly full: ${Math.round(free * 100)}% free.`);
  $("attention").hidden = alerts.length === 0;
  $("attention").textContent = alerts.join(" ");

  $("trouble").hidden = !(d && state.trouble);
  $("trouble").textContent = d && state.trouble ? state.trouble : "";
}

function renderChecked(now) {
  const d = state.data;
  if (!d) {
    if (state.missing || state.trouble) $("checked").textContent = "";
    return;
  }
  const when = new Date(d.checked);
  $("checked").textContent = `Checked ${ago(now - when.getTime())}, at ${CLOCK.format(when)}`;
}

// ---------------------------------------------------------------- right now

function row(list, label, parts, small, meter) {
  const wrap = el("div", "row");
  wrap.appendChild(el("dt", "", label));
  const dd = el("dd");
  const value = el("div", "value");
  for (const part of parts) value.appendChild(part);
  dd.appendChild(value);
  if (meter) dd.appendChild(meter);
  if (small) dd.appendChild(el("small", "", small));
  wrap.appendChild(dd);
  list.appendChild(wrap);
}

const num = (text) => el("span", "num", text);
const unit = (text) => el("span", "", text);
const word = (text) => el("span", "word", text);

function meter(share, kind) {
  const svg = draw("svg", { class: "meter", viewBox: "0 0 100 6", preserveAspectRatio: "none", "aria-hidden": "true" });
  draw("rect", { class: "track", width: 100, height: 6 }, svg);
  draw("rect", { class: `fill ${kind || ""}`, width: Math.min(100, Math.max(0, share * 100)), height: 6 }, svg);
  return svg;
}

const gb = (kib) => kib / 1048576;
const diskGb = (bytes) => bytes / 1073741824;

function renderNow() {
  const d = state.data;
  const game = $("game");
  const machine = $("machine");
  const upkeep = $("upkeep");
  game.replaceChildren();
  machine.replaceChildren();
  upkeep.replaceChildren();
  const names = $("names");
  names.replaceChildren();

  if (d.tick) {
    row(game, "Ticks a second", [num(one(d.tick.tps)), unit(`of ${Math.round(d.tick.target)}`)]);
    row(game, "Time per tick", [num(one(d.tick.avg)), unit(`ms of ${Math.round(1000 / d.tick.target)}`)],
      `P95 ${one(d.tick.p95)} ms, P99 ${one(d.tick.p99)} ms`);
  } else {
    row(game, "Ticks a second", [word("No reading")]);
  }
  if (d.players) {
    row(game, "Players", [num(String(d.players.count)), unit(`of ${d.players.max}`)]);
    if (d.players.names.length) {
      for (const name of d.players.names) names.appendChild(el("li", "", name));
    } else {
      names.appendChild(el("li", "nobody", "Nobody on right now"));
    }
  } else {
    row(game, "Players", [word("No reading")]);
  }

  const host = d.host || {};
  if (host.memory) {
    const used = host.memory.total - host.memory.available;
    row(machine, "Memory in use", [num(one(gb(used))), unit(`of ${Math.round(gb(host.memory.total))} GB`)], "",
      meter(used / host.memory.total));
  }
  if (host.swap && host.swap.total) {
    const used = host.swap.total - host.swap.free;
    row(machine, "Swap in use", [num(one(gb(used))), unit(`of ${one(gb(host.swap.total))} GB`)]);
  }
  if (host.load) {
    const threads = host.threads || 0;
    row(machine, "CPU load", [num(host.load[0].toFixed(2)), unit(threads ? `of ${threads} threads` : "")],
      `${host.load[1].toFixed(2)} over 5 minutes, ${host.load[2].toFixed(2)} over 15`,
      threads ? meter(host.load[0] / threads) : null);
  }
  if (host.disk) {
    const free = host.disk.free / host.disk.total;
    const kind = free < CRITICAL_DISK ? "slow" : free < LOW_DISK ? "busy" : "";
    row(machine, "Disk free", [num(String(Math.round(diskGb(host.disk.free)))), unit(`of ${Math.round(diskGb(host.disk.total))} GB`)], "",
      meter(1 - free, kind));
  }
  if (!machine.children.length) row(machine, "Numbers", [word("No reading")]);

  row(upkeep, "Release", [word(d.release || "Unknown")]);
  const box = d.container;
  if (box) {
    const running = box.state === "running" && box.uptime;
    row(upkeep, running ? "Running for" : "Container", [word(running ? box.uptime : box.state)]);
  }
  const backups = d.backups || {};
  if (backups.local) {
    const when = new Date(backups.local);
    // The copy a deploy takes before it updates; the hourly backups are the off-site row below.
    row(upkeep, "Copy before the last update", [word(ago(Date.now() - when.getTime()))], DAY_CLOCK.format(when));
  } else {
    row(upkeep, "Copy before the last update", [word("None found")]);
  }
  const offsite = { on: ["good", "On"], failing: ["slow", "Failing"], "not set up": ["busy", "Not set up"] }[backups.offsite] || ["unknown", "Unknown"];
  row(upkeep, "Off-site backups", [mark(offsite[0]), word(offsite[1])]);
}

// ---------------------------------------------------------------- what went wrong

function problem(kind, label, when, text) {
  const item = el("li", "problem");
  const head = el("p", "problem-head");
  head.append(mark(kind), el("span", "word", label), el("span", "problem-when", when));
  item.appendChild(head);
  if (text) item.appendChild(el("p", "problem-text", text));
  return item;
}

function howOften(group, now) {
  if (group.older) {
    const before = "before this page started watching";
    return group.count === 1 ? `Sometime ${before}` : `${plural(group.count, "time")} ${before}`;
  }
  const last = ago(now - Date.parse(group.last));
  if (group.count === 1) return last;
  return `${plural(group.count, "time")} since ${DAY_CLOCK.format(new Date(group.first))}, last ${last}`;
}

function renderProblems(now) {
  const p = state.data.problems;
  const rows = [];
  if (!p) {
    rows.push(problem("unknown", "No reading yet", "", "The log hasn't been read yet."));
    $("problems").replaceChildren(...rows);
    $("problems-fine").textContent = "";
    return;
  }
  if (!p.read || p.crashes === null) {
    rows.push(problem("unknown", "Can't read everything", "",
      `The ${p.read ? "crash reports" : "server's log"} couldn't be read just now, so this list may be missing something.`));
  }
  for (const crash of p.crashes || []) {
    rows.push(problem("slow", "Crashed", ago(now - Date.parse(crash.when)), crash.text));
  }
  if (p.lag) {
    rows.push(problem("busy", "Fell behind", howOften(p.lag, now),
      `The worst was ${one(p.lag.worst / 1000)} seconds behind. Players feel this as a freeze.`));
  }
  const errors = p.errors || [];
  for (const group of errors.slice(0, ERRORS_SHOWN)) {
    rows.push(problem("busy", "Error", howOften(group, now), group.text));
  }
  if (errors.length > ERRORS_SHOWN) rows.push(el("li", "problem-more", `and ${errors.length - ERRORS_SHOWN} more`));
  if (!rows.length) rows.push(problem("good", "Nothing in the last 24 hours", ""));
  $("problems").replaceChildren(...rows);

  const startup = p.log && p.log.startup;
  $("problems-fine").textContent = "Errors since the server finished starting, stalls of 2 seconds or more, and crashes. "
    + `Warnings aren't listed${startup ? `, nor the ${plural(startup, "error")} from its last start: this pack logs about that many each time` : ""}. `
    + "The full story is in the server's log.";
}

// ---------------------------------------------------------------- over time

function visibleRows() {
  const rows = (state.data && state.data.history) || [];
  const end = (state.data ? Date.parse(state.data.checked) : Date.now()) / 1000;
  const start = end - state.hours * 3600;
  return { rows: rows.filter((r) => r[0] >= start && r[0] <= end), start, end };
}

// The stretches of a series with readings; a missing reading or a long wait breaks the line rather than joining across it.
function segments(rows, index) {
  const out = [];
  let run = [];
  let last = null;
  for (const r of rows) {
    if (r[index] === null || r[index] === undefined || (last !== null && r[0] - last > READING_S * 3)) {
      if (run.length) out.push(run);
      run = [];
    }
    if (r[index] !== null && r[index] !== undefined) {
      run.push(r);
      last = r[0];
    }
  }
  if (run.length) out.push(run);
  return out;
}

// The stretches with no reading, between the readings on each side.
function gaps(rows) {
  const out = [];
  let from = null;
  let previous = null;
  for (const r of rows) {
    const empty = r[3] === null && r[1] === null;
    if (empty && from === null) from = previous === null ? r[0] : previous;
    if (!empty) {
      if (from !== null) {
        out.push([from, r[0]]);
        from = null;
      } else if (previous !== null && r[0] - previous > READING_S * 3) {
        out.push([previous, r[0]]);
      }
    }
    previous = r[0];
  }
  if (from !== null && previous !== null) out.push([from, previous]);
  return out;
}

function timeTicks(start, end, hours, narrow) {
  const every = { 1: 15, 6: narrow ? 120 : 60, 24: narrow ? 480 : 240 }[hours];
  const ticks = [];
  const t = new Date(start * 1000);
  t.setMinutes(Math.floor(t.getMinutes() / 15) * 15, 0, 0);
  for (; t.getTime() / 1000 <= end; t.setMinutes(t.getMinutes() + 15)) {
    const minutes = t.getHours() * 60 + t.getMinutes();
    if (t.getTime() / 1000 >= start && minutes % every === 0) ticks.push(t.getTime() / 1000);
  }
  return { ticks, every };
}

const SPECS = {
  tick: {
    // Capped, or one huge spike would flatten the rest of the day against the floor: the line pins at the top, and
    // the readout and the table still say the real number.
    height: 190, unit: " ms", yTop: (rows) => Math.min(250, Math.max(60, Math.ceil(Math.max(0, ...rows.map((r) => r[2] || 0)) * 1.1 / 10) * 10)),
    yTicks: (top) => (top <= 60 ? [0, 25, 50] : top <= 120 ? [0, 50, 100] : [0, 50, 100, 200].filter((n) => n < top)),
    series: [{ index: 2, name: "P95", key: "p95", line: "line-2" }, { index: 1, name: "Average", key: "avg", line: "line-1" }],
    format: one, step: false, limit: 50,
    what: "Time per tick",
  },
  players: {
    height: 120, unit: "", yTop: (rows) => Math.max((state.data.players && state.data.players.max) || 30, ...rows.map((r) => r[3] || 0)),
    yTicks: (top) => [0, Math.round(top / 3), Math.round(top * 2 / 3), top],
    series: [{ index: 3, name: "Players", line: "line-solo" }],
    format: String, step: true,
    what: "Players online",
  },
};

function drawChart(name) {
  const spec = SPECS[name];
  const plot = $(`${name}-plot`);
  const width = plot.clientWidth;
  if (!width) return;
  const { rows, start, end } = visibleRows();
  // The same sides on both charts, so their times line up under the crosshair.
  const pad = { left: 30, right: 34, top: 8, bottom: 22 };
  const height = spec.height;
  const top = spec.yTop(rows);
  const x = (t) => pad.left + (t - start) / (end - start) * (width - pad.left - pad.right);
  const y = (v) => height - pad.bottom - Math.min(v, top) / top * (height - pad.top - pad.bottom);

  const svg = draw("svg", { viewBox: `0 0 ${width} ${height}`, height, role: "img", tabindex: 0 });
  for (const value of spec.yTicks(top)) {
    if (value === spec.limit) continue;
    draw("line", { class: "grid", x1: pad.left, x2: width - pad.right, y1: y(value), y2: y(value) }, svg);
    draw("text", { class: "axis", x: pad.left - 6, y: y(value) + 4, "text-anchor": "end" }, svg).textContent = String(value);
  }
  const { ticks, every } = timeTicks(start, end, state.hours, width < 480);
  for (const t of ticks) {
    const label = every < 60 ? CLOCK.format(new Date(t * 1000)) : HOUR.format(new Date(t * 1000));
    draw("text", { class: "axis", x: x(t), y: height - 6, "text-anchor": "middle" }, svg).textContent = label;
  }
  for (const [from, to] of gaps(rows)) {
    draw("rect", { class: "gap", x: x(from), y: pad.top, width: Math.max(2, x(to) - x(from)), height: height - pad.top - pad.bottom }, svg);
  }
  if (spec.limit) {
    draw("line", { class: "limit", x1: pad.left, x2: width - pad.right, y1: y(spec.limit), y2: y(spec.limit) }, svg);
    draw("text", { class: "axis", x: pad.left - 6, y: y(spec.limit) + 4, "text-anchor": "end" }, svg).textContent = String(spec.limit);
    draw("text", { class: "limit-label", x: pad.left + 4, y: y(spec.limit) - 4 }, svg).textContent = "The limit";
  }

  const ends = [];
  for (const s of spec.series) {
    for (const run of segments(rows, s.index)) {
      if (run.length === 1) {
        draw("rect", { class: `dot ${s.line}`, x: x(run[0][0]) - 3, y: y(run[0][s.index]) - 3, width: 6, height: 6 }, svg);
        continue;
      }
      let path = `M${x(run[0][0]).toFixed(1)} ${y(run[0][s.index]).toFixed(1)}`;
      for (const r of run.slice(1)) {
        path += spec.step
          ? `H${x(r[0]).toFixed(1)}V${y(r[s.index]).toFixed(1)}`
          : `L${x(r[0]).toFixed(1)} ${y(r[s.index]).toFixed(1)}`;
      }
      draw("path", { class: `series ${s.line}`, d: path }, svg);
    }
    const lastRow = rows.length ? rows[rows.length - 1] : null;
    if (lastRow && lastRow[s.index] !== null && s.key) ends.push({ key: s.key, y: y(lastRow[s.index]), x: x(lastRow[0]) });
  }
  // Direct labels at the lines' ends, pushed apart where the lines run close.
  ends.sort((a, b) => a.y - b.y);
  for (let i = 1; i < ends.length; i++) ends[i].y = Math.max(ends[i].y, ends[i - 1].y + 14);
  for (const e of ends) {
    draw("text", { class: "axis", x: e.x + 5, y: Math.min(e.y + 4, height - pad.bottom) }, svg).textContent = LINE_LABELS[e.key];
  }

  if (rows.length < 2) {
    draw("text", { class: "empty", x: width / 2, y: height / 2, "text-anchor": "middle" }, svg).textContent =
      width < 400 ? "A reading comes every 2 minutes." : "This fills in as readings come in, one every 2 minutes.";
  }

  const cross = draw("line", { class: "cross", y1: pad.top, y2: height - pad.bottom, visibility: "hidden" }, svg);
  const dots = spec.series.map((s) => draw("rect", { class: `cross-dot ${s.line}`, width: 8, height: 8, visibility: "hidden" }, svg));
  plot.replaceChildren(svg);
  charts[name] = { spec, rows, x, y, cross, dots };

  const latest = rows.length ? rows[rows.length - 1] : null;
  const words = spec.series.map((s) => `${s.name} ${latest && latest[s.index] !== null ? spec.format(latest[s.index]) + spec.unit : "no reading"}`);
  svg.setAttribute("aria-label", `${spec.what}, the last ${plural(state.hours, "hour")}. Latest: ${words.join(", ")}. The table below has every reading. Arrow keys step through them.`);

  svg.addEventListener("pointermove", (e) => {
    const box = svg.getBoundingClientRect();
    const t = start + ((e.clientX - box.left) / box.width * width - pad.left) / (width - pad.left - pad.right) * (end - start);
    state.keyed = false;
    point(nearest(rows, t));
  });
  svg.addEventListener("pointerleave", () => point(null));
  svg.addEventListener("blur", () => point(null));
  svg.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      point(null);
      return;
    }
    const by = { ArrowLeft: -1, ArrowRight: 1 }[e.key];
    if (!by || !rows.length) return;
    e.preventDefault();
    const at = state.hover === null ? rows.length - 1 : rows.findIndex((r) => r[0] >= state.hover);
    state.keyed = true;
    point(rows[Math.min(rows.length - 1, Math.max(0, at + by))][0]);
  });
}

function nearest(rows, t) {
  let best = null;
  for (const r of rows) if (best === null || Math.abs(r[0] - t) < Math.abs(best - t)) best = r[0];
  return best;
}

// Moves the crosshair on both charts to the reading at time t (null: none, and the readouts show the latest).
function point(t) {
  state.hover = t;
  for (const name of Object.keys(SPECS)) {
    const chart = charts[name];
    if (!chart) continue;
    const r = t === null ? null : chart.rows.find((row) => row[0] === t);
    chart.cross.setAttribute("visibility", r ? "visible" : "hidden");
    if (r) {
      chart.cross.setAttribute("x1", chart.x(t));
      chart.cross.setAttribute("x2", chart.x(t));
    }
    chart.spec.series.forEach((s, i) => {
      const value = r ? r[s.index] : null;
      chart.dots[i].setAttribute("visibility", value === null ? "hidden" : "visible");
      if (value !== null) {
        chart.dots[i].setAttribute("x", chart.x(t) - 4);
        chart.dots[i].setAttribute("y", chart.y(value) - 4);
      }
    });
    readout(name, r);
  }
}

function readout(name, picked) {
  const chart = charts[name];
  const box = $(`${name}-readout`);
  const r = picked || (chart.rows.length ? chart.rows[chart.rows.length - 1] : null);
  const parts = [];
  parts.push(el("span", "", r ? DAY_CLOCK.format(new Date(r[0] * 1000)) : "No readings yet"));
  // Top line of the chart first in the key: the series are drawn back to front.
  for (const s of [...chart.spec.series].reverse()) {
    const key = el("span", "key");
    if (chart.spec.series.length > 1) {
      key.appendChild(el("i", `swatch ${s.line}`));
      key.appendChild(el("span", "", s.name));
    }
    const value = r && r[s.index] !== null ? chart.spec.format(r[s.index]) + chart.spec.unit : "no reading";
    key.appendChild(el("b", "", value));
    parts.push(key);
  }
  box.replaceChildren(...parts);
  // Said aloud only when someone is stepping through with the keys: a moving mouse would never stop talking.
  if (state.keyed && picked) box.setAttribute("aria-live", "polite");
  else box.removeAttribute("aria-live");
}

function renderTable() {
  if (!$("table").open) return;
  const body = $("rows");
  const fill = (v, text) => (v === null ? "no reading" : text);
  const { rows } = visibleRows();
  body.replaceChildren(...[...rows].reverse().map((r) => {
    const tr = el("tr");
    tr.appendChild(el("td", "", DAY_CLOCK.format(new Date(r[0] * 1000))));
    tr.appendChild(el("td", "", fill(r[1], r[1] === null ? "" : `${one(r[1])} ms`)));
    tr.appendChild(el("td", "", fill(r[2], r[2] === null ? "" : `${one(r[2])} ms`)));
    tr.appendChild(el("td", "", fill(r[3], String(r[3]))));
    return tr;
  }));
}

function renderCharts() {
  if (!state.data) return;
  for (const name of Object.keys(SPECS)) {
    drawChart(name);
    if (charts[name]) readout(name, null);
  }
  state.hover = null;
  renderTable();
}

// ---------------------------------------------------------------- reading the file

function render() {
  const now = Date.now();
  renderVerdict(now);
  renderChecked(now);
  document.body.classList.add("ready");
  $("layout").hidden = !state.data;
  if (state.data) {
    renderNow();
    renderProblems(now);
    renderCharts();
  }
}

async function load() {
  try {
    const answer = await fetch("staff.json", { cache: "no-store" });
    if (answer.status === 401) {
      state.trouble = "Your login has run out. Reload this page to log in again.";
    } else if (answer.status === 404) {
      state.missing = true;
      state.trouble = null;
    } else if (!answer.ok) {
      state.trouble = `The page's data didn't load (error ${answer.status}). It tries again every minute.`;
    } else {
      state.data = await answer.json();
      state.missing = false;
      state.trouble = null;
    }
  } catch {
    state.trouble = "The page can't reach the server's machine right now. It tries again every minute.";
  }
  render();
}

for (const button of document.querySelectorAll(".range button")) {
  button.addEventListener("click", () => {
    state.hours = Number(button.dataset.hours);
    for (const other of document.querySelectorAll(".range button")) {
      other.setAttribute("aria-pressed", String(other === button));
    }
    renderCharts();
  });
}
$("table").addEventListener("toggle", renderTable);

let lastWidth = 0;
new ResizeObserver(() => {
  const width = $("tick-plot").clientWidth;
  if (width !== lastWidth) {
    lastWidth = width;
    renderCharts();
  }
}).observe($("tick-plot"));

load();
setInterval(() => {
  if (!document.hidden) load();
}, POLL_MS);
setInterval(() => {
  const now = Date.now();
  renderVerdict(now);
  renderChecked(now);
}, CLOCK_MS);
document.addEventListener("visibilitychange", () => {
  if (!document.hidden) load();
});
