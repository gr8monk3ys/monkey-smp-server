"use client";

import { useEffect, useState } from "react";
import { shortWhen } from "@/lib/config";

/** What tools/status.py writes (deploy/monkey-status.sh, every 2 minutes), as far as the page reads it. */
type Report = {
  checked: string;
  phase: "preseason" | "live" | "offseason";
  online: boolean;
  players: number | null;
  next: { what: string; at: string } | null;
  border: { size: number; growing_to: number | null; next: { size: number; at: string } | null } | null;
};
type Phase = Report["phase"];

/** Older than this, the file says nothing about now: the timer or the server has stopped writing it. */
const STALE_MS = 10 * 60_000;
const POLL_MS = 2 * 60_000;
const TIMEOUT_MS = 8000;

function time(value: unknown): number {
  return typeof value === "string" ? Date.parse(value) : NaN;
}

/** The file, if it is one tools/status.py wrote; anything else counts as no file. */
function read(data: unknown): Report | null {
  if (!data || typeof data !== "object") return null;
  const r = data as Report;
  if (isNaN(time(r.checked)) || !["preseason", "live", "offseason"].includes(r.phase)) return null;
  if (typeof r.online !== "boolean" || (r.players !== null && typeof r.players !== "number")) return null;
  if (r.next && (typeof r.next.what !== "string" || isNaN(time(r.next.at)))) r.next = null;
  if (r.border && typeof r.border.size !== "number") r.border = null;
  return r;
}

function ago(ms: number): string {
  const minutes = Math.floor(Math.max(0, ms) / 60_000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.floor(minutes / 60);
  return hours < 48 ? `${hours} h ago` : `${Math.floor(hours / 24)} days ago`;
}

function phaseAt(now: number, launch: number): Phase {
  // Without the file the page can only tell the launch apart; the off-season comes from the file.
  return now < launch ? "preseason" : "live";
}

type Cell = { main: string; sub: string; href?: string };
type Shown = { state: "online" | "offline" | "quiet"; server: Cell; next: Cell; border: Cell };

/** The three cells for a moment: from a fresh report, a stale one, or none (the quiet fallback). */
function show(report: Report | null, now: number, launch: number, mapUrl: string): Shown {
  const age = report ? now - time(report.checked) : Infinity;
  const fresh = age <= STALE_MS;
  const phase = report && fresh ? report.phase : phaseAt(now, launch);
  const opens = shortWhen(new Date(launch));
  const map: Cell = { main: "On the live map", sub: "Open it to see the edge", href: mapUrl };

  let server: Cell;
  let state: Shown["state"] = "quiet";
  if (phase === "preseason") {
    server = { main: "Pre-season", sub: "Opens with Season I" };
  } else if (!report) {
    server = { main: "Status not available", sub: "Ask in the Discord" };
  } else if (!fresh) {
    server = { main: "Not checked lately", sub: `Last checked ${ago(age)}` };
  } else if (phase === "offseason") {
    server = { main: "Off-season", sub: `Checked ${ago(age)}` };
  } else if (report.online) {
    state = "online";
    const n = report.players;
    server = { main: n === null ? "Online" : `Online, ${n} playing`, sub: `Checked ${ago(age)}` };
  } else {
    state = "offline";
    server = { main: "Offline", sub: `Checked ${ago(age)}` };
  }

  const upcoming = report?.next && time(report.next.at) > now ? report.next : null;
  const next: Cell = upcoming
    ? { main: upcoming.what, sub: shortWhen(new Date(upcoming.at)) }
    : phase === "preseason"
      ? { main: "Season I opens", sub: opens }
      : phase === "offseason" ? { main: "The next season", sub: "Dates in the Discord" }
        : { main: "The weekly event", sub: "Saturdays, 6 PM Pacific" };

  let border = map;
  const b = report?.border;
  if (b) {
    const grow = b.next && time(b.next.at) > now ? b.next : null;
    border = {
      main: b.growing_to ? `Growing to ${b.growing_to}` : `${b.size} blocks wide`,
      sub: b.growing_to ? `${b.size} wide now`
        : grow ? `Grows to ${grow.size} ${shortWhen(new Date(grow.at)).split(",")[0]}` : "See it on the live map",
      href: b.growing_to || grow ? undefined : mapUrl,
    };
  }
  return { state, server, next, border };
}

function Value({ cell }: { cell: Cell }) {
  return (
    <dd>
      <span className="main">{cell.main}</span>
      <span className="sub">{cell.href ? <a href={cell.href}>{cell.sub}</a> : cell.sub}</span>
    </dd>
  );
}

/** The server's status from the file beside the live map: online or not and how many are playing (a count,
 * never names), what is next, and the border. The page is built with the quiet fallback for the season's phase
 * at build time, which is also what shows without JavaScript and when the file is missing, stale or blocked:
 * every state takes the same room, so nothing below moves when it arrives. `line` is the guide's one-line
 * form. */
export function ServerStatus({ url, mapUrl, launchAt, builtPhase, line = false }: {
  url: string; mapUrl: string; launchAt: string; builtPhase: Phase; line?: boolean;
}) {
  const launch = new Date(launchAt).getTime();
  const [view, setView] = useState<{ report: Report | null; now: number } | null>(null);

  useEffect(() => {
    let report: Report | null = null;
    let stopped = false;
    async function check() {
      const abort = new AbortController();
      const timer = window.setTimeout(() => abort.abort(), TIMEOUT_MS);
      try {
        const answer = await fetch(url, { signal: abort.signal, credentials: "omit" });
        if (answer.ok) report = read(await answer.json()) ?? report;
      } catch {
        // Missing, blocked (CORS) or offline: keep the last report, which goes stale by itself.
      } finally {
        clearTimeout(timer);
      }
      if (!stopped) setView({ report, now: Date.now() });
    }
    // Again every 2 minutes while the page is in view, and as soon as it comes back into view.
    const visible = () => { if (document.visibilityState === "visible") void check(); };
    void check();
    const poll = window.setInterval(visible, POLL_MS);
    document.addEventListener("visibilitychange", visible);
    return () => { stopped = true; clearInterval(poll); document.removeEventListener("visibilitychange", visible); };
  }, [url]);

  // Before the page's script has run: the built fallback, at a moment in the built phase.
  const shown = view
    ? show(view.report, view.now, launch, mapUrl)
    : show(null, builtPhase === "preseason" ? launch - 1 : launch, launch, mapUrl);

  if (line) {
    return (
      <p className={`status-line ${shown.state}`}>
        <span className="dot" aria-hidden="true" />
        <span><b>{shown.server.main}</b>{" · "}Next: {shown.next.main}, {shown.next.sub}</span>
      </p>
    );
  }
  return (
    <section className={`status ${shown.state}`} aria-labelledby="status-label">
      <h2 id="status-label" className="visually-hidden">Server status</h2>
      <dl>
        <div>
          <dt><span className="dot" aria-hidden="true" />Server</dt>
          <Value cell={shown.server} />
        </div>
        <div>
          <dt>Next</dt>
          <Value cell={shown.next} />
        </div>
        <div>
          <dt>Border</dt>
          <Value cell={shown.border} />
        </div>
      </dl>
    </section>
  );
}
