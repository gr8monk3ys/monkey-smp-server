"use client";

import { useEffect, useState } from "react";
import { LaunchTime } from "@/components/links";
import { ago } from "@/components/status";
import { shortWhen } from "@/lib/config";
import { afterAnswer, freshness, roman, type Row, type Standings } from "@/lib/standings";

/** The file is written every hour, and a page left open picks up the newest every few minutes. */
const POLL_MS = 5 * 60_000;
const TIMEOUT_MS = 8000;

/** Why there is no table: the season hasn't opened, the server hasn't published one (or what it published can't
 * be read), it stopped publishing a while ago, or the file is dated ahead of this device's clock. */
type Why = "soon" | "none" | "stale" | "clock";
const TITLES: Record<Why, string> = {
  soon: "No standings yet", none: "No standings yet", stale: "Not updating right now", clock: "Check this device's clock",
};

function Empty({ why }: { why: Why }) {
  return (
    <section className="standings-empty" aria-labelledby="standings-empty-title">
      <h2 id="standings-empty-title">{TITLES[why]}</h2>
      {why === "soon" && (
        <p>Season I opens <LaunchTime template="{date}, {pacific}" />. The standings are published here once the
          season is under way.</p>
      )}
      {why === "none" && (
        <p>The server hasn&apos;t published any yet. They will show here when it does.</p>
      )}
      {why === "stale" && (
        <p>The last standings are too old to trust, so none are shown. They come back when the server publishes
          again. If this lasts, check the clock on this device. In the game, <code>/trigger standings</code> shows
          the board.</p>
      )}
      {why === "clock" && (
        <p>The standings are dated ahead of this device&apos;s clock, so they can&apos;t be shown. Set the right time
          and reload. In the game, <code>/trigger standings</code> shows the board.</p>
      )}
    </section>
  );
}

function Table({ title, caption, rows }: { title: string; caption: string; rows: Row[] }) {
  return (
    <table className="standings-table">
      <caption className="visually-hidden">{title}</caption>
      <thead>
        <tr><th scope="col">Rank</th><th scope="col">Faction</th><th scope="col">Points</th></tr>
      </thead>
      <tbody>
        {rows.length === 0 && <tr><td colSpan={3} className="none">{caption}</td></tr>}
        {rows.map((row, i) => (
          <tr key={i}>
            <td className="rank">{row.rank}</td>
            {/* A player chose this name and nobody has read it: it is text in a text node, nothing else. <bdi>
                keeps a name that runs right to left from rearranging the cells around it. */}
            <td className="name"><bdi>{row.name}</bdi></td>
            <td className="points">{row.points}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function Tables({ file, now }: { file: Standings; now: number }) {
  const season = `Season ${roman(file.season)}`;
  const over = file.closes === null;   // the season's last week has closed: no week is running
  return (
    <>
      {!over && (
        <section className="standings-week" aria-labelledby="standings-this">
          <h2 id="standings-this">This week, so far</h2>
          <p className="small">
            {season}. Updated {ago(now - file.checked)}.
            {file.closes !== null && file.closes > now && <> The week closes {shortWhen(new Date(file.closes))}.</>}
          </p>
          <Table title="Factions this week, so far" caption="No faction has points yet." rows={file.factions} />
        </section>
      )}
      {file.last && (
        <section className="standings-week" aria-labelledby="standings-last">
          <h2 id="standings-last">{over ? "The last week of the season, final" : "Last week, final"}</h2>
          <p className="small">{over && <>{season} is over. </>}Closed {shortWhen(new Date(file.last.closed))}.</p>
          <Table title="Factions last week, final" caption="No faction had points." rows={file.last.factions} />
        </section>
      )}
    </>
  );
}

/** What is on show at `now`: the file if it can be trusted, otherwise the reason it can't be. */
function show(file: Standings | null, now: number, launch: number): { file: Standings } | { why: Why } {
  if (file) {
    const state = freshness(file, now);
    if (state === "stale") return { why: "stale" };
    if (state === "ahead") return { why: "clock" };
    if (file.closes !== null || file.last) return { file };
  }
  return { why: now < launch ? "soon" : "none" };
}

/** The weekly faction standings from the file beside the live map (STANDINGS_URL): a table of rank, name and
 * points for this week so far and for the last week to close. Names, ranks and points only.
 *
 * The page is built showing the empty state for the season's phase, which is also what shows without JavaScript
 * and whenever the file is missing, can't be read whole, is too old or is blocked: a table is shown complete and
 * recent, or not at all. A file the server answers with but that can't be read replaces what was shown; a request
 * that fails (offline, a 5xx, too slow) keeps the last table, and that goes stale by itself. */
export function FactionStandings({ url, launchAt, builtPhase }: {
  url: string; launchAt: string; builtPhase: "preseason" | "live";
}) {
  const launch = new Date(launchAt).getTime();
  const [view, setView] = useState<{ file: Standings | null; now: number } | null>(null);

  useEffect(() => {
    if (!url) return;
    let file: Standings | null = null;
    let stopped = false;
    let latest = 0;
    async function check() {
      const mine = ++latest;   // a poll and a tab coming back can overlap: only the newest counts
      let next = file;
      const abort = new AbortController();
      const timer = window.setTimeout(() => abort.abort(), TIMEOUT_MS);
      try {
        const answer = await fetch(url, { signal: abort.signal, credentials: "omit" });
        next = afterAnswer(file, answer.status, answer.ok ? await answer.text() : null);
      } catch {
        // Blocked (CORS), offline or too slow: keep what was shown, which goes stale by itself.
      } finally {
        clearTimeout(timer);
      }
      if (stopped || mine !== latest) return;
      file = next;
      setView({ file, now: Date.now() });
    }
    const visible = () => { if (document.visibilityState === "visible") void check(); };
    void check();
    const poll = window.setInterval(visible, POLL_MS);
    document.addEventListener("visibilitychange", visible);
    return () => { stopped = true; clearInterval(poll); document.removeEventListener("visibilitychange", visible); };
  }, [url]);

  // Before the page's script has run (and with it off): the built empty state, for the phase it was built in.
  if (!view) return <Empty why={builtPhase === "preseason" ? "soon" : "none"} />;
  const shown = show(view.file, view.now, launch);
  return "file" in shown ? <Tables file={shown.file} now={view.now} /> : <Empty why={shown.why} />;
}
