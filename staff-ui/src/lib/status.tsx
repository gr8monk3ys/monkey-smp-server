// The latest reading of staff.json (tools/staff_status.py), shared by the header (its status word on every tab),
// the Status tab and the Server tab's power steps (how many players a stop would disconnect). Read every minute,
// and again when the browser tab comes back; the clock ("2 minutes ago", staleness) ticks every 10 seconds.
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { plural } from "./format";
import { usePoll } from "./hooks";

const POLL_MS = 60_000;          // the file changes every 2 minutes
const CLOCK_MS = 10_000;
export const STALE_MS = 5 * 60_000;   // more than two readings missed: the numbers are old, whatever they say
const BUSY_SHARE = 0.8;          // past this share of a tick's time, the server is near its limit
export const LOW_DISK = 0.1;

export type VerdictKind = "good" | "busy" | "slow" | "off" | "unknown";
export interface Verdict {
  kind: VerdictKind;
  word: string;
  text: string;
}

export interface StatusState {
  /** staff.json as it was read last, or null. */
  data: any | null;
  /** No file yet (404): the job hasn't written its first reading. */
  missing: boolean;
  /** Why the last read failed, or null. */
  trouble: string | null;
  /** Date.now(), ticking every 10 seconds. */
  now: number;
  /** Whether the first read has finished (either way). */
  loaded: boolean;
}

const one = (n: number) => n.toFixed(1);

/** "just now", "40 seconds ago", "5 minutes ago"... for milliseconds. */
export function agoMs(ms: number): string {
  const s = Math.max(0, Math.round(ms / 1000));
  if (s < 60) return s < 10 ? "just now" : `${plural(s, "second")} ago`;
  const m = Math.round(s / 60);
  if (m < 60) return `${plural(m, "minute")} ago`;
  const h = Math.round(m / 60);
  if (h < 48) return `${plural(h, "hour")} ago`;
  return `${plural(Math.round(h / 24), "day")} ago`;
}

/** One word for how the server is doing, and the sentence that explains it (the old staff.js verdict()). */
export function verdict(d: any, now: number): Verdict {
  const age = now - Date.parse(d.checked);
  if (age > STALE_MS) {
    return { kind: "unknown", word: "Not updating",
      text: `The last reading is from ${agoMs(age)}, so the numbers below are old. The job that takes them, or the whole machine, may be down.` };
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

/** The verdict for whatever state the reading is in, or null while the first read is on its way. */
export function currentVerdict(s: StatusState): Verdict | null {
  if (s.data) return verdict(s.data, s.now);
  if (s.missing) {
    return { kind: "unknown", word: "No reading yet",
      text: "The job writes the first one within 2 minutes of being set up. If this stays, run monkey-staff.sh --check on the server." };
  }
  if (s.trouble) return { kind: "unknown", word: "Can't reach it", text: s.trouble };
  return null;
}

export const isFresh = (s: StatusState) => !!s.data && s.now - Date.parse(s.data.checked) <= STALE_MS;

/** How many players a stop would disconnect: a number from a fresh reading (0 when it is stopped), else null. */
export function playersOn(s: StatusState): number | null {
  if (!isFresh(s)) return null;
  if (s.data.online && s.data.players) return Number(s.data.players.count) || 0;
  if (!s.data.online) return 0;
  return null;
}

const StatusContext = createContext<StatusState>({ data: null, missing: false, trouble: null, now: Date.now(), loaded: false });

export function StatusProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<StatusState>({ data: null, missing: false, trouble: null, now: Date.now(), loaded: false });

  const load = async () => {
    let next: Partial<StatusState>;
    try {
      const answer = await fetch("/staff.json", { cache: "no-store", headers: { "X-Monkey-Staff": "1" } });
      if (answer.status === 401) next = { trouble: "Your login has run out. Reload this page to log in again." };
      else if (answer.status === 404) next = { missing: true, trouble: null };
      else if (!answer.ok) next = { trouble: `The page's data didn't load (error ${answer.status}). It tries again every minute.` };
      else next = { data: await answer.json(), missing: false, trouble: null };
    } catch {
      next = { trouble: "The page can't reach the server's machine right now. It tries again every minute." };
    }
    setState((s) => ({ ...s, ...next, now: Date.now(), loaded: true }));
  };

  usePoll(load, POLL_MS, true);
  useEffect(() => {
    const timer = window.setInterval(() => setState((s) => ({ ...s, now: Date.now() })), CLOCK_MS);
    return () => window.clearInterval(timer);
  }, []);

  return <StatusContext.Provider value={state}>{children}</StatusContext.Provider>;
}

export const useStatus = () => useContext(StatusContext);
